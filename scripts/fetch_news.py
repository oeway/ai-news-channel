#!/usr/bin/env python3
"""
AI Pulse Newsletter Generator
Fetches the latest AI news from multiple sources and generates a static HTML newsletter.
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

# feedparser is used when available; falls back to stdlib XML parser
try:
    import feedparser as _feedparser
    _HAS_FEEDPARSER = True
except Exception:
    _feedparser = None  # type: ignore
    _HAS_FEEDPARSER = False

# ─── Paths ──────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR   = SCRIPT_DIR.parent
DOCS_DIR   = ROOT_DIR / "docs"
OUTPUT     = DOCS_DIR / "index.html"
STATE_FILE = DOCS_DIR / "state.json"

# ─── Sources ────────────────────────────────────────────────────────────────

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
]

HN_API  = "https://hn.algolia.com/api/v1/search_by_date"
HN_TAGS = ["artificial intelligence", "AI agent", "large language model", "machine learning"]

ARXIV_API   = "https://export.arxiv.org/api/query"
ARXIV_QUERY = "cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.NE"

# ─── Categories ─────────────────────────────────────────────────────────────

CATEGORIES: Dict[str, Dict] = {
    "research": {
        "label": "Research & Breakthroughs",
        "icon":  "🔬",
        "color": "#22d3ee",
        "keywords": [
            "paper", "arxiv", "research", "study", "benchmark", "dataset", "training",
            "pretrain", "fine-tun", "neural", "transformer", "diffusion", "multimodal",
            "evaluation", "algorithm", "architecture", "inference", "reasoning",
            "capability", "scaling", "emergent", "alignment", "rlhf", "reward model",
            "breakthrough", "experiment", "model", "weight"
        ]
    },
    "agents": {
        "label": "AI Agents & Automation",
        "icon":  "🤖",
        "color": "#c084fc",
        "keywords": [
            "agent", "autonomous", "agentic", "multi-agent", "planning", "memory",
            "tool use", "function call", "workflow", "automation", "copilot",
            "computer use", "browse", "execute", "retrieval", "rag", "orchestrat",
            "self-improv", "task complet", "action", "mcp", "langchain", "langgraph",
            "autogen", "crewai", "cursor", "devin"
        ]
    },
    "products": {
        "label": "New Products & Releases",
        "icon":  "🚀",
        "color": "#60a5fa",
        "keywords": [
            "launch", "release", "introduc", "announc", "unveil", "new", "gpt",
            "claude", "gemini", "llama", "mistral", "update", "feature", "api",
            "version", "preview", "beta", "availab", "product", "app", "platform",
            "service", "plugin", "integrat", "chatgpt", "sora", "dall-e", "midjourney"
        ]
    },
    "industry": {
        "label": "Industry & Business",
        "icon":  "💼",
        "color": "#4ade80",
        "keywords": [
            "funding", "million", "billion", "acqui", "ceo", "hire", "policy",
            "regulat", "invest", "startup", "openai", "google", "microsoft", "meta",
            "nvidia", "amazon", "apple", "partnership", "deal", "market", "revenue",
            "valuat", "ipo", "lawsuit", "safety", "govern", "antitrust", "strategy"
        ]
    },
    "open_source": {
        "label": "Open Source & Community",
        "icon":  "🌐",
        "color": "#fb923c",
        "keywords": [
            "open source", "open-source", "github", "hugging face", "huggingface",
            "llama", "open weight", "open model", "community", "contrib", "fork",
            "mit license", "apache", "open access", "weights", "permissive", "ollama",
            "mistral", "qwen", "deepseek", "falcon"
        ]
    }
}

DEFAULT_CATEGORY   = "industry"
MAX_PER_CATEGORY   = 8
MAX_FEATURED_AGE_H = 72

# ─── HTTP ────────────────────────────────────────────────────────────────────

UA = "AI-Pulse-Newsletter/3.0 (+https://github.com/oeway/ai-news-channel)"

def fetch(url: str, timeout: int = 20) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [!] fetch {url[:70]}: {e}", file=sys.stderr)
        return None

# ─── Date helpers ────────────────────────────────────────────────────────────

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
    return dt.strftime("%b %d")

def is_fresh(dt: Optional[datetime], hours: int = 24) -> bool:
    if dt is None: return False
    return (datetime.now(timezone.utc) - dt).total_seconds() < hours * 3600

def reading_time(text: str) -> int:
    words = len(text.split())
    return max(1, round(words / 200))

# ─── Fetchers ────────────────────────────────────────────────────────────────

def _parse_rss_xml(raw: str, source: str, color: str) -> List[Dict]:
    """Parse RSS 2.0 or Atom 1.0 using stdlib ElementTree."""
    articles: List[Dict] = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        # Some feeds have a BOM or encoding declaration — strip it
        raw = re.sub(r"^[^<]+", "", raw, count=1)
        try:
            root = ET.fromstring(raw)
        except Exception:
            return articles

    ns_atom = "http://www.w3.org/2005/Atom"

    def strip_tags(s: str) -> str:
        s = re.sub(r"<[^>]+>", " ", s)
        return re.sub(r"\s+", " ", s).strip()[:400]

    # ── Atom ──────────────────────────────────────────────────────────────
    if root.tag == f"{{{ns_atom}}}feed" or root.tag == "feed":
        ns = {"a": ns_atom}
        for entry in list(root.findall("a:entry", ns))[:20]:
            title = (entry.findtext("a:title", "", ns) or "").strip()
            link_el = entry.find("a:link", ns)
            url = ""
            if link_el is not None:
                url = link_el.get("href", "") or link_el.text or ""
            desc = ""
            for tag in ("a:summary", "a:content"):
                raw_desc = entry.findtext(tag, "", ns) or ""
                if raw_desc:
                    desc = strip_tags(raw_desc)
                    break
            pub = entry.findtext("a:published", "", ns) or entry.findtext("a:updated", "", ns) or ""
            if not title or not url: continue
            articles.append({"title": title.strip(), "url": url.strip(), "desc": desc,
                              "source": source, "source_color": color,
                              "date": to_dt(pub.strip()), "category": None})
        return articles

    # ── RSS 2.0 ───────────────────────────────────────────────────────────
    channel = root.find("channel") or root
    for item in list(channel.findall("item"))[:20]:
        title = (item.findtext("title") or "").strip()
        url   = (item.findtext("link")  or "").strip()
        desc  = ""
        for tag in ("description", "summary", "{http://purl.org/rss/1.0/modules/content/}encoded"):
            raw_desc = item.findtext(tag) or ""
            if raw_desc:
                desc = strip_tags(raw_desc)
                break
        pub = (item.findtext("pubDate") or item.findtext("dc:date",
               namespaces={"dc": "http://purl.org/dc/elements/1.1/"}) or "")
        if not title or not url: continue
        articles.append({"title": title, "url": url, "desc": desc,
                          "source": source, "source_color": color,
                          "date": to_dt(pub.strip()), "category": None})
    return articles


def fetch_rss(cfg: Dict) -> List[Dict]:
    print(f"  RSS  {cfg['source']}…", flush=True)
    raw = fetch(cfg["url"])
    if not raw: return []
    try:
        if _HAS_FEEDPARSER:
            feed     = _feedparser.parse(raw)
            articles = []
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
                articles.append({"title": title, "url": url, "desc": desc,
                                  "source": cfg["source"], "source_color": cfg["color"],
                                  "date": dt, "category": None})
        else:
            articles = _parse_rss_xml(raw, cfg["source"], cfg["color"])
        print(f"     → {len(articles)} items", flush=True)
        return articles
    except Exception as ex:
        print(f"  [!] parse error {cfg['source']}: {ex}", file=sys.stderr)
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
                                  "date": dt, "category": None, "hn_pts": pts})
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
            summ  = (entry.findtext("a:summary", "", ns) or "").replace("\n", " ").strip()[:350]
            link  = (entry.findtext("a:id",      "", ns) or "").strip()
            pub   = entry.findtext("a:published", "", ns)
            cats  = [c.get("term","") for c in entry.findall("a:category", ns)]
            cat_s = " · ".join(cats[:3])
            desc  = f"[{cat_s}] {summ}"
            if not title or not link: continue
            arts.append({"title": title, "url": link, "desc": desc,
                         "source": "arXiv", "source_color": "#a78bfa",
                         "date": to_dt(pub), "category": "research"})
        print(f"     → {len(arts)} papers", flush=True)
        return arts
    except Exception as ex:
        print(f"  [!] Arxiv parse: {ex}", file=sys.stderr)
        return []

# ─── Classify ────────────────────────────────────────────────────────────────

def classify(a: Dict) -> str:
    if a.get("category"):
        return a["category"]
    text   = (a.get("title","") + " " + a.get("desc","")).lower()
    scores = {cat: sum(1 for kw in cfg["keywords"] if kw in text)
              for cat, cfg in CATEGORIES.items()}
    best   = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else DEFAULT_CATEGORY

# ─── Score ───────────────────────────────────────────────────────────────────

def score(a: Dict) -> float:
    s  = 0.0
    dt = a.get("date")
    if dt:
        age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        s  += max(0, 10 - age * 0.07)
    source_bonus = {
        "arXiv": 2.5, "IEEE Spectrum": 2.0, "MIT Tech Review": 1.8,
        "TechCrunch": 1.5, "VentureBeat": 1.3, "Wired": 1.3,
        "The Verge": 1.2, "HackerNews": 0.9,
    }
    s += source_bonus.get(a.get("source",""), 1.0)
    hn_pts = a.get("hn_pts", 0)
    if hn_pts: s += min(hn_pts / 80, 2.0)
    tl = len(a.get("title",""))
    if 40 < tl < 130: s += 0.4
    return s

# ─── Deduplicate ─────────────────────────────────────────────────────────────

def dedup(articles: List[Dict]) -> List[Dict]:
    seen_urls:   set = set()
    seen_titles: set = set()
    out:  List[Dict] = []
    for a in articles:
        url  = re.sub(r"\?.*$", "", a.get("url","")).rstrip("/")
        tkey = hashlib.md5(a.get("title","").lower()[:60].encode()).hexdigest()
        if url in seen_urls or tkey in seen_titles: continue
        if url: seen_urls.add(url)
        seen_titles.add(tkey)
        out.append(a)
    return out

# ─── Issue counter ───────────────────────────────────────────────────────────

def load_issue() -> int:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text()).get("issue", 0)
        except: pass
    return 0

def save_issue(n: int) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"issue": n}, indent=2))

# ─── HTML helpers ────────────────────────────────────────────────────────────

SOURCE_COLORS: Dict[str, str] = {
    "TechCrunch":     "#22c55e",
    "VentureBeat":    "#f97316",
    "The Verge":      "#e11d48",
    "Wired":          "#818cf8",
    "IEEE Spectrum":  "#0ea5e9",
    "MIT Tech Review":"#a78bfa",
    "arXiv":          "#a78bfa",
    "HackerNews":     "#f97316",
}

def source_pill(source: str, color: str = "") -> str:
    c = color or SOURCE_COLORS.get(source, "#6b7280")
    return (f'<span class="pill" style="background:{c}22;color:{c};'
            f'border-color:{c}44">{h(source)}</span>')

def fresh_badge(dt: Optional[datetime]) -> str:
    if is_fresh(dt, 6):
        return '<span class="badge-new">NEW</span>'
    if is_fresh(dt, 24):
        return '<span class="badge-today">TODAY</span>'
    return ""

def card_html(a: Dict, cat_color: str) -> str:
    title  = h(a.get("title","Untitled"))
    url    = h(a.get("url","#"))
    desc   = h(a.get("desc","")[:260])
    src    = a.get("source","")
    src_c  = a.get("source_color","") or SOURCE_COLORS.get(src,"#6b7280")
    age    = age_str(a.get("date"))
    badge  = fresh_badge(a.get("date"))
    rt     = reading_time(a.get("title","") + " " + a.get("desc",""))
    return f'''
    <article class="card" style="--cat:{cat_color}" data-title="{h(a.get('title','').lower())}" data-desc="{h(a.get('desc','').lower())}">
      <div class="card-top">
        <div class="card-badges">{source_pill(src, src_c)}{badge}</div>
        <span class="card-age" title="{h(str(a.get('date','')))}">{h(age)}</span>
      </div>
      <h3 class="card-title"><a href="{url}" target="_blank" rel="noopener">{title}</a></h3>
      <p  class="card-desc">{desc}</p>
      <div class="card-foot">
        <a class="card-link" href="{url}" target="_blank" rel="noopener">Read more ↗</a>
        <span class="card-rt">~{rt} min</span>
      </div>
    </article>'''

def section_html(cat: str, articles: List[Dict]) -> str:
    if not articles: return ""
    cfg   = CATEGORIES[cat]
    color = cfg["color"]
    items = articles[:MAX_PER_CATEGORY]
    cards = "\n".join(card_html(a, color) for a in items)
    count = len(items)
    return f'''
  <section class="cat-section" id="{cat}" style="--cat:{color}">
    <header class="section-hdr">
      <span class="section-icon">{cfg["icon"]}</span>
      <h2 class="section-label">{h(cfg["label"])}</h2>
      <span class="section-count">{count} stories</span>
    </header>
    <div class="card-grid">
      {cards}
    </div>
  </section>'''

def featured_html(a: Dict) -> str:
    title = h(a.get("title","Untitled"))
    url   = h(a.get("url","#"))
    desc  = h(a.get("desc","")[:520])
    src   = a.get("source","")
    src_c = a.get("source_color","") or SOURCE_COLORS.get(src,"#6b7280")
    age   = age_str(a.get("date"))
    cat   = a.get("category", DEFAULT_CATEGORY)
    cat_c = CATEGORIES.get(cat,{}).get("color","#8b5cf6")
    cat_l = CATEGORIES.get(cat,{}).get("label","News")
    cat_i = CATEGORIES.get(cat,{}).get("icon","📌")
    badge = fresh_badge(a.get("date"))
    return f'''
  <section class="featured-wrap">
    <div class="featured-card">
      <div class="featured-eyebrow">
        <span class="featured-badge">✦ Top Story</span>
        <span class="featured-cat" style="color:{cat_c}">{cat_i} {h(cat_l)}</span>
      </div>
      <h2 class="featured-title">{title}</h2>
      <div class="featured-meta">
        {source_pill(src, src_c)}
        {badge}
        <span class="featured-age">{h(age)}</span>
      </div>
      <p class="featured-body">{desc}</p>
      <a class="featured-btn" href="{url}" target="_blank" rel="noopener">
        Read Full Story ↗
      </a>
    </div>
  </section>'''

def nav_html(active_cats: List[str]) -> str:
    links = [
        '<a class="nav-pill nav-all active" href="#" data-cat="all" style="--cat:#8b5cf6">All</a>'
    ]
    for cat in active_cats:
        cfg = CATEGORIES.get(cat, {})
        links.append(
            f'<a class="nav-pill" href="#{cat}" data-cat="{cat}" '
            f'style="--cat:{cfg.get("color","#8b5cf6")}">'
            f'{cfg.get("icon","")}&thinsp;{h(cfg.get("label",""))}</a>'
        )
    return '<nav class="cat-nav">' + "".join(links) + '</nav>'

# ─── CSS ─────────────────────────────────────────────────────────────────────

PAGE_CSS = r"""
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0 }

