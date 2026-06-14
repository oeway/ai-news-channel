#!/usr/bin/env python3
"""
AI Pulse Newsletter Generator
Fetches the latest AI news from multiple sources and generates a static HTML newsletter.
No external dependencies required — uses only Python stdlib.
"""

import os, re, sys, json, time, hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from html import escape as h
from typing import List, Dict, Any, Optional
import urllib.parse, urllib.request, urllib.error

# ─── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR   = SCRIPT_DIR.parent
DOCS_DIR   = ROOT_DIR / "docs"
OUTPUT     = DOCS_DIR / "index.html"
STATE_FILE = DOCS_DIR / "state.json"

# ─── Sources ──────────────────────────────────────────────────────────────────

RSS_FEEDS = [
    {"url": "https://techcrunch.com/category/artificial-intelligence/feed/",
     "source": "TechCrunch",    "color": "#22c55e"},
    {"url": "https://venturebeat.com/category/ai/feed/",
     "source": "VentureBeat",   "color": "#f97316"},
    {"url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
     "source": "The Verge",     "color": "#e11d48"},
    {"url": "https://www.wired.com/feed/category/artificial-intelligence/latest/rss",
     "source": "Wired",         "color": "#818cf8"},
    {"url": "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss",
     "source": "IEEE Spectrum",  "color": "#0ea5e9"},
    {"url": "https://www.technologyreview.com/feed/",
     "source": "MIT Tech Review","color": "#a78bfa"},
    {"url": "https://blog.google/technology/ai/rss/",
     "source": "Google AI",     "color": "#4285f4"},
    {"url": "https://blogs.microsoft.com/ai/feed/",
     "source": "Microsoft AI",  "color": "#00a4ef"},
    {"url": "https://www.artificialintelligence-news.com/feed/",
     "source": "AI News",       "color": "#f59e0b"},
]

HN_API  = "https://hn.algolia.com/api/v1/search_by_date"
HN_TAGS = [
    "artificial intelligence", "AI agent", "large language model",
    "machine learning", "LLM", "GPT", "Claude AI", "Gemini"
]

ARXIV_API   = "https://export.arxiv.org/api/query"
ARXIV_QUERY = "cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.NE+OR+cat:cs.CV"

# ─── Categories ───────────────────────────────────────────────────────────────

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
            "attention", "embedding", "token", "context window", "parameter",
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
            "self-improv", "task complet", "action", "langchain", "langraph",
            "autogen", "crewai", "mcp", "model context protocol",
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
            "service", "plugin", "integrat", "sora", "dall-e", "midjourney", "stable diffusion",
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
            "valuat", "ipo", "lawsuit", "safety", "govern", "anthropic", "deepmind",
            "xai", "inflection", "cohere", "databricks",
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
            "lm studio", "vllm", "exllama", "gguf", "ggml", "mistral 7b",
        ]
    }
}

DEFAULT_CATEGORY   = "industry"
MAX_PER_CATEGORY   = 8
MAX_FEATURED_AGE_H = 72

# ─── HTTP ─────────────────────────────────────────────────────────────────────

