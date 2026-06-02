#!/usr/bin/env python3
"""
AI Pulse Newsletter Generator v3
Fetches the latest AI news from RSS feeds, HackerNews and arXiv,
then renders a beautiful single-file HTML newsletter in docs/index.html.
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
    print("Error: feedparser not installed.  Run: pip install feedparser", file=sys.stderr)
    sys.exit(1)

# ─── Paths ───────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR   = SCRIPT_DIR.parent
DOCS_DIR   = ROOT_DIR / "docs"
OUTPUT     = DOCS_DIR / "index.html"
STATE_FILE = DOCS_DIR / "state.json"

# ─── News sources ────────────────────────────────────────────────────────────

RSS_FEEDS = [
    # Tech news
    {"url": "https://techcrunch.com/category/artificial-intelligence/feed/",
     "source": "TechCrunch",    "color": "#22c55e"},
    {"url": "https://venturebeat.com/category/ai/feed/",
     "source": "VentureBeat",   "color": "#f97316"},
    {"url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
     "source": "The Verge",     "color": "#e11d48"},
    {"url": "https://www.wired.com/feed/category/artificial-intelligence/latest/rss",
     "source": "Wired",         "color": "#818cf8"},
    # Deeper tech / engineering
    {"url": "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss",
     "source": "IEEE Spectrum",  "color": "#0ea5e9"},
    {"url": "https://www.technologyreview.com/feed/",
     "source": "MIT Tech Review","color": "#a78bfa"},
    # Google News AI aggregation (broad, less likely to block)
    {"url": "https://news.google.com/rss/search?q=artificial+intelligence+AI&hl=en-US&gl=US&ceid=US:en",
     "source": "Google News",    "color": "#34d399"},
    {"url": "https://news.google.com/rss/search?q=AI+agents+LLM&hl=en-US&gl=US&ceid=US:en",
     "source": "Google News",    "color": "#34d399"},
    # AI-specific aggregators
    {"url": "https://www.artificialintelligence-news.com/feed/",
     "source": "AI News",        "color": "#f472b6"},
    {"url": "https://syncedreview.com/feed/",
     "source": "Synced",         "color": "#fb923c"},
]

HN_API  = "https://hn.algolia.com/api/v1/search_by_date"
HN_TAGS = [
    "artificial intelligence", "AI agent", "large language model",
    "machine learning", "LLM", "GPT", "Claude AI",
]

ARXIV_API   = "https://export.arxiv.org/api/query"
ARXIV_QUERY = "cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.NE"

# ─── Categories ──────────────────────────────────────────────────────────────

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
            "breakthrough", "novel", "propose", "sota", "state-of-the-art",
        ],
    },
    "agents": {
        "label": "AI Agents & Automation",
        "icon":  "🤖",
        "color": "#c084fc",
        "keywords": [
            "agent", "autonomous", "agentic", "multi-agent", "planning", "memory",
            "tool use", "function call", "workflow", "automation", "copilot",
            "computer use", "browse", "execute", "retrieval", "rag", "orchestrat",
            "self-improv", "task complet", "action", "swe-bench", "devin",
        ],
    },
    "products": {
        "label": "New Products & Releases",
        "icon":  "🚀",
        "color": "#60a5fa",
        "keywords": [
            "launch", "release", "introduc", "announc", "unveil", "new", "gpt",
            "claude", "gemini", "llama", "mistral", "update", "feature", "api",
            "version", "preview", "beta", "availab", "product", "app", "platform",
            "service", "plugin", "integrat", "model release",
        ],
    },
    "industry": {
        "label": "Industry & Business",
        "icon":  "💼",
        "color": "#4ade80",
        "keywords": [
            "funding", "million", "billion", "acqui", "ceo", "hire", "policy",
            "regulat", "invest", "startup", "openai", "google", "microsoft", "meta",
            "nvidia", "amazon", "apple", "partnership", "deal", "market", "revenue",
            "valuat", "ipo", "lawsuit", "safety", "govern", "regulation",
        ],
    },
    "open_source": {
        "label": "Open Source & Community",
        "icon":  "🌐",
        "color": "#fb923c",
        "keywords": [
            "open source", "open-source", "github", "hugging face", "huggingface",
            "llama", "open weight", "open model", "community", "contrib", "fork",
            "mit license", "apache", "open access", "weights", "permissive",
            "ollama", "lm studio", "gguf", "quantiz",
        ],
    },
}

DEFAULT_CATEGORY    = "industry"
MAX_PER_CATEGORY    = 6
MAX_FEATURED_AGE_H  = 96   # featured must be < 4 days old

# ─── HTTP ─────────────────────────────────────────────────────────────────────

UA = "Mozilla/5.0 (compatible; AI-Pulse-Bot/3.0; +https://github.com/oeway/ai-news-channel)"

def fetch(url: str, timeout: int = 25, retries: int = 2) -> Optional[str]:
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            print(f"  [!] HTTP {e.code} {url[:70]}", file=sys.stderr)
            return None
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
                continue
            print(f"  [!] fetch {url[:70]}: {e}", file=sys.stderr)
            return None
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
        for fmt in (
            "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z",
            "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT",
            "%a, %d %b %Y %H:%M:%S +0000", "%Y-%m-%d",
        ):
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
        hrs = delta.seconds // 3600
        if hrs == 0:
            mins = delta.seconds // 60
            return f"{mins}m ago" if mins > 0 else "Just now"
        return f"{hrs}h ago"
    if delta.days == 1:  return "Yesterday"
    if delta.days < 7:   return f"{delta.days}d ago"
    return dt.strftime("%b %d, %Y")

def reading_time(text: str) -> int:
    words = len(text.split())
    return max(1, round(words / 200))

# ─── Fetchers ─────────────────────────────────────────────────────────────────

def fetch_rss(cfg: Dict) -> List[Dict]:
    print(f"  RSS  {cfg['source']}…", flush=True)
    raw = fetch(cfg["url"])
    if not raw:
        return []
    try:
        feed = feedparser.parse(raw)
        articles = []
        for e in feed.entries[:25]:
            # Description
            desc = ""
            for attr in ("summary", "description", "content"):
                val = getattr(e, attr, None)
                if isinstance(val, list):
                    val = val[0].get("value", "") if val else ""
                if val:
                    desc = re.sub(r"<[^>]+>", " ", val)
                    desc = re.sub(r"\s+", " ", desc).strip()[:500]
                    break
            # Date
            dt = None
            for attr in ("published_parsed", "updated_parsed", "created_parsed"):
                dt = to_dt(getattr(e, attr, None))
                if dt:
                    break
            title = getattr(e, "title", "").strip()
            url   = getattr(e, "link",  "").strip()
            if not title or not url:
                continue
            articles.append({
                "title":        title,
                "url":          url,
                "desc":         desc,
                "source":       cfg["source"],
                "source_color": cfg["color"],
                "date":         dt,
                "category":     None,
            })
        print(f"     → {len(articles)} items", flush=True)
        return articles
    except Exception as ex:
        print(f"  [!] parse {cfg['source']}: {ex}", file=sys.stderr)
        return []


def fetch_hn() -> List[Dict]:
    print("  HN   Algolia search…", flush=True)
    seen: set  = set()
    articles: List[Dict] = []
    for q in HN_TAGS[:5]:
        url = (f"{HN_API}?"
               f"{urllib.parse.urlencode({'query': q, 'tags': 'story', 'hitsPerPage': 15})}")
        raw = fetch(url)
        if not raw:
            continue
        try:
            for hit in json.loads(raw).get("hits", []):
                oid = hit.get("objectID", "")
                if oid in seen:
                    continue
                seen.add(oid)
                title = hit.get("title", "").strip()
                if not title:
                    continue
                story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={oid}"
                pts   = hit.get("points",       0)
                cmnts = hit.get("num_comments", 0)
                desc  = f"🔥 {pts} points · {cmnts} comments on Hacker News"
                dt    = to_dt(hit.get("created_at_i"))
                articles.append({
                    "title":        title,
                    "url":          story_url,
                    "desc":         desc,
                    "source":       "HackerNews",
                    "source_color": "#f97316",
                    "date":         dt,
                    "category":     None,
                })
        except Exception as ex:
            print(f"  [!] HN parse: {ex}", file=sys.stderr)
        time.sleep(0.4)
    print(f"     → {len(articles)} items", flush=True)
    return articles


def fetch_arxiv() -> List[Dict]:
    print("  arXiv papers…", flush=True)
    url = (
        f"{ARXIV_API}?search_query={ARXIV_QUERY}"
        "&start=0&max_results=25&sortBy=submittedDate&sortOrder=descending"
    )
    raw = fetch(url)
    if not raw:
        return []
    try:
        ns   = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(raw)
        arts = []
        for entry in root.findall("a:entry", ns):
            title = (entry.findtext("a:title",   "", ns) or "").replace("\n", " ").strip()
            summ  = (entry.findtext("a:summary", "", ns) or "").replace("\n", " ").strip()[:400]
            link  = (entry.findtext("a:id",      "", ns) or "").strip()
            pub   = entry.findtext("a:published", "", ns)
            cats  = [c.get("term", "") for c in entry.findall("a:category", ns)]
            desc  = f"[{' · '.join(cats[:3])}] {summ}"
            if not title or not link:
                continue
            arts.append({
                "title":        title,
                "url":          link,
                "desc":         desc,
                "source":       "arXiv",
                "source_color": "#a78bfa",
                "date":         to_dt(pub),
                "category":     "research",
            })
        print(f"     → {len(arts)} papers", flush=True)
        return arts
    except Exception as ex:
        print(f"  [!] arXiv parse: {ex}", file=sys.stderr)
        return []

# ─── Classify / Score / Dedup ─────────────────────────────────────────────────

def classify(a: Dict) -> str:
    if a.get("category"):
        return a["category"]
    text   = (a.get("title", "") + " " + a.get("desc", "")).lower()
    scores = {
        cat: sum(1 for kw in cfg["keywords"] if kw in text)
        for cat, cfg in CATEGORIES.items()
    }
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else DEFAULT_CATEGORY


def score(a: Dict) -> float:
    s  = 0.0
    dt = a.get("date")
    if dt:
        age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        s += max(0.0, 10.0 - age_h * 0.06)   # decay over ~7 days
    source_bonus = {
        "arXiv": 2.5, "IEEE Spectrum": 2.0, "MIT Tech Review": 1.9,
        "TechCrunch": 1.6, "VentureBeat": 1.4, "Wired": 1.4,
        "The Verge": 1.2, "HackerNews": 1.0,
        "Google News": 1.1, "AI News": 1.1, "Synced": 1.2,
    }
    s += source_bonus.get(a.get("source", ""), 1.0)
    tl = len(a.get("title", ""))
    if 40 < tl < 130:
        s += 0.5
    return s


def dedup(articles: List[Dict]) -> List[Dict]:
    seen_urls:   set = set()
    seen_titles: set = set()
    out:  List[Dict] = []
    for a in articles:
        url  = re.sub(r"\?.*$", "", a.get("url", "")).rstrip("/")
        tkey = hashlib.md5(a.get("title", "").lower()[:60].encode()).hexdigest()
        if url in seen_urls or tkey in seen_titles:
            continue
        if url:
            seen_urls.add(url)
        seen_titles.add(tkey)
        out.append(a)
    return out

# ─── Issue counter ────────────────────────────────────────────────────────────

def load_issue() -> int:
    if STATE_FILE.exists():
        try:
            return int(json.loads(STATE_FILE.read_text()).get("issue", 0))
        except Exception:
            pass
    return 0


def save_issue(n: int) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"issue": n}, indent=2))

# ─── HTML helpers ─────────────────────────────────────────────────────────────

SOURCE_COLORS: Dict[str, str] = {
    "TechCrunch":     "#22c55e",
    "VentureBeat":    "#f97316",
    "The Verge":      "#e11d48",
    "Wired":          "#818cf8",
    "IEEE Spectrum":  "#0ea5e9",
    "MIT Tech Review":"#a78bfa",
    "arXiv":          "#a78bfa",
    "HackerNews":     "#f97316",
    "Google News":    "#34d399",
    "AI News":        "#f472b6",
    "Synced":         "#fb923c",
}


def pill(source: str, color: str = "") -> str:
    c = color or SOURCE_COLORS.get(source, "#6b7280")
    return (
        f'<span class="pill" style="background:{c}22;color:{c};border-color:{c}55">'
        f'{h(source)}</span>'
    )


def freshness_badge(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    if age_h < 6:
        return '<span class="badge badge-hot">🔥 Hot</span>'
    if age_h < 24:
        return '<span class="badge badge-new">✦ New</span>'
    if age_h < 72:
        return '<span class="badge badge-recent">↑ Recent</span>'
    return ""


def card_html(a: Dict, cat_color: str) -> str:
    title   = h(a.get("title", "Untitled"))
    url_s   = h(a.get("url",   "#"))
    desc    = h((a.get("desc") or "")[:280])
    src     = a.get("source", "")
    src_c   = a.get("source_color") or SOURCE_COLORS.get(src, "#6b7280")
    age     = age_str(a.get("date"))
    badge   = freshness_badge(a.get("date"))
    rt      = reading_time(a.get("title","") + " " + a.get("desc",""))
    return f"""
      <article class="card" style="--cat:{cat_color}" data-cat="{h(a.get('category',''))}">
        <div class="card-top">
          {pill(src, src_c)}
          <div class="card-meta-right">
            {badge}
            <span class="card-age">{h(age)}</span>
          </div>
        </div>
        <h3 class="card-title"><a href="{url_s}" target="_blank" rel="noopener">{title}</a></h3>
        <p class="card-desc">{desc}</p>
        <div class="card-footer">
          <span class="read-time">{rt} min read</span>
          <a class="card-link" href="{url_s}" target="_blank" rel="noopener">Read more ↗</a>
        </div>
      </article>"""


def section_html(cat: str, articles: List[Dict]) -> str:
    if not articles:
        return ""
    cfg    = CATEGORIES[cat]
    color  = cfg["color"]
    items  = articles[:MAX_PER_CATEGORY]
    cards  = "\n".join(card_html(a, color) for a in items)
    count  = len(items)
    return f"""
  <section class="cat-section" id="{cat}" style="--cat:{color}">
    <header class="section-hdr">
      <span class="section-icon">{cfg['icon']}</span>
      <h2 class="section-title">{h(cfg['label'])}</h2>
      <span class="section-count">{count} {('story' if count == 1 else 'stories')}</span>
    </header>
    <div class="card-grid">
      {cards}
    </div>
  </section>"""


def featured_html(a: Dict) -> str:
    title = h(a.get("title", "Untitled"))
    url_s = h(a.get("url",   "#"))
    desc  = h((a.get("desc") or "")[:600])
    src   = a.get("source", "")
    src_c = a.get("source_color") or SOURCE_COLORS.get(src, "#6b7280")
    age   = age_str(a.get("date"))
    badge = freshness_badge(a.get("date"))
    cat   = a.get("category", DEFAULT_CATEGORY)
    cat_c = CATEGORIES.get(cat, {}).get("color", "#8b5cf6")
    cat_l = CATEGORIES.get(cat, {}).get("label", "News")
    cat_i = CATEGORIES.get(cat, {}).get("icon",  "📌")
    return f"""
  <section class="featured-wrap">
    <article class="featured-card">
      <div class="featured-eyebrow">
        <span class="featured-label">✦ Featured Story</span>
        <span class="featured-cat" style="color:{cat_c}">{cat_i} {h(cat_l)}</span>
        {badge}
      </div>
      <h2 class="featured-title">{title}</h2>
      <div class="featured-meta">
        {pill(src, src_c)}
        <span class="featured-age">{h(age)}</span>
      </div>
      <p class="featured-body">{desc}</p>
      <a class="featured-btn" href="{url_s}" target="_blank" rel="noopener">
        Read Full Story ↗
      </a>
    </article>
  </section>"""

# ─── CSS ──────────────────────────────────────────────────────────────────────

PAGE_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0 }

:root {
  --bg:       #07071a;
  --surface:  #0c0c22;
  --card:     #10102a;
  --card-h:   #15153a;
  --border:   rgba(255,255,255,0.07);
  --border-h: rgba(255,255,255,0.14);
  --text:     #e2e8f0;
  --sub:      #94a3b8;
  --muted:    #64748b;
  --dim:      #334155;
}

html { scroll-behavior: smooth }

body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  line-height: 1.6;
  min-height: 100vh;
  font-size: 15px;
}
a { color: inherit; text-decoration: none }

/* ── Ambient background glow ── */
body::before {
  content: '';
  position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background:
    radial-gradient(ellipse 65% 45% at 18%  8%,  rgba(99,102,241,.08) 0%, transparent 70%),
    radial-gradient(ellipse 55% 40% at 82% 88%,  rgba(6,182,212,.06)  0%, transparent 70%),
    radial-gradient(ellipse 40% 30% at 50% 48%,  rgba(139,92,246,.04) 0%, transparent 60%);
}
.page { position: relative; z-index: 1 }

/* ══════════════════════════════════════════
   HEADER
══════════════════════════════════════════ */
.site-header {
  border-bottom: 1px solid var(--border);
  background: linear-gradient(180deg, rgba(12,12,34,.98) 0%, rgba(7,7,26,.92) 100%);
  backdrop-filter: blur(14px);
  position: sticky; top: 0; z-index: 100;
}
.header-inner {
  max-width: 1200px; margin: 0 auto;
  padding: .85rem 1.5rem;
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  flex-wrap: wrap;
}
.brand {
  display: flex; align-items: center; gap: .75rem;
}
.brand-logo { font-size: 1.75rem; line-height: 1 }
.brand-name {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.35rem; font-weight: 700;
  background: linear-gradient(135deg, #a78bfa 0%, #38bdf8 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.brand-tagline { font-size: .71rem; color: var(--muted); margin-top: 1px }

.header-right { display: flex; align-items: center; gap: .75rem; flex-shrink: 0 }
.issue-badge {
  font-size: .72rem; font-weight: 700; letter-spacing: .07em;
  background: linear-gradient(135deg, rgba(167,139,250,.18), rgba(56,189,248,.14));
  border: 1px solid rgba(167,139,250,.32); color: #a78bfa;
  padding: .24rem .72rem; border-radius: 20px;
}
.header-date { font-size: .8rem; color: var(--muted) }
.live-dot {
  display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  background: #22c55e; margin-right: .32rem;
  animation: pulse-dot 2.4s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%,100% { opacity:1;  box-shadow: 0 0 0 0   rgba(34,197,94,.5) }
  50%      { opacity:.7; box-shadow: 0 0 0 5px rgba(34,197,94,0) }
}

/* ── Category nav ── */
.cat-nav {
  max-width: 1200px; margin: 0 auto;
  padding: .85rem 1.5rem;
  display: flex; gap: .45rem; flex-wrap: wrap;
  border-bottom: 1px solid var(--border);
}
.nav-pill {
  font-size: .77rem; font-weight: 500;
  padding: .3rem .8rem; border-radius: 20px;
  border: 1px solid color-mix(in srgb, var(--cat) 30%, transparent);
  color: var(--cat); cursor: pointer; background: transparent;
  transition: background .15s, transform .12s, box-shadow .15s;
  white-space: nowrap;
}
.nav-pill:hover,
.nav-pill.active {
  background: color-mix(in srgb, var(--cat) 14%, transparent);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--cat) 30%, transparent);
  transform: translateY(-1px);
}
.nav-pill.all { --cat: #94a3b8 }

/* ══════════════════════════════════════════
   STATS STRIP
══════════════════════════════════════════ */
.stats-strip {
  max-width: 1200px; margin: 0 auto;
  padding: .65rem 1.5rem;
  display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap;
  border-bottom: 1px solid var(--border);
  font-size: .76rem; color: var(--muted);
}
.stat-item { display: flex; align-items: center; gap: .35rem }
.stat-dot  { width: 6px; height: 6px; border-radius: 50%; background: var(--c, #6b7280) }
.stats-right { margin-left: auto; font-size: .74rem; color: var(--dim) }

/* ══════════════════════════════════════════
   MAIN
══════════════════════════════════════════ */
main { max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem }

/* ══════════════════════════════════════════
   FEATURED
══════════════════════════════════════════ */
.featured-wrap { margin-bottom: 2.75rem }
.featured-card {
  background: linear-gradient(135deg, #130f38 0%, #0e0e2c 55%, #0a1428 100%);
  border: 1px solid rgba(167,139,250,.24);
  border-radius: 20px; padding: 2.25rem 2.75rem;
  position: relative; overflow: hidden;
}
.featured-card::before {
  content: ''; position: absolute; top: -100px; right: -100px;
  width: 420px; height: 420px; border-radius: 50%; pointer-events: none;
  background: radial-gradient(circle, rgba(99,102,241,.14) 0%, transparent 65%);
}
.featured-card::after {
  content: ''; position: absolute; bottom: -50px; left: 15%;
  width: 300px; height: 300px; border-radius: 50%; pointer-events: none;
  background: radial-gradient(circle, rgba(6,182,212,.07) 0%, transparent 65%);
}
.featured-eyebrow {
  display: flex; align-items: center; gap: .9rem; margin-bottom: 1.1rem;
  flex-wrap: wrap; position: relative; z-index: 1;
}
.featured-label {
  font-size: .71rem; font-weight: 700; letter-spacing: .11em;
  color: #a78bfa; text-transform: uppercase;
}
.featured-cat { font-size: .78rem; font-weight: 500 }
.featured-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: clamp(1.3rem, 3.2vw, 2rem); font-weight: 700; line-height: 1.28;
  margin-bottom: 1rem; position: relative; z-index: 1;
}
.featured-meta {
  display: flex; align-items: center; gap: .75rem;
  margin-bottom: 1.1rem; flex-wrap: wrap; position: relative; z-index: 1;
}
.featured-age { font-size: .8rem; color: var(--muted) }
.featured-body {
  color: var(--sub); line-height: 1.75; margin-bottom: 1.65rem;
  max-width: 720px; position: relative; z-index: 1;
}
.featured-btn {
  display: inline-flex; align-items: center; gap: .4rem;
  background: linear-gradient(135deg, #6d28d9, #4f46e5);
  color: #fff; padding: .62rem 1.4rem; border-radius: 10px;
  font-size: .88rem; font-weight: 600;
  box-shadow: 0 4px 18px rgba(99,102,241,.38);
  transition: opacity .2s, transform .15s;
  position: relative; z-index: 1;
}
.featured-btn:hover { opacity: .88; transform: translateY(-1px) }

/* ══════════════════════════════════════════
   SECTIONS
══════════════════════════════════════════ */
.cat-section { margin-bottom: 3rem }

.section-hdr {
  display: flex; align-items: center; gap: .6rem;
  margin-bottom: 1.3rem; padding-bottom: .7rem;
  border-bottom: 2px solid color-mix(in srgb, var(--cat) 30%, transparent);
}
.section-icon  { font-size: 1.25rem }
.section-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.1rem; font-weight: 700; color: var(--cat);
}
.section-count {
  margin-left: auto; font-size: .72rem; color: var(--muted);
  background: color-mix(in srgb, var(--cat) 10%, var(--card));
  border: 1px solid color-mix(in srgb, var(--cat) 22%, transparent);
  padding: .14rem .55rem; border-radius: 12px;
}

/* ══════════════════════════════════════════
   CARD GRID
══════════════════════════════════════════ */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1rem;
}

/* ══════════════════════════════════════════
   CARD
══════════════════════════════════════════ */
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px; padding: 1.15rem 1.25rem;
  display: flex; flex-direction: column; gap: .6rem;
  transition: border-color .2s, background .2s, transform .2s, box-shadow .2s;
  position: relative; overflow: hidden;
}
.card::before {
  content: ''; position: absolute;
  top: 0; left: 0; right: 0; height: 2px;
  background: var(--cat, #8b5cf6);
  opacity: 0; transition: opacity .2s;
}
.card:hover {
  border-color: color-mix(in srgb, var(--cat) 40%, transparent);
  background: var(--card-h);
  transform: translateY(-3px);
  box-shadow:
    0 10px 30px rgba(0,0,0,.38),
    0 0 0 1px color-mix(in srgb, var(--cat) 14%, transparent);
}
.card:hover::before { opacity: 1 }

.card-top {
  display: flex; align-items: center; justify-content: space-between; gap: .4rem;
  flex-wrap: wrap;
}
.card-meta-right { display: flex; align-items: center; gap: .4rem }
.card-age  { font-size: .71rem; color: var(--muted) }

.card-title {
  font-size: .93rem; font-weight: 600; line-height: 1.46;
}
.card-title a { color: var(--text); transition: color .15s }
.card-title a:hover { color: var(--cat, #a78bfa) }

.card-desc {
  font-size: .81rem; color: var(--muted); line-height: 1.56; flex-grow: 1;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-footer {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: auto; padding-top: .35rem;
  border-top: 1px solid var(--border);
}
.read-time {
  font-size: .7rem; color: var(--dim);
}
.card-link {
  font-size: .78rem; font-weight: 500;
  color: color-mix(in srgb, var(--cat) 90%, #fff);
  transition: opacity .15s;
}
.card-link:hover { opacity: .72 }

/* ── Source pill ── */
.pill {
  display: inline-block; font-size: .67rem; font-weight: 700;
  letter-spacing: .04em; padding: .14rem .52rem;
  border-radius: 5px; border: 1px solid; text-transform: uppercase;
  white-space: nowrap;
}

/* ── Freshness badges ── */
.badge {
  display: inline-block; font-size: .66rem; font-weight: 700;
  letter-spacing: .03em; padding: .12rem .46rem; border-radius: 5px;
  white-space: nowrap;
}
.badge-hot    { background: rgba(249,115, 22,.18); color: #fb923c; border: 1px solid rgba(249,115,22,.35) }
.badge-new    { background: rgba( 34,197, 94,.15); color: #4ade80; border: 1px solid rgba(34,197,94,.3) }
.badge-recent { background: rgba(148,163,184,.10); color: #94a3b8; border: 1px solid rgba(148,163,184,.22) }

/* ══════════════════════════════════════════
   FOOTER
══════════════════════════════════════════ */
.site-footer {
  background: var(--surface);
  border-top: 1px solid var(--border);
  padding: 2.25rem 1.5rem; margin-top: 3rem;
}
.footer-inner {
  max-width: 1200px; margin: 0 auto;
  display: flex; flex-direction: column; align-items: center;
  gap: 1rem; text-align: center;
}
.footer-brand {
  font-family: 'Space Grotesk', sans-serif; font-size: 1.1rem; font-weight: 700;
  background: linear-gradient(135deg, #a78bfa, #38bdf8);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.footer-links { display: flex; gap: 1.25rem; flex-wrap: wrap; justify-content: center }
.footer-links a { font-size: .82rem; color: var(--muted) }
.footer-links a:hover { color: var(--text) }
.footer-sources {
  font-size: .74rem; color: var(--dim);
  display: flex; gap: .5rem; flex-wrap: wrap; justify-content: center;
}
.footer-sources span::after { content: '·'; margin-left: .5rem }
.footer-sources span:last-child::after { content: '' }
.footer-note { font-size: .74rem; color: var(--dim); line-height: 1.7 }

/* ── Scroll-to-top ── */
.scroll-top {
  position: fixed; bottom: 1.5rem; right: 1.5rem; z-index: 200;
  background: rgba(12,12,34,.92); border: 1px solid rgba(167,139,250,.3);
  color: #a78bfa; width: 40px; height: 40px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem; backdrop-filter: blur(10px);
  box-shadow: 0 4px 14px rgba(0,0,0,.35);
  transition: background .2s, transform .2s, opacity .2s;
  opacity: 0; pointer-events: none;
}
.scroll-top.visible { opacity: 1; pointer-events: auto }
.scroll-top:hover { background: rgba(99,102,241,.25); transform: translateY(-2px) }

/* ── Empty state ── */
.empty-state {
  text-align: center; padding: 4rem 1rem; color: var(--muted);
}
.empty-icon { font-size: 3rem; margin-bottom: 1rem }

/* ── Responsive ── */
@media (max-width: 800px) {
  .featured-card { padding: 1.65rem 1.5rem }
  main { padding: 1.5rem 1rem }
  .cat-nav { padding: .75rem 1rem }
  .stats-strip { padding: .6rem 1rem }
}
@media (max-width: 520px) {
  .card-grid { grid-template-columns: 1fr }
  .header-date { display: none }
  .featured-card { padding: 1.25rem 1.1rem }
}
"""

