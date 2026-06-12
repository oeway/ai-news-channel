#!/usr/bin/env python3
"""
AI Pulse Newsletter Generator v3
Fetches the latest AI news from multiple sources and generates a beautiful static HTML newsletter.
"""

import re, sys, json, time, hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from html import escape as h
from typing import List, Dict, Any, Optional
from collections import Counter
import urllib.parse, urllib.request

try:
    import feedparser
except ImportError:
    print("Error: feedparser not installed. Run: pip install feedparser", file=sys.stderr)
    sys.exit(1)

# ─── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR   = SCRIPT_DIR.parent
DOCS_DIR   = ROOT_DIR / "docs"
OUTPUT     = DOCS_DIR / "index.html"
STATE_FILE = DOCS_DIR / "state.json"

# ─── Sources ─────────────────────────────────────────────────────────────────

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
    {"url": "https://openai.com/blog/rss/",
     "source": "OpenAI Blog",     "color": "#10b981"},
    {"url": "https://www.anthropic.com/rss.xml",
     "source": "Anthropic",       "color": "#d97706"},
    {"url": "https://huggingface.co/blog/feed.xml",
     "source": "HuggingFace",     "color": "#f59e0b"},
    {"url": "https://blog.google/products/google-deepmind/rss/",
     "source": "DeepMind",        "color": "#4285f4"},
    {"url": "https://ai.googleblog.com/feeds/posts/default?alt=rss",
     "source": "Google AI",       "color": "#34a853"},
    {"url": "https://www.marktechpost.com/feed/",
     "source": "MarkTechPost",    "color": "#8b5cf6"},
    {"url": "https://bdtechtalks.com/feed/",
     "source": "TechTalks",       "color": "#06b6d4"},
    {"url": "https://syncedreview.com/feed/",
     "source": "Synced Review",   "color": "#ec4899"},
]

HN_API  = "https://hn.algolia.com/api/v1/search_by_date"
HN_TAGS = ["artificial intelligence", "AI agent", "large language model", "machine learning"]

ARXIV_API   = "https://export.arxiv.org/api/query"
ARXIV_QUERY = "cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.NE"

# ─── Categories ──────────────────────────────────────────────────────────────

CATEGORIES: Dict[str, Dict] = {
    "research": {
        "label": "Research & Breakthroughs",
        "icon":  "🔬",
        "color": "#22d3ee",
        "bg":    "rgba(34,211,238,0.06)",
        "keywords": [
            "paper", "arxiv", "research", "study", "benchmark", "dataset", "training",
            "pretrain", "fine-tun", "neural", "transformer", "diffusion", "multimodal",
            "evaluation", "algorithm", "architecture", "inference", "reasoning",
            "capability", "scaling", "emergent", "alignment", "rlhf", "reward model",
            "reinforcement", "self-supervised", "contrastive", "attention",
        ]
    },
    "agents": {
        "label": "AI Agents & Automation",
        "icon":  "🤖",
        "color": "#c084fc",
        "bg":    "rgba(192,132,252,0.06)",
        "keywords": [
            "agent", "autonomous", "agentic", "multi-agent", "planning", "memory",
            "tool use", "function call", "workflow", "automation", "copilot",
            "computer use", "browse", "execute", "retrieval", "rag", "orchestrat",
            "self-improv", "task complet", "action", "plugin", "mcp", "tool-calling",
        ]
    },
    "products": {
        "label": "New Products & Releases",
        "icon":  "🚀",
        "color": "#60a5fa",
        "bg":    "rgba(96,165,250,0.06)",
        "keywords": [
            "launch", "release", "introduc", "announc", "unveil", "new", "gpt",
            "claude", "gemini", "llama", "mistral", "update", "feature", "api",
            "version", "preview", "beta", "availab", "product", "app", "platform",
            "service", "integrat", "model", "upgrade",
        ]
    },
    "industry": {
        "label": "Industry & Business",
        "icon":  "💼",
        "color": "#4ade80",
        "bg":    "rgba(74,222,128,0.06)",
        "keywords": [
            "funding", "million", "billion", "acqui", "ceo", "hire", "policy",
            "regulat", "invest", "startup", "openai", "google", "microsoft", "meta",
            "nvidia", "amazon", "apple", "partnership", "deal", "market", "revenue",
            "valuat", "ipo", "lawsuit", "safety", "govern", "EU AI", "senate", "congress",
        ]
    },
    "open_source": {
        "label": "Open Source & Community",
        "icon":  "🌐",
        "color": "#fb923c",
        "bg":    "rgba(251,146,60,0.06)",
        "keywords": [
            "open source", "open-source", "github", "hugging face", "huggingface",
            "llama", "open weight", "open model", "community", "contrib", "fork",
            "mit license", "apache", "open access", "weights", "permissive", "ollama",
            "mistral", "open llm",
        ]
    }
}

DEFAULT_CATEGORY   = "industry"
MAX_PER_CATEGORY   = 8
MAX_FEATURED_AGE_H = 72

TRENDING_TERMS = [
    "GPT", "Claude", "Gemini", "Llama", "Mistral", "Grok", "Sora",
    "AI agent", "multimodal", "RAG", "fine-tuning", "alignment", "RLHF",
    "reasoning", "autonomous", "robotics", "diffusion", "vision model",
    "code generation", "AI safety", "LLM", "foundation model", "MCP",
    "benchmark", "o3", "o4", "GPT-5", "Claude 4", "Gemini 2",
]

