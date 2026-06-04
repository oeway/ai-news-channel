#!/usr/bin/env python3
"""AI Pulse Newsletter Generator — fetches AI news and renders a static HTML newsletter."""

import os, re, sys, json, time, hashlib, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from html import escape as h
from typing import List, Dict, Any, Optional
import urllib.parse, urllib.request, urllib.error

try:
    import feedparser
except ImportError:
    print("Error: feedparser not installed. Run: pip install feedparser", file=sys.stderr)
    sys.exit(1)

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR   = SCRIPT_DIR.parent
DOCS_DIR   = ROOT_DIR / "docs"
OUTPUT     = DOCS_DIR / "index.html"
STATE_FILE = DOCS_DIR / "state.json"

# ── Sources ───────────────────────────────────────────────────────────────────
RSS_FEEDS = [
    {"url": "https://techcrunch.com/category/artificial-intelligence/feed/",
     "source": "TechCrunch",      "color": "#22c55e"},
    {"url": "https://venturebeat.com/category/ai/feed/",
     "source": "VentureBeat",     "color": "#f97316"},
    {"url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
     "source": "The Verge",       "color": "#e11d48"},
    {"url": "https://www.wired.com/feed/category/artificial-intelligence/latest/rss",
     "source": "Wired",           "color": "#818cf8"},
    {"url": "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss",
     "source": "IEEE Spectrum",   "color": "#0ea5e9"},
    {"url": "https://www.technologyreview.com/feed/",
     "source": "MIT Tech Review", "color": "#a78bfa"},
    {"url": "https://ai.googleblog.com/feeds/posts/default?alt=rss",
     "source": "Google AI Blog",  "color": "#4285f4"},
    {"url": "https://openai.com/blog/rss.xml",
     "source": "OpenAI",          "color": "#10a37f"},
    {"url": "https://huggingface.co/blog/feed.xml",
     "source": "HuggingFace",     "color": "#ffbd59"},
    {"url": "https://www.deeplearning.ai/the-batch/feed/",
     "source": "DeepLearning.AI", "color": "#ff6b35"},
    {"url": "https://blogs.microsoft.com/ai/feed/",
     "source": "Microsoft AI",    "color": "#0078d4"},
]

HN_API   = "https://hn.algolia.com/api/v1/search_by_date"
HN_TAGS  = ["artificial intelligence", "AI agent", "large language model", "machine learning", "LLM", "GPT", "Claude AI"]

ARXIV_API   = "https://export.arxiv.org/api/query"
ARXIV_QUERY = "cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.NE"

# ── Categories ────────────────────────────────────────────────────────────────
CATEGORIES: Dict[str, Dict] = {
    "research": {
        "label": "Research & Breakthroughs",
        "icon":  "🔬",
        "color": "#22d3ee",
        "bg":    "rgba(34,211,238,0.07)",
        "keywords": [
            "paper", "arxiv", "research", "study", "benchmark", "dataset", "training",
            "pretrain", "fine-tun", "neural", "transformer", "diffusion", "multimodal",
            "evaluation", "algorithm", "architecture", "inference", "reasoning",
            "capability", "scaling", "emergent", "alignment", "rlhf", "reward model",
            "breakthrough", "novel", "sota", "state-of-the-art", "outperform",
        ]
    },
    "agents": {
        "label": "AI Agents & Automation",
        "icon":  "🤖",
        "color": "#c084fc",
        "bg":    "rgba(192,132,252,0.07)",
        "keywords": [
            "agent", "autonomous", "agentic", "multi-agent", "planning", "memory",
            "tool use", "function call", "workflow", "automation", "copilot",
            "computer use", "browser", "execute", "retrieval", "rag", "orchestrat",
            "self-improv", "task complet", "action", "mcp", "crew", "autogen",
            "langchain", "langgraph", "swarm", "assistant", "chatbot",
        ]
    },
    "products": {
        "label": "New Products & Releases",
        "icon":  "🚀",
        "color": "#60a5fa",
        "bg":    "rgba(96,165,250,0.07)",
        "keywords": [
            "launch", "release", "introduc", "announc", "unveil", "new model", "gpt",
            "claude", "gemini", "llama", "mistral", "update", "feature", "api",
            "version", "preview", "beta", "availab", "product", "app", "platform",
            "service", "plugin", "integrat", "sora", "dall-e", "midjourney", "stable diffusion",
        ]
    },
    "industry": {
        "label": "Industry & Business",
        "icon":  "💼",
        "color": "#4ade80",
        "bg":    "rgba(74,222,128,0.07)",
        "keywords": [
            "funding", "million", "billion", "acqui", "ceo", "hire", "policy",
            "regulat", "invest", "startup", "openai", "google", "microsoft", "meta",
            "nvidia", "amazon", "apple", "partnership", "deal", "market", "revenue",
            "valuat", "ipo", "lawsuit", "safety", "govern", "antitrust", "datacenter",
            "compute", "chip", "semiconductor",
        ]
    },
    "open_source": {
        "label": "Open Source & Community",
        "icon":  "🌐",
        "color": "#fb923c",
        "bg":    "rgba(251,146,60,0.07)",
        "keywords": [
            "open source", "open-source", "github", "hugging face", "huggingface",
            "llama", "open weight", "open model", "community", "contrib", "fork",
            "mit license", "apache", "open access", "weights", "permissive", "ollama",
            "localai", "gguf", "quantiz", "lm studio",
        ]
    }
}

