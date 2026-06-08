#!/usr/bin/env python3
"""AI Pulse Newsletter Generator v3"""

import re
import sys
import json
import time
import hashlib
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from html import escape as h
from typing import List, Dict, Any, Optional, Tuple
import urllib.parse
import urllib.request

try:
    import feedparser
except ImportError:
    print("Error: feedparser not installed. Run: pip install feedparser", file=sys.stderr)
    sys.exit(1)

# ─── Paths ───────────────────────────────────────────────────────────────────

SCRIPT_DIR  = Path(__file__).resolve().parent
ROOT_DIR    = SCRIPT_DIR.parent
DOCS_DIR    = ROOT_DIR / "docs"
ARCHIVE_DIR = DOCS_DIR / "archive"
OUTPUT      = DOCS_DIR / "index.html"
STATE_FILE  = DOCS_DIR / "state.json"

# ─── Sources ─────────────────────────────────────────────────────────────────

RSS_FEEDS = [
    {"url": "https://techcrunch.com/category/artificial-intelligence/feed/",
     "source": "TechCrunch",     "color": "#22c55e"},
    {"url": "https://venturebeat.com/category/ai/feed/",
     "source": "VentureBeat",    "color": "#f97316"},
    {"url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
     "source": "The Verge",      "color": "#e11d48"},
    {"url": "https://www.wired.com/feed/category/artificial-intelligence/latest/rss",
     "source": "Wired",          "color": "#818cf8"},
    {"url": "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss",
     "source": "IEEE Spectrum",  "color": "#0ea5e9"},
    {"url": "https://www.technologyreview.com/feed/",
     "source": "MIT Tech Review","color": "#a78bfa"},
    {"url": "https://openai.com/news/rss.xml",
     "source": "OpenAI",         "color": "#10a37f"},
    {"url": "https://blog.google/technology/ai/rss/",
     "source": "Google AI",      "color": "#4285f4"},
    {"url": "https://huggingface.co/blog/feed.xml",
     "source": "Hugging Face",   "color": "#ff9d00"},
    {"url": "https://thegradient.pub/rss/",
     "source": "The Gradient",   "color": "#e879f9"},
    {"url": "https://news.mit.edu/topic/artificial-intelligence2.rss",
     "source": "MIT News",       "color": "#cc0000"},
    {"url": "https://bair.berkeley.edu/blog/feed.xml",
     "source": "BAIR Blog",      "color": "#003899"},
]

HN_API   = "https://hn.algolia.com/api/v1/search_by_date"
HN_TAGS  = ["artificial intelligence", "AI agent", "large language model", "machine learning", "LLM"]

ARXIV_API   = "https://export.arxiv.org/api/query"
ARXIV_QUERY = "cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.NE+OR+cat:cs.RO"

PWCODE_API = "https://paperswithcode.com/api/v1/papers/?ordering=-published&format=json&page_size=20"

# ─── Categories ──────────────────────────────────────────────────────────────

CATEGORIES: Dict[str, Dict] = {
    "research": {
        "label": "Research & Breakthroughs", "icon": "🔬",
        "color": "#22d3ee", "bg": "rgba(34,211,238,0.07)", "glow": "rgba(34,211,238,0.12)",
        "keywords": [
            "paper", "arxiv", "research", "study", "benchmark", "dataset", "training",
            "pretrain", "fine-tun", "neural", "transformer", "diffusion", "multimodal",
            "evaluation", "algorithm", "architecture", "inference", "reasoning",
            "capability", "scaling", "emergent", "alignment", "rlhf", "reward model",
            "foundation model", "vision language", "parameter", "model",
        ],
    },
    "agents": {
        "label": "AI Agents & Automation", "icon": "🤖",
        "color": "#c084fc", "bg": "rgba(192,132,252,0.07)", "glow": "rgba(192,132,252,0.12)",
        "keywords": [
            "agent", "autonomous", "agentic", "multi-agent", "planning", "memory",
            "tool use", "function call", "workflow", "automation", "copilot",
            "computer use", "browse", "execute", "retrieval", "rag", "orchestrat",
            "self-improv", "task complet", "action", "assistant", "mcp",
            "model context protocol", "robot", "agentic",
        ],
    },
    "products": {
        "label": "New Products & Releases", "icon": "🚀",
        "color": "#60a5fa", "bg": "rgba(96,165,250,0.07)", "glow": "rgba(96,165,250,0.12)",
        "keywords": [
            "launch", "release", "introduc", "announc", "unveil", "gpt",
            "claude", "gemini", "llama", "mistral", "update", "feature", "api",
            "version", "preview", "beta", "availab", "product", "app", "platform",
            "service", "plugin", "integrat", "sora", "grok", "o1", "o3",
        ],
    },
    "industry": {
        "label": "Industry & Business", "icon": "💼",
        "color": "#4ade80", "bg": "rgba(74,222,128,0.07)", "glow": "rgba(74,222,128,0.12)",
        "keywords": [
            "funding", "million", "billion", "acqui", "ceo", "hire", "policy",
            "regulat", "invest", "startup", "openai", "google", "microsoft", "meta",
            "nvidia", "amazon", "apple", "partnership", "deal", "market", "revenue",
            "valuat", "ipo", "lawsuit", "safety", "govern", "anthropic", "deepmind",
            "cohere", "perplexity", "mistral",
        ],
    },
    "open_source": {
        "label": "Open Source & Community", "icon": "🌐",
        "color": "#fb923c", "bg": "rgba(251,146,60,0.07)", "glow": "rgba(251,146,60,0.12)",
        "keywords": [
            "open source", "open-source", "github", "hugging face", "huggingface",
            "llama", "open weight", "open model", "community", "contrib", "fork",
            "mit license", "apache", "open access", "weights", "permissive", "ollama",
            "qwen", "gemma", "phi", "deepseek",
        ],
    },
}