# ─── Full page ────────────────────────────────────────────────────────────────

def full_page(
    featured: Optional[Dict],
    sections: Dict[str, List[Dict]],
    issue: int,
    generated: datetime,
) -> str:
    now_str  = generated.strftime("%B %d, %Y")
    gen_iso  = generated.strftime("%Y-%m-%dT%H:%M:%SZ")
    total    = sum(len(v) for v in sections.values())
    src_set  = sorted({a["source"] for v in sections.values() for a in v})
    cat_order = list(CATEGORIES.keys())
    active   = [c for c in cat_order if sections.get(c)]

    featured_block = featured_html(featured) if featured else ""

    sections_html = ""
    for cat in active:
        sections_html += section_html(cat, sections[cat])

    if not featured_block and not sections_html:
        sections_html = """
  <div class="empty-state">
    <div class="empty-icon">🤖</div>
    <p>No articles fetched yet — the daily workflow will populate this shortly.</p>
  </div>"""

    # Nav pills
    nav_pills = '<a class="nav-pill all active" href="#" onclick="filterCat(event,\'all\')">All</a>'
    for cat in active:
        cfg = CATEGORIES[cat]
        nav_pills += (
            f'<a class="nav-pill" href="#{cat}" '
            f'style="--cat:{cfg["color"]}" '
            f'onclick="filterCat(event,\'{cat}\')">'
            f'{cfg["icon"]}&thinsp;{h(cfg["label"])}</a>'
        )

    # Stats strip
    stats_items = "".join(
        f'<span class="stat-item">'
        f'<span class="stat-dot" style="--c:{CATEGORIES[c]["color"]}"></span>'
        f'{CATEGORIES[c]["icon"]} {len(sections.get(c,[]))} {h(CATEGORIES[c]["label"])}'
        f'</span>'
        for c in active
        if sections.get(c)
    )

    sources_pills = "".join(f"<span>{h(s)}</span>" for s in src_set[:14])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Pulse — Issue #{issue} · {now_str}</title>
  <meta name="description"
        content="Daily curated AI news: research breakthroughs, AI agents, new products, industry — Issue #{issue}, {now_str}.">
  <meta property="og:title"       content="AI Pulse — Issue #{issue} · {now_str}">
  <meta property="og:description" content="Daily AI news digest covering research, agents, products and industry.">
  <meta property="og:type"        content="website">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
  <style>{PAGE_CSS}</style>