SOURCE_COLORS: Dict[str, str] = {s["source"]: s["color"] for s in RSS_FEEDS}
SOURCE_COLORS.update({"arXiv": "#a78bfa", "HackerNews": "#f97316"})

UA = "AI-Pulse-Newsletter/3.0 (+https://github.com/oeway/ai-news-channel)"

# ─── HTTP ─────────────────────────────────────────────────────────────────────

def fetch(url: str, timeout: int = 20) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [!] {url[:70]}: {e}", file=sys.stderr)
        return None

# ─── Date helpers ─────────────────────────────────────────────────────────────

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
        mins = delta.seconds // 60
        h_val = mins // 60
        return f"{mins}m ago" if h_val == 0 else f"{h_val}h ago"
    if delta.days == 1: return "Yesterday"
    if delta.days < 7:  return f"{delta.days}d ago"
    return dt.strftime("%b %d")

def is_breaking(dt: Optional[datetime]) -> bool:
    if dt is None: return False
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600 < 6

def reading_time(text: str) -> int:
    words = len(text.split())
    return max(1, round(words / 200))

# ─── Fetchers ─────────────────────────────────────────────────────────────────

def fetch_rss(cfg: Dict) -> List[Dict]:
    print(f"  RSS  {cfg['source']}…", flush=True)
    raw = fetch(cfg["url"])
    if not raw: return []
    try:
        feed = feedparser.parse(raw)
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
    for q in HN_TAGS[:4]:
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
                pts   = hit.get("points", 0)
                cmnts = hit.get("num_comments", 0)
                if pts < 20: continue  # filter low-signal posts
                story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={oid}"
                desc  = f"🔥 {pts} points · {cmnts} comments on Hacker News"
                dt    = to_dt(hit.get("created_at_i"))
                articles.append({"title": title, "url": story_url, "desc": desc,
                                  "source": "HackerNews", "source_color": "#f97316",
                                  "date": dt, "category": None})
        except Exception as ex:
            print(f"  [!] HN: {ex}", file=sys.stderr)
        time.sleep(0.3)
    print(f"     → {len(articles)} items", flush=True)
    return articles

def fetch_arxiv() -> List[Dict]:
    print("  arXiv papers…", flush=True)
    url = (f"{ARXIV_API}?search_query={ARXIV_QUERY}"
           "&start=0&max_results=20&sortBy=submittedDate&sortOrder=descending")
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
        print(f"  [!] arXiv: {ex}", file=sys.stderr)
        return []

# ─── Classify / Score / Dedup ─────────────────────────────────────────────────

def classify(a: Dict) -> str:
    if a.get("category"):
        return a["category"]
    text   = (a.get("title","") + " " + a.get("desc","")).lower()
    scores = {cat: sum(1 for kw in cfg["keywords"] if kw in text)
              for cat, cfg in CATEGORIES.items()}
    best   = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else DEFAULT_CATEGORY

def score(a: Dict) -> float:
    s  = 0.0
    dt = a.get("date")
    if dt:
        age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        s    += max(0, 12 - age_h * 0.07)
    source_bonus = {
        "arXiv": 2.8, "IEEE Spectrum": 2.2, "MIT Tech Review": 2.0,
        "Anthropic": 2.0, "OpenAI Blog": 2.0, "DeepMind": 1.9,
        "Google AI": 1.7, "TechCrunch": 1.6, "VentureBeat": 1.4,
        "Wired": 1.4, "HuggingFace": 1.3, "The Verge": 1.2, "HackerNews": 0.9,
    }
    s += source_bonus.get(a.get("source",""), 1.0)
    tl = len(a.get("title",""))
    if 40 < tl < 130: s += 0.5
    return s

def dedup(articles: List[Dict]) -> List[Dict]:
    seen_urls:   set = set()
    seen_titles: set = set()
    out: List[Dict] = []
    for a in articles:
        url  = re.sub(r"\?.*$", "", a.get("url","")).rstrip("/")
        tkey = hashlib.md5(a.get("title","").lower()[:60].encode()).hexdigest()
        if url in seen_urls or tkey in seen_titles: continue
        if url: seen_urls.add(url)
        seen_titles.add(tkey)
        out.append(a)
    return out

def extract_trending(articles: List[Dict]) -> List[tuple]:
    counts: Counter = Counter()
    for a in articles:
        text = (a.get("title","") + " " + a.get("desc","")).lower()
        for term in TRENDING_TERMS:
            if term.lower() in text:
                counts[term] += 1
    return [(k, v) for k, v in counts.most_common(14) if v >= 2]

# ─── Issue counter ────────────────────────────────────────────────────────────

def load_issue() -> int:
    if STATE_FILE.exists():
        try: return json.loads(STATE_FILE.read_text()).get("issue", 0)
        except: pass
    return 0

def save_issue(n: int) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"issue": n}, indent=2))

# ─── HTML helpers ─────────────────────────────────────────────────────────────

def source_pill(source: str, color: str = "") -> str:
    c = color or SOURCE_COLORS.get(source, "#6b7280")
    return (f'<span class="pill" style="background:{c}22;color:{c};border-color:{c}44">'
            f'{h(source)}</span>')