DEFAULT_CATEGORY   = "industry"
MAX_PER_CATEGORY   = 8
MAX_FEATURED_AGE_H = 72

# ── HTTP ──────────────────────────────────────────────────────────────────────
UA = "AI-Pulse-Newsletter/3.0 (+https://github.com/oeway/ai-news-channel)"

def fetch(url: str, timeout: int = 20) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [!] fetch {url[:70]}: {e}", file=sys.stderr)
        return None

# ── Date helpers ──────────────────────────────────────────────────────────────
def to_dt(v: Any) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, (list, tuple)):
        try:    return datetime(*v[:6], tzinfo=timezone.utc)
        except: return None
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v, tz=timezone.utc)
    if isinstance(v, str):
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z",
                    "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(v.strip(), fmt)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None

def age_str(dt: Optional[datetime]) -> str:
    if dt is None: return "Recently"
    delta = datetime.now(timezone.utc) - dt
    if delta.days == 0:
        h_val = delta.seconds // 3600
        return f"{delta.seconds // 60}m ago" if h_val == 0 else f"{h_val}h ago"
    if delta.days == 1: return "Yesterday"
    if delta.days < 7:  return f"{delta.days}d ago"
    return dt.strftime("%b %d, %Y")

def is_new(a: Dict) -> bool:
    dt = a.get("date")
    if not dt: return False
    return (datetime.now(timezone.utc) - dt).total_seconds() < 86400

def read_time(text: str) -> str:
    words = len(text.split())
    mins = max(1, round(words / 200))
    return f"{mins} min"

# ── Fetchers ──────────────────────────────────────────────────────────────────
def fetch_rss(cfg: Dict) -> List[Dict]:
    print(f"  RSS  {cfg['source']}…", flush=True)
    raw = fetch(cfg["url"])
    if not raw: return []
    try:
        feed     = feedparser.parse(raw)
        articles = []
        for e in feed.entries[:20]:
            desc = ""
            for attr in ("summary", "description", "content"):
                val = getattr(e, attr, None)
                if isinstance(val, list): val = val[0].get("value", "") if val else ""
                if val:
                    desc = re.sub(r"<[^>]+>", " ", val)
                    desc = re.sub(r"\s+", " ", desc).strip()[:500]
                    break
            dt = None
            for attr in ("published_parsed", "updated_parsed", "created_parsed"):
                dt = to_dt(getattr(e, attr, None))
                if dt: break
            title = getattr(e, "title", "").strip()
            url   = getattr(e, "link",  "").strip()
            if not title or not url: continue
            articles.append({"title": title, "url": url, "desc": desc,
                              "source": cfg["source"], "source_color": cfg["color"],
                              "date": dt, "category": None})
        print(f"     → {len(articles)} items", flush=True)
        return articles
    except Exception as ex:
        print(f"  [!] parse {cfg['source']}: {ex}", file=sys.stderr)
        return []

def fetch_hn() -> List[Dict]:
    print("  HN   Algolia search…", flush=True)
    seen: set = set()
    articles: List[Dict] = []
    for q in HN_TAGS[:5]:
        url = f"{HN_API}?{urllib.parse.urlencode({'query': q, 'tags': 'story', 'hitsPerPage': 12})}"
        raw = fetch(url)
        if not raw: continue
        try:
            for hit in json.loads(raw).get("hits", []):
                oid = hit.get("objectID", "")
                if oid in seen: continue
                seen.add(oid)
                title = hit.get("title", "").strip()
                if not title: continue
                story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={oid}"
                pts   = hit.get("points", 0)
                cmnts = hit.get("num_comments", 0)
                desc  = f"🔥 {pts} points · {cmnts} comments on Hacker News"
                dt    = to_dt(hit.get("created_at_i"))
                articles.append({"title": title, "url": story_url, "desc": desc,
                                  "source": "HackerNews", "source_color": "#f97316",
                                  "date": dt, "category": None,
                                  "hn_points": pts, "hn_comments": cmnts,
                                  "hn_id": oid})
        except Exception as ex:
            print(f"  [!] HN parse: {ex}", file=sys.stderr)
        time.sleep(0.3)
    print(f"     → {len(articles)} items", flush=True)
    return articles

def fetch_arxiv() -> List[Dict]:
    print("  Arxiv papers…", flush=True)
    url = (f"{ARXIV_API}?search_query={ARXIV_QUERY}"
           "&start=0&max_results=25&sortBy=submittedDate&sortOrder=descending")
    raw = fetch(url)
    if not raw: return []
    try:
        ns   = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(raw)
        arts = []
        for entry in root.findall("a:entry", ns):
            title = (entry.findtext("a:title",   "", ns) or "").replace("\n", " ").strip()
            summ  = (entry.findtext("a:summary", "", ns) or "").replace("\n", " ").strip()[:400]
            link  = (entry.findtext("a:id",      "", ns) or "").strip()
            pub   = entry.findtext("a:published", "", ns)
            cats  = [c.get("term","") for c in entry.findall("a:category", ns)]
            desc  = f"[{' · '.join(cats[:3])}] {summ}"
            if not title or not link: continue
            arts.append({"title": title, "url": link, "desc": desc,
                         "source": "arXiv", "source_color": "#a78bfa",
                         "date": to_dt(pub), "category": "research"})
        print(f"     → {len(arts)} papers", flush=True)
        return arts
    except Exception as ex:
        print(f"  [!] Arxiv: {ex}", file=sys.stderr)
        return []