UA = "AI-Pulse/3.0 (+https://github.com/oeway/ai-news-channel)"

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
        v = v.strip()
        for fmt in (
            "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z",
            "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT",
            "%a, %d %b %Y %H:%M:%S +0000", "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(v, fmt)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None

def age_str(dt: Optional[datetime]) -> str:
    if dt is None: return "Recently"
    delta = datetime.now(timezone.utc) - dt
    mins  = delta.total_seconds() / 60
    if mins < 60:   return f"{int(mins)}m ago"
    if mins < 1440: return f"{int(mins/60)}h ago"
    if delta.days == 1: return "Yesterday"
    if delta.days < 7:  return f"{delta.days}d ago"
    return dt.strftime("%b %d")

def is_fresh(dt: Optional[datetime], hours: float = 6) -> bool:
    if not dt: return False
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600 < hours

# ─── RSS parser (stdlib only, handles RSS 2.0 + Atom) ─────────────────────────

_ATOM    = "http://www.w3.org/2005/Atom"
_CONTENT = "http://purl.org/rss/1.0/modules/content/"
_DC      = "http://purl.org/dc/elements/1.1/"
_MEDIA   = "http://search.yahoo.com/mrss/"

def _text(el: Any, *paths: str) -> str:
    if el is None: return ""
    for p in paths:
        t = el.findtext(p)
        if t: return t.strip()
    return ""

def fetch_rss(cfg: Dict) -> List[Dict]:
    print(f"  RSS  {cfg['source']}…", flush=True)
    raw = fetch(cfg["url"])
    if not raw: return []
    try:
        root = ET.fromstring(raw)
        articles: List[Dict] = []
        is_atom = root.tag in (f"{{{_ATOM}}}feed", "feed") or \
                  "{http://www.w3.org/2005/Atom}" in root.tag

        if is_atom:
            entries = root.findall(f"{{{_ATOM}}}entry")
        else:
            entries = root.findall(".//item")

        for entry in entries[:25]:
            if is_atom:
                title = _text(entry, f"{{{_ATOM}}}title")
                # prefer alternate link
                link_el = (entry.find(f"{{{_ATOM}}}link[@rel='alternate']") or
                           entry.find(f"{{{_ATOM}}}link"))
                url = link_el.get("href", "") if link_el is not None else ""
                desc = (_text(entry, f"{{{_ATOM}}}summary", f"{{{_ATOM}}}content") or "")
                pub  = _text(entry, f"{{{_ATOM}}}published", f"{{{_ATOM}}}updated")
            else:
                title = _text(entry, "title")
                url   = _text(entry, "link")
                desc  = (_text(entry, "description",
                               f"{{{_CONTENT}}}encoded") or "")
                pub   = _text(entry, "pubDate", f"{{{_DC}}}date")

            if not title or not url: continue
            desc = re.sub(r"<[^>]+>", " ", desc)
            desc = re.sub(r"\s+", " ", desc).strip()[:450]
            articles.append({
                "title": title, "url": url, "desc": desc,
                "source": cfg["source"], "source_color": cfg["color"],
                "date": to_dt(pub), "category": None,
            })

        print(f"     → {len(articles)} items", flush=True)
        return articles
    except Exception as ex:
        print(f"  [!] parse {cfg['source']}: {ex}", file=sys.stderr)
        return []

# ─── Hacker News ──────────────────────────────────────────────────────────────

def fetch_hn() -> List[Dict]:
    print("  HN   Algolia search…", flush=True)
    seen: set = set()
    articles: List[Dict] = []
    for q in HN_TAGS[:5]:
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
                articles.append({
                    "title": title, "url": story_url, "desc": desc,
                    "source": "HackerNews", "source_color": "#f97316",
                    "date": dt, "category": None, "_hn_pts": pts,
                })
        except Exception as ex:
            print(f"  [!] HN parse: {ex}", file=sys.stderr)
        time.sleep(0.25)
    print(f"     → {len(articles)} items", flush=True)
    return articles

# ─── arXiv ────────────────────────────────────────────────────────────────────

def fetch_arxiv() -> List[Dict]:
    print("  arXiv papers…", flush=True)
    url = (f"{ARXIV_API}?search_query={ARXIV_QUERY}"
           "&start=0&max_results=25&sortBy=submittedDate&sortOrder=descending")
    raw = fetch(url)
    if not raw: return []
    try:
        ns   = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(raw)
        arts = []
        for entry in root.findall("a:entry", ns):
            title = (entry.findtext("a:title", "", ns) or "").replace("\n", " ").strip()
            summ  = (entry.findtext("a:summary", "", ns) or "").replace("\n", " ").strip()[:380]
            link  = (entry.findtext("a:id", "", ns) or "").strip()
            pub   = entry.findtext("a:published", "", ns)
            cats  = [c.get("term", "") for c in entry.findall("a:category", ns)]
            cat_s = " · ".join(cats[:3])
            # Extract authors
            authors = [a.findtext("a:name", "", ns)
                       for a in entry.findall("a:author", ns)][:3]
            author_s = ", ".join(authors) + ("…" if len(authors) >= 3 else "")
            desc = f"[{cat_s}] {summ}"
            if author_s:
                desc = f"By {author_s} · {desc}"
            if not title or not link: continue
            arts.append({
                "title": title, "url": link, "desc": desc,
                "source": "arXiv", "source_color": "#a78bfa",
                "date": to_dt(pub), "category": "research",
            })
        print(f"     → {len(arts)} papers", flush=True)
        return arts
    except Exception as ex:
        print(f"  [!] arXiv parse: {ex}", file=sys.stderr)
        return []

# ─── Classify ─────────────────────────────────────────────────────────────────

def classify(a: Dict) -> str:
    if a.get("category"):
        return a["category"]
    text   = (a.get("title", "") + " " + a.get("desc", "")).lower()
    scores = {cat: sum(1 for kw in cfg["keywords"] if kw in text)
              for cat, cfg in CATEGORIES.items()}
    best   = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else DEFAULT_CATEGORY

# ─── Score ────────────────────────────────────────────────────────────────────

def score(a: Dict) -> float:
    s  = 0.0
    dt = a.get("date")
    if dt:
        age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        s += max(0, 12 - age_h * 0.07)
    source_bonus = {
        "arXiv": 2.8, "IEEE Spectrum": 2.2, "MIT Tech Review": 2.0, "Google AI": 2.0,
        "TechCrunch": 1.6, "VentureBeat": 1.4, "Wired": 1.4, "Microsoft AI": 1.4,
        "The Verge": 1.3, "AI News": 1.1, "HackerNews": 0.9,
    }
    s += source_bonus.get(a.get("source", ""), 1.0)
    hn_pts = a.get("_hn_pts", 0)
    if hn_pts: s += min(hn_pts * 0.01, 3.0)
    tl = len(a.get("title", ""))
    if 40 < tl < 120: s += 0.5
    return s

# ─── Dedup ────────────────────────────────────────────────────────────────────

def dedup(articles: List[Dict]) -> List[Dict]:
    seen_urls:   set = set()
    seen_titles: set = set()
    out: List[Dict] = []
    for a in articles:
        url  = re.sub(r"\?.*$", "", a.get("url", "")).rstrip("/")
        tkey = hashlib.md5(a.get("title", "").lower()[:70].encode()).hexdigest()
        if url in seen_urls or tkey in seen_titles: continue
        if url: seen_urls.add(url)
        seen_titles.add(tkey)
        out.append(a)
    return out

# ─── State ────────────────────────────────────────────────────────────────────

def load_issue() -> int:
    if STATE_FILE.exists():
        try: return json.loads(STATE_FILE.read_text()).get("issue", 0)
        except: pass
    return 0

def save_issue(n: int) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"issue": n}, indent=2))