def card_html(a: Dict, cat_color: str) -> str:
    title   = h(a.get("title","Untitled"))
    url     = h(a.get("url","#"))
    desc    = h(a.get("desc","")[:260])
    src     = a.get("source","")
    src_c   = a.get("source_color","") or SOURCE_COLORS.get(src,"#6b7280")
    age     = age_str(a.get("date"))
    rt      = reading_time(a.get("desc","") + a.get("title",""))
    brk     = is_breaking(a.get("date"))
    brk_badge = '<span class="badge-new">NEW</span>' if brk else ""
    cat     = a.get("category", DEFAULT_CATEGORY)
    return f'''<article class="card" data-cat="{cat}" style="--cat:{cat_color}">
      <div class="card-top">
        {source_pill(src, src_c)}{brk_badge}
        <span class="card-age">{h(age)} · {rt}m read</span>
      </div>
      <h3 class="card-title"><a href="{url}" target="_blank" rel="noopener">{title}</a></h3>
      <p  class="card-desc">{desc}</p>
      <a  class="card-link" href="{url}" target="_blank" rel="noopener">Read more ↗</a>
    </article>'''

def section_html(cat: str, articles: List[Dict]) -> str:
    if not articles: return ""
    cfg   = CATEGORIES[cat]
    color = cfg["color"]
    bg    = cfg["bg"]
    cards = "\n".join(card_html(a, color) for a in articles[:MAX_PER_CATEGORY])
    count = min(len(articles), MAX_PER_CATEGORY)
    return f'''
  <section class="cat-section" id="{cat}" style="--cat:{color};--cat-bg:{bg}">
    <header class="section-hdr">
      <span class="section-icon">{cfg["icon"]}</span>
      <h2 class="section-title">{h(cfg["label"])}</h2>
      <span class="section-count">{count} stories</span>
    </header>
    <div class="card-grid">{cards}</div>
  </section>'''

def featured_html(a: Dict) -> str:
    title  = h(a.get("title","Untitled"))
    url    = h(a.get("url","#"))
    desc   = h(a.get("desc","")[:600])
    src    = a.get("source","")
    src_c  = a.get("source_color","") or SOURCE_COLORS.get(src,"#6b7280")
    age    = age_str(a.get("date"))
    cat    = a.get("category", DEFAULT_CATEGORY)
    cat_c  = CATEGORIES.get(cat,{}).get("color","#8b5cf6")
    cat_l  = CATEGORIES.get(cat,{}).get("label","News")
    cat_i  = CATEGORIES.get(cat,{}).get("icon","📌")
    return f'''
  <section class="featured-wrap" data-cat="{cat}">
    <div class="featured-card">
      <div class="featured-eyebrow">
        <span class="featured-badge">✦ Featured Story</span>
        <span class="featured-cat" style="color:{cat_c}">{cat_i} {h(cat_l)}</span>
      </div>
      <h2 class="featured-title">{title}</h2>
      <div class="featured-meta">
        {source_pill(src, src_c)}
        <span class="featured-age">{h(age)}</span>
      </div>
      <p class="featured-body">{desc}</p>
      <a class="featured-btn" href="{url}" target="_blank" rel="noopener">Read Full Story ↗</a>
    </div>
  </section>'''

def trending_html(terms: List[tuple]) -> str:
    if not terms: return ""
    MAX_COUNT = terms[0][1] if terms else 1
    tags = ""
    for term, count in terms:
        size  = 0.78 + (count / MAX_COUNT) * 0.4
        alpha = 0.5  + (count / MAX_COUNT) * 0.5
        tags += (f'<button class="trend-tag" data-q="{h(term)}" '
                 f'style="font-size:{size:.2f}rem;opacity:{alpha:.2f}">'
                 f'{h(term)} <sup>{count}</sup></button>')
    return f'''
  <section class="trending-section">
    <div class="trending-hdr">
      <span class="trending-icon">🔥</span>
      <h3 class="trending-title">Trending Topics</h3>
      <span class="trending-sub">click to filter</span>
    </div>
    <div class="trend-cloud">{tags}</div>
  </section>'''

def hero_html(issue: int, total: int, sources: int, generated: datetime) -> str:
    date_str = generated.strftime("%B %d, %Y")
    time_str = generated.strftime("%H:%M UTC")
    return f'''
  <section class="hero">
    <div class="hero-inner">
      <div class="hero-eyebrow">
        <span class="live-pill"><span class="live-dot"></span>Live Feed</span>
        <span class="hero-issue">Issue #{issue}</span>
      </div>
      <h1 class="hero-title">AI Pulse</h1>
      <p class="hero-sub">Your daily briefing on AI research, agents, products & industry</p>
      <div class="hero-stats">
        <div class="hero-stat">
          <span class="hero-stat-val">{total}</span>
          <span class="hero-stat-lbl">Articles</span>
        </div>
        <div class="hero-divider"></div>
        <div class="hero-stat">
          <span class="hero-stat-val">{sources}</span>
          <span class="hero-stat-lbl">Sources</span>
        </div>
        <div class="hero-divider"></div>
        <div class="hero-stat">
          <span class="hero-stat-val">{date_str}</span>
          <span class="hero-stat-lbl">Updated {time_str}</span>
        </div>
      </div>
    </div>
  </section>'''

# ─── CSS ──────────────────────────────────────────────────────────────────────