DEFAULT_CATEGORY   = "industry"
MAX_PER_CATEGORY   = 6
MAX_FEATURED_AGE_H = 72

# ─── HTTP ─────────────────────────────────────────────────────────────────────

UA = "AI-Pulse-Newsletter/3.0 (+https://github.com/oeway/ai-news-channel)"

def fetch(url: str, timeout: int = 20) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [!] fetch {url[:70]}: {e}", file=sys.stderr)
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
        hv = delta.seconds // 3600
        return f"{delta.seconds // 60}m ago" if hv == 0 else f"{hv}h ago"
    if delta.days == 1: return "Yesterday"
    if delta.days < 7:  return f"{delta.days}d ago"
    return dt.strftime("%b %d, %Y")

def reading_time(title: str, desc: str) -> str:
    words = len((title + " " + desc).split())
    mins  = max(1, round(words / 220))
    return f"{mins} min read"

# ─── Fetchers ─────────────────────────────────────────────────────────────────

def fetch_rss(cfg: Dict) -> List[Dict]:
    print(f"  RSS  {cfg['source']}…", flush=True)
    raw = fetch(cfg["url"])
    if not raw: return []
    try:
        feed = feedparser.parse(raw)
        arts = []
        for e in feed.entries[:20]:
            desc = ""
            for attr in ("summary", "description", "content"):
                val = getattr(e, attr, None)
                if isinstance(val, list): val = val[0].get("value", "") if val else ""
                if val:
                    desc = re.sub(r"<[^>]+>", " ", val)
                    desc = re.sub(r"\s+", " ", desc).strip()[:400]
                    break
            dt = None
            for attr in ("published_parsed", "updated_parsed", "created_parsed"):
                dt = to_dt(getattr(e, attr, None))
                if dt: break
            title = getattr(e, "title", "").strip()
            url   = getattr(e, "link",  "").strip()
            if not title or not url: continue
            arts.append({"title": title, "url": url, "desc": desc,
                         "source": cfg["source"], "source_color": cfg["color"],
                         "date": dt, "category": None})
        print(f"     → {len(arts)} items", flush=True)
        return arts
    except Exception as ex:
        print(f"  [!] parse {cfg['source']}: {ex}", file=sys.stderr)
        return []

def fetch_hn() -> List[Dict]:
    print("  HN   Algolia…", flush=True)
    seen: set = set()
    arts: List[Dict] = []
    for q in HN_TAGS[:4]:
        url = f"{HN_API}?{urllib.parse.urlencode({'query': q, 'tags': 'story', 'hitsPerPage': 15})}"
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
                arts.append({"title": title, "url": story_url, "desc": desc,
                             "source": "HackerNews", "source_color": "#f97316",
                             "date": to_dt(hit.get("created_at_i")), "category": None})
        except Exception as ex:
            print(f"  [!] HN parse: {ex}", file=sys.stderr)
        time.sleep(0.3)
    print(f"     → {len(arts)} items", flush=True)
    return arts

def fetch_arxiv() -> List[Dict]:
    print("  arXiv…", flush=True)
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
            summ  = (entry.findtext("a:summary", "", ns) or "").replace("\n", " ").strip()[:350]
            link  = (entry.findtext("a:id",      "", ns) or "").strip()
            pub   = entry.findtext("a:published", "", ns)
            cats  = [c.get("term", "") for c in entry.findall("a:category", ns)]
            desc  = f"[{' · '.join(cats[:3])}] {summ}"
            if not title or not link: continue
            arts.append({"title": title, "url": link, "desc": desc,
                         "source": "arXiv", "source_color": "#a78bfa",
                         "date": to_dt(pub), "category": "research"})
        print(f"     → {len(arts)} papers", flush=True)
        return arts
    except Exception as ex:
        print(f"  [!] arXiv parse: {ex}", file=sys.stderr)
        return []