# ── Classify / Score / Dedup ──────────────────────────────────────────────────
def classify(a: Dict) -> str:
    if a.get("category"): return a["category"]
    text   = (a.get("title","") + " " + a.get("desc","")).lower()
    scores = {cat: sum(1 for kw in cfg["keywords"] if kw in text)
              for cat, cfg in CATEGORIES.items()}
    best   = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else DEFAULT_CATEGORY

def score(a: Dict) -> float:
    s = 0.0
    dt = a.get("date")
    if dt:
        age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        s  += max(0, 12 - age * 0.08)
    source_bonus = {"arXiv": 2.5, "IEEE Spectrum": 2.0, "MIT Tech Review": 1.8,
                    "Google AI Blog": 1.8, "OpenAI": 1.8, "DeepLearning.AI": 1.6,
                    "TechCrunch": 1.5, "VentureBeat": 1.3, "Wired": 1.3,
                    "HuggingFace": 1.3, "Microsoft AI": 1.2,
                    "The Verge": 1.2, "HackerNews": 0.9, "Anthropic": 2.0}
    s += source_bonus.get(a.get("source",""), 1.0)
    s += min(a.get("hn_points", 0) / 200, 2.0)
    tl = len(a.get("title",""))
    if 40 < tl < 130: s += 0.4
    return s

def dedup(articles: List[Dict]) -> List[Dict]:
    seen_urls: set = set(); seen_titles: set = set(); out: List[Dict] = []
    for a in articles:
        url  = re.sub(r"\?.*$", "", a.get("url","")).rstrip("/")
        tkey = hashlib.md5(a.get("title","").lower()[:60].encode()).hexdigest()
        if url in seen_urls or tkey in seen_titles: continue
        if url: seen_urls.add(url)
        seen_titles.add(tkey)
        out.append(a)
    return out

# ── State ─────────────────────────────────────────────────────────────────────
def load_issue() -> int:
    if STATE_FILE.exists():
        try: return json.loads(STATE_FILE.read_text()).get("issue", 0)
        except: pass
    return 0

def save_issue(n: int) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"issue": n}, indent=2))

# ── HTML helpers ──────────────────────────────────────────────────────────────
SOURCE_COLORS: Dict[str, str] = {
    "TechCrunch": "#22c55e", "VentureBeat": "#f97316", "The Verge": "#e11d48",
    "Wired": "#818cf8", "IEEE Spectrum": "#0ea5e9", "MIT Tech Review": "#a78bfa",
    "arXiv": "#a78bfa", "HackerNews": "#f97316", "Google AI Blog": "#4285f4",
    "OpenAI": "#10a37f", "HuggingFace": "#ffbd59", "DeepLearning.AI": "#ff6b35",
    "Microsoft AI": "#0078d4", "Anthropic": "#b85c38",
}

def pill(source: str, color: str = "") -> str:
    c = color or SOURCE_COLORS.get(source, "#6b7280")
    return (f'<span class="pill" style="background:{c}1a;color:{c};border-color:{c}44">'
            f'{h(source)}</span>')

def card_html(a: Dict, cat_color: str) -> str:
    title    = h(a.get("title","Untitled"))
    url      = h(a.get("url","#"))
    desc     = h(a.get("desc","")[:260])
    src      = a.get("source","")
    src_c    = a.get("source_color","") or SOURCE_COLORS.get(src,"#6b7280")
    age      = h(age_str(a.get("date")))
    rtime    = read_time(a.get("desc","") + " " + a.get("title",""))
    new_badge= '<span class="badge-new">New</span>' if is_new(a) else ""
    return f'''
    <article class="card" style="--cat:{cat_color}">
      <div class="card-top">
        {pill(src, src_c)}
        <span class="card-age">{age}{new_badge}</span>
      </div>
      <h3 class="card-title"><a href="{url}" target="_blank" rel="noopener">{title}</a></h3>
      <p  class="card-desc">{desc}</p>
      <div class="card-footer">
        <a class="card-link" href="{url}" target="_blank" rel="noopener">Read more ↗</a>
        <span class="card-rtime">⏱ {rtime}</span>
      </div>
    </article>'''

def section_html(cat: str, articles: List[Dict]) -> str:
    if not articles: return ""
    cfg   = CATEGORIES[cat]
    color = cfg["color"]
    cards = "\n".join(card_html(a, color) for a in articles[:MAX_PER_CATEGORY])
    count = len(articles[:MAX_PER_CATEGORY])
    return f'''
  <section class="cat-section" id="{cat}" style="--cat:{color}">
    <header class="section-hdr">
      <span class="section-icon">{cfg["icon"]}</span>
      <h2 class="section-title">{h(cfg["label"])}</h2>
      <span class="section-count">{count} stories</span>
    </header>
    <div class="card-grid">{cards}
    </div>
  </section>'''