PAGE_CSS = r"""
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0 }

:root {
  --bg:       #06061a;
  --surface:  #0b0b22;
  --card:     #0f0f28;
  --card-h:   #14143a;
  --border:   rgba(255,255,255,0.07);
  --border-h: rgba(255,255,255,0.14);
  --text:     #e8eaf6;
  --sub:      #94a3b8;
  --muted:    #64748b;
  --dim:      #334155;
  font-size: 15px;
}
html { scroll-behavior: smooth }
body {
  background: var(--bg); color: var(--text);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  line-height: 1.6; min-height: 100vh;
}
a { color: inherit; text-decoration: none }

body::before {
  content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background:
    radial-gradient(ellipse 70% 50% at 15%  0%,  rgba(99,102,241,.10) 0%, transparent 65%),
    radial-gradient(ellipse 55% 40% at 85% 90%,  rgba(6,182,212,.07)  0%, transparent 65%),
    radial-gradient(ellipse 40% 30% at 50% 50%,  rgba(139,92,246,.04) 0%, transparent 60%);
}
.page { position: relative; z-index: 1 }

/* ── Sticky header ── */
.site-header {
  border-bottom: 1px solid var(--border);
  background: rgba(6,6,26,.96);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  position: sticky; top: 0; z-index: 100;
}
.header-inner {
  max-width: 1200px; margin: 0 auto;
  padding: .8rem 1.5rem;
  display: flex; align-items: center; gap: 1rem;
}
.brand { display: flex; align-items: center; gap: .65rem }
.brand-logo { font-size: 1.6rem; line-height: 1 }
.brand-name {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.25rem; font-weight: 700;
  background: linear-gradient(135deg, #a78bfa 0%, #38bdf8 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.brand-sub { font-size: .7rem; color: var(--muted) }

/* Search */
.header-search {
  flex: 1; max-width: 340px; margin-left: auto;
  position: relative;
}
.search-input {
  width: 100%;
  background: rgba(255,255,255,.05);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  padding: .45rem .9rem .45rem 2.2rem;
  font-size: .82rem; font-family: inherit;
  transition: border-color .2s, background .2s;
  outline: none;
}
.search-input::placeholder { color: var(--muted) }
.search-input:focus {
  border-color: rgba(167,139,250,.5);
  background: rgba(167,139,250,.07);
}
.search-icon {
  position: absolute; left: .7rem; top: 50%; transform: translateY(-50%);
  color: var(--muted); font-size: .85rem; pointer-events: none;
}
.header-right { display: flex; align-items: center; gap: .6rem; flex-shrink: 0 }
.issue-badge {
  font-size: .7rem; font-weight: 700; letter-spacing: .07em;
  background: linear-gradient(135deg,rgba(167,139,250,.15),rgba(56,189,248,.15));
  border: 1px solid rgba(167,139,250,.3);
  color: #a78bfa; padding: .22rem .65rem; border-radius: 20px;
}

/* ── Category nav bar ── */
.cat-nav {
  max-width: 1200px; margin: 0 auto;
  padding: .65rem 1.5rem;
  display: flex; gap: .4rem; flex-wrap: wrap;
  border-top: 1px solid var(--border);
}
.nav-pill {
  font-size: .76rem; font-weight: 500;
  padding: .28rem .7rem; border-radius: 20px;
  border: 1px solid color-mix(in srgb,var(--cat) 28%, transparent);
  color: var(--cat);
  transition: background .15s, transform .15s;
  white-space: nowrap; cursor: pointer;
}
.nav-pill:hover, .nav-pill.active {
  background: color-mix(in srgb, var(--cat) 14%, transparent);
  transform: translateY(-1px);
}
.nav-all {
  font-size: .76rem; font-weight: 500;
  padding: .28rem .7rem; border-radius: 20px;
  border: 1px solid var(--border);
  color: var(--sub);
  transition: background .15s, color .15s; cursor: pointer;
}
.nav-all:hover, .nav-all.active { background: rgba(255,255,255,.07); color: var(--text) }

/* ── Hero ── */
.hero {
  padding: 3.5rem 1.5rem 2.5rem;
  text-align: center;
  position: relative; overflow: hidden;
}
.hero::before {
  content: '';
  position: absolute; top: -60px; left: 50%; transform: translateX(-50%);
  width: 700px; height: 400px; border-radius: 50%;
  background: radial-gradient(ellipse, rgba(99,102,241,.14) 0%, transparent 70%);
  pointer-events: none;
}
.hero-inner { position: relative; z-index: 1 }
.hero-eyebrow {
  display: flex; align-items: center; justify-content: center;
  gap: .75rem; margin-bottom: 1rem;
}
.live-pill {
  display: inline-flex; align-items: center; gap: .35rem;
  font-size: .72rem; font-weight: 600; letter-spacing: .06em; text-transform: uppercase;
  background: rgba(34,197,94,.12); color: #22c55e;
  border: 1px solid rgba(34,197,94,.3);
  padding: .22rem .65rem; border-radius: 20px;
}
.live-dot {
  display: inline-block; width: 6px; height: 6px; border-radius: 50%;
  background: #22c55e;
  animation: pulse-dot 2.5s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%,100% { opacity:1; box-shadow:0 0 0 0 rgba(34,197,94,.5) }
  50%      { opacity:.7; box-shadow:0 0 0 5px rgba(34,197,94,0) }
}
.hero-issue {
  font-size: .72rem; font-weight: 700; letter-spacing: .05em;
  color: var(--muted); text-transform: uppercase;
}
.hero-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: clamp(2.5rem, 6vw, 4.5rem);
  font-weight: 700; line-height: 1.1; margin-bottom: .75rem;
  background: linear-gradient(135deg, #e8eaf6 0%, #a78bfa 40%, #38bdf8 80%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.hero-sub {
  font-size: clamp(.9rem, 2vw, 1.1rem); color: var(--sub);
  max-width: 560px; margin: 0 auto 2rem;
}
.hero-stats {
  display: inline-flex; align-items: center; gap: 0;
  background: rgba(255,255,255,.04);
  border: 1px solid var(--border);
  border-radius: 14px; padding: .75rem 1.5rem;
  flex-wrap: wrap; justify-content: center;
}
.hero-stat { text-align: center; padding: 0 1.25rem }
.hero-stat-val {
  display: block; font-size: 1.1rem; font-weight: 700;
  font-family: 'Space Grotesk', sans-serif;
  background: linear-gradient(135deg, #e8eaf6, #a78bfa);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.hero-stat-lbl { font-size: .7rem; color: var(--muted); text-transform: uppercase; letter-spacing: .05em }
.hero-divider { width: 1px; height: 32px; background: var(--border) }

/* ── Trending topics ── */
.trending-section {
  max-width: 1200px; margin: 0 auto 2rem;
  padding: 0 1.5rem;
}
.trending-inner {
  background: rgba(255,255,255,.025);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1.1rem 1.4rem;
}
.trending-hdr {
  display: flex; align-items: center; gap: .5rem; margin-bottom: .85rem;
}
.trending-icon { font-size: 1rem }
.trending-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: .88rem; font-weight: 600; color: var(--sub);
}
.trending-sub { font-size: .72rem; color: var(--dim); margin-left: auto }
.trend-cloud { display: flex; flex-wrap: wrap; gap: .45rem }
.trend-tag {
  background: rgba(255,255,255,.05); border: 1px solid var(--border);
  color: var(--sub); border-radius: 20px;
  padding: .25rem .7rem;
  font-size: .78rem; font-family: inherit; cursor: pointer;
  transition: background .15s, color .15s, border-color .15s, transform .15s;
}
.trend-tag sup { font-size: .6em; color: var(--dim) }
.trend-tag:hover, .trend-tag.active {
  background: rgba(167,139,250,.15);
  border-color: rgba(167,139,250,.4);
  color: #a78bfa; transform: translateY(-1px);
}

/* ── Main ── */
main { max-width: 1200px; margin: 0 auto; padding: 0 1.5rem 2rem }

/* ── Featured ── */
.featured-wrap { margin-bottom: 2.5rem }
.featured-card {
  background: linear-gradient(135deg, #130f3a 0%, #0e0e2c 50%, #091828 100%);
  border: 1px solid rgba(167,139,250,.2);
  border-radius: 20px; padding: 2rem 2.5rem;
  position: relative; overflow: hidden;
}
.featured-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, #a78bfa, #38bdf8, transparent);
}
.featured-card::after {
  content: ''; position: absolute; top: -100px; right: -100px;
  width: 400px; height: 400px; border-radius: 50%;
  background: radial-gradient(circle, rgba(99,102,241,.1) 0%, transparent 70%);
  pointer-events: none;
}
.featured-eyebrow {
  display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem
}
.featured-badge {
  font-size: .7rem; font-weight: 700; letter-spacing: .1em;
  color: #a78bfa; text-transform: uppercase;
}
.featured-cat { font-size: .76rem; font-weight: 500 }
.featured-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: clamp(1.25rem, 3vw, 1.85rem); font-weight: 700;
  line-height: 1.3; margin-bottom: .9rem;
}
.featured-meta { display: flex; align-items: center; gap: .75rem; margin-bottom: 1rem }
.featured-age  { font-size: .78rem; color: var(--muted) }
.featured-body { color: var(--sub); line-height: 1.75; margin-bottom: 1.5rem; max-width: 700px }
.featured-btn {
  display: inline-flex; align-items: center; gap: .4rem;
  background: linear-gradient(135deg, #6d28d9, #4f46e5);
  color: #fff; padding: .6rem 1.4rem; border-radius: 10px;
  font-size: .87rem; font-weight: 600;
  transition: opacity .2s, transform .15s;
  box-shadow: 0 4px 18px rgba(99,102,241,.4);
}
.featured-btn:hover { opacity: .88; transform: translateY(-2px) }

/* ── Category section ── */
.cat-section { margin-bottom: 3rem }
.section-hdr {
  display: flex; align-items: center; gap: .6rem;
  margin-bottom: 1.25rem; padding-bottom: .7rem;
  border-bottom: 2px solid color-mix(in srgb, var(--cat) 25%, transparent);
}
.section-icon  { font-size: 1.2rem }
.section-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.05rem; font-weight: 700; color: var(--cat);
}
.section-count {
  margin-left: auto; font-size: .7rem; color: var(--muted);
  background: var(--card); border: 1px solid var(--border);
  padding: .12rem .5rem; border-radius: 12px;
}

/* ── Cards ── */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px; padding: 1.1rem 1.2rem;
  display: flex; flex-direction: column; gap: .55rem;
  transition: border-color .2s, background .2s, transform .2s, box-shadow .2s;
  position: relative; overflow: hidden;
  animation: card-enter .4s ease both;
}
@keyframes card-enter {
  from { opacity: 0; transform: translateY(12px) }
  to   { opacity: 1; transform: translateY(0) }
}
.card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: var(--cat, #8b5cf6); opacity: 0; transition: opacity .2s;
}
.card:hover {
  border-color: color-mix(in srgb, var(--cat) 45%, transparent);
  background: var(--card-h);
  transform: translateY(-3px);
  box-shadow: 0 8px 32px rgba(0,0,0,.4),
              0 0 0 1px color-mix(in srgb,var(--cat) 15%,transparent);
}
.card:hover::before { opacity: 1 }

.card-top  { display: flex; align-items: center; gap: .4rem; flex-wrap: wrap }
.card-age  { font-size: .7rem; color: var(--muted); margin-left: auto }
.card-title {
  font-size: .91rem; font-weight: 600; line-height: 1.45;
}
.card-title a { color: var(--text); transition: color .15s }
.card-title a:hover { color: var(--cat, #a78bfa) }
.card-desc {
  font-size: .8rem; color: var(--muted); line-height: 1.55; flex-grow: 1;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.card-link {
  font-size: .76rem; font-weight: 500;
  color: color-mix(in srgb, var(--cat) 90%, #fff);
  margin-top: auto; transition: opacity .15s;
}
.card-link:hover { opacity: .75 }

/* ── Pill / badges ── */
.pill {
  display: inline-block; font-size: .66rem; font-weight: 700; letter-spacing: .04em;
  padding: .13rem .45rem; border-radius: 5px; border: 1px solid;
  text-transform: uppercase; flex-shrink: 0;
}
.badge-new {
  display: inline-block; font-size: .62rem; font-weight: 800; letter-spacing: .06em;
  padding: .1rem .4rem; border-radius: 4px;
  background: rgba(239,68,68,.2); color: #f87171;
  border: 1px solid rgba(239,68,68,.4);
  text-transform: uppercase; animation: pulse-new 2s ease-in-out infinite;
}
@keyframes pulse-new {
  0%,100% { opacity: 1 } 50% { opacity: .6 }
}

/* ── Empty / no-results ── */
.empty-state {
  text-align: center; padding: 4rem 1rem; color: var(--muted);
}
.empty-icon { font-size: 3rem; margin-bottom: 1rem }
#no-results { display: none; text-align: center; padding: 2rem; color: var(--muted) }

/* ── Stats bar ── */
.stats-bar {
  max-width: 1200px; margin: 0 auto;
  padding: .7rem 1.5rem;
  display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap;
  border-top: 1px solid var(--border);
  font-size: .76rem; color: var(--muted);
}
.stat-item { display: flex; align-items: center; gap: .3rem }
.stat-dot  { width: 6px; height: 6px; border-radius: 50%; background: var(--c,#6b7280) }

/* ── Footer ── */
.site-footer {
  background: var(--surface); border-top: 1px solid var(--border);
  padding: 2.5rem 1.5rem; margin-top: 1rem;
}
.footer-inner {
  max-width: 1200px; margin: 0 auto;
  display: grid; grid-template-columns: 1fr auto;
  gap: 2rem; align-items: start;
}
.footer-brand-wrap .footer-brand {
  font-family: 'Space Grotesk', sans-serif; font-size: 1.1rem; font-weight: 700;
  background: linear-gradient(135deg,#a78bfa,#38bdf8);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
  margin-bottom: .5rem;
}
.footer-brand-wrap p { font-size: .78rem; color: var(--muted); max-width: 360px; line-height: 1.55 }
.footer-links { display: flex; flex-direction: column; gap: .5rem; align-items: flex-end }
.footer-links a { font-size: .82rem; color: var(--muted); transition: color .15s }
.footer-links a:hover { color: var(--text) }
.footer-bottom {
  max-width: 1200px; margin: 1.5rem auto 0;
  padding-top: 1rem; border-top: 1px solid var(--border);
  display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;
  font-size: .72rem; color: var(--dim);
}
.footer-sources { display: flex; gap: .35rem; flex-wrap: wrap; flex: 1 }
.footer-sources .src { opacity: .7 }

/* ── Scroll-to-top ── */
.scroll-top {
  position: fixed; bottom: 1.5rem; right: 1.5rem; z-index: 200;
  background: rgba(11,11,34,.92); border: 1px solid rgba(167,139,250,.3);
  color: #a78bfa; width: 40px; height: 40px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem; cursor: pointer; backdrop-filter: blur(8px);
  transition: background .2s, transform .2s;
  box-shadow: 0 4px 14px rgba(0,0,0,.4);
}
.scroll-top:hover { background: rgba(99,102,241,.28); transform: translateY(-2px) }

/* ── Responsive ── */
@media (max-width: 768px) {
  .hero { padding: 2.5rem 1rem 2rem }
  .featured-card { padding: 1.4rem 1.25rem }
  main { padding: 0 1rem 2rem }
  .trending-section { padding: 0 1rem }
  .footer-inner { grid-template-columns: 1fr }
  .footer-links { align-items: flex-start }
}
@media (max-width: 560px) {
  .card-grid { grid-template-columns: 1fr }
  .header-search { display: none }
  .hero-stats { padding: .65rem .75rem }
  .hero-stat { padding: 0 .75rem }
}
"""