def fetch_pwcode() -> List[Dict]:
    print("  Papers w/ Code…", flush=True)
    raw = fetch(PWCODE_API)
    if not raw: return []
    try:
        arts = []
        for p in (json.loads(raw).get("results") or [])[:20]:
            title   = (p.get("title") or "").strip()
            arxiv_id = p.get("arxiv_id", "")
            url      = (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id
                        else p.get("url_abs") or p.get("url_pdf") or "")
            if not title or not url: continue
            stars = p.get("total_stars") or 0
            desc  = f"⭐ {stars} GitHub stars" if stars else ""
            arts.append({"title": title, "url": url, "desc": desc,
                         "source": "Papers w/ Code", "source_color": "#21cbce",
                         "date": to_dt(p.get("published")), "category": "research"})
        print(f"     → {len(arts)} papers", flush=True)
        return arts
    except Exception as ex:
        print(f"  [!] PWCode parse: {ex}", file=sys.stderr)
        return []

# ─── Classify / score / dedup ─────────────────────────────────────────────────

def classify(a: Dict) -> str:
    if a.get("category"): return a["category"]
    text   = (a.get("title", "") + " " + a.get("desc", "")).lower()
    scores = {cat: sum(1 for kw in cfg["keywords"] if kw in text)
              for cat, cfg in CATEGORIES.items()}
    best   = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else DEFAULT_CATEGORY

SOURCE_BONUS = {
    "arXiv": 2.5, "Papers w/ Code": 2.3, "IEEE Spectrum": 2.0,
    "MIT Tech Review": 1.8, "MIT News": 1.7, "BAIR Blog": 1.6,
    "OpenAI": 1.8, "Google AI": 1.8, "Hugging Face": 1.6,
    "TechCrunch": 1.5, "The Gradient": 1.5, "VentureBeat": 1.3,
    "Wired": 1.3, "The Verge": 1.2, "HackerNews": 0.8,
}

def score(a: Dict) -> float:
    s = 0.0
    dt = a.get("date")
    if dt:
        age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        s  += max(0, 10 - age * 0.08)
    s += SOURCE_BONUS.get(a.get("source", ""), 1.0)
    if 40 < len(a.get("title", "")) < 130: s += 0.4
    return s

def dedup(articles: List[Dict]) -> List[Dict]:
    seen_urls: set = set()
    seen_keys: set = set()
    out: List[Dict] = []
    for a in articles:
        url  = re.sub(r"\?.*$", "", a.get("url", "")).rstrip("/")
        tkey = hashlib.md5(a.get("title", "").lower()[:60].encode()).hexdigest()
        if url in seen_urls or tkey in seen_keys: continue
        if url: seen_urls.add(url)
        seen_keys.add(tkey)
        out.append(a)
    return out

# ─── Trending topics ──────────────────────────────────────────────────────────

STOP = {
    "the","a","an","is","in","on","at","to","of","and","for","with","by","as",
    "this","that","from","are","it","its","new","how","what","why","when","will",
    "can","has","have","more","than","into","use","using","used","says","say",
    "not","but","also","their","about","which","who","you","your","our",
}

def trending_topics(articles: List[Dict]) -> List[Tuple[str, int]]:
    words: Counter = Counter()
    for a in articles[:80]:
        for tok in re.findall(r"\b[a-z][a-z\-]{2,}\b", a.get("title", "").lower()):
            if tok not in STOP:
                words[tok] += 1
    return words.most_common(14)

# ─── State ────────────────────────────────────────────────────────────────────

def load_state() -> Dict:
    if STATE_FILE.exists():
        try: return json.loads(STATE_FILE.read_text())
        except: pass
    return {"issue": 0, "archives": []}

def save_state(state: Dict) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))

# ─── HTML helpers ─────────────────────────────────────────────────────────────

SOURCE_COLORS: Dict[str, str] = {
    "TechCrunch": "#22c55e", "VentureBeat": "#f97316", "The Verge": "#e11d48",
    "Wired": "#818cf8", "IEEE Spectrum": "#0ea5e9", "MIT Tech Review": "#a78bfa",
    "MIT News": "#cc0000", "arXiv": "#a78bfa", "Papers w/ Code": "#21cbce",
    "HackerNews": "#f97316", "OpenAI": "#10a37f", "Google AI": "#4285f4",
    "Hugging Face": "#ff9d00", "The Gradient": "#e879f9", "BAIR Blog": "#2563eb",
}

def pill(source: str, color: str = "") -> str:
    c = color or SOURCE_COLORS.get(source, "#6b7280")
    return (f'<span class="pill" style="background:{c}22;color:{c};border-color:{c}44">'
            f'{h(source)}</span>')

def card_html(a: Dict, cat_color: str) -> str:
    title = h(a.get("title", "Untitled"))
    url   = h(a.get("url", "#"))
    desc  = h(a.get("desc", "")[:240])
    src   = a.get("source", "")
    src_c = a.get("source_color", "") or SOURCE_COLORS.get(src, "#6b7280")
    rt    = reading_time(a.get("title", ""), a.get("desc", ""))
    return f'''
    <article class="card" style="--cat:{cat_color}">
      <div class="card-top">
        {pill(src, src_c)}
        <span class="card-age">{h(age_str(a.get("date")))}</span>
      </div>
      <h3 class="card-title"><a href="{url}" target="_blank" rel="noopener">{title}</a></h3>
      <p class="card-desc">{desc}</p>
      <div class="card-footer">
        <span class="read-time">⏱ {h(rt)}</span>
        <a class="card-link" href="{url}" target="_blank" rel="noopener">Read more ↗</a>
      </div>
    </article>'''