def featured_html(a: Dict) -> str:
    title = h(a.get("title","Untitled"))
    url   = h(a.get("url","#"))
    desc  = h(a.get("desc","")[:600])
    src   = a.get("source","")
    src_c = a.get("source_color","") or SOURCE_COLORS.get(src,"#6b7280")
    age   = h(age_str(a.get("date")))
    cat   = a.get("category", DEFAULT_CATEGORY)
    cat_c = CATEGORIES.get(cat,{}).get("color","#8b5cf6")
    cat_l = CATEGORIES.get(cat,{}).get("label","News")
    cat_i = CATEGORIES.get(cat,{}).get("icon","📌")
    return f'''
  <section class="featured-wrap">
    <div class="featured-card">
      <div class="featured-eyebrow">
        <span class="featured-badge">✦ Featured Story</span>
        <span class="featured-cat" style="color:{cat_c}">{cat_i} {h(cat_l)}</span>
      </div>
      <h2 class="featured-title">{title}</h2>
      <div class="featured-meta">
        {pill(src, src_c)}
        <span class="featured-age">{age}</span>
      </div>
      <p class="featured-body">{desc}</p>
      <a class="featured-btn" href="{url}" target="_blank" rel="noopener">Read Full Story ↗</a>
    </div>
  </section>'''

def hn_trending_html(all_articles: List[Dict]) -> str:
    hn = [a for a in all_articles if a.get("source") == "HackerNews"]
    hn.sort(key=lambda x: x.get("hn_points", 0), reverse=True)
    top = hn[:5]
    if not top: return ""
    rows = ""
    for i, a in enumerate(top, 1):
        title = h(a.get("title",""))
        url   = h(a.get("url","#"))
        pts   = a.get("hn_points", 0)
        cmnts = a.get("hn_comments", 0)
        age   = h(age_str(a.get("date")))
        hn_id = a.get("hn_id","")
        hn_url= h(f"https://news.ycombinator.com/item?id={hn_id}" if hn_id else "#")
        rows += f'''
      <li class="hn-item">
        <span class="hn-rank">#{i}</span>
        <div class="hn-info">
          <div class="hn-title"><a href="{url}" target="_blank" rel="noopener">{title}</a></div>
          <div class="hn-meta">
            <span class="hn-pts">▲ {pts} pts</span>
            <span>·</span>
            <a href="{hn_url}" target="_blank" rel="noopener" class="hn-discuss">{cmnts} comments</a>
            <span>·</span>
            <span>{age}</span>
          </div>
        </div>
      </li>'''
    return f'''
  <section class="hn-section">
    <header class="hn-header">
      <span class="hn-icon">🔥</span>
      <h2 class="hn-title">Trending on Hacker News</h2>
    </header>
    <ol class="hn-list">{rows}
    </ol>
  </section>'''