PAGE_JS = r"""
(function() {
  const $ = s => document.querySelectorAll(s);

  // ── Search ──
  const searchEl = document.getElementById('q');
  const noRes    = document.getElementById('no-results');

  function filterAll() {
    const q   = (searchEl ? searchEl.value : '').toLowerCase().trim();
    const cat = document.querySelector('.nav-pill.active, .nav-all.active')?.dataset?.cat || '';
    let visible = 0;

    $('[data-cat]').forEach(el => {
      const text   = el.textContent.toLowerCase();
      const elCat  = el.dataset.cat || '';
      const matchQ = !q || text.includes(q);
      const matchC = !cat || elCat === cat;
      const show   = matchQ && matchC;
      el.style.display = show ? '' : 'none';
      if (show) visible++;
    });

    // Hide empty sections
    $('.cat-section').forEach(sec => {
      const hasVisible = [...sec.querySelectorAll('.card')].some(c => c.style.display !== 'none');
      sec.style.display = hasVisible ? '' : 'none';
    });

    if (noRes) noRes.style.display = visible === 0 ? 'block' : 'none';
  }

  if (searchEl) {
    let timer;
    searchEl.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(filterAll, 200) });
  }

  // ── Category nav ──
  $('.nav-pill, .nav-all').forEach(btn => {
    btn.addEventListener('click', e => {
      $('.nav-pill, .nav-all').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      filterAll();
      // smooth-scroll to section if pill
      if (btn.dataset.cat) {
        const sec = document.getElementById(btn.dataset.cat);
        if (sec) sec.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // ── Trending tags ──
  $('.trend-tag').forEach(tag => {
    tag.addEventListener('click', () => {
      const q = tag.dataset.q;
      if (!searchEl) return;
      if (searchEl.value === q) {
        searchEl.value = '';
        tag.classList.remove('active');
      } else {
        searchEl.value = q;
        $('.trend-tag').forEach(t => t.classList.remove('active'));
        tag.classList.add('active');
      }
      // reset cat filter
      $('.nav-pill, .nav-all').forEach(b => b.classList.remove('active'));
      document.querySelector('.nav-all')?.classList.add('active');
      filterAll();
    });
  });

  // ── Staggered card animations ──
  const observer = new IntersectionObserver(entries => {
    entries.forEach((e, i) => {
      if (e.isIntersecting) {
        e.target.style.animationDelay = (i * 0.04) + 's';
        observer.unobserve(e.target);
      }
    });
  }, { threshold: 0.05 });
  $('.card').forEach(c => observer.observe(c));

  // ── Live relative-time updates ──
  function tick() {
    document.querySelectorAll('[data-ts]').forEach(el => {
      const ts = +el.dataset.ts;
      const d  = Math.floor((Date.now()/1000 - ts) / 60);
      el.textContent = d < 1 ? 'just now' : d < 60 ? d+'m ago' :
                       d < 1440 ? Math.floor(d/60)+'h ago' : Math.floor(d/1440)+'d ago';
    });
  }
  tick();
  setInterval(tick, 60000);
})();
"""