def section_html(cat: str, articles: List[Dict]) -> str:
    if not articles: return ""
    cfg   = CATEGORIES[cat]
    cards = "\n".join(card_html(a, cfg["color"]) for a in articles[:MAX_PER_CATEGORY])
    count = min(len(articles), MAX_PER_CATEGORY)
    return f'''
  <section class="cat-section" id="{cat}"
           style="--cat:{cfg["color"]};--cat-bg:{cfg["bg"]};--cat-glow:{cfg["glow"]}">
    <header class="section-hdr">
      <span class="section-icon">{cfg["icon"]}</span>
      <h2 class="section-title">{h(cfg["label"])}</h2>
      <span class="section-count">{count} stories</span>
    </header>
    <div class="card-grid">{cards}
    </div>
  </section>'''

def featured_html(a: Dict) -> str:
    title = h(a.get("title", "Untitled"))
    url   = h(a.get("url", "#"))
    desc  = h(a.get("desc", "")[:500])
    src   = a.get("source", "")
    src_c = a.get("source_color", "") or SOURCE_COLORS.get(src, "#6b7280")
    cat   = a.get("category", DEFAULT_CATEGORY)
    cat_c = CATEGORIES.get(cat, {}).get("color", "#8b5cf6")
    cat_l = CATEGORIES.get(cat, {}).get("label", "News")
    cat_i = CATEGORIES.get(cat, {}).get("icon", "📌")
    rt    = reading_time(a.get("title", ""), a.get("desc", ""))
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
        <span class="featured-age">{h(age_str(a.get("date")))}</span>
        <span class="featured-rt">⏱ {h(rt)}</span>
      </div>
      <p class="featured-body">{desc}</p>
      <a class="featured-btn" href="{url}" target="_blank" rel="noopener">Read Full Story ↗</a>
    </div>
  </section>'''

def trending_html(topics: List[Tuple[str, int]]) -> str:
    if not topics: return ""
    tags = "".join(
        f'<span class="trend-tag">{h(w)} <span class="trend-count">{n}</span></span>'
        for w, n in topics[:12]
    )
    return f'''
  <div class="trending-bar">
    <span class="trending-label">🔥 Trending</span>
    <div class="trend-tags">{tags}</div>
  </div>'''

def archive_section_html(archives: List[Dict]) -> str:
    if len(archives) < 2: return ""
    recent = archives[-8:][::-1]
    items = "".join(
        f'<a class="archive-item" href="archive/{a["file"]}">'
        f'<span class="archive-issue">#{a["issue"]}</span>'
        f'<span class="archive-date">{a["date"]}</span>'
        f'<span class="archive-count">{a.get("total", 0)} articles</span>'
        f'</a>'
        for a in recent
    )
    return f'''
  <section class="archive-section">
    <header class="section-hdr" style="--cat:#64748b">
      <span class="section-icon">📚</span>
      <h2 class="section-title" style="color:#94a3b8">Past Issues</h2>
      <a class="section-count" href="archive/" style="color:#a78bfa">View all →</a>
    </header>
    <div class="archive-grid">{items}</div>
  </section>'''

# ─── CSS ──────────────────────────────────────────────────────────────────────

PAGE_CSS = """\
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#07071a;--surface:#0d0d24;--card:#111128;--card-h:#16163a;
  --border:rgba(255,255,255,0.06);--border-h:rgba(255,255,255,0.12);
  --text:#e8eaf6;--sub:#94a3b8;--muted:#64748b;--dim:#334155;
  font-size:15px;
}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--text);font-family:'Inter',system-ui,-apple-system,sans-serif;line-height:1.6;min-height:100vh}
a{color:inherit;text-decoration:none}
body::before{content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background:
    radial-gradient(ellipse 65% 45% at 15% 5%,rgba(99,102,241,.09) 0%,transparent 65%),
    radial-gradient(ellipse 55% 40% at 85% 90%,rgba(6,182,212,.07) 0%,transparent 65%),
    radial-gradient(ellipse 40% 35% at 50% 50%,rgba(139,92,246,.04) 0%,transparent 60%);}
body::after{content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background-image:radial-gradient(rgba(255,255,255,.018) 1px,transparent 1px);
  background-size:28px 28px;}
.page{position:relative;z-index:1}

#progress-bar{position:fixed;top:0;left:0;z-index:999;height:2px;width:0%;
  background:linear-gradient(90deg,#6d28d9,#38bdf8,#22d3ee);transition:width .1s linear;}

.site-header{border-bottom:1px solid var(--border);
  background:linear-gradient(180deg,rgba(13,13,36,.98) 0%,rgba(7,7,26,.9) 100%);
  backdrop-filter:blur(14px);position:sticky;top:0;z-index:100;}
.header-inner{max-width:1180px;margin:0 auto;padding:.85rem 1.5rem;
  display:flex;align-items:center;justify-content:space-between;gap:1rem;}
.brand{display:flex;align-items:center;gap:.7rem}
.brand-logo{font-size:1.65rem;line-height:1}
.brand-name{font-family:'Space Grotesk',sans-serif;font-size:1.3rem;font-weight:700;
  background:linear-gradient(130deg,#a78bfa 0%,#38bdf8 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.brand-sub{font-size:.7rem;color:var(--muted);margin-top:1px}
.header-right{display:flex;align-items:center;gap:.65rem;flex-shrink:0}
.issue-badge{font-size:.7rem;font-weight:700;letter-spacing:.07em;
  background:linear-gradient(135deg,rgba(167,139,250,.15),rgba(56,189,248,.12));
  border:1px solid rgba(167,139,250,.28);color:#a78bfa;padding:.22rem .65rem;border-radius:20px;}
.header-date{font-size:.78rem;color:var(--muted)}
.live-dot{display:inline-block;width:7px;height:7px;border-radius:50%;
  background:#22c55e;margin-right:.35rem;animation:pulse-dot 2.5s ease-in-out infinite;}
@keyframes pulse-dot{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(34,197,94,.4)}50%{opacity:.7;box-shadow:0 0 0 5px rgba(34,197,94,0)}}

.cat-nav{max-width:1180px;margin:0 auto;padding:.8rem 1.5rem;
  display:flex;gap:.45rem;flex-wrap:wrap;border-bottom:1px solid var(--border);}
.nav-pill{font-size:.76rem;font-weight:500;padding:.28rem .72rem;border-radius:20px;
  border:1px solid color-mix(in srgb,var(--cat) 30%,transparent);
  color:var(--cat);transition:background .15s,transform .15s;white-space:nowrap;}
.nav-pill:hover{background:color-mix(in srgb,var(--cat) 12%,transparent);transform:translateY(-1px)}

main{max-width:1180px;margin:0 auto;padding:2rem 1.5rem}

.featured-wrap{margin-bottom:2.5rem}
.featured-card{
  background:linear-gradient(135deg,#14103a 0%,#0e0e28 60%,#0a1428 100%);
  border:1px solid rgba(167,139,250,.22);border-radius:18px;padding:2.25rem 2.75rem;
  position:relative;overflow:hidden;}
.featured-card::before{content:'';position:absolute;top:-100px;right:-100px;
  width:420px;height:420px;border-radius:50%;pointer-events:none;
  background:radial-gradient(circle,rgba(99,102,241,.13) 0%,transparent 65%);}
.featured-card::after{content:'';position:absolute;bottom:-60px;left:20%;
  width:250px;height:250px;border-radius:50%;pointer-events:none;
  background:radial-gradient(circle,rgba(6,182,212,.07) 0%,transparent 65%);}
.featured-eyebrow{display:flex;align-items:center;gap:1rem;margin-bottom:1rem}
.featured-badge{font-size:.7rem;font-weight:700;letter-spacing:.1em;color:#a78bfa;text-transform:uppercase}
.featured-cat{font-size:.76rem;font-weight:500}
.featured-title{font-family:'Space Grotesk',sans-serif;
  font-size:clamp(1.35rem,3vw,1.95rem);font-weight:700;line-height:1.28;margin-bottom:1rem;}
.featured-meta{display:flex;align-items:center;gap:.75rem;margin-bottom:1rem;flex-wrap:wrap}
.featured-age,.featured-rt{font-size:.78rem;color:var(--muted)}
.featured-body{color:var(--sub);line-height:1.75;margin-bottom:1.6rem;max-width:700px;position:relative;z-index:1}
.featured-btn{display:inline-flex;align-items:center;gap:.4rem;
  background:linear-gradient(135deg,#6d28d9,#4f46e5);color:#fff;
  padding:.6rem 1.35rem;border-radius:9px;font-size:.87rem;font-weight:600;
  box-shadow:0 4px 18px rgba(99,102,241,.38);
  transition:opacity .2s,transform .15s;position:relative;z-index:1;}
.featured-btn:hover{opacity:.86;transform:translateY(-1px)}

.trending-bar{display:flex;align-items:center;gap:1rem;flex-wrap:wrap;
  background:var(--card);border:1px solid var(--border);border-radius:14px;
  padding:.85rem 1.25rem;margin-bottom:2.5rem;}
.trending-label{font-size:.78rem;font-weight:700;color:#f97316;flex-shrink:0}
.trend-tags{display:flex;gap:.4rem;flex-wrap:wrap}
.trend-tag{font-size:.72rem;font-weight:500;padding:.2rem .6rem;border-radius:20px;
  background:rgba(255,255,255,.04);border:1px solid var(--border);color:var(--sub);}
.trend-count{color:var(--dim);margin-left:.1rem}

.cat-section{margin-bottom:3rem}
.section-hdr{display:flex;align-items:center;gap:.6rem;
  margin-bottom:1.25rem;padding-bottom:.75rem;border-bottom:1px solid var(--border);}
.section-icon{font-size:1.2rem}
.section-title{font-family:'Space Grotesk',sans-serif;font-size:1.05rem;font-weight:600;color:var(--cat)}
.section-count{margin-left:auto;font-size:.7rem;color:var(--muted);
  background:var(--card);border:1px solid var(--border);padding:.13rem .52rem;border-radius:12px;}

.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:1rem;}
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;
  padding:1.1rem 1.25rem;display:flex;flex-direction:column;gap:.55rem;
  transition:border-color .2s,background .2s,transform .2s,box-shadow .2s;
  position:relative;overflow:hidden;}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:var(--cat,#8b5cf6);opacity:0;transition:opacity .2s;}
.card:hover{border-color:color-mix(in srgb,var(--cat) 40%,transparent);
  background:var(--card-h);transform:translateY(-3px);
  box-shadow:0 10px 30px rgba(0,0,0,.4),0 0 0 1px color-mix(in srgb,var(--cat) 15%,transparent);}
.card:hover::before{opacity:1}
.card-top{display:flex;align-items:center;justify-content:space-between}
.card-age{font-size:.7rem;color:var(--muted)}
.card-title{font-size:.92rem;font-weight:600;line-height:1.45}
.card-title a{color:var(--text);transition:color .15s}
.card-title a:hover{color:var(--cat,#a78bfa)}
.card-desc{font-size:.8rem;color:var(--muted);line-height:1.55;flex-grow:1;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;}
.card-footer{display:flex;align-items:center;justify-content:space-between;margin-top:auto}
.read-time{font-size:.7rem;color:var(--dim)}
.card-link{font-size:.77rem;font-weight:500;
  color:color-mix(in srgb,var(--cat) 85%,#fff);transition:opacity .15s;}
.card-link:hover{opacity:.7}

.pill{display:inline-block;font-size:.66rem;font-weight:700;letter-spacing:.04em;
  padding:.14rem .5rem;border-radius:5px;border:1px solid;text-transform:uppercase;}

.stats-bar{max-width:1180px;margin:0 auto;padding:.7rem 1.5rem;
  display:flex;align-items:center;gap:1.5rem;flex-wrap:wrap;
  border-top:1px solid var(--border);font-size:.77rem;color:var(--muted);}
.stat-item{display:flex;align-items:center;gap:.4rem;transition:color .15s}
.stat-item:hover{color:var(--text)}
.stat-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}

.archive-section{margin-bottom:3rem}
.archive-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:.65rem;}
.archive-item{background:var(--card);border:1px solid var(--border);border-radius:10px;
  padding:.75rem 1rem;display:flex;flex-direction:column;gap:.25rem;
  transition:border-color .15s,background .15s;}
.archive-item:hover{background:var(--card-h);border-color:rgba(167,139,250,.3)}
.archive-issue{font-size:.7rem;font-weight:700;color:#a78bfa}
.archive-date{font-size:.82rem;font-weight:500;color:var(--text)}
.archive-count{font-size:.72rem;color:var(--muted)}

.site-footer{background:var(--surface);border-top:1px solid var(--border);padding:2rem 1.5rem;margin-top:3rem;}
.footer-inner{max-width:1180px;margin:0 auto;display:flex;flex-direction:column;
  align-items:center;gap:1rem;text-align:center;}
.footer-brand{font-family:'Space Grotesk',sans-serif;font-size:1.1rem;font-weight:700;
  background:linear-gradient(135deg,#a78bfa,#38bdf8);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.footer-links{display:flex;gap:1.25rem;flex-wrap:wrap;justify-content:center}
.footer-links a{font-size:.82rem;color:var(--muted);transition:color .15s}
.footer-links a:hover{color:var(--text)}
.footer-sources{font-size:.75rem;color:var(--dim);display:flex;gap:.5rem;flex-wrap:wrap;justify-content:center}
.footer-sources span::after{content:'·';margin-left:.5rem}
.footer-sources span:last-child::after{content:''}
.footer-note{font-size:.74rem;color:var(--dim)}

.empty-state{text-align:center;padding:4rem 1rem;color:var(--muted)}
.empty-icon{font-size:3rem;margin-bottom:1rem}

.scroll-top{position:fixed;bottom:1.5rem;right:1.5rem;z-index:200;
  background:rgba(13,13,36,.9);border:1px solid rgba(167,139,250,.3);
  color:#a78bfa;width:38px;height:38px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;font-size:1.1rem;
  backdrop-filter:blur(8px);transition:background .2s,transform .2s;
  box-shadow:0 4px 14px rgba(0,0,0,.3);}
.scroll-top:hover{background:rgba(99,102,241,.25);transform:translateY(-2px)}

@media(max-width:768px){
  .header-inner{flex-wrap:wrap}
  .featured-card{padding:1.5rem 1.75rem}
  main{padding:1.25rem 1rem}
  .cat-nav{padding:.7rem 1rem}
}
@media(max-width:500px){
  .card-grid{grid-template-columns:1fr}
  .header-date{display:none}
}
"""

PAGE_JS = """\
const bar=document.getElementById('progress-bar');
window.addEventListener('scroll',()=>{
  const t=document.body.scrollHeight-window.innerHeight;
  bar.style.width=(t>0?window.scrollY/t*100:0)+'%';
},{passive:true});
"""

# ─── Archive page ─────────────────────────────────────────────────────────────

ARCHIVE_CSS = """\
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#07071a;--surface:#0d0d24;--card:#111128;--card-h:#16163a;
  --border:rgba(255,255,255,0.06);--text:#e8eaf6;--muted:#64748b;--dim:#334155;}
body{background:var(--bg);color:var(--text);font-family:'Inter',system-ui,sans-serif;min-height:100vh}
a{color:inherit;text-decoration:none}
body::before{content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background:radial-gradient(ellipse 65% 45% at 15% 5%,rgba(99,102,241,.09) 0%,transparent 65%);}
.page{position:relative;z-index:1;max-width:960px;margin:0 auto;padding:3rem 1.5rem}
.back{font-size:.82rem;color:#a78bfa;display:inline-flex;align-items:center;gap:.4rem;margin-bottom:2rem}
.back:hover{opacity:.8}
h1{font-family:'Space Grotesk',sans-serif;font-size:1.75rem;font-weight:700;
  background:linear-gradient(130deg,#a78bfa,#38bdf8);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:.5rem;}
.sub{color:var(--muted);margin-bottom:2.5rem;font-size:.9rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:.8rem}
.item{background:var(--card);border:1px solid var(--border);border-radius:12px;
  padding:1.1rem 1.25rem;display:flex;flex-direction:column;gap:.3rem;
  transition:border-color .15s,background .15s;}
.item:hover{background:var(--card-h);border-color:rgba(167,139,250,.3)}
.item-issue{font-size:.7rem;font-weight:700;color:#a78bfa}
.item-date{font-size:.9rem;font-weight:600;color:var(--text)}
.item-count{font-size:.76rem;color:var(--muted)}
"""

def write_archive_index(archives: List[Dict]) -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    items = "".join(
        f'<a class="item" href="{a["file"]}">'
        f'<span class="item-issue">Issue #{a["issue"]}</span>'
        f'<span class="item-date">{a["date"]}</span>'
        f'<span class="item-count">{a.get("total", 0)} articles</span>'
        f'</a>'
        for a in reversed(archives)
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>AI Pulse — Archive</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
  <style>{ARCHIVE_CSS}</style>
</head>
<body><div class="page">
  <a class="back" href="../">← Back to latest</a>
  <h1>📚 Newsletter Archive</h1>
  <p class="sub">{len(archives)} issue{"s" if len(archives) != 1 else ""} published</p>
  <div class="grid">{items}</div>
</div></body></html>"""
    (ARCHIVE_DIR / "index.html").write_text(html, encoding="utf-8")

# ─── Full page ────────────────────────────────────────────────────────────────

def full_page(
    featured:  Optional[Dict],
    sections:  Dict[str, List[Dict]],
    issue:     int,
    generated: datetime,
    trending:  List[Tuple[str, int]],
    archives:  List[Dict],
) -> str:
    now_str  = generated.strftime("%B %d, %Y")
    gen_iso  = generated.strftime("%Y-%m-%dT%H:%M:%SZ")
    total    = sum(len(v) for v in sections.values())
    src_set  = sorted({a["source"] for v in sections.values() for a in v})
    cat_order   = list(CATEGORIES.keys())
    active_cats = [c for c in cat_order if sections.get(c)]

    feat_block  = featured_html(featured) if featured else ""
    trend_block = trending_html(trending)
    arch_block  = archive_section_html(archives)
    secs_block  = "".join(section_html(c, sections[c]) for c in active_cats)
    nav_block   = "".join(
        f'<a class="nav-pill" href="#{c}" style="--cat:{CATEGORIES[c]["color"]}">'
        f'{CATEGORIES[c]["icon"]}&thinsp;{h(CATEGORIES[c]["label"])}</a>'
        for c in active_cats
    )
    stats_items = "".join(
        f'<a class="stat-item" href="#{c}">'
        f'<span class="stat-dot" style="background:{CATEGORIES[c]["color"]}"></span>'
        f'{CATEGORIES[c]["icon"]} {len(sections.get(c,[]))} {h(CATEGORIES[c]["label"])}</a>'
        for c in active_cats if sections.get(c)
    )
    stats_block    = f'<div class="stats-bar">{stats_items}</div>' if stats_items else ""
    sources_pills  = "".join(f'<span>{h(s)}</span>' for s in src_set[:14])

    if not feat_block and not secs_block:
        secs_block = '<div class="empty-state"><div class="empty-icon">🤖</div><p>Newsletter will populate on next scheduled run.</p></div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Pulse — Daily AI News · Issue #{issue}</title>
  <meta name="description" content="Daily curated AI news: research, agents, products, industry — Issue #{issue}, {now_str}">
  <meta property="og:title" content="AI Pulse — Issue #{issue} · {now_str}">
  <meta property="og:description" content="Daily curated AI news digest covering research breakthroughs, AI agents, new products, and industry.">
  <meta property="og:type" content="website">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
  <style>{PAGE_CSS}</style>
</head>
<body>
<div id="progress-bar"></div>
<div class="page">
  <header class="site-header">
    <div class="header-inner">
      <a class="brand" href="#">
        <span class="brand-logo">⚡</span>
        <div><div class="brand-name">AI Pulse</div><div class="brand-sub">Daily AI News Digest</div></div>
      </a>
      <div class="header-right">
        <span class="issue-badge">Issue #{issue}</span>
        <span class="header-date"><span class="live-dot"></span>{now_str}</span>
      </div>
    </div>
    <nav class="cat-nav">{nav_block}</nav>
  </header>

  <main>
    {feat_block}
    {trend_block}
    {secs_block}
    {arch_block}
  </main>

  {stats_block}

  <footer class="site-footer">
    <div class="footer-inner">
      <div class="footer-brand">⚡ AI Pulse</div>
      <div class="footer-links">
        <a href="https://github.com/oeway/ai-news-channel" target="_blank" rel="noopener">GitHub</a>
        <a href="archive/">Archive</a>
        <a href="https://arxiv.org/list/cs.AI/recent" target="_blank" rel="noopener">arXiv CS.AI</a>
        <a href="https://news.ycombinator.com" target="_blank" rel="noopener">HackerNews</a>
      </div>
      <div class="footer-sources">{sources_pills}</div>
      <div class="footer-note">
        Auto-generated · {len(src_set)} sources · {total} articles · {now_str}
        &nbsp;·&nbsp;<time datetime="{gen_iso}">{gen_iso}</time>
      </div>
    </div>
  </footer>
</div>
<a class="scroll-top" href="#" aria-label="Back to top">↑</a>
<script>{PAGE_JS}</script>
</body>
</html>"""

# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("⚡ AI Pulse Newsletter Generator v3", flush=True)
    print("─" * 50, flush=True)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    state = load_state()
    issue = state.get("issue", 0) + 1
    print(f"Generating Issue #{issue}", flush=True)

    print("\n[1/5] Fetching news…", flush=True)
    all_articles: List[Dict] = []
    for cfg in RSS_FEEDS:
        all_articles.extend(fetch_rss(cfg))
        time.sleep(0.2)
    all_articles.extend(fetch_hn())
    all_articles.extend(fetch_arxiv())
    all_articles.extend(fetch_pwcode())
    print(f"  Total raw: {len(all_articles)}", flush=True)

    print("\n[2/5] Deduplicating & classifying…", flush=True)
    articles = dedup(all_articles)
    for a in articles:
        a["category"] = classify(a)
    print(f"  After dedup: {len(articles)}", flush=True)

    print("\n[3/5] Scoring & sorting…", flush=True)
    articles.sort(key=score, reverse=True)
    sections: Dict[str, List[Dict]] = {cat: [] for cat in CATEGORIES}
    for a in articles:
        cat = a.get("category", DEFAULT_CATEGORY)
        if cat in sections and len(sections[cat]) < MAX_PER_CATEGORY:
            sections[cat].append(a)

    featured: Optional[Dict] = None
    now = datetime.now(timezone.utc)
    for a in articles:
        dt = a.get("date")
        if dt and (now - dt).total_seconds() / 3600 < MAX_FEATURED_AGE_H:
            featured = a
            break
    if featured is None and articles:
        featured = articles[0]

    total = sum(len(v) for v in sections.values())
    print(f"  Sections: {', '.join(f'{k}:{len(v)}' for k, v in sections.items() if v)}", flush=True)

    print("\n[4/5] Trending topics…", flush=True)
    trending = trending_topics(articles)
    print(f"  Top: {', '.join(w for w, _ in trending[:8])}", flush=True)

    print("\n[5/5] Rendering HTML…", flush=True)
    generated = datetime.now(timezone.utc)
    archives  = state.get("archives", [])

    html_out = full_page(featured, sections, issue, generated, trending, archives)
    OUTPUT.write_text(html_out, encoding="utf-8")

    date_str  = generated.strftime("%Y-%m-%d")
    arch_file = f"{date_str}-issue-{issue}.html"
    (ARCHIVE_DIR / arch_file).write_text(html_out, encoding="utf-8")

    archives.append({
        "issue": issue,
        "date":  generated.strftime("%B %d, %Y"),
        "file":  arch_file,
        "total": total,
    })
    state["issue"]    = issue
    state["archives"] = archives
    save_state(state)
    write_archive_index(archives)

    print(f"\n✅  docs/index.html — Issue #{issue} · {total} articles", flush=True)
    print(f"    Archive: docs/archive/{arch_file}", flush=True)


if __name__ == "__main__":
    main()