# ─── HTML components ──────────────────────────────────────────────────────────

SOURCE_COLORS: Dict[str, str] = {
    "TechCrunch":    "#22c55e", "VentureBeat": "#f97316", "The Verge": "#e11d48",
    "Wired":         "#818cf8", "IEEE Spectrum": "#0ea5e9", "MIT Tech Review": "#a78bfa",
    "arXiv":         "#a78bfa", "HackerNews": "#f97316", "Google AI": "#4285f4",
    "Microsoft AI":  "#00a4ef", "AI News": "#f59e0b",
}

def pill(source: str, color: str = "") -> str:
    c = color or SOURCE_COLORS.get(source, "#6b7280")
    return (f'<span class="pill" style="--pc:{c}">{h(source)}</span>')

def card_html(a: Dict, cat_color: str) -> str:
    title  = h(a.get("title", "Untitled"))
    url    = h(a.get("url", "#"))
    desc   = h((a.get("desc") or "")[:260])
    src    = a.get("source", "")
    src_c  = a.get("source_color", "") or SOURCE_COLORS.get(src, "#6b7280")
    age    = age_str(a.get("date"))
    fresh  = is_fresh(a.get("date"), 6)
    new_b  = '<span class="new-badge">NEW</span>' if fresh else ""
    return f'''
    <article class="card" style="--cc:{cat_color}">
      <div class="card-top">
        {pill(src, src_c)}
        <span class="card-meta">{new_b}<span class="card-age">{h(age)}</span></span>
      </div>
      <h3 class="card-title"><a href="{url}" target="_blank" rel="noopener">{title}</a></h3>
      <p  class="card-desc">{desc}</p>
      <a  class="card-cta" href="{url}" target="_blank" rel="noopener">Read more →</a>
    </article>'''