# ─── Full page assembly ───────────────────────────────────────────────────────

def full_page(featured: Optional[Dict],
              sections: Dict[str, List[Dict]],
              issue: int,
              generated: datetime,
              trending: List[tuple]) -> str:

    now_str  = generated.strftime("%B %d, %Y")
    gen_iso  = generated.strftime("%Y-%m-%dT%H:%M:%SZ")
    total    = sum(len(v) for v in sections.values())
    src_set  = sorted({a["source"] for v in sections.values() for a in v})

    cat_order   = list(CATEGORIES.keys())
    active_cats = [c for c in cat_order if sections.get(c)]

    # blocks
    hero_block     = hero_html(issue, total, len(src_set), generated)
    trending_block = f'<div class="trending-section"><div class="trending-inner">{trending_html(trending)[len("<section class=")..:].lstrip()}</div></div>' if trending else ""
    # Rebuild trending properly
    if trending:
        MAX_COUNT = trending[0][1]
        tags = ""
        for term, count in trending:
            size  = 0.78 + (count / MAX_COUNT) * 0.4
            alpha = 0.55 + (count / MAX_COUNT) * 0.45
            tags += (f'<button class="trend-tag" data-q="{h(term)}" '
                     f'style="font-size:{size:.2f}rem;opacity:{alpha:.2f}">'
                     f'{h(term)} <sup>{count}</sup></button>')
        trending_block = f'''<div class="trending-section"><div class="trending-inner">
    <div class="trending-hdr">
      <span class="trending-icon">🔥</span>
      <h3 class="trending-title">Trending Topics</h3>
      <span class="trending-sub">click to filter</span>
    </div>
    <div class="trend-cloud">{tags}</div>
  </div></div>'''
    else:
        trending_block = ""

    featured_block = featured_html(featured) if featured else ""

    sections_html = ""
    for cat in active_cats:
        sections_html += section_html(cat, sections[cat])

    if not featured_block and not sections_html:
        sections_html = '''<div class="empty-state">
    <div class="empty-icon">🤖</div>
    <p>No articles fetched yet. The workflow will populate this shortly.</p>
  </div>'''

    # nav
    nav_links = '<button class="nav-all active" data-cat="">All</button>'
    for cat in active_cats:
        cfg = CATEGORIES[cat]
        nav_links += (f'<button class="nav-pill" data-cat="{cat}" style="--cat:{cfg["color"]}">'
                      f'{cfg["icon"]}&thinsp;{h(cfg["label"])}</button>')
    nav_block = f'<nav class="cat-nav">{nav_links}</nav>'

    # stats
    stats_items = "".join(
        f'<span class="stat-item"><span class="stat-dot" style="--c:{CATEGORIES[c]["color"]}"></span>'
        f'{CATEGORIES[c]["icon"]} {len(sections.get(c,[]))} {h(CATEGORIES[c]["label"])}</span>'
        for c in active_cats if sections.get(c)
    )
    stats_block = f'<div class="stats-bar">{stats_items}</div>' if stats_items else ""

    src_pills = "".join(f'<span class="src">{h(s)}</span>' for s in src_set[:16])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Pulse — Issue #{issue} · {now_str}</title>
  <meta name="description" content="Daily curated AI news: research breakthroughs, AI agents, new products &amp; industry — Issue #{issue}, {now_str}">
  <meta property="og:title"       content="AI Pulse — Issue #{issue} · {now_str}">
  <meta property="og:description" content="Daily AI digest: {total} articles from {len(src_set)} sources covering research, agents, products &amp; industry.">
  <meta property="og:type"        content="website">
  <meta name="theme-color"        content="#06061a">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
  <style>{PAGE_CSS}</style>