# ── CSS ───────────────────────────────────────────────────────────────────────
PAGE_CSS = r"""
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#060614;--surface:#0b0b1e;--card:#0f0f26;--card-h:#141430;
  --border:rgba(255,255,255,.07);--border-h:rgba(255,255,255,.14);
  --text:#e2e8f0;--muted:#64748b;--dim:#2d3748;
  font-size:15px;
}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--text);font-family:'Inter',system-ui,sans-serif;line-height:1.6;min-height:100vh}
a{color:inherit}

/* progress */
#progress-bar{position:fixed;top:0;left:0;z-index:999;height:3px;width:0%;
  background:linear-gradient(90deg,#7c3aed,#06b6d4,#10a37f);pointer-events:none}

/* bg glow */
.bg-glow{position:fixed;inset:0;pointer-events:none;z-index:0;
  background:
    radial-gradient(ellipse 70% 50% at 15% 5%,rgba(124,58,237,.07) 0%,transparent 65%),
    radial-gradient(ellipse 50% 40% at 85% 85%,rgba(14,165,233,.05) 0%,transparent 65%),
    radial-gradient(ellipse 40% 30% at 50% 50%,rgba(6,182,212,.04) 0%,transparent 65%)}
.page{position:relative;z-index:1}

/* header */
.site-header{position:sticky;top:0;z-index:100;
  background:rgba(6,6,20,.92);backdrop-filter:blur(16px);
  border-bottom:1px solid var(--border)}
.header-inner{max-width:1200px;margin:0 auto;padding:.8rem 1.5rem;
  display:flex;align-items:center;gap:1rem}
.brand{display:flex;align-items:center;gap:.6rem;text-decoration:none;flex-shrink:0}
.brand-icon{font-size:1.55rem;line-height:1}
.brand-name{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:1.15rem;
  background:linear-gradient(135deg,#a78bfa 0%,#38bdf8 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.brand-tag{font-size:.66rem;color:var(--muted);margin-top:1px}

.header-search{flex:1;max-width:300px;margin:0 auto}
.search-wrap{position:relative;display:flex;align-items:center}
.search-icon{position:absolute;left:.65rem;color:var(--muted);font-size:.82rem;pointer-events:none}
#search-input{width:100%;padding:.42rem .75rem .42rem 2rem;
  background:rgba(255,255,255,.05);border:1px solid var(--border);
  border-radius:8px;color:var(--text);font-size:.8rem;outline:none;
  transition:border-color .2s,background .2s}
#search-input:focus{border-color:rgba(167,139,250,.4);background:rgba(255,255,255,.07)}
#search-input::placeholder{color:var(--muted)}

.header-meta{display:flex;align-items:center;gap:.7rem;flex-shrink:0}
.issue-badge{font-size:.68rem;font-weight:700;letter-spacing:.08em;
  background:rgba(124,58,237,.15);border:1px solid rgba(124,58,237,.3);
  color:#a78bfa;padding:.2rem .6rem;border-radius:20px}
.header-date{font-size:.76rem;color:var(--muted);display:flex;align-items:center;gap:.3rem}
.live-dot{width:6px;height:6px;border-radius:50%;background:#22c55e;flex-shrink:0;
  animation:pulse-dot 2.5s ease-in-out infinite}
@keyframes pulse-dot{
  0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(34,197,94,.5)}
  50%{opacity:.7;box-shadow:0 0 0 4px rgba(34,197,94,0)}}

/* cat nav */
.cat-nav-wrap{background:rgba(6,6,20,.8);border-bottom:1px solid var(--border);backdrop-filter:blur(8px)}
.cat-nav{max-width:1200px;margin:0 auto;padding:.55rem 1.5rem;
  display:flex;align-items:center;gap:.4rem;flex-wrap:wrap}
.nav-all{font-size:.73rem;font-weight:600;padding:.26rem .6rem;border-radius:20px;
  background:rgba(255,255,255,.07);border:1px solid var(--border);color:var(--text);
  cursor:pointer;text-decoration:none;white-space:nowrap;transition:background .15s;user-select:none}
.nav-all:hover,.nav-all.active{background:rgba(255,255,255,.14)}
.nav-pill{font-size:.73rem;font-weight:500;padding:.26rem .6rem;border-radius:20px;
  border:1px solid color-mix(in srgb,var(--cat) 25%,transparent);color:var(--cat);
  cursor:pointer;text-decoration:none;white-space:nowrap;transition:background .15s;
  user-select:none;display:inline-flex;align-items:center;gap:.25rem}
.nav-pill:hover{background:color-mix(in srgb,var(--cat) 10%,transparent)}
.nav-pill.active{background:color-mix(in srgb,var(--cat) 18%,transparent);
  border-color:color-mix(in srgb,var(--cat) 50%,transparent)}
.nav-count{background:color-mix(in srgb,var(--cat) 20%,transparent);
  border-radius:10px;padding:.04rem .32rem;font-size:.63rem;font-weight:700}

/* main */
main{max-width:1200px;margin:0 auto;padding:1.75rem 1.5rem}

/* digest banner */
.digest-banner{
  background:linear-gradient(135deg,rgba(124,58,237,.08) 0%,rgba(14,165,233,.06) 100%);
  border:1px solid rgba(124,58,237,.18);border-radius:14px;padding:1rem 1.5rem;
  margin-bottom:2rem;display:flex;align-items:center;justify-content:space-between;
  gap:1rem;flex-wrap:wrap}
.digest-left{}
.digest-title{font-family:'Space Grotesk',sans-serif;font-size:.93rem;font-weight:600}
.digest-sub{font-size:.76rem;color:var(--muted);margin-top:.15rem}
.digest-stats{display:flex;gap:1.25rem;flex-wrap:wrap}
.dstat{display:flex;align-items:center;gap:.4rem;font-size:.76rem}
.dstat-dot{width:8px;height:8px;border-radius:50%;background:var(--c);flex-shrink:0}
.dstat-val{font-weight:700;color:var(--text)}
.dstat-lbl{color:var(--muted)}

/* featured */
.featured-wrap{margin-bottom:2.5rem}
.featured-card{
  background:linear-gradient(135deg,rgba(20,16,56,.92) 0%,rgba(14,14,36,.92) 60%,rgba(10,20,40,.92) 100%);
  border:1px solid rgba(124,58,237,.25);border-radius:20px;padding:2.25rem;
  position:relative;overflow:hidden}
.featured-card::before{content:'';position:absolute;top:-100px;right:-100px;
  width:400px;height:400px;border-radius:50%;
  background:radial-gradient(circle,rgba(124,58,237,.1) 0%,transparent 70%);pointer-events:none}
.featured-card::after{content:'';position:absolute;bottom:-80px;left:30%;
  width:300px;height:300px;border-radius:50%;
  background:radial-gradient(circle,rgba(6,182,212,.06) 0%,transparent 70%);pointer-events:none}
.featured-eyebrow{display:flex;align-items:center;gap:1rem;margin-bottom:.85rem}
.featured-badge{font-size:.67rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#a78bfa}
.featured-cat{font-size:.76rem;font-weight:500}
.featured-title{font-family:'Space Grotesk',sans-serif;
  font-size:clamp(1.4rem,3vw,2rem);font-weight:700;line-height:1.25;margin-bottom:1rem}
.featured-meta{display:flex;align-items:center;gap:.75rem;margin-bottom:1rem;flex-wrap:wrap}
.featured-age{font-size:.76rem;color:var(--muted)}
.featured-body{color:#94a3b8;line-height:1.75;margin-bottom:1.5rem;max-width:700px;font-size:.91rem}
.featured-btn{display:inline-flex;align-items:center;gap:.45rem;
  background:linear-gradient(135deg,#6d28d9 0%,#4f46e5 100%);
  color:#fff;text-decoration:none;padding:.65rem 1.5rem;border-radius:10px;
  font-size:.88rem;font-weight:600;box-shadow:0 4px 20px rgba(109,40,217,.35);
  transition:transform .2s,box-shadow .2s,opacity .2s}
.featured-btn:hover{transform:translateY(-2px);box-shadow:0 6px 24px rgba(109,40,217,.45);opacity:.95}

/* HN trending */
.hn-section{margin-bottom:2.5rem}
.hn-header{display:flex;align-items:center;gap:.55rem;margin-bottom:1rem;
  padding-bottom:.65rem;border-bottom:1px solid var(--border)}
.hn-icon{font-size:1.15rem}
.hn-title{font-family:'Space Grotesk',sans-serif;font-size:1rem;font-weight:700;color:#f97316}
.hn-list{list-style:none;display:flex;flex-direction:column;gap:.5rem}
.hn-item{display:flex;align-items:flex-start;gap:.75rem;padding:.7rem 1rem;
  border-radius:10px;background:var(--card);border:1px solid var(--border);
  transition:border-color .2s,background .2s}
.hn-item:hover{border-color:rgba(249,115,22,.3);background:var(--card-h)}
.hn-rank{font-size:.75rem;font-weight:700;color:#f97316;flex-shrink:0;min-width:20px;margin-top:2px}
.hn-info{flex:1;min-width:0}
.hn-title-text{font-size:.87rem;font-weight:500;line-height:1.4}
.hn-title-text a{text-decoration:none;color:var(--text)}
.hn-title-text a:hover{color:#f97316}
.hn-meta{font-size:.7rem;color:var(--muted);margin-top:.2rem;display:flex;gap:.4rem;align-items:center}
.hn-pts{color:#f97316;font-weight:600}
.hn-discuss{color:var(--muted);text-decoration:none}
.hn-discuss:hover{color:var(--text)}

/* cat sections */
.cat-section{margin-bottom:3rem}
.cat-section[hidden]{display:none!important}
.section-hdr{display:flex;align-items:center;gap:.65rem;margin-bottom:1.25rem;
  padding-bottom:.75rem;border-bottom:2px solid var(--border);position:relative}
.section-hdr::after{content:'';position:absolute;bottom:-2px;left:0;
  width:60px;height:2px;background:var(--cat);border-radius:2px}
.section-icon{font-size:1.2rem}
.section-title{font-family:'Space Grotesk',sans-serif;font-size:1.05rem;font-weight:700;color:var(--cat)}
.section-count{margin-left:auto;font-size:.68rem;color:var(--muted);
  background:var(--card);border:1px solid var(--border);padding:.1rem .48rem;border-radius:10px}

/* cards */
.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1rem}
.card[hidden]{display:none!important}
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;
  padding:1.1rem 1.2rem;display:flex;flex-direction:column;gap:.55rem;
  position:relative;overflow:hidden;
  transition:border-color .2s,background .2s,transform .2s,box-shadow .2s}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,var(--cat),color-mix(in srgb,var(--cat) 40%,transparent));
  opacity:0;transition:opacity .2s}
.card:hover{border-color:color-mix(in srgb,var(--cat) 35%,transparent);
  background:var(--card-h);transform:translateY(-3px);
  box-shadow:0 10px 30px rgba(0,0,0,.4),0 0 0 1px color-mix(in srgb,var(--cat) 12%,transparent)}
.card:hover::before{opacity:1}
.card-top{display:flex;align-items:center;justify-content:space-between;gap:.5rem}
.card-age{font-size:.69rem;color:var(--muted);flex-shrink:0;white-space:nowrap}
.badge-new{display:inline-block;font-size:.59rem;font-weight:800;letter-spacing:.06em;
  background:rgba(34,197,94,.15);border:1px solid rgba(34,197,94,.3);
  color:#22c55e;padding:.08rem .32rem;border-radius:4px;text-transform:uppercase;margin-left:.3rem}
.card-title{font-size:.9rem;font-weight:600;line-height:1.45}
.card-title a{text-decoration:none;color:var(--text);transition:color .15s}
.card-title a:hover{color:var(--cat)}
.card-desc{font-size:.78rem;color:var(--muted);line-height:1.55;flex-grow:1;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.card-footer{display:flex;align-items:center;justify-content:space-between;
  margin-top:auto;padding-top:.4rem;border-top:1px solid var(--border)}
.card-link{font-size:.74rem;font-weight:500;
  color:color-mix(in srgb,var(--cat) 85%,#fff);text-decoration:none;transition:opacity .15s}
.card-link:hover{opacity:.75}
.card-rtime{font-size:.67rem;color:var(--dim)}

/* pill */
.pill{display:inline-block;font-size:.64rem;font-weight:700;letter-spacing:.04em;
  padding:.11rem .43rem;border-radius:5px;border:1px solid;text-transform:uppercase;white-space:nowrap}

/* stats */
.stats-bar{max-width:1200px;margin:0 auto;padding:.65rem 1.5rem;
  display:flex;align-items:center;gap:1.5rem;flex-wrap:wrap;
  border-top:1px solid var(--border);font-size:.74rem;color:var(--muted)}
.stat-item{display:flex;align-items:center;gap:.3rem}
.stat-dot{width:6px;height:6px;border-radius:50%;background:var(--c,#6b7280)}

/* no results */
#no-results{display:none;text-align:center;padding:4rem 1rem;color:var(--muted);font-size:.93rem}
#no-results.show{display:block}
.empty-icon{font-size:2.5rem;margin-bottom:.75rem}

/* footer */
.site-footer{background:var(--surface);border-top:1px solid var(--border);padding:2rem 1.5rem;margin-top:2rem}
.footer-inner{max-width:1200px;margin:0 auto;
  display:flex;flex-direction:column;align-items:center;gap:.85rem;text-align:center}
.footer-brand{font-family:'Space Grotesk',sans-serif;font-size:1.05rem;font-weight:700;
  background:linear-gradient(135deg,#a78bfa,#38bdf8);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.footer-links{display:flex;gap:1.25rem;flex-wrap:wrap;justify-content:center}
.footer-links a{font-size:.79rem;color:var(--muted);text-decoration:none}
.footer-links a:hover{color:var(--text)}
.footer-sources{font-size:.71rem;color:var(--dim);display:flex;gap:.4rem;flex-wrap:wrap;justify-content:center}
.footer-sources span::after{content:'·';margin-left:.4rem}
.footer-sources span:last-child::after{content:''}
.footer-note{font-size:.71rem;color:var(--dim)}

/* scroll top */
.scroll-top{position:fixed;bottom:1.5rem;right:1.5rem;z-index:200;
  background:rgba(11,11,30,.9);border:1px solid rgba(124,58,237,.3);
  color:#a78bfa;width:38px;height:38px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;text-decoration:none;
  font-size:1rem;backdrop-filter:blur(8px);transition:background .2s,transform .2s;
  box-shadow:0 4px 14px rgba(0,0,0,.3)}
.scroll-top:hover{background:rgba(124,58,237,.2);transform:translateY(-2px)}

@media(max-width:768px){
  .header-inner{flex-wrap:wrap}
  .header-search{order:3;max-width:100%;width:100%}
  .featured-card{padding:1.5rem}
  main{padding:1.25rem 1rem}
  .digest-banner{flex-direction:column;align-items:flex-start}
}
@media(max-width:480px){
  .card-grid{grid-template-columns:1fr}
  .header-date{display:none}
  .brand-tag{display:none}
}
"""