</head>
<body>
<div class="page">

  <!-- ══ Header ══ -->
  <header class="site-header">
    <div class="header-inner">
      <a class="brand" href="#">
        <span class="brand-logo">⚡</span>
        <div>
          <div class="brand-name">AI Pulse</div>
          <div class="brand-tagline">Daily AI News Digest</div>
        </div>
      </a>
      <div class="header-right">
        <span class="issue-badge">Issue #{issue}</span>
        <span class="header-date"><span class="live-dot"></span>{now_str}</span>
      </div>
    </div>
    <nav class="cat-nav">
      {nav_pills}
    </nav>
  </header>

  <!-- ══ Stats strip ══ -->
  <div class="stats-strip">
    {stats_items}
    <span class="stats-right">
      ⚡ {total} articles · {len(src_set)} sources · Updated {now_str}
    </span>
  </div>

  <!-- ══ Main ══ -->
  <main id="main-content">
    {featured_block}
    {sections_html}
  </main>

  <!-- ══ Footer ══ -->
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
        Auto-generated from {len(src_set)} sources · {total} articles · {now_str}<br>
        Generated <time datetime="{gen_iso}">{gen_iso}</time> ·
        <a href="https://github.com/oeway/ai-news-channel" target="_blank" rel="noopener"
           style="color:var(--dim)">View source</a>
      </div>
    </div>
  </footer>