</head>
<body>
<div class="page">

  <header class="site-header">
    <div class="header-inner">
      <a class="brand" href="#">
        <span class="brand-logo">⚡</span>
        <div>
          <div class="brand-name">AI Pulse</div>
          <div class="brand-sub">Daily AI News Digest</div>
        </div>
      </a>
      <div class="header-search">
        <span class="search-icon">🔍</span>
        <input class="search-input" id="q" type="search" placeholder="Search articles…" autocomplete="off">
      </div>
      <div class="header-right">
        <span class="issue-badge">Issue #{issue}</span>
      </div>
    </div>
    {nav_block}
  </header>

  {hero_block}

  {trending_block}

  <main>
    {featured_block}
    {sections_html}
    <p id="no-results">No matching articles found.</p>
  </main>

  {stats_block}

  <footer class="site-footer">
    <div class="footer-inner">
      <div class="footer-brand-wrap">
        <div class="footer-brand">⚡ AI Pulse</div>
        <p>An automated daily digest of AI news — research breakthroughs, agent frameworks, new products, industry moves, and open-source releases. Updated every morning at 07:00 UTC.</p>
      </div>
      <div class="footer-links">
        <a href="https://github.com/oeway/ai-news-channel" target="_blank" rel="noopener">⭐ GitHub</a>
        <a href="https://arxiv.org/list/cs.AI/recent" target="_blank" rel="noopener">📄 arXiv CS.AI</a>
        <a href="https://news.ycombinator.com" target="_blank" rel="noopener">🔶 HackerNews</a>
        <a href="https://huggingface.co/blog" target="_blank" rel="noopener">🤗 HuggingFace</a>
      </div>
    </div>
    <div class="footer-bottom">
      <div class="footer-sources">{src_pills}</div>
      <span>{total} articles · {len(src_set)} sources · <time datetime="{gen_iso}">{gen_iso}</time></span>
    </div>
  </footer>