PAGE_JS = r"""
// Scroll progress bar
const progressBar = document.getElementById('progress-bar');
function updateProgress() {
  const pct = window.scrollY / (document.body.scrollHeight - window.innerHeight) * 100;
  if (progressBar) progressBar.style.width = Math.min(pct || 0, 100) + '%';
}
window.addEventListener('scroll', updateProgress, {passive: true});

// Category filter
const navItems = document.querySelectorAll('[data-cat]');
const sections = document.querySelectorAll('.cat-section');
let activeCat = 'all';

function filterCat(cat) {
  activeCat = cat;
  navItems.forEach(n => n.classList.toggle('active', n.dataset.cat === cat));
  sections.forEach(s => {
    const show = cat === 'all' || s.id === cat;
    s.hidden = !show;
  });
  applySearch(document.getElementById('search-input')?.value || '');
}
navItems.forEach(n => n.addEventListener('click', e => { e.preventDefault(); filterCat(n.dataset.cat); }));

// Search
const searchInput = document.getElementById('search-input');
const noResults   = document.getElementById('no-results');
const allCards    = document.querySelectorAll('.card');

function applySearch(q) {
  const term = q.toLowerCase().trim();
  let visible = 0;
  allCards.forEach(card => {
    const txt = card.textContent.toLowerCase();
    const sec = card.closest('.cat-section');
    const catOk = activeCat === 'all' || (sec && sec.id === activeCat);
    const show = catOk && (!term || txt.includes(term));
    card.hidden = !show;
    if (show) visible++;
  });
  sections.forEach(sec => {
    if (activeCat !== 'all' && sec.id !== activeCat) return;
    const anyVisible = [...sec.querySelectorAll('.card')].some(c => !c.hidden);
    if (!term) sec.hidden = activeCat !== 'all' && sec.id !== activeCat;
    else sec.hidden = !anyVisible;
  });
  if (noResults) noResults.classList.toggle('show', visible === 0 && !!term);
}

if (searchInput) {
  searchInput.addEventListener('input', e => applySearch(e.target.value));
  searchInput.addEventListener('keydown', e => { if (e.key === 'Escape') { e.target.value = ''; applySearch(''); } });
}
"""

