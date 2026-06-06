#!/usr/bin/env python3
"""
AI Pulse Newsletter Generator
Fetches latest AI news from multiple sources and generates a beautiful static HTML newsletter.
"""

import os
import re
import sys
import json
import time
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from html import escape as h
from typing import List, Dict, Any, Optional
import urllib.parse
import urllib.request
import urllib.error

try:
    import feedparser
except ImportError:
    print("Error: feedparser not installed. Run: pip install feedparser", file=sys.stderr)
    sys.exit(1)

# ─── Paths ───────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR   = SCRIPT_DIR.parent
DOCS_DIR   = ROOT_DIR / "docs"
OUTPUT     = DOCS_DIR / "index.html"
STATE_FILE = DOCS_DIR / "state.json"

# ─── Sources ─────────────────────────────────────────────────────────────────

RSS_FEEDS = [
    # Mainstream tech press
    {"url": "https://techcrunch.com/category/artificial-intelligence/feed/",
     "source": "TechCrunch",      "color": "#22c55e"},
    {"url": "https://venturebeat.com/category/ai/feed/",
     "source": "VentureBeat",     "color": "#f97316"},
    {"url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
     "source": "The Verge",       "color": "#e11d48"},
    {"url": "https://www.wired.com/feed/category/artificial-intelligence/latest/rss",
     "source": "Wired",           "color": "#818cf8"},
    # Science & Engineering
    {"url": "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss",
     "source": "IEEE Spectrum",   "color": "#0ea5e9"},
    {"url": "https://www.technologyreview.com/feed/",
     "source": "MIT Tech Review", "color": "#a78bfa"},
    # AI Lab blogs
    {"url": "https://openai.com/news/rss/",
     "source": "OpenAI Blog",     "color": "#10b981"},
    {"url": "https://www.anthropic.com/rss.xml",
     "source": "Anthropic",       "color": "#f59e0b"},
    {"url": "https://blog.google/technology/ai/rss/",
     "source": "Google AI",       "color": "#4285f4"},
    {"url": "https://deepmind.google/blog/rss.xml",
     "source": "DeepMind",        "color": "#06b6d4"},
    {"url": "https://huggingface.co/blog/feed.xml",
     "source": "Hugging Face",    "color": "#fbbf24"},
    {"url": "https://ai.meta.com/blog/rss/",
     "source": "Meta AI",         "color": "#3b82f6"},
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
        "bg":    "rgba(34,211,238,0.07)",
        "glow":  "rgba(34,211,238,0.18)",
        "keywords": [
            "paper", "arxiv", "research", "study", "benchmark", "dataset", "training",
            "pretrain", "fine-tun", "neural", "transformer", "diffusion", "multimodal",
            "evaluation", "algorithm", "architecture", "inference", "reasoning",
            "capability", "scaling", "emergent", "alignment", "rlhf", "reward model",
            "o1", "o3", "chain-of-thought", "test-time", "compute", "frontier",
        ]
    },
    "agents": {
        "label": "AI Agents & Automation",
        "icon":  "🤖",
        "color": "#c084fc",
        "bg":    "rgba(192,132,252,0.07)",
        "glow":  "rgba(192,132,252,0.18)",
        "keywords": [
            "agent", "autonomous", "agentic", "multi-agent", "planning", "memory",
            "tool use", "function call", "workflow", "automation", "copilot",
            "computer use", "browse", "execute", "retrieval", "rag", "orchestrat",
            "self-improv", "task complet", "action", "mcp", "model context protocol",
        ]
    },
    "products": {
        "label": "New Products & Releases",
        "icon":  "🚀",
        "color": "#60a5fa",
        "bg":    "rgba(96,165,250,0.07)",
        "glow":  "rgba(96,165,250,0.18)",
        "keywords": [
            "launch", "release", "introduc", "announc", "unveil", "gpt", "claude",
            "gemini", "llama", "mistral", "update", "feature", "api", "version",
            "preview", "beta", "availab", "product", "app", "platform", "service",
            "plugin", "integrat", "new model", "now available",
        ]
    },
    "industry": {
        "label": "Industry & Business",
        "icon":  "💼",
        "color": "#4ade80",
        "bg":    "rgba(74,222,128,0.07)",
        "glow":  "rgba(74,222,128,0.18)",
        "keywords": [
            "funding", "million", "billion", "acqui", "ceo", "hire", "policy",
            "regulat", "invest", "startup", "openai", "google", "microsoft", "meta",
            "nvidia", "amazon", "apple", "partnership", "deal", "market", "revenue",
            "valuat", "ipo", "lawsuit", "safety", "govern", "raised", "series",
        ]
    },
    "open_source": {
        "label": "Open Source & Community",
        "icon":  "🌐",
        "color": "#fb923c",
        "bg":    "rgba(251,146,60,0.07)",
        "glow":  "rgba(251,146,60,0.18)",
        "keywords": [
            "open source", "open-source", "github", "hugging face", "huggingface",
            "llama", "open weight", "open model", "community", "contrib", "fork",
            "mit license", "apache", "open access", "weights", "permissive", "ollama",
            "gguf", "quantiz", "mistral", "qwen", "deepseek",
        ]
    }
}