def section_html(cat: str, articles: List[Dict]) -> str:
    if not articles: return ""
    cfg   = CATEGORIES[cat]
    color = cfg["color"]
    bg    = cfg["bg"]
    n     = len(articles[:MAX_PER_CATEGORY])
    cards = "\n".join(card_html(a, color) for a in articles[:MAX_PER_CATEGORY])
    return f'''
  <section class="section" id="{cat}" style="--cc:{color};--cbg:{bg}">
    <header class="section-hdr">
      <span class="s-icon">{cfg["icon"]}</span>
      <h2 class="s-title">{h(cfg["label"])}</h2>
      <span class="s-count">{n}</span>
    </header>
    <div class="card-grid">{cards}</div>
  </section>'''

def featured_html(a: Dict) -> str:
    title = h(a.get("title", "Untitled"))
    url   = h(a.get("url", "#"))
    desc  = h((a.get("desc") or "")[:520])
    src   = a.get("source", "")
    src_c = a.get("source_color", "") or SOURCE_COLORS.get(src, "#6b7280")
    age   = age_str(a.get("date"))
    cat   = a.get("category", DEFAULT_CATEGORY)
    cat_c = CATEGORIES.get(cat, {}).get("color", "#8b5cf6")
    cat_l = CATEGORIES.get(cat, {}).get("label", "News")
    cat_i = CATEGORIES.get(cat, {}).get("icon", "📌")
    fresh  = is_fresh(a.get("date"), 6)
    new_b  = '<span class="f-new">● JUST IN</span>' if fresh else ""
    return f'''
  <section class="featured">
    <div class="f-card">
      <div class="f-eyebrow">
        <span class="f-tag">✦ Top Story</span>
        <span class="f-cat" style="color:{cat_c}">{cat_i} {h(cat_l)}</span>
        {new_b}
      </div>
      <h2 class="f-title">{title}</h2>
      <div class="f-meta">{pill(src, src_c)}<span class="f-age">{h(age)}</span></div>
      <p class="f-body">{desc}</p>
      <a class="f-btn" href="{url}" target="_blank" rel="noopener">Read Full Story →</a>
    </div>
  </section>'''

def nav_html(active: List[str]) -> str:
    links = "".join(
        f'<a class="npill" href="#{c}" style="--cc:{CATEGORIES[c]["color"]}">'
        f'{CATEGORIES[c]["icon"]}&thinsp;{h(CATEGORIES[c]["label"])}</a>'
        for c in active
    )
    return f'<nav class="top-nav">{links}</nav>'

# ─── CSS ──────────────────────────────────────────────────────────────────────

PAGE_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0 }

:root {
  --bg:      #07071a;
  --surf:    #0d0d24;
  --card:    #0f0f2a;
  --card-h:  #141435;
  --border:  rgba(255,255,255,0.07);
  --border-h:rgba(255,255,255,0.14);
  --text:    #e2e8f0;
  --sub:     #94a3b8;
  --muted:   #64748b;
  --dim:     #334155;
  font-size: 15px;
}

html { scroll-behavior: smooth }

body {
  background: var(--bg); color: var(--text);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  line-height: 1.6; min-height: 100vh;
}