# ── Full page ─────────────────────────────────────────────────────────────────
def full_page(featured: Optional[Dict],
              sections: Dict[str, List[Dict]],
              all_articles: List[Dict],
              issue: int,
              generated: datetime) -> str:

    now_str  = generated.strftime("%B %d, %Y")
    gen_iso  = generated.strftime("%Y-%m-%dT%H:%M:%SZ")
    total    = sum(len(v) for v in sections.values())
    src_set  = sorted({a["source"] for v in sections.values() for a in v})

    cat_order    = list(CATEGORIES.keys())
    active_cats  = [c for c in cat_order if sections.get(c)]

    featured_block = featured_html(featured) if featured else ""
    hn_block       = hn_trending_html(all_articles)
    sections_html  = "".join(section_html(c, sections[c]) for c in active_cats)

    if not featured_block and not sections_html:
        sections_html = '''
  <div style="text-align:center;padding:4rem 1rem;color:#64748b">
    <div style="font-size:3rem;margin-bottom:1rem">🤖</div>
    <p>No articles fetched yet — the workflow will populate this soon.</p>
  </div>'''

    # Category nav pills
    nav_all  = '<a class="nav-all active" data-cat="all" href="#">All</a>'
    nav_pills = nav_all + "".join(
        f'<a class="nav-pill" data-cat="{cat}" href="#{cat}" style="--cat:{CATEGORIES[cat]["color"]}">'
        f'{CATEGORIES[cat]["icon"]}&thinsp;{h(CATEGORIES[cat]["label"])}'
        f'<span class="nav-count">{len(sections.get(cat,[]))}</span></a>'
        for cat in active_cats
    )

    # Digest stats
    dstats = "".join(
        f'<span class="dstat"><span class="dstat-dot" style="--c:{CATEGORIES[c]["color"]}"></span>'
        f'<span class="dstat-val">{len(sections.get(c,[]))}</span>'
        f'<span class="dstat-lbl">{CATEGORIES[c]["label"]}</span></span>'
        for c in active_cats if sections.get(c)
    )

    # Stats bar
    stats_items = "".join(
        f'<span class="stat-item"><span class="stat-dot" style="--c:{CATEGORIES[c]["color"]}"></span>'
        f'{CATEGORIES[c]["icon"]} {len(sections.get(c,[]))} {h(CATEGORIES[c]["label"])}</span>'
        for c in active_cats if sections.get(c)
    )

    sources_pills = "".join(f'<span>{h(s)}</span>' for s in src_set[:14])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Pulse — Daily AI News Digest · Issue #{issue}</title>
  <meta name="description" content="Daily curated AI news: research, agents, products, industry — Issue #{issue}, {now_str}">
  <meta property="og:title"       content="AI Pulse — Issue #{issue} · {now_str}">
  <meta property="og:description" content="Curated daily AI news: breakthroughs, agents, products, industry.">
  <meta property="og:type"        content="website">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
  <style>{PAGE_CSS}</style>