DEFAULT_CATEGORY    = "industry"
MAX_PER_CATEGORY    = 8
MAX_FEATURED_AGE_H  = 72

# ─── HTTP ────────────────────────────────────────────────────────────────────

UA = "AI-Pulse-Newsletter/3.0 (+https://github.com/oeway/ai-news-channel)"

def fetch(url: str, timeout: int = 20) -> Optional[str]:
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": UA, "Accept": "*/*",
                          "Accept-Language": "en-US,en;q=0.9"})
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
                    "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT",
                    "%Y-%m-%d"):
            try:
                dt = datetime.strptime(v.strip(), fmt)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None

def age_str(dt: Optional[datetime]) -> str:
    if dt is None:
        return "Recently"
    delta = datetime.now(timezone.utc) - dt
    if delta.days == 0:
        h_val = delta.seconds // 3600
        return f"{delta.seconds // 60}m ago" if h_val == 0 else f"{h_val}h ago"
    if delta.days == 1: return "Yesterday"
    if delta.days < 7:  return f"{delta.days}d ago"
    return dt.strftime("%b %d, %Y")

# ─── Fetchers ─────────────────────────────────────────────────────────────────

def fetch_rss(cfg: Dict) -> List[Dict]:
    print(f"  RSS  {cfg['source']}…", flush=True)
    raw = fetch(cfg["url"])
    if not raw: return []
    try:
        feed = feedparser.parse(raw)
        articles = []
        for e in feed.entries[:25]:
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
    for q in HN_TAGS:
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
                dt    = to_dt(hit.get("created_at_i"))
                articles.append({"title": title, "url": story_url, "desc": desc,
                                  "source": "HackerNews", "source_color": "#f97316",
                                  "date": dt, "category": None})
        except Exception as ex:
            print(f"  [!] HN parse: {ex}", file=sys.stderr)
        time.sleep(0.3)
    print(f"     → {len(articles)} items", flush=True)
    return articles


def fetch_arxiv() -> List[Dict]:
    print("  arXiv papers…", flush=True)
    url = (f"{ARXIV_API}?search_query={ARXIV_QUERY}"
           "&start=0&max_results=30&sortBy=submittedDate&sortOrder=descending")
    raw = fetch(url)
    if not raw: return []
    try:
        ns   = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(raw)
        arts = []
        for entry in root.findall("a:entry", ns):
            title  = (entry.findtext("a:title",   "", ns) or "").replace("\n", " ").strip()
            summ   = (entry.findtext("a:summary", "", ns) or "").replace("\n", " ").strip()[:400]
            link   = (entry.findtext("a:id",      "", ns) or "").strip()
            pub    = entry.findtext("a:published", "", ns)
            cats   = [c.get("term","") for c in entry.findall("a:category", ns)]
            cat_s  = " · ".join(cats[:3])
            # get author names
            authors = [a.findtext("a:name", "", ns)
                       for a in entry.findall("a:author", ns)][:3]
            author_s = ", ".join(authors)
            desc   = f"[{cat_s}] {author_s and author_s + ' — '}{summ}"
            if not title or not link: continue
            arts.append({"title": title, "url": link, "desc": desc,
                         "source": "arXiv", "source_color": "#a78bfa",
                         "date": to_dt(pub), "category": "research"})
        print(f"     → {len(arts)} papers", flush=True)
        return arts
    except Exception as ex:
        print(f"  [!] arXiv parse: {ex}", file=sys.stderr)
        return []

# ─── Classify ─────────────────────────────────────────────────────────────────

def classify(a: Dict) -> str:
    if a.get("category"):
        return a["category"]
    text   = (a.get("title","") + " " + a.get("desc","")).lower()
    scores = {}
    for cat, cfg in CATEGORIES.items():
        scores[cat] = sum(1 for kw in cfg["keywords"] if kw in text)
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else DEFAULT_CATEGORY

# ─── Score ────────────────────────────────────────────────────────────────────

SOURCE_AUTHORITY = {
    "arXiv": 3.0, "IEEE Spectrum": 2.5, "MIT Tech Review": 2.3, "DeepMind": 2.2,
    "Anthropic": 2.2, "OpenAI Blog": 2.2, "Google AI": 2.0, "Meta AI": 1.8,
    "Hugging Face": 1.8, "TechCrunch": 1.5, "VentureBeat": 1.3,
    "Wired": 1.3, "The Verge": 1.2, "HackerNews": 0.8,
}

def score(a: Dict) -> float:
    s  = 0.0
    dt = a.get("date")
    if dt:
        age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        s  += max(0, 12 - age * 0.07)
    s += SOURCE_AUTHORITY.get(a.get("source",""), 1.0)
    tl = len(a.get("title",""))
    if 40 < tl < 130: s += 0.4
    dl = len(a.get("desc",""))
    if dl > 80: s += 0.3
    return s

# ─── Deduplicate ──────────────────────────────────────────────────────────────

def dedup(articles: List[Dict]) -> List[Dict]:
    seen_urls:   set = set()
    seen_titles: set = set()
    out: List[Dict]  = []
    for a in articles:
        url  = re.sub(r"\?.*$", "", a.get("url","")).rstrip("/")
        tkey = hashlib.md5(a.get("title","").lower()[:60].encode()).hexdigest()
        if url in seen_urls or tkey in seen_titles: continue
        if url: seen_urls.add(url)
        seen_titles.add(tkey)
        out.append(a)
    return out

# ─── State ────────────────────────────────────────────────────────────────────

def load_issue() -> int:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text()).get("issue", 0)
        except: pass
    return 0

def save_issue(n: int) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"issue": n}, indent=2))

# ─── HTML helpers ─────────────────────────────────────────────────────────────

SOURCE_COLORS: Dict[str, str] = {
    s: c for feed in [
        {"source": s, "color": c}
        for s, c in {
            "TechCrunch": "#22c55e", "VentureBeat": "#f97316",
            "The Verge":  "#e11d48", "Wired":        "#818cf8",
            "IEEE Spectrum": "#0ea5e9", "MIT Tech Review": "#a78bfa",
            "arXiv": "#a78bfa", "HackerNews": "#f97316",
            "OpenAI Blog": "#10b981", "Anthropic": "#f59e0b",
            "Google AI": "#4285f4", "DeepMind": "#06b6d4",
            "Hugging Face": "#fbbf24", "Meta AI": "#3b82f6",
        }.items()
    ]
    for s, c in [(feed["source"], feed["color"])]
}

def source_pill(source: str, color: str = "") -> str:
    c = color or SOURCE_COLORS.get(source, "#6b7280")
    return (f'<span class="pill" style="background:{c}22;color:{c};'
            f'border-color:{c}44">{h(source)}</span>')

def card_html(a: Dict, cat_color: str) -> str:
    title = h(a.get("title","Untitled"))
    url   = h(a.get("url","#"))
    desc  = h(a.get("desc","")[:280])
    src   = a.get("source","")
    src_c = a.get("source_color","") or SOURCE_COLORS.get(src,"#6b7280")
    age   = age_str(a.get("date"))
    return f'''<article class="card" style="--cat:{cat_color}">
      <div class="card-top">
        {source_pill(src, src_c)}
        <span class="card-age">{h(age)}</span>
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
    glow  = cfg["glow"]
    count = min(len(articles), MAX_PER_CATEGORY)
    cards = "\n".join(card_html(a, color) for a in articles[:count])
    return f'''<section class="cat-section" id="{cat}" style="--cat:{color};--cat-bg:{bg};--cat-glow:{glow}">
    <header class="section-hdr">
      <span class="section-icon">{cfg["icon"]}</span>
      <h2 class="section-title">{h(cfg["label"])}</h2>
      <span class="section-count">{count} stories</span>
    </header>
    <div class="card-grid">{cards}</div>
  </section>'''

def featured_html(a: Dict) -> str:
    title = h(a.get("title","Untitled"))
    url   = h(a.get("url","#"))
    desc  = h(a.get("desc","")[:600])
    src   = a.get("source","")
    src_c = a.get("source_color","") or SOURCE_COLORS.get(src,"#6b7280")
    age   = age_str(a.get("date"))
    cat   = a.get("category", DEFAULT_CATEGORY)
    cat_c = CATEGORIES.get(cat,{}).get("color","#8b5cf6")
    cat_l = CATEGORIES.get(cat,{}).get("label","News")
    cat_i = CATEGORIES.get(cat,{}).get("icon","📌")
    return f'''<section class="featured-wrap">
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

def nav_html(active_cats: List[str]) -> str:
    links = []
    for cat in active_cats:
        cfg = CATEGORIES.get(cat, {})
        links.append(
            f'<a class="nav-pill" href="#{cat}" style="--cat:{cfg.get("color","#8b5cf6")}">'
            f'{cfg.get("icon","")}&thinsp;{h(cfg.get("label",""))}</a>'
        )
    return f'<nav class="cat-nav">{"".join(links)}</nav>'

# ─── Page CSS ─────────────────────────────────────────────────────────────────

PAGE_CSS = r"""
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0 }

:root {
  --bg:       #07071a;
  --surface:  #0d0d24;
  --card:     #111128;
  --card-h:   #16163a;
  --border:   rgba(255,255,255,0.06);
  --border-h: rgba(255,255,255,0.13);
  --text:     #e8eaf6;
  --sub:      #94a3b8;
  --muted:    #64748b;
  --dim:      #334155;
  font-size: 15px;
}

html { scroll-behavior: smooth }

body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  line-height: 1.6;
  min-height: 100vh;
}

a { color: inherit; text-decoration: none }

/* ── Background glows ── */
body::before {
  content: '';
  position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background:
    radial-gradient(ellipse 70% 50% at 15% 0%,  rgba(99,102,241,.09) 0%, transparent 65%),
    radial-gradient(ellipse 50% 40% at 85% 90%, rgba(6,182,212,.07)  0%, transparent 65%),
    radial-gradient(ellipse 40% 30% at 50% 50%, rgba(139,92,246,.04) 0%, transparent 60%);
}