/* Ambient glows */
body::before {
  content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background:
    radial-gradient(ellipse 70% 45% at 10% 5%,  rgba(99,102,241,.09) 0%, transparent 65%),
    radial-gradient(ellipse 55% 40% at 85% 85%, rgba(6,182,212,.07)  0%, transparent 65%),
    radial-gradient(ellipse 40% 35% at 50% 50%, rgba(139,92,246,.04) 0%, transparent 60%);
}

.page { position: relative; z-index: 1 }

/* ── Header ── */
.site-header {
  border-bottom: 1px solid var(--border);
  background: rgba(7,7,26,.96);
  backdrop-filter: blur(16px);
  position: sticky; top: 0; z-index: 100;
}

.header-inner {
  max-width: 1200px; margin: 0 auto; padding: .9rem 1.5rem;
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
}

.brand { display: flex; align-items: center; gap: .7rem; text-decoration: none }
.brand-logo { font-size: 1.75rem; line-height: 1 }
.brand-name {
  font-family: 'Space Grotesk', sans-serif; font-size: 1.35rem; font-weight: 700;
  background: linear-gradient(130deg, #a78bfa 0%, #38bdf8 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.brand-sub { font-size: .7rem; color: var(--muted); margin-top: 1px }

.hdr-right { display: flex; align-items: center; gap: .65rem; flex-shrink: 0 }
.issue-tag {
  font-size: .7rem; font-weight: 700; letter-spacing: .07em;
  background: linear-gradient(135deg, rgba(167,139,250,.15), rgba(56,189,248,.12));
  border: 1px solid rgba(167,139,250,.3); color: #a78bfa;
  padding: .22rem .65rem; border-radius: 20px;
}
.hdr-date { font-size: .78rem; color: var(--muted) }
.live-dot {
  display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  background: #22c55e; margin-right: .3rem;
  animation: pulse 2.4s ease-in-out infinite;
}
@keyframes pulse {
  0%,100% { opacity:1; box-shadow: 0 0 0 0 rgba(34,197,94,.5) }
  50%      { opacity:.6; box-shadow: 0 0 0 6px rgba(34,197,94,0) }
}

/* ── Top nav ── */
.top-nav {
  max-width: 1200px; margin: 0 auto; padding: .75rem 1.5rem;
  display: flex; gap: .4rem; flex-wrap: wrap;
  border-bottom: 1px solid var(--border);
}
.npill {
  font-size: .75rem; font-weight: 500; padding: .28rem .7rem; border-radius: 20px;
  border: 1px solid color-mix(in srgb, var(--cc) 25%, transparent);
  color: var(--cc); text-decoration: none;
  transition: background .15s, transform .15s; white-space: nowrap;
}
.npill:hover {
  background: color-mix(in srgb, var(--cc) 12%, transparent);
  transform: translateY(-1px);
}

/* ── Main ── */
main { max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem }

/* ── Featured ── */
.featured { margin-bottom: 2.5rem }
.f-card {
  background: linear-gradient(135deg, #13103e 0%, #0d0d2a 55%, #091530 100%);
  border: 1px solid rgba(167,139,250,.22); border-radius: 20px;
  padding: 2.25rem 2.75rem; position: relative; overflow: hidden;
}
.f-card::before {
  content: ''; position: absolute; top: 0; left: 0; width: 4px; height: 100%;
  background: linear-gradient(180deg, #a78bfa, #38bdf8);
}
.f-card::after {
  content: ''; position: absolute; top: -120px; right: -120px;
  width: 500px; height: 500px; border-radius: 50%; pointer-events: none;
  background: radial-gradient(circle, rgba(99,102,241,.1) 0%, transparent 65%);
}
.f-eyebrow { display: flex; align-items: center; gap: .85rem; margin-bottom: 1.1rem; flex-wrap: wrap }
.f-tag {
  font-size: .7rem; font-weight: 700; letter-spacing: .11em;
  color: #a78bfa; text-transform: uppercase;
}
.f-cat  { font-size: .76rem; font-weight: 500 }
.f-new  { font-size: .65rem; font-weight: 700; color: #22c55e; letter-spacing: .08em; animation: pulse 2s infinite }
.f-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: clamp(1.3rem, 3.2vw, 2rem); font-weight: 700;
  line-height: 1.28; margin-bottom: .9rem;
}
.f-meta { display: flex; align-items: center; gap: .7rem; margin-bottom: 1rem; flex-wrap: wrap }
.f-age  { font-size: .78rem; color: var(--muted) }
.f-body { color: var(--sub); line-height: 1.75; margin-bottom: 1.5rem; max-width: 720px; position: relative; z-index: 1 }
.f-btn {
  display: inline-flex; align-items: center; gap: .35rem;
  background: linear-gradient(135deg, #6d28d9, #4f46e5);
  color: #fff; text-decoration: none;
  padding: .62rem 1.4rem; border-radius: 9px;
  font-size: .87rem; font-weight: 600;
  box-shadow: 0 4px 20px rgba(99,102,241,.4);
  transition: opacity .2s, transform .15s; position: relative; z-index: 1;
}
.f-btn:hover { opacity: .85; transform: translateY(-2px) }

/* ── Section ── */
.section { margin-bottom: 3rem }
.section-hdr {
  display: flex; align-items: center; gap: .55rem;
  margin-bottom: 1.3rem; padding-bottom: .75rem;
  border-bottom: 2px solid color-mix(in srgb, var(--cc) 25%, transparent);
}
.s-icon  { font-size: 1.25rem }
.s-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.1rem; font-weight: 700; color: var(--cc);
}
.s-count {
  margin-left: auto; font-size: .7rem; font-weight: 700;
  background: color-mix(in srgb, var(--cc) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--cc) 25%, transparent);
  color: var(--cc); padding: .15rem .55rem; border-radius: 12px;
}

/* ── Cards ── */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}
.card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 14px; padding: 1.1rem 1.2rem;
  display: flex; flex-direction: column; gap: .55rem;
  transition: border-color .2s, background .2s, transform .2s, box-shadow .2s;
  position: relative; overflow: hidden;
}
.card::after {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: var(--cc, #8b5cf6); opacity: 0; transition: opacity .2s;
}
.card:hover {
  border-color: color-mix(in srgb, var(--cc) 40%, transparent);
  background: var(--card-h); transform: translateY(-3px);
  box-shadow: 0 12px 32px rgba(0,0,0,.4),
              0 0 0 1px color-mix(in srgb, var(--cc) 12%, transparent);
}
.card:hover::after { opacity: 1 }

.card-top  { display: flex; align-items: center; justify-content: space-between; gap: .4rem }
.card-meta { display: flex; align-items: center; gap: .35rem; flex-shrink: 0 }
.card-age  { font-size: .7rem; color: var(--muted) }
.new-badge {
  font-size: .6rem; font-weight: 800; letter-spacing: .07em;
  color: #22c55e; background: rgba(34,197,94,.12);
  border: 1px solid rgba(34,197,94,.3);
  padding: .1rem .35rem; border-radius: 4px;
}
.card-title { font-size: .91rem; font-weight: 600; line-height: 1.45 }
.card-title a { text-decoration: none; color: var(--text); transition: color .15s }
.card-title a:hover { color: var(--cc, #a78bfa) }
.card-desc {
  font-size: .8rem; color: var(--muted); line-height: 1.55; flex-grow: 1;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.card-cta {
  font-size: .76rem; font-weight: 500; margin-top: auto;
  color: color-mix(in srgb, var(--cc) 85%, #fff);
  text-decoration: none; transition: opacity .15s;
}
.card-cta:hover { opacity: .7 }

/* ── Source pill ── */
.pill {
  display: inline-block; font-size: .65rem; font-weight: 700; letter-spacing: .04em;
  padding: .13rem .48rem; border-radius: 5px;
  background: color-mix(in srgb, var(--pc) 12%, transparent);
  color: var(--pc); border: 1px solid color-mix(in srgb, var(--pc) 28%, transparent);
  text-transform: uppercase; white-space: nowrap;
}

/* ── Stats bar ── */
.stats-bar {
  max-width: 1200px; margin: 0 auto; padding: .75rem 1.5rem;
  display: flex; align-items: center; gap: 1.4rem; flex-wrap: wrap;
  border-top: 1px solid var(--border); font-size: .76rem; color: var(--muted);
}
.sb-item { display: flex; align-items: center; gap: .35rem }
.sb-dot  { width: 6px; height: 6px; border-radius: 50%; background: var(--c, #6b7280); flex-shrink: 0 }
.sb-right { margin-left: auto; font-size: .72rem }

/* ── Footer ── */
.site-footer {
  background: var(--surf); border-top: 1px solid var(--border);
  padding: 2.25rem 1.5rem; margin-top: 3rem;
}
.footer-inner {
  max-width: 1200px; margin: 0 auto;
  display: flex; flex-direction: column; align-items: center; gap: 1rem; text-align: center;
}
.footer-brand {
  font-family: 'Space Grotesk', sans-serif; font-size: 1.1rem; font-weight: 700;
  background: linear-gradient(130deg, #a78bfa, #38bdf8);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.footer-links { display: flex; gap: 1.25rem; flex-wrap: wrap; justify-content: center }
.footer-links a { font-size: .8rem; color: var(--muted); text-decoration: none; transition: color .15s }
.footer-links a:hover { color: var(--text) }
.footer-sources {
  display: flex; gap: .45rem; flex-wrap: wrap; justify-content: center;
  font-size: .73rem; color: var(--dim);
}
.footer-sources span::after { content: '·'; margin-left: .45rem }
.footer-sources span:last-child::after { content: '' }
.footer-note { font-size: .73rem; color: var(--dim); line-height: 1.65 }

/* ── Scroll top ── */
.scroll-top {
  position: fixed; bottom: 1.5rem; right: 1.5rem; z-index: 200;
  background: rgba(13,13,36,.9); border: 1px solid rgba(167,139,250,.28);
  color: #a78bfa; width: 38px; height: 38px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 1rem; backdrop-filter: blur(10px);
  box-shadow: 0 4px 14px rgba(0,0,0,.4);
  text-decoration: none; transition: background .2s, transform .2s;
}
.scroll-top:hover { background: rgba(99,102,241,.25); transform: translateY(-2px) }

/* ── Responsive ── */
@media (max-width: 800px) {
  .f-card { padding: 1.6rem 1.5rem }
  main    { padding: 1.25rem 1rem }
  .top-nav { padding: .7rem 1rem }
}
@media (max-width: 480px) {
  .card-grid    { grid-template-columns: 1fr }
  .hdr-date     { display: none }
  .f-title      { font-size: 1.3rem }
}
"""

# ─── Full page ────────────────────────────────────────────────────────────────

def full_page(featured: Optional[Dict],
              sections: Dict[str, List[Dict]],
              issue: int,
              generated: datetime) -> str:

    now_str  = generated.strftime("%B %d, %Y")
    gen_iso  = generated.strftime("%Y-%m-%dT%H:%M:%SZ")
    total    = sum(len(v) for v in sections.values())
    src_set  = sorted({a["source"] for v in sections.values() for a in v})
    cat_order  = list(CATEGORIES.keys())
    active     = [c for c in cat_order if sections.get(c)]

    featured_block = featured_html(featured) if featured else ""
    sections_html  = "".join(section_html(cat, sections[cat]) for cat in active)

    if not featured_block and not sections_html:
        sections_html = '''
  <div style="text-align:center;padding:4rem 1rem;color:#64748b">
    <div style="font-size:3rem;margin-bottom:1rem">🤖</div>
    <p>No articles fetched yet — the workflow will populate this soon.</p>
  </div>'''

    nav_block   = nav_html(active) if active else ""
    sources_html = "".join(f"<span>{h(s)}</span>" for s in src_set[:14])

    stats_items = "".join(
        f'<span class="sb-item"><span class="sb-dot" style="--c:{CATEGORIES[c]["color"]}"></span>'
        f'{CATEGORIES[c]["icon"]} <strong>{len(sections.get(c,[]))}</strong> {h(CATEGORIES[c]["label"])}</span>'
        for c in active if sections.get(c)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Pulse — Issue #{issue} · {h(now_str)}</title>
  <meta name="description" content="Daily curated AI news: research, agents, products &amp; industry. Issue #{issue}, {h(now_str)}.">
  <meta property="og:title"       content="AI Pulse #{issue} · {h(now_str)}">
  <meta property="og:description" content="Daily curated AI news digest — {total} stories across {len(src_set)} sources.">
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
      <div class="hdr-right">
        <span class="issue-tag">Issue #{issue}</span>
        <span class="hdr-date"><span class="live-dot"></span>{h(now_str)}</span>
      </div>
    </div>
    {nav_block}
  </header>

  <main>
    {featured_block}
    {sections_html}
  </main>

  <div class="stats-bar">
    {stats_items}
    <span class="sb-right">⚡ {total} stories · {len(src_set)} sources · Auto-updated daily</span>
  </div>

  <footer class="site-footer">
    <div class="footer-inner">
      <div class="footer-brand">⚡ AI Pulse</div>
      <div class="footer-links">
        <a href="https://github.com/oeway/ai-news-channel" target="_blank" rel="noopener">GitHub</a>
        <a href="https://arxiv.org/list/cs.AI/recent"       target="_blank" rel="noopener">arXiv CS.AI</a>
        <a href="https://news.ycombinator.com"              target="_blank" rel="noopener">HackerNews</a>
        <a href="https://huggingface.co"                    target="_blank" rel="noopener">Hugging Face</a>
      </div>
      <div class="footer-sources">{sources_html}</div>
      <div class="footer-note">
        Auto-generated from {len(src_set)} sources · {total} articles · Issue #{issue}<br>
        Last updated <time datetime="{gen_iso}">{gen_iso}</time>
      </div>
    </div>
  </footer>

</div>
<a class="scroll-top" href="#" aria-label="Back to top">↑</a>
</body>
</html>"""

# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("⚡ AI Pulse Newsletter Generator v3", flush=True)
    print("─" * 50, flush=True)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    issue = load_issue() + 1
    print(f"Generating Issue #{issue}", flush=True)

    print("\n[1/4] Fetching news…", flush=True)
    all_articles: List[Dict] = []
    for cfg in RSS_FEEDS:
        all_articles.extend(fetch_rss(cfg))
    all_articles.extend(fetch_hn())
    all_articles.extend(fetch_arxiv())
    print(f"  Total raw: {len(all_articles)}", flush=True)

    print("\n[2/4] Deduplicating & classifying…", flush=True)
    articles = dedup(all_articles)
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
    total = sum(len(v) for v in sections.values())
    print(f"  Buckets: {', '.join(f'{k}:{len(v)}' for k,v in sections.items() if v)}", flush=True)

    # Pick featured: most recent high-quality article
    featured: Optional[Dict] = None
    now = datetime.now(timezone.utc)
    for a in articles:
        dt = a.get("date")
        if dt and (now - dt).total_seconds() / 3600 < MAX_FEATURED_AGE_H:
            featured = a
            break
    if featured is None and articles:
        featured = articles[0]

    print("\n[4/4] Rendering HTML…", flush=True)
    generated = datetime.now(timezone.utc)
    html      = full_page(featured, sections, issue, generated)
    OUTPUT.write_text(html, encoding="utf-8")
    save_issue(issue)

    print(f"\n✅ Written → {OUTPUT}", flush=True)
    print(f"   Issue #{issue} · {total} articles · {generated.strftime('%Y-%m-%dT%H:%M:%SZ')}")


if __name__ == "__main__":
    main()