</head>
<body>
<div id="progress-bar"></div>
<div class="bg-glow"></div>
<div class="page">

  <header class="site-header">
    <div class="header-inner">
      <a class="brand" href="#">
        <span class="brand-icon">⚡</span>
        <div>
          <div class="brand-name">AI Pulse</div>
          <div class="brand-tag">Daily AI News Digest</div>
        </div>
      </a>
      <div class="header-search">
        <div class="search-wrap">
          <span class="search-icon">🔍</span>
          <input id="search-input" type="search" placeholder="Search articles…" autocomplete="off">
        </div>
      </div>
      <div class="header-meta">
        <span class="issue-badge">#{issue}</span>
        <span class="header-date"><span class="live-dot"></span>{now_str}</span>
      </div>
    </div>
    <div class="cat-nav-wrap">
      <nav class="cat-nav">{nav_pills}</nav>
    </div>
  </header>

  <main>
    <div class="digest-banner">
      <div class="digest-left">
        <div class="digest-title">Today's AI Intelligence Brief</div>
        <div class="digest-sub">{total} stories curated from {len(src_set)} sources · {now_str}</div>
      </div>
      <div class="digest-stats">{dstats}</div>
    </div>

    {featured_block}
    {hn_block}
    {sections_html}

    <div id="no-results">
      <div class="empty-icon">🔍</div>
      <p>No articles match your search. Try a different term.</p>
    </div>
  </main>

  <div class="stats-bar">{stats_items}</div>

  <footer class="site-footer">
    <div class="footer-inner">
      <div class="footer-brand">⚡ AI Pulse</div>
      <div class="footer-links">
        <a href="https://github.com/oeway/ai-news-channel" target="_blank" rel="noopener">GitHub</a>
        <a href="https://arxiv.org/list/cs.AI/recent" target="_blank" rel="noopener">arXiv CS.AI</a>
        <a href="https://news.ycombinator.com" target="_blank" rel="noopener">HackerNews</a>
      </div>
      <div class="footer-sources">{sources_pills}</div>
      <div class="footer-note">
        Auto-generated · {total} articles · {len(src_set)} sources · Issue #{issue}
        <br><time datetime="{gen_iso}">Updated {now_str}</time>
      </div>
    </div>
  </footer>

</div>
<a class="scroll-top" href="#" aria-label="Back to top">↑</a>
<script>{PAGE_JS}</script>
</body>
</html>"""

# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    print("⚡ AI Pulse Newsletter Generator v3", flush=True)
    print("─" * 50, flush=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    issue = load_issue() + 1
    print(f"Generating Issue #{issue}", flush=True)

    print("\n[1/4] Fetching news…", flush=True)
    raw_articles: List[Dict] = []
    for cfg in RSS_FEEDS:
        raw_articles.extend(fetch_rss(cfg))
    raw_articles.extend(fetch_hn())
    raw_articles.extend(fetch_arxiv())
    print(f"  Total raw: {len(raw_articles)}", flush=True)

    print("\n[2/4] Deduplicating & classifying…", flush=True)
    articles = dedup(raw_articles)
    for a in articles:
        a["category"] = classify(a)
    print(f"  After dedup: {len(articles)}", flush=True)

    print("\n[3/4] Scoring & bucketing…", flush=True)
    articles.sort(key=score, reverse=True)
    sections: Dict[str, List[Dict]] = {cat: [] for cat in CATEGORIES}
    for a in articles:
        cat = a.get("category", DEFAULT_CATEGORY)
        if cat in sections and len(sections[cat]) < MAX_PER_CATEGORY:
            sections[cat].append(a)

    now = datetime.now(timezone.utc)
    featured: Optional[Dict] = None
    for a in articles:
        dt = a.get("date")
        if dt and (now - dt).total_seconds() / 3600 < MAX_FEATURED_AGE_H:
            featured = a
            break
    if featured is None and articles:
        featured = articles[0]

    total = sum(len(v) for v in sections.values())
    print(f"  {', '.join(f'{k}:{len(v)}' for k,v in sections.items() if v)}", flush=True)

    print("\n[4/4] Rendering HTML…", flush=True)
    generated = datetime.now(timezone.utc)
    html_out  = full_page(featured, sections, articles, issue, generated)
    OUTPUT.write_text(html_out, encoding="utf-8")
    save_issue(issue)

    print(f"\n✅ Written → {OUTPUT}", flush=True)
    print(f"   Issue #{issue} · {total} articles · {generated.strftime('%Y-%m-%dT%H:%M:%SZ')}")

if __name__ == "__main__":
    main()