</div><!-- .page -->

<a class="scroll-top" href="#" id="scrollTop" aria-label="Back to top">↑</a>

<script>
// ── Category filter ──────────────────────────────────────────────────────────
function filterCat(e, cat) {{
  if (cat !== 'all') e.preventDefault();
  document.querySelectorAll('.nav-pill').forEach(p => p.classList.remove('active'));
  e.currentTarget.classList.add('active');
  const sections = document.querySelectorAll('.cat-section');
  if (cat === 'all') {{
    sections.forEach(s => s.style.display = '');
    const fp = document.querySelector('.featured-wrap');
    if (fp) fp.style.display = '';
  }} else {{
    sections.forEach(s => s.style.display = s.id === cat ? '' : 'none');
    const fp = document.querySelector('.featured-wrap');
    if (fp) fp.style.display = 'none';
    const target = document.getElementById(cat);
    if (target) target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
  }}
}}

// ── Scroll-to-top ────────────────────────────────────────────────────────────
const btn = document.getElementById('scrollTop');
window.addEventListener('scroll', () => {{
  btn.classList.toggle('visible', window.scrollY > 400);
}}, {{ passive: true }});
btn.addEventListener('click', e => {{
  e.preventDefault();
  window.scrollTo({{ top: 0, behavior: 'smooth' }});
}});
</script>
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
        time.sleep(0.2)
    all_articles.extend(fetch_hn())
    all_articles.extend(fetch_arxiv())
    print(f"  Total raw: {len(all_articles)}", flush=True)

    print("\n[2/4] Deduplicating & classifying…", flush=True)
    articles = dedup(all_articles)
    for a in articles:
        a["category"] = classify(a)
    print(f"  After dedup: {len(articles)}", flush=True)

    print("\n[3/4] Scoring & sorting…", flush=True)
    articles.sort(key=score, reverse=True)
    sections: Dict[str, List[Dict]] = {cat: [] for cat in CATEGORIES}
    for a in articles:
        cat = a.get("category", DEFAULT_CATEGORY)
        if cat in sections and len(sections[cat]) < MAX_PER_CATEGORY:
            sections[cat].append(a)

    # Pick featured article: most recent high-scoring item
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
    print(f"  Sections: {', '.join(f'{k}:{len(v)}' for k,v in sections.items() if v)}",
          flush=True)
    print(f"  Total placed: {total}", flush=True)

    print("\n[4/4] Rendering HTML…", flush=True)
    generated = datetime.now(timezone.utc)
    html_out  = full_page(featured, sections, issue, generated)
    OUTPUT.write_text(html_out, encoding="utf-8")
    save_issue(issue)

    print(f"\n✅  Written to {OUTPUT}", flush=True)
    print(f"    Issue #{issue} · {total} articles · {generated.strftime('%Y-%m-%dT%H:%M:%SZ')}")


if __name__ == "__main__":
    main()