</div>
<a class="scroll-top" href="#" aria-label="Back to top" title="Back to top">↑</a>
<script>{PAGE_JS}</script>
</body>
</html>"""

# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("⚡ AI Pulse Newsletter Generator v3", flush=True)
    print("─" * 50, flush=True)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    issue = load_issue() + 1
    print(f"Generating Issue #{issue}", flush=True)

    # 1 — Fetch
    print("\n[1/4] Fetching news…", flush=True)
    all_articles: List[Dict] = []
    for cfg in RSS_FEEDS:
        all_articles.extend(fetch_rss(cfg))
    all_articles.extend(fetch_hn())
    all_articles.extend(fetch_arxiv())
    print(f"  Total raw: {len(all_articles)}", flush=True)

    # 2 — Dedup + classify
    print("\n[2/4] Deduplicating & classifying…", flush=True)
    articles = dedup(all_articles)
    for a in articles:
        a["category"] = classify(a)
    print(f"  After dedup: {len(articles)}", flush=True)

    # 3 — Sort & bucket
    print("\n[3/4] Scoring & bucketing…", flush=True)
    articles.sort(key=score, reverse=True)
    sections: Dict[str, List[Dict]] = {cat: [] for cat in CATEGORIES}
    for a in articles:
        cat = a.get("category", DEFAULT_CATEGORY)
        if cat in sections and len(sections[cat]) < MAX_PER_CATEGORY:
            sections[cat].append(a)

    # Featured = highest-scored article within 3 days
    featured: Optional[Dict] = None
    now = datetime.now(timezone.utc)
    for a in articles:
        dt = a.get("date")
        if dt and (now - dt).total_seconds() / 3600 < MAX_FEATURED_AGE_H:
            featured = a
            break
    if featured is None and articles:
        featured = articles[0]

    trending = extract_trending(articles)
    total    = sum(len(v) for v in sections.values())
    print(f"  Sections: {', '.join(f'{k}:{len(v)}' for k,v in sections.items() if v)}", flush=True)
    print(f"  Trending: {', '.join(t for t,_ in trending[:5])}", flush=True)

    # 4 — Render
    print("\n[4/4] Rendering HTML…", flush=True)
    generated = datetime.now(timezone.utc)
    html_out  = full_page(featured, sections, issue, generated, trending)
    OUTPUT.write_text(html_out, encoding="utf-8")
    save_issue(issue)

    print(f"\n✅ Written → {OUTPUT}", flush=True)
    print(f"   Issue #{issue} · {total} articles · {generated.strftime('%Y-%m-%dT%H:%M:%SZ')}", flush=True)


if __name__ == "__main__":
    main()