.page { position: relative; z-index: 1 }

/* ── Header ── */
.site-header {
  border-bottom: 1px solid var(--border);
  background: linear-gradient(180deg, rgba(13,13,36,.98) 0%, rgba(7,7,26,.92) 100%);
  backdrop-filter: blur(14px);
  position: sticky; top: 0; z-index: 100;
}
.header-inner {
  max-width: 1200px; margin: 0 auto; padding: .85rem 1.5rem;
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  flex-wrap: wrap;
}
.brand { display: flex; align-items: center; gap: .7rem }
.brand-logo { font-size: 1.7rem; line-height: 1 }
.brand-name {
  font-family: 'Space Grotesk', sans-serif; font-size: 1.3rem; font-weight: 700;
  background: linear-gradient(130deg, #a78bfa 0%, #38bdf8 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.brand-sub { font-size: .7rem; color: var(--muted); margin-top: 2px }

.header-right { display: flex; align-items: center; gap: .65rem; flex-shrink: 0 }
.issue-badge {
  font-size: .7rem; font-weight: 700; letter-spacing: .07em;
  background: linear-gradient(135deg, rgba(167,139,250,.14), rgba(56,189,248,.12));
  border: 1px solid rgba(167,139,250,.28); color: #a78bfa;
  padding: .22rem .65rem; border-radius: 20px;
}
.header-date { font-size: .78rem; color: var(--muted) }
.live-dot {
  display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  background: #22c55e; margin-right: .3rem;
  animation: blink 2.4s ease-in-out infinite;
}
@keyframes blink {
  0%,100% { opacity:1; box-shadow: 0 0 0 0 rgba(34,197,94,.5) }
  50%      { opacity:.6; box-shadow: 0 0 0 5px rgba(34,197,94,0) }
}

/* ── Category nav ── */
.cat-nav {
  max-width: 1200px; margin: 0 auto; padding: .75rem 1.5rem;
  display: flex; gap: .45rem; flex-wrap: wrap;
  border-bottom: 1px solid var(--border);
}
.nav-pill {
  font-size: .76rem; font-weight: 500; padding: .28rem .72rem; border-radius: 20px;
  border: 1px solid color-mix(in srgb, var(--cat) 28%, transparent);
  color: var(--cat); transition: background .15s, transform .15s; white-space: nowrap;
}
.nav-pill:hover { background: color-mix(in srgb, var(--cat) 11%, transparent); transform: translateY(-1px) }

/* ── Main ── */
main { max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem }

/* ── Featured ── */
.featured-wrap { margin-bottom: 2.75rem }
.featured-card {
  background: linear-gradient(135deg, #140f3c 0%, #0e0e2c 55%, #091428 100%);
  border: 1px solid rgba(167,139,250,.22); border-radius: 20px;
  padding: 2.25rem 2.75rem; position: relative; overflow: hidden;
}
.featured-card::before {
  content: ''; position: absolute; top: -100px; right: -100px;
  width: 420px; height: 420px; border-radius: 50%; pointer-events: none;
  background: radial-gradient(circle, rgba(99,102,241,.14) 0%, transparent 65%);
}
.featured-card::after {
  content: ''; position: absolute; bottom: -60px; left: 20%;
  width: 250px; height: 250px; border-radius: 50%; pointer-events: none;
  background: radial-gradient(circle, rgba(6,182,212,.07) 0%, transparent 65%);
}
.featured-eyebrow { display: flex; align-items: center; gap: .85rem; margin-bottom: 1.1rem }
.featured-badge { font-size: .7rem; font-weight: 700; letter-spacing: .11em; color: #a78bfa; text-transform: uppercase }
.featured-cat   { font-size: .76rem; font-weight: 500 }
.featured-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: clamp(1.35rem, 3.5vw, 2rem); font-weight: 700; line-height: 1.28;
  margin-bottom: 1rem; position: relative; z-index: 1;
}
.featured-meta { display: flex; align-items: center; gap: .7rem; margin-bottom: 1.1rem; flex-wrap: wrap }
.featured-age  { font-size: .78rem; color: var(--muted) }
.featured-body { color: var(--sub); line-height: 1.75; margin-bottom: 1.6rem; max-width: 700px; position: relative; z-index: 1 }
.featured-btn {
  display: inline-flex; align-items: center; gap: .4rem;
  background: linear-gradient(135deg, #6d28d9, #4f46e5);
  color: #fff; padding: .62rem 1.35rem; border-radius: 9px;
  font-size: .87rem; font-weight: 600;
  box-shadow: 0 4px 18px rgba(99,102,241,.38);
  transition: opacity .2s, transform .15s; position: relative; z-index: 1;
}
.featured-btn:hover { opacity: .86; transform: translateY(-1px) }

/* ── Section ── */
.cat-section { margin-bottom: 3rem }
.section-hdr {
  display: flex; align-items: center; gap: .55rem;
  margin-bottom: 1.3rem; padding-bottom: .7rem;
  border-bottom: 2px solid transparent;
  border-image: linear-gradient(90deg, var(--cat) 0%, transparent 100%) 1;
}
.section-icon  { font-size: 1.25rem }
.section-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.1rem; font-weight: 600; color: var(--cat);
}
.section-count {
  margin-left: auto; font-size: .7rem; color: var(--muted);
  background: var(--card); border: 1px solid var(--border);
  padding: .13rem .52rem; border-radius: 12px;
}

/* ── Card grid ── */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1rem;
}

/* ── Card ── */
.card {
  background: var(--card); border: 1px solid var(--border); border-radius: 14px;
  padding: 1.1rem 1.2rem;
  display: flex; flex-direction: column; gap: .55rem;
  transition: border-color .2s, background .2s, transform .2s, box-shadow .2s;
  position: relative; overflow: hidden;
}
.card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: var(--cat, #8b5cf6); opacity: 0; transition: opacity .2s;
}
.card:hover {
  border-color: color-mix(in srgb, var(--cat) 38%, transparent);
  background: var(--card-h); transform: translateY(-3px);
  box-shadow: 0 10px 32px rgba(0,0,0,.4), 0 0 0 1px color-mix(in srgb,var(--cat) 12%,transparent);
}
.card:hover::before { opacity: 1 }
.card-top  { display: flex; align-items: center; justify-content: space-between }
.card-age  { font-size: .7rem; color: var(--muted) }
.card-title { font-size: .92rem; font-weight: 600; line-height: 1.45 }
.card-title a { color: var(--text); transition: color .15s }
.card-title a:hover { color: var(--cat, #a78bfa) }
.card-desc {
  font-size: .8rem; color: var(--muted); line-height: 1.55; flex-grow: 1;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.card-link {
  font-size: .77rem; font-weight: 500; margin-top: auto;
  color: color-mix(in srgb, var(--cat) 85%, #fff);
  transition: opacity .15s;
}
.card-link:hover { opacity: .7 }

/* ── Pill / badge ── */
.pill {
  display: inline-block; font-size: .66rem; font-weight: 700; letter-spacing: .04em;
  padding: .13rem .48rem; border-radius: 5px; border: 1px solid; text-transform: uppercase;
  white-space: nowrap;
}

/* ── Stats bar ── */
.stats-bar {
  max-width: 1200px; margin: 0 auto;
  padding: .7rem 1.5rem;
  display: flex; gap: 1.4rem; flex-wrap: wrap;
  border-top: 1px solid var(--border);
  font-size: .76rem; color: var(--muted);
}
.stat-item { display: flex; align-items: center; gap: .32rem }
.stat-dot  { width: 6px; height: 6px; border-radius: 50%; background: var(--c, #6b7280) }

/* ── Footer ── */
.site-footer {
  background: var(--surface); border-top: 1px solid var(--border);
  padding: 2rem 1.5rem; margin-top: 3rem;
}
.footer-inner {
  max-width: 1200px; margin: 0 auto;
  display: flex; flex-direction: column; align-items: center; gap: .9rem; text-align: center;
}
.footer-brand {
  font-family: 'Space Grotesk', sans-serif; font-size: 1.1rem; font-weight: 700;
  background: linear-gradient(130deg,#a78bfa,#38bdf8);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.footer-links { display: flex; gap: 1.2rem; flex-wrap: wrap; justify-content: center }
.footer-links a { font-size: .82rem; color: var(--muted) }
.footer-links a:hover { color: var(--text) }
.footer-sources { display: flex; gap: .45rem; flex-wrap: wrap; justify-content: center; font-size: .73rem; color: var(--dim) }
.footer-sources span::after { content: '·'; margin-left: .45rem }
.footer-sources span:last-child::after { content: '' }
.footer-note { font-size: .73rem; color: var(--dim); line-height: 1.6 }

/* ── Scroll-to-top ── */
.scroll-top {
  position: fixed; bottom: 1.5rem; right: 1.5rem; z-index: 200;
  background: rgba(13,13,36,.88); border: 1px solid rgba(167,139,250,.28);
  color: #a78bfa; width: 40px; height: 40px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem; backdrop-filter: blur(10px);
  box-shadow: 0 4px 14px rgba(0,0,0,.35);
  transition: background .2s, transform .2s;
}
.scroll-top:hover { background: rgba(99,102,241,.22); transform: translateY(-2px) }

/* ── Empty state ── */
.empty-state { text-align: center; padding: 4rem 1rem; color: var(--muted) }
.empty-icon  { font-size: 3rem; margin-bottom: 1rem }

/* ── Responsive ── */
@media (max-width: 780px) {
  .featured-card { padding: 1.6rem 1.5rem }
  main  { padding: 1.25rem 1rem }
  .cat-nav { padding: .7rem 1rem }
}
@media (max-width: 480px) {
  .card-grid { grid-template-columns: 1fr }
  .header-date { display: none }
}
"""

# ─── Full page ────────────────────────────────────────────────────────────────

def full_page(featured: Optional[Dict],
              sections: Dict[str, List[Dict]],
              issue: int,
              generated: datetime) -> str:

    now_str = generated.strftime("%B %d, %Y")
    gen_iso = generated.strftime("%Y-%m-%dT%H:%M:%SZ")
    total   = sum(len(v) for v in sections.values())
    src_set = sorted({a["source"] for v in sections.values() for a in v})

    featured_block = featured_html(featured) if featured else ""

    cat_order    = list(CATEGORIES.keys())
    active_cats  = [c for c in cat_order if sections.get(c)]
    sections_html = "\n".join(section_html(cat, sections[cat]) for cat in active_cats)

    if not featured_block and not sections_html:
        sections_html = '''<div class="empty-state">
    <div class="empty-icon">🤖</div>
    <p>The workflow will populate this page with live AI news shortly.</p>
  </div>'''

    nav_block = nav_html(active_cats) if active_cats else ""

    stats_items = "".join(
        f'<span class="stat-item"><span class="stat-dot" style="--c:{CATEGORIES[c]["color"]}"></span>'
        f'{CATEGORIES[c]["icon"]} {len(sections.get(c,[]))} {h(CATEGORIES[c]["label"])}</span>'
        for c in active_cats if sections.get(c)
    )
    stats_block  = f'<div class="stats-bar">{stats_items}</div>' if stats_items else ""
    sources_html = "".join(f'<span>{h(s)}</span>' for s in src_set[:14])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Pulse — Daily AI News Digest · Issue #{issue}</title>
  <meta name="description" content="Daily curated AI news covering research breakthroughs, AI agents, new products &amp; industry — Issue #{issue}, {now_str}">
  <meta property="og:title"       content="AI Pulse — Issue #{issue} · {now_str}">
  <meta property="og:description" content="Automated daily AI news digest: research, agents, products, industry &amp; open source.">
  <meta property="og:type"        content="website">
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
      <div class="header-right">
        <span class="issue-badge">Issue #{issue}</span>
        <span class="header-date"><span class="live-dot"></span>{now_str}</span>
      </div>
    </div>
    {nav_block}
  </header>

  <main>
    {featured_block}
    {sections_html}
  </main>

  {stats_block}

  <footer class="site-footer">
    <div class="footer-inner">
      <div class="footer-brand">⚡ AI Pulse</div>
      <div class="footer-links">
        <a href="https://github.com/oeway/ai-news-channel" target="_blank" rel="noopener">GitHub</a>
        <a href="https://arxiv.org/list/cs.AI/recent"        target="_blank" rel="noopener">arXiv CS.AI</a>
        <a href="https://news.ycombinator.com"               target="_blank" rel="noopener">HackerNews</a>
        <a href="https://huggingface.co"                     target="_blank" rel="noopener">Hugging Face</a>
      </div>
      <div class="footer-sources">{sources_html}</div>
      <div class="footer-note">
        Auto-generated from {len(src_set)} sources · {total} articles · {now_str}<br>
        <time datetime="{gen_iso}">{gen_iso}</time>
      </div>
    </div>
  </footer>

</div>
<a class="scroll-top" href="#" aria-label="Back to top">↑</a>
</body>
</html>"""

# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    print("⚡ AI Pulse Newsletter Generator", flush=True)
    print("─" * 50, flush=True)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    issue = load_issue() + 1
    print(f"Generating Issue #{issue}", flush=True)

    # ── Fetch ──
    print("\n[1/4] Fetching news…", flush=True)
    all_articles: List[Dict] = []
    for cfg in RSS_FEEDS:
        all_articles.extend(fetch_rss(cfg))
    all_articles.extend(fetch_hn())
    all_articles.extend(fetch_arxiv())
    print(f"  Total raw: {len(all_articles)}", flush=True)

    # ── Deduplicate + classify ──
    print("\n[2/4] Deduplicating & classifying…", flush=True)
    articles = dedup(all_articles)
    for a in articles:
        a["category"] = classify(a)
    print(f"  After dedup: {len(articles)}", flush=True)

    # ── Sort & bucket ──
    print("\n[3/4] Scoring & sorting…", flush=True)
    articles.sort(key=score, reverse=True)

    sections: Dict[str, List[Dict]] = {cat: [] for cat in CATEGORIES}
    for a in articles:
        cat = a.get("category", DEFAULT_CATEGORY)
        if cat in sections and len(sections[cat]) < MAX_PER_CATEGORY:
            sections[cat].append(a)

    # ── Featured ──
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
    print(f"  Sections: {', '.join(f'{k}:{len(v)}' for k,v in sections.items() if v)}", flush=True)
    print(f"  Total placed: {total}", flush=True)

    # ── Render ──
    print("\n[4/4] Rendering HTML…", flush=True)
    generated = datetime.now(timezone.utc)
    html_out  = full_page(featured, sections, issue, generated)
    OUTPUT.write_text(html_out, encoding="utf-8")
    save_issue(issue)

    print(f"\n✅ Written → {OUTPUT}", flush=True)
    print(f"   Issue #{issue} · {total} articles · {generated.strftime('%Y-%m-%dT%H:%M:%SZ')}")


if __name__ == "__main__":
    main()