:root {
  --bg:       #07071a;
  --surface:  #0d0d24;
  --card:     #111128;
  --card-h:   #16163a;
  --border:   rgba(255,255,255,0.06);
  --border-h: rgba(255,255,255,0.12);
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
a { color: inherit }

body::before {
  content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background:
    radial-gradient(ellipse 65% 45% at 15% 5%,  rgba(99,102,241,.09) 0%, transparent 70%),
    radial-gradient(ellipse 50% 40% at 85% 85%,  rgba(6,182,212,.07)  0%, transparent 70%),
    radial-gradient(ellipse 35% 30% at 50% 50%,  rgba(139,92,246,.04) 0%, transparent 65%);
}
.page { position: relative; z-index: 1 }

/* ── Header ── */
.site-header {
  border-bottom: 1px solid var(--border);
  background: linear-gradient(180deg, rgba(13,13,36,.98) 0%, rgba(7,7,26,.93) 100%);
  backdrop-filter: blur(14px);
  position: sticky; top: 0; z-index: 100;
}
.header-inner {
  max-width: 1180px; margin: 0 auto; padding: .9rem 1.5rem;
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  flex-wrap: wrap;
}
.brand { display: flex; align-items: center; gap: .75rem; text-decoration: none }
.brand-logo { font-size: 1.7rem; line-height: 1 }
.brand-name {
  font-family: 'Space Grotesk', sans-serif; font-size: 1.35rem; font-weight: 700;
  background: linear-gradient(135deg, #a78bfa 0%, #38bdf8 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.brand-sub { font-size: .72rem; color: var(--muted); margin-top: 1px }
.header-right { display: flex; align-items: center; gap: .75rem; flex-shrink: 0 }
.issue-badge {
  font-size: .72rem; font-weight: 700; letter-spacing: .07em;
  background: linear-gradient(135deg, rgba(167,139,250,.15), rgba(56,189,248,.15));
  border: 1px solid rgba(167,139,250,.3);
  color: #a78bfa; padding: .25rem .7rem; border-radius: 20px;
}
.header-date { font-size: .8rem; color: var(--muted) }
.live-dot {
  display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  background: #22c55e; margin-right: .3rem;
  animation: pulse-dot 2.5s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%,100% { opacity:1; box-shadow: 0 0 0 0 rgba(34,197,94,.4) }
  50%      { opacity:.7; box-shadow: 0 0 0 5px rgba(34,197,94,0) }
}

/* ── Search bar ── */
.search-wrap {
  max-width: 1180px; margin: 0 auto;
  padding: .65rem 1.5rem;
  border-bottom: 1px solid var(--border);
  position: relative; display: flex; align-items: center;
}
.search-icon {
  position: absolute; left: calc(1.5rem + .85rem); top: 50%;
  transform: translateY(-50%); font-size: .9rem; pointer-events: none;
  opacity: .45;
}
.search-input {
  width: 100%; max-width: 400px;
  background: var(--card); border: 1px solid var(--border);
  color: var(--text); padding: .5rem 1rem .5rem 2.4rem;
  border-radius: 9px; font-size: .87rem; font-family: inherit;
  outline: none; transition: border-color .2s, box-shadow .2s;
}
.search-input::placeholder { color: var(--muted) }
.search-input:focus {
  border-color: rgba(167,139,250,.4);
  box-shadow: 0 0 0 3px rgba(167,139,250,.08);
}
.search-clear {
  margin-left: .5rem; background: none; border: none; color: var(--muted);
  font-size: 1.1rem; cursor: pointer; padding: .2rem .4rem; border-radius: 5px;
  display: none; transition: color .15s;
}
.search-clear:hover { color: var(--text) }
.search-clear.visible { display: inline }

/* ── Category nav ── */
.cat-nav {
  max-width: 1180px; margin: 0 auto;
  padding: .8rem 1.5rem;
  display: flex; gap: .45rem; flex-wrap: wrap;
  border-bottom: 1px solid var(--border);
}
.nav-pill {
  font-size: .77rem; font-weight: 500;
  padding: .28rem .75rem; border-radius: 20px;
  border: 1px solid color-mix(in srgb, var(--cat) 28%, transparent);
  color: var(--cat); text-decoration: none;
  transition: background .15s, border-color .15s, transform .15s;
  white-space: nowrap;
}
.nav-pill:hover, .nav-pill.active {
  background: color-mix(in srgb, var(--cat) 14%, transparent);
  border-color: var(--cat);
  transform: translateY(-1px);
}
.nav-all { --cat: #8b5cf6 }

/* ── Main ── */
main { max-width: 1180px; margin: 0 auto; padding: 2rem 1.5rem }

/* ── Featured / Top Story ── */
.featured-wrap { margin-bottom: 2.5rem }
.featured-card {
  background: linear-gradient(135deg, #130e38 0%, #0e0e28 55%, #091428 100%);
  border: 1px solid rgba(167,139,250,.22); border-radius: 20px;
  padding: 2rem 2.5rem; position: relative; overflow: hidden;
}
.featured-card::before {
  content: ''; position: absolute; top: -90px; right: -90px;
  width: 380px; height: 380px; border-radius: 50%; pointer-events: none;
  background: radial-gradient(circle, rgba(99,102,241,.13) 0%, transparent 68%);
}
.featured-card::after {
  content: ''; position: absolute; bottom: -50px; left: 15%;
  width: 240px; height: 240px; border-radius: 50%; pointer-events: none;
  background: radial-gradient(circle, rgba(6,182,212,.07) 0%, transparent 68%);
}
.featured-eyebrow { display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem }
.featured-badge {
  font-size: .7rem; font-weight: 700; letter-spacing: .1em;
  color: #a78bfa; text-transform: uppercase;
}
.featured-cat { font-size: .78rem; font-weight: 500 }
.featured-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: clamp(1.25rem, 3vw, 1.9rem); font-weight: 700;
  line-height: 1.3; margin-bottom: 1rem; position: relative; z-index: 1;
}
.featured-meta { display: flex; align-items: center; gap: .75rem; margin-bottom: 1rem; flex-wrap: wrap }
.featured-age  { font-size: .8rem; color: var(--muted) }
.featured-body { color: var(--sub); line-height: 1.72; margin-bottom: 1.5rem; max-width: 680px; position: relative; z-index: 1 }
.featured-btn {
  display: inline-flex; align-items: center; gap: .4rem;
  background: linear-gradient(135deg, #6d28d9, #4f46e5); color: #fff;
  text-decoration: none; padding: .62rem 1.35rem; border-radius: 9px;
  font-size: .88rem; font-weight: 600;
  box-shadow: 0 4px 16px rgba(99,102,241,.38);
  transition: opacity .2s, transform .15s; position: relative; z-index: 1;
}
.featured-btn:hover { opacity: .88; transform: translateY(-1px) }

/* ── Section ── */
.cat-section { margin-bottom: 3rem }
.section-hdr {
  display: flex; align-items: center; gap: .6rem;
  margin-bottom: 1.3rem; padding-bottom: .75rem;
  border-bottom: 1px solid var(--border);
}
.section-icon  { font-size: 1.25rem }
.section-label {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.08rem; font-weight: 600; color: var(--cat);
}
.section-count {
  margin-left: auto; font-size: .7rem; color: var(--muted);
  background: var(--card); border: 1px solid var(--border);
  padding: .13rem .52rem; border-radius: 12px;
}

/* ── Card grid ── */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(310px, 1fr));
  gap: 1rem;
}

/* ── Card ── */
.card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 14px; padding: 1.15rem 1.25rem;
  display: flex; flex-direction: column; gap: .55rem;
  transition: border-color .22s, background .22s, transform .22s, box-shadow .22s;
  position: relative; overflow: hidden;
  animation: card-in .3s ease both;
}
@keyframes card-in {
  from { opacity: 0; transform: translateY(6px) }
  to   { opacity: 1; transform: translateY(0) }
}
.card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: var(--cat, #8b5cf6); opacity: 0; transition: opacity .22s;
}
.card:hover {
  border-color: color-mix(in srgb, var(--cat) 38%, transparent);
  background: var(--card-h); transform: translateY(-3px);
  box-shadow: 0 10px 30px rgba(0,0,0,.38), 0 0 0 1px color-mix(in srgb,var(--cat) 12%,transparent);
}
.card:hover::before { opacity: 1 }
.card[hidden] { display: none !important }
.card-top     { display: flex; align-items: center; justify-content: space-between }
.card-badges  { display: flex; align-items: center; gap: .35rem }
.card-age     { font-size: .7rem; color: var(--muted) }
.card-title   { font-size: .93rem; font-weight: 600; line-height: 1.45 }
.card-title a { text-decoration: none; color: var(--text); transition: color .15s }
.card-title a:hover { color: var(--cat, #a78bfa) }
.card-desc {
  font-size: .81rem; color: var(--muted); line-height: 1.55; flex-grow: 1;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.card-foot  { display: flex; align-items: center; justify-content: space-between; margin-top: auto }
.card-link  {
  font-size: .78rem; font-weight: 500;
  color: color-mix(in srgb, var(--cat) 90%, #fff);
  text-decoration: none; transition: opacity .15s;
}
.card-link:hover { opacity: .75 }
.card-rt { font-size: .7rem; color: var(--dim) }

/* ── Badges ── */
.pill {
  display: inline-block; font-size: .66rem; font-weight: 700; letter-spacing: .04em;
  padding: .12rem .48rem; border-radius: 5px; border: 1px solid; text-transform: uppercase;
}
.badge-new {
  display: inline-block; font-size: .6rem; font-weight: 700; letter-spacing: .06em;
  padding: .12rem .45rem; border-radius: 5px; text-transform: uppercase;
  background: rgba(34,197,94,.18); color: #22c55e; border: 1px solid rgba(34,197,94,.35);
}
.badge-today {
  display: inline-block; font-size: .6rem; font-weight: 700; letter-spacing: .06em;
  padding: .12rem .45rem; border-radius: 5px; text-transform: uppercase;
  background: rgba(251,191,36,.14); color: #fbbf24; border: 1px solid rgba(251,191,36,.32);
}

/* ── How it works ── */
.how-section {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 18px; padding: 1.75rem 2.25rem; margin-bottom: 2.5rem;
}
.how-title {
  font-family: 'Space Grotesk', sans-serif; font-size: 1rem; font-weight: 600;
  margin-bottom: 1.2rem; display: flex; align-items: center; gap: .5rem;
}
.how-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px,1fr)); gap: 1rem }
.how-card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1rem 1.1rem;
}
.how-icon  { font-size: 1.5rem; margin-bottom: .5rem }
.how-label { font-size: .87rem; font-weight: 600; margin-bottom: .28rem }
.how-desc  { font-size: .77rem; color: var(--muted); line-height: 1.5 }
code { font-size: .74rem; background: rgba(255,255,255,.08); padding: .08rem .3rem; border-radius: 3px }

/* ── Stats bar ── */
.stats-bar {
  max-width: 1180px; margin: 0 auto;
  padding: .75rem 1.5rem;
  display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap;
  border-top: 1px solid var(--border);
  font-size: .77rem; color: var(--muted);
}
.stat-item { display: flex; align-items: center; gap: .35rem }
.stat-dot  { width: 6px; height: 6px; border-radius: 50%; background: var(--c, #6b7280) }

/* ── No-results ── */
.no-results {
  display: none; text-align: center; padding: 2.5rem 1rem; color: var(--muted);
}
.no-results.visible { display: block }
.no-results-icon { font-size: 2.5rem; margin-bottom: .75rem }

/* ── Footer ── */
.site-footer {
  background: var(--surface); border-top: 1px solid var(--border);
  padding: 2rem 1.5rem; margin-top: 2rem;
}
.footer-inner {
  max-width: 1180px; margin: 0 auto;
  display: flex; flex-direction: column; align-items: center; gap: 1rem; text-align: center;
}
.footer-brand {
  font-family: 'Space Grotesk', sans-serif; font-size: 1.1rem; font-weight: 700;
  background: linear-gradient(135deg,#a78bfa,#38bdf8);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.footer-links { display: flex; gap: 1.3rem; flex-wrap: wrap; justify-content: center }
.footer-links a { font-size: .82rem; color: var(--muted); text-decoration: none }
.footer-links a:hover { color: var(--text) }
.footer-sources {
  display: flex; gap: .45rem; flex-wrap: wrap; justify-content: center;
  font-size: .74rem; color: var(--dim);
}
.footer-sources span::after { content: '·'; margin-left: .45rem }
.footer-sources span:last-child::after { content: '' }
.footer-note { font-size: .74rem; color: var(--dim); line-height: 1.6 }

/* ── Scroll-to-top ── */
.scroll-top {
  position: fixed; bottom: 1.5rem; right: 1.5rem; z-index: 200;
  background: rgba(13,13,36,.9); border: 1px solid rgba(167,139,250,.28);
  color: #a78bfa; width: 40px; height: 40px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem; text-decoration: none; cursor: pointer;
  backdrop-filter: blur(10px); box-shadow: 0 4px 14px rgba(0,0,0,.32);
  transition: background .2s, transform .2s, opacity .2s;
  opacity: 0;
}
.scroll-top:hover { background: rgba(99,102,241,.25); transform: translateY(-2px) }

/* ── Empty state ── */
.empty-state { text-align: center; padding: 4rem 1rem; color: var(--muted) }
.empty-icon  { font-size: 3rem; margin-bottom: 1rem }

/* ── Responsive ── */
@media (max-width: 780px) {
  .featured-card { padding: 1.6rem 1.5rem }
  main { padding: 1.25rem 1rem }
  .cat-nav, .search-wrap { padding-left: 1rem; padding-right: 1rem }
  .how-section { padding: 1.4rem 1.25rem }
  .stats-bar { padding: .65rem 1rem }
}
@media (max-width: 500px) {
  .card-grid { grid-template-columns: 1fr }
  .header-date { display: none }
}
"""

# ─── JavaScript ──────────────────────────────────────────────────────────────

PAGE_JS = r"""
(function () {
  var activeCat = 'all';

  // ── Category filter ──
  var pills    = document.querySelectorAll('.nav-pill[data-cat]');
  var sections = document.querySelectorAll('.cat-section');

  pills.forEach(function (pill) {
    pill.addEventListener('click', function (e) {
      e.preventDefault();
      var cat = pill.dataset.cat;

      if (cat === 'all' || activeCat === cat) {
        activeCat = 'all';
        pills.forEach(function (p) { p.classList.toggle('active', p.dataset.cat === 'all'); });
        sections.forEach(function (s) { s.removeAttribute('hidden'); });
      } else {
        activeCat = cat;
        pills.forEach(function (p) { p.classList.toggle('active', p.dataset.cat === cat); });
        sections.forEach(function (s) {
          if (s.id === cat) s.removeAttribute('hidden');
          else              s.setAttribute('hidden', '');
        });
      }

      // scroll to section
      if (activeCat !== 'all') {
        var target = document.getElementById(activeCat);
        if (target) { target.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
      }
    });
  });

  // ── Search ──
  var searchInput = document.getElementById('search-input');
  var searchClear = document.getElementById('search-clear');
  var noResults   = document.getElementById('no-results');

  function doSearch () {
    var q = searchInput ? searchInput.value.toLowerCase().trim() : '';
    var visible = 0;

    document.querySelectorAll('.card').forEach(function (card) {
      if (!q) {
        card.removeAttribute('hidden');
        visible++;
        return;
      }
      var title = card.dataset.title || '';
      var desc  = card.dataset.desc  || '';
      if (title.includes(q) || desc.includes(q)) {
        card.removeAttribute('hidden');
        visible++;
      } else {
        card.setAttribute('hidden', '');
      }
    });

    // Show all sections when searching (to show results across categories)
    if (q) {
      sections.forEach(function (s) { s.removeAttribute('hidden'); });
      pills.forEach(function (p) { p.classList.toggle('active', p.dataset.cat === 'all'); });
      activeCat = 'all';
    }

    if (noResults) {
      noResults.classList.toggle('visible', q.length > 0 && visible === 0);
    }
    if (searchClear) {
      searchClear.classList.toggle('visible', q.length > 0);
    }
  }

  if (searchInput) {
    searchInput.addEventListener('input', doSearch);
    searchInput.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { searchInput.value = ''; doSearch(); searchInput.blur(); }
    });
  }
  if (searchClear) {
    searchClear.addEventListener('click', function () {
      searchInput.value = ''; doSearch(); searchInput.focus();
    });
  }

  // ── Keyboard shortcut: "/" to focus search ──
  document.addEventListener('keydown', function (e) {
    if (e.key === '/' && e.target.tagName !== 'INPUT') {
      e.preventDefault();
      if (searchInput) { searchInput.focus(); }
    }
  });

  // ── Scroll-to-top button ──
  var scrollBtn = document.querySelector('.scroll-top');
  if (scrollBtn) {
    window.addEventListener('scroll', function () {
      scrollBtn.style.opacity = window.scrollY > 500 ? '1' : '0';
    }, { passive: true });
  }
})();
"""

# ─── Full page ───────────────────────────────────────────────────────────────

def full_page(featured: Optional[Dict],
              sections: Dict[str, List[Dict]],
              issue: int,
              generated: datetime) -> str:

    now_str  = generated.strftime("%B %d, %Y")
    gen_iso  = generated.strftime("%Y-%m-%dT%H:%M:%SZ")
    total    = sum(len(v) for v in sections.values())
    src_set  = sorted({a["source"] for v in sections.values() for a in v})

    featured_block  = featured_html(featured) if featured else ""
    cat_order       = list(CATEGORIES.keys())
    active_cats     = [c for c in cat_order if sections.get(c)]
    sections_html   = "".join(section_html(cat, sections[cat]) for cat in active_cats)

    if not featured_block and not sections_html:
        sections_html = '''
  <div class="empty-state">
    <div class="empty-icon">🤖</div>
    <p>No articles fetched yet — the first workflow run will populate this page.</p>
  </div>'''

    nav_block = nav_html(active_cats) if active_cats else ""

    stats_items = "".join(
        f'<span class="stat-item">'
        f'<span class="stat-dot" style="--c:{CATEGORIES[c]["color"]}"></span>'
        f'{h(CATEGORIES[c]["icon"])} {len(sections[c])} {h(CATEGORIES[c]["label"])}'
        f'</span>'
        for c in active_cats if sections.get(c)
    )
    stats_block = f'<div class="stats-bar">{stats_items}<span style="margin-left:auto">⚡ Auto-updated daily</span></div>'

    sources_pills = "".join(f'<span>{h(s)}</span>' for s in src_set[:14])

    how_section = f"""
  <section class="how-section">
    <div class="how-title">⚙️ How AI Pulse Works</div>
    <div class="how-grid">
      <div class="how-card">
        <div class="how-icon">📡</div>
        <div class="how-label">8+ Live Sources</div>
        <div class="how-desc">RSS feeds from TechCrunch, VentureBeat, The Verge, Wired, IEEE Spectrum &amp; MIT Tech Review, plus arXiv papers and HackerNews via Algolia API.</div>
      </div>
      <div class="how-card">
        <div class="how-icon">🗂️</div>
        <div class="how-label">Auto Classification</div>
        <div class="how-desc">Each article is matched against keyword sets for Research, Agents, Products, Industry and Open Source. URL &amp; title fingerprints remove duplicates.</div>
      </div>
      <div class="how-card">
        <div class="how-icon">📊</div>
        <div class="how-label">Recency Ranking</div>
        <div class="how-desc">A composite score weighs freshness (exponential decay), source authority, and HackerNews engagement to surface the most impactful stories first.</div>
      </div>
      <div class="how-card">
        <div class="how-icon">⚡</div>
        <div class="how-label">Zero-Infra Deploy</div>
        <div class="how-desc">GitHub Actions runs <code>fetch_news.py</code> every morning at 07:00 UTC, commits the new <code>docs/index.html</code>, and GitHub Pages serves it instantly.</div>
      </div>
    </div>
  </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Pulse — Daily AI News Digest · Issue #{issue}</title>
  <meta name="description" content="Daily curated AI news: research breakthroughs, AI agents, new products and industry — Issue #{issue}, {now_str}">
  <meta property="og:title"       content="AI Pulse — Issue #{issue} · {now_str}">
  <meta property="og:description" content="Daily curated AI news digest covering research, agents, products and industry. Auto-generated every morning.">
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
    <div class="search-wrap">
      <span class="search-icon">🔍</span>
      <input id="search-input" class="search-input" type="search"
             placeholder="Search articles… (press / to focus)" autocomplete="off" spellcheck="false">
      <button id="search-clear" class="search-clear" aria-label="Clear search">✕</button>
    </div>
    {nav_block}
  </header>

  <main>
    {featured_block}
    {how_section}
    {sections_html}
    <div id="no-results" class="no-results">
      <div class="no-results-icon">🔎</div>
      <p>No articles match your search. Try a different keyword.</p>
    </div>
  </main>

  {stats_block}

  <footer class="site-footer">
    <div class="footer-inner">
      <div class="footer-brand">⚡ AI Pulse</div>
      <div class="footer-links">
        <a href="https://github.com/oeway/ai-news-channel" target="_blank" rel="noopener">GitHub</a>
        <a href="https://arxiv.org/list/cs.AI/recent"       target="_blank" rel="noopener">arXiv CS.AI</a>
        <a href="https://news.ycombinator.com"              target="_blank" rel="noopener">HackerNews</a>
        <a href="https://huggingface.co"                    target="_blank" rel="noopener">Hugging Face</a>
      </div>
      <div class="footer-sources">{sources_pills}</div>
      <div class="footer-note">
        Auto-generated from {len(src_set)} sources · {total} articles · Updated {now_str}<br>
        <time datetime="{gen_iso}">Generated at {gen_iso} UTC</time>
      </div>
    </div>
  </footer>

</div>
<a class="scroll-top" href="#" aria-label="Back to top">↑</a>
<script>{PAGE_JS}</script>
</body>
</html>"""

# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    print("⚡ AI Pulse Newsletter Generator", flush=True)
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

    print("\n[4/4] Rendering HTML…", flush=True)
    generated = datetime.now(timezone.utc)
    html_out  = full_page(featured, sections, issue, generated)
    OUTPUT.write_text(html_out, encoding="utf-8")
    save_issue(issue)

    print(f"\n✅  Written → {OUTPUT}", flush=True)
    print(f"    Issue #{issue} · {total} articles · {generated.strftime('%Y-%m-%dT%H:%M:%SZ')}", flush=True)


if __name__ == "__main__":
    main()
