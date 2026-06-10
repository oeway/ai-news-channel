#!/usr/bin/env python3
"""
AI Pulse Newsletter Generator
Fetches the latest AI news from multiple sources and generates a beautiful static HTML newsletter.
"""

import os
import re
import sys
import json
import time
import random
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

# ─── Paths ──────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR   = SCRIPT_DIR.parent
DOCS_DIR   = ROOT_DIR / "docs"
OUTPUT     = DOCS_DIR / "index.html"
STATE_FILE = DOCS_DIR / "state.json"

# ─── Sources ────────────────────────────────────────────────────────────────

RSS_FEEDS = [
    # Tier 1: High-quality AI-focused
    {"url": "https://techcrunch.com/feed/",
     "source": "TechCrunch",    "color": "#22c55e", "filter_ai": True},
    {"url": "https://venturebeat.com/feed/",
     "source": "VentureBeat",   "color": "#f97316", "filter_ai": True},
    {"url": "https://feeds.feedburner.com/venturebeat/SZYF",
     "source": "VentureBeat",   "color": "#f97316", "filter_ai": True},
    {"url": "https://www.theverge.com/rss/index.xml",
     "source": "The Verge",     "color": "#e11d48", "filter_ai": True},
    {"url": "https://www.technologyreview.com/feed/",
     "source": "MIT Tech Review","color": "#a78bfa", "filter_ai": True},
    # Tier 2: Broad tech (filtered for AI)
    {"url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
     "source": "WSJ",           "color": "#3b82f6", "filter_ai": True},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
     "source": "NY Times Tech", "color": "#64748b", "filter_ai": True},
    # Tier 3: AI / ML specialist
    {"url": "https://huggingface.co/blog/feed.xml",
     "source": "HuggingFace",   "color": "#fbbf24", "filter_ai": False},
    {"url": "https://openai.com/blog/rss.xml",
     "source": "OpenAI Blog",   "color": "#10b981", "filter_ai": False},
    {"url": "https://www.deepmind.com/blog/rss.xml",
     "source": "DeepMind",      "color": "#6366f1", "filter_ai": False},
    {"url": "https://bair.berkeley.edu/blog/feed.xml",
     "source": "BAIR Blog",     "color": "#8b5cf6", "filter_ai": False},
    {"url": "https://ai.googleblog.com/feeds/posts/default?alt=rss",
     "source": "Google AI Blog","color": "#4285f4", "filter_ai": False},
    {"url": "https://research.facebook.com/feed/",
     "source": "Meta AI Research","color": "#1877f2","filter_ai": False},
    # Tier 4: Community / Discussion
    {"url": "https://blog.langchain.dev/rss/",
     "source": "LangChain Blog","color": "#f59e0b", "filter_ai": False},
    {"url": "https://lilianweng.github.io/index.xml",
     "source": "Lilian Weng",   "color": "#ec4899", "filter_ai": False},
]

HN_API  = "https://hn.algolia.com/api/v1/search_by_date"
HN_TAGS = [
    "artificial intelligence", "AI agent", "large language model",
    "machine learning", "LLM", "GPT", "Claude", "Gemini",
]

ARXIV_API   = "https://export.arxiv.org/api/query"
ARXIV_QUERY = "cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.NE"

# ─── Categories ─────────────────────────────────────────────────────────────

CATEGORIES: Dict[str, Dict] = {
    "research": {
        "label": "Research & Breakthroughs",
        "icon":  "🔬",
        "color": "#22d3ee",
        "bg":    "rgba(34,211,238,0.07)",
        "glow":  "rgba(34,211,238,0.14)",
        "keywords": [
            "paper", "arxiv", "research", "study", "benchmark", "dataset", "training",
            "pretrain", "fine-tun", "neural", "transformer", "diffusion", "multimodal",
            "evaluation", "algorithm", "architecture", "inference", "reasoning",
            "capability", "scaling", "emergent", "alignment", "rlhf", "reward model",
            "breakthrough", "discovery", "achieve", "state-of-the-art", "sota",
            "science", "university", "lab", "institute", "demo", "token", "attention",
            "mamba", "mixture of experts", "moe", "context length", "vision language",
            "vlm", "sft", "dpo", "rlaif", "synthetic data", "world model",
        ]
    },
    "agents": {
        "label": "AI Agents & Automation",
        "icon":  "🤖",
        "color": "#c084fc",
        "bg":    "rgba(192,132,252,0.07)",
        "glow":  "rgba(192,132,252,0.14)",
        "keywords": [
            "agent", "autonomous", "agentic", "multi-agent", "planning", "memory",
            "tool use", "function call", "workflow", "automation", "copilot",
            "computer use", "browse", "execute", "retrieval", "rag", "orchestrat",
            "self-improv", "task complet", "action", "mcp", "model context protocol",
            "devin", "swe-agent", "autogen", "crewai", "langgraph", "swarm",
            "reasoning agent", "react", "chain-of-thought", "o1", "o3", "r1",
            "code generation", "coding agent", "software engineer", "robot",
        ]
    },
    "products": {
        "label": "New Products & Releases",
        "icon":  "🚀",
        "color": "#60a5fa",
        "bg":    "rgba(96,165,250,0.07)",
        "glow":  "rgba(96,165,250,0.14)",
        "keywords": [
            "launch", "release", "introduc", "announc", "unveil", "new", "gpt",
            "claude", "gemini", "llama", "mistral", "update", "feature", "api",
            "version", "preview", "beta", "availab", "product", "app", "platform",
            "service", "plugin", "integrat", "shipped", "deploy", "roll out",
            "now available", "introduces", "grok", "sora", "dall-e", "midjourney",
            "stable diffusion", "flux", "imagen", "veo", "suno", "udio",
        ]
    },
    "industry": {
        "label": "Industry & Business",
        "icon":  "💼",
        "color": "#4ade80",
        "bg":    "rgba(74,222,128,0.07)",
        "glow":  "rgba(74,222,128,0.14)",
        "keywords": [
            "funding", "million", "billion", "acqui", "ceo", "hire", "policy",
            "regulat", "invest", "startup", "openai", "google", "microsoft", "meta",
            "nvidia", "amazon", "apple", "partnership", "deal", "market", "revenue",
            "valuat", "ipo", "lawsuit", "safety", "govern", "anthropic", "xai",
            "sam altman", "satya", "sundar", "jensen", "cto", "raises", "round",
            "enterprise", "chip", "hardware", "datacenter", "inference cost",
        ]
    },
    "open_source": {
        "label": "Open Source & Community",
        "icon":  "🌐",
        "color": "#fb923c",
        "bg":    "rgba(251,146,60,0.07)",
        "glow":  "rgba(251,146,60,0.14)",
        "keywords": [
            "open source", "open-source", "github", "hugging face", "huggingface",
            "llama", "open weight", "open model", "community", "contrib", "fork",
            "mit license", "apache", "open access", "weights", "permissive", "ollama",
            "mistral", "qwen", "phi", "gemma", "falcon", "bloom", "gguf", "quantiz",
            "lora", "qlora", "fine-tune", "local", "self-host", "mlx", "ggml",
        ]
    },
}

DEFAULT_CATEGORY    = "industry"
MAX_PER_CATEGORY    = 8
MAX_FEATURED_AGE_H  = 72
AI_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "deep learning", "llm",
    "language model", "neural", "gpt", "claude", "gemini", "openai", "anthropic",
    "chatbot", "generative", "ml", "nlp", "computer vision", "robotics", "agi",
    "model", "transformer", "diffusion", "agent", "automation",
]

# ─── HTTP ────────────────────────────────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (compatible; Feedfetcher-Google; +http://www.google.com/feedfetcher.html)",
    "Googlebot-News",
    "AI-Pulse-Newsletter/3.0 (+https://github.com/oeway/ai-news-channel)",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

def fetch(url: str, timeout: int = 25, retries: int = 2) -> Optional[str]:
    ua = random.choice(USER_AGENTS)
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": ua,
                    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Cache-Control": "no-cache",
                }
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < retries:
                time.sleep(2 ** attempt)
            else:
                print(f"  [!] HTTP {e.code} {url[:65]}", file=sys.stderr)
                return None
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
            else:
                print(f"  [!] {type(e).__name__} {url[:65]}: {e}", file=sys.stderr)
                return None
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
                    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
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

def long_date(dt: Optional[datetime]) -> str:
    if dt is None: return ""
    return dt.strftime("%B %d, %Y")

def reading_time(text: str) -> int:
    words = len(text.split())
    return max(1, round(words / 200))

# ─── Fetchers ────────────────────────────────────────────────────────────────

def is_ai_related(title: str, desc: str) -> bool:
    text = (title + " " + desc).lower()
    return any(kw in text for kw in AI_KEYWORDS)

def fetch_rss(cfg: Dict) -> List[Dict]:
    print(f"  RSS  {cfg['source']}…", flush=True)
    raw = fetch(cfg["url"])
    if not raw: return []
    try:
        feed      = feedparser.parse(raw)
        articles  = []
        filter_ai = cfg.get("filter_ai", False)
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
            if filter_ai and not is_ai_related(title, desc):
                continue
            articles.append({
                "title": title, "url": url, "desc": desc,
                "source": cfg["source"], "source_color": cfg["color"],
                "date": dt, "category": None,
            })
        print(f"     → {len(articles)} items", flush=True)
        return articles
    except Exception as ex:
        print(f"  [!] parse error {cfg['source']}: {ex}", file=sys.stderr)
        return []


def fetch_hn() -> List[Dict]:
    print("  HN   Algolia search…", flush=True)
    seen: set = set()
    articles: List[Dict] = []
    for q in HN_TAGS[:5]:
        url  = f"{HN_API}?{urllib.parse.urlencode({'query': q, 'tags': 'story', 'hitsPerPage': 20})}"
        raw  = fetch(url)
        if not raw: continue
        try:
            for hit in json.loads(raw).get("hits", []):
                oid   = hit.get("objectID", "")
                if oid in seen: continue
                seen.add(oid)
                title = hit.get("title", "").strip()
                if not title or not is_ai_related(title, ""):
                    continue
                story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={oid}"
                pts   = hit.get("points", 0)
                cmnts = hit.get("num_comments", 0)
                desc  = f"{pts} points · {cmnts} comments on Hacker News"
                dt    = to_dt(hit.get("created_at_i"))
                articles.append({
                    "title": title, "url": story_url, "desc": desc,
                    "source": "Hacker News", "source_color": "#f97316",
                    "date": dt, "category": None,
                })
        except Exception as ex:
            print(f"  [!] HN parse: {ex}", file=sys.stderr)
        time.sleep(0.35)
    print(f"     → {len(articles)} items", flush=True)
    return articles


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
            title   = (entry.findtext("a:title",   "", ns) or "").replace("\n", " ").strip()
            summ    = (entry.findtext("a:summary", "", ns) or "").replace("\n", " ").strip()[:400]
            link    = (entry.findtext("a:id",      "", ns) or "").strip()
            pub     = entry.findtext("a:published", "", ns)
            authors = [a.findtext("a:name", "", ns)
                       for a in entry.findall("a:author", ns)][:3]
            author_str = ", ".join(authors) + (" et al." if len(authors) == 3 else "")
            cats    = [c.get("term","") for c in entry.findall("a:category", ns)]
            cat_s   = " · ".join(cats[:3])
            desc    = f"[{cat_s}] {author_str} — {summ}"
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

# ─── Classify ────────────────────────────────────────────────────────────────

def classify(a: Dict) -> str:
    if a.get("category"):
        return a["category"]
    text   = (a.get("title","") + " " + a.get("desc","")).lower()
    scores = {}
    for cat, cfg in CATEGORIES.items():
        scores[cat] = sum(2 if kw in a.get("title","").lower() else 1
                          for kw in cfg["keywords"] if kw in text)
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else DEFAULT_CATEGORY

# ─── Score ───────────────────────────────────────────────────────────────────

def score(a: Dict) -> float:
    s    = 0.0
    dt   = a.get("date")
    if dt:
        age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        # Fresher = higher score, decay over ~5 days
        s += max(0, 12 - age_h * 0.09)
    source_bonus = {
        "arXiv": 3.0, "IEEE Spectrum": 2.5, "MIT Tech Review": 2.2,
        "OpenAI Blog": 3.5, "DeepMind": 3.0, "Google AI Blog": 2.8,
        "HuggingFace": 2.5, "BAIR Blog": 2.3, "Anthropic": 3.5,
        "Meta AI Research": 2.5, "LangChain Blog": 2.0, "Lilian Weng": 2.8,
        "TechCrunch": 1.8, "VentureBeat": 1.5, "Wired": 1.4,
        "The Verge": 1.3, "Hacker News": 0.9,
    }
    s += source_bonus.get(a.get("source",""), 1.0)
    tl = len(a.get("title",""))
    if 35 < tl < 120: s += 0.5
    return s

# ─── Deduplicate ─────────────────────────────────────────────────────────────

def dedup(articles: List[Dict]) -> List[Dict]:
    seen_urls:   set = set()
    seen_titles: set = set()
    out: List[Dict] = []
    for a in articles:
        url  = re.sub(r"[?#].*$", "", a.get("url","")).rstrip("/").lower()
        tkey = hashlib.md5(re.sub(r"\W+", " ", a.get("title","").lower()[:70]).encode()).hexdigest()
        if url in seen_urls or tkey in seen_titles: continue
        if url: seen_urls.add(url)
        seen_titles.add(tkey)
        out.append(a)
    return out

# ─── Load / save state ───────────────────────────────────────────────────────

def load_state() -> Dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except: pass
    return {"issue": 0}

def save_state(state: Dict) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))

# ─── HTML helpers ────────────────────────────────────────────────────────────

SOURCE_COLORS: Dict[str, str] = {
    "TechCrunch":      "#22c55e",
    "VentureBeat":     "#f97316",
    "The Verge":       "#e11d48",
    "Wired":           "#818cf8",
    "IEEE Spectrum":   "#0ea5e9",
    "MIT Tech Review": "#a78bfa",
    "arXiv":           "#a78bfa",
    "Hacker News":     "#f97316",
    "HuggingFace":     "#fbbf24",
    "OpenAI Blog":     "#10b981",
    "DeepMind":        "#6366f1",
    "Google AI Blog":  "#4285f4",
    "BAIR Blog":       "#8b5cf6",
    "Meta AI Research":"#1877f2",
    "LangChain Blog":  "#f59e0b",
    "Lilian Weng":     "#ec4899",
    "Anthropic":       "#6b7280",
    "NY Times Tech":   "#64748b",
    "WSJ":             "#3b82f6",
}

def source_pill(source: str, color: str = "") -> str:
    c = color or SOURCE_COLORS.get(source, "#6b7280")
    return (f'<span class="pill" style="--c:{c}">{h(source)}</span>')

def card_html(a: Dict, cat_color: str) -> str:
    title = h(a.get("title","Untitled"))
    url   = h(a.get("url","#"))
    desc  = h(a.get("desc","")[:260])
    src   = a.get("source","")
    src_c = a.get("source_color","") or SOURCE_COLORS.get(src,"#6b7280")
    age   = age_str(a.get("date"))
    rt    = reading_time(a.get("desc",""))
    return f'''\
    <article class="card" style="--cat:{cat_color}">
      <div class="card-top">
        {source_pill(src, src_c)}
        <span class="card-age">{h(age)}</span>
      </div>
      <h3 class="card-title"><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></h3>
      <p  class="card-desc">{desc}</p>
      <div class="card-foot">
        <span class="card-rt">{rt} min read</span>
        <a class="card-link" href="{url}" target="_blank" rel="noopener noreferrer">Read more ↗</a>
      </div>
    </article>'''

def section_html(cat: str, articles: List[Dict]) -> str:
    if not articles: return ""
    cfg   = CATEGORIES[cat]
    color = cfg["color"]
    bg    = cfg["bg"]
    glow  = cfg["glow"]
    cards = "\n".join(card_html(a, color) for a in articles[:MAX_PER_CATEGORY])
    count = len(articles[:MAX_PER_CATEGORY])
    return f'''\
  <section class="cat-section" id="{cat}" style="--cat:{color};--cat-bg:{bg};--cat-glow:{glow}">
    <header class="section-hdr">
      <span class="section-icon">{cfg["icon"]}</span>
      <h2 class="section-title">{h(cfg["label"])}</h2>
      <span class="section-count">{count}</span>
    </header>
    <div class="card-grid">
      {cards}
    </div>
  </section>'''

def featured_html(a: Dict) -> str:
    title = h(a.get("title","Untitled"))
    url   = h(a.get("url","#"))
    desc  = h(a.get("desc","")[:550])
    src   = a.get("source","")
    src_c = a.get("source_color","") or SOURCE_COLORS.get(src,"#6b7280")
    age   = age_str(a.get("date"))
    cat   = a.get("category", DEFAULT_CATEGORY)
    cat_c = CATEGORIES.get(cat,{}).get("color","#8b5cf6")
    cat_l = CATEGORIES.get(cat,{}).get("label","News")
    cat_i = CATEGORIES.get(cat,{}).get("icon","📌")
    return f'''\
  <section class="featured-wrap">
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
      <a class="featured-btn" href="{url}" target="_blank" rel="noopener noreferrer">
        Read Full Story ↗
      </a>
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

# ─── CSS ─────────────────────────────────────────────────────────────────────

PAGE_CSS = """\
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

:root{
  --bg:#07071a;
  --surface:#0d0d24;
  --card:#111128;
  --card-h:#15152e;
  --border:rgba(255,255,255,0.065);
  --border-h:rgba(255,255,255,0.13);
  --text:#e8eaf6;
  --sub:#94a3b8;
  --muted:#64748b;
  --dim:#2d3a4a;
  font-size:15px;
}

html{scroll-behavior:smooth}

body{
  background:var(--bg);
  color:var(--text);
  font-family:'Inter',system-ui,-apple-system,sans-serif;
  line-height:1.65;
  min-height:100vh;
}

a{color:inherit;text-decoration:none}

/* background glows */
body::before{
  content:'';
  position:fixed;inset:0;pointer-events:none;z-index:0;
  background:
    radial-gradient(ellipse 70% 50% at 15% 5%,  rgba(99,102,241,.09)  0%,transparent 70%),
    radial-gradient(ellipse 55% 40% at 85% 85%,  rgba(6,182,212,.07)   0%,transparent 70%),
    radial-gradient(ellipse 40% 35% at 55% 45%,  rgba(139,92,246,.04)  0%,transparent 65%);
}
.page{position:relative;z-index:1}

/* ── Header ── */
.site-header{
  border-bottom:1px solid var(--border);
  background:linear-gradient(180deg,rgba(13,13,36,.98) 0%,rgba(7,7,26,.93) 100%);
  backdrop-filter:blur(14px);
  -webkit-backdrop-filter:blur(14px);
  position:sticky;top:0;z-index:100;
}
.header-inner{
  max-width:1200px;margin:0 auto;
  padding:.85rem 1.5rem;
  display:flex;align-items:center;justify-content:space-between;gap:1rem;
  flex-wrap:wrap;
}
.brand{display:flex;align-items:center;gap:.75rem}
.brand-logo{font-size:1.75rem;line-height:1;filter:drop-shadow(0 0 8px rgba(167,139,250,.6))}
.brand-text{}
.brand-name{
  font-family:'Space Grotesk',sans-serif;
  font-size:1.35rem;font-weight:700;line-height:1.1;
  background:linear-gradient(130deg,#a78bfa 0%,#38bdf8 55%,#34d399 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.brand-sub{font-size:.68rem;color:var(--muted);margin-top:2px;letter-spacing:.04em}

.header-right{display:flex;align-items:center;gap:.65rem;flex-shrink:0}
.issue-badge{
  font-size:.7rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;
  background:linear-gradient(135deg,rgba(167,139,250,.16),rgba(56,189,248,.14));
  border:1px solid rgba(167,139,250,.32);
  color:#a78bfa;padding:.24rem .72rem;border-radius:20px;
}
.header-date{font-size:.78rem;color:var(--muted);display:flex;align-items:center;gap:.35rem}
.live-dot{
  display:inline-block;width:7px;height:7px;border-radius:50%;
  background:#22c55e;flex-shrink:0;
  animation:pulse-dot 2.6s ease-in-out infinite;
}
@keyframes pulse-dot{
  0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(34,197,94,.45)}
  50%{opacity:.65;box-shadow:0 0 0 5px rgba(34,197,94,0)}
}

/* ── Category nav ── */
.cat-nav-wrap{border-bottom:1px solid var(--border)}
.cat-nav{
  max-width:1200px;margin:0 auto;
  padding:.7rem 1.5rem;
  display:flex;gap:.4rem;flex-wrap:wrap;
  align-items:center;
}
.nav-pill{
  font-size:.75rem;font-weight:500;
  padding:.28rem .72rem;border-radius:20px;
  border:1px solid color-mix(in srgb,var(--cat) 28%,transparent);
  color:var(--cat);
  transition:background .15s,transform .15s,box-shadow .15s;
  white-space:nowrap;
}
.nav-pill:hover{
  background:color-mix(in srgb,var(--cat) 13%,transparent);
  transform:translateY(-1px);
  box-shadow:0 2px 8px color-mix(in srgb,var(--cat) 20%,transparent);
}

/* ── Main ── */
main{max-width:1200px;margin:0 auto;padding:2.25rem 1.5rem 3rem}

/* ── Featured ── */
.featured-wrap{margin-bottom:2.75rem}
.featured-card{
  background:linear-gradient(135deg,#140f3c 0%,#0e0e2a 55%,#0a1428 100%);
  border:1px solid rgba(167,139,250,.2);
  border-radius:20px;
  padding:2.25rem 2.75rem;
  position:relative;overflow:hidden;
}
.featured-card::before{
  content:'';position:absolute;top:-120px;right:-120px;
  width:420px;height:420px;border-radius:50%;
  background:radial-gradient(circle,rgba(99,102,241,.14) 0%,transparent 65%);
  pointer-events:none;
}
.featured-card::after{
  content:'';position:absolute;bottom:-80px;left:15%;
  width:300px;height:300px;border-radius:50%;
  background:radial-gradient(circle,rgba(6,182,212,.07) 0%,transparent 65%);
  pointer-events:none;
}
.featured-eyebrow{
  display:flex;align-items:center;gap:1rem;margin-bottom:1.1rem;
  position:relative;z-index:1;
}
.featured-badge{
  font-size:.7rem;font-weight:700;letter-spacing:.12em;
  color:#a78bfa;text-transform:uppercase;
}
.featured-cat{font-size:.78rem;font-weight:500}
.featured-title{
  font-family:'Space Grotesk',sans-serif;
  font-size:clamp(1.3rem,3vw,2rem);font-weight:700;
  line-height:1.28;margin-bottom:1rem;
  position:relative;z-index:1;
}
.featured-meta{display:flex;align-items:center;gap:.75rem;margin-bottom:1rem;flex-wrap:wrap;position:relative;z-index:1}
.featured-age{font-size:.78rem;color:var(--muted)}
.featured-body{
  color:var(--sub);line-height:1.75;
  margin-bottom:1.6rem;max-width:700px;
  position:relative;z-index:1;
}
.featured-btn{
  display:inline-flex;align-items:center;gap:.4rem;
  background:linear-gradient(135deg,#6d28d9,#4f46e5);
  color:#fff;
  padding:.62rem 1.4rem;border-radius:10px;
  font-size:.875rem;font-weight:600;
  box-shadow:0 4px 20px rgba(99,102,241,.4);
  transition:opacity .2s,transform .15s,box-shadow .2s;
  position:relative;z-index:1;
}
.featured-btn:hover{opacity:.88;transform:translateY(-2px);box-shadow:0 6px 24px rgba(99,102,241,.5)}

/* ── Category section ── */
.cat-section{margin-bottom:3rem;scroll-margin-top:100px}
.section-hdr{
  display:flex;align-items:center;gap:.6rem;
  margin-bottom:1.25rem;padding-bottom:.8rem;
  border-bottom:2px solid color-mix(in srgb,var(--cat) 20%,transparent);
}
.section-icon{font-size:1.2rem}
.section-title{
  font-family:'Space Grotesk',sans-serif;
  font-size:1.08rem;font-weight:700;color:var(--cat);
}
.section-count{
  margin-left:auto;
  font-size:.7rem;font-weight:600;color:var(--cat);
  background:color-mix(in srgb,var(--cat) 12%,transparent);
  border:1px solid color-mix(in srgb,var(--cat) 25%,transparent);
  padding:.15rem .55rem;border-radius:12px;
}

/* ── Card grid ── */
.card-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
  gap:1.1rem;
}

/* ── Card ── */
.card{
  background:var(--card);
  border:1px solid var(--border);
  border-radius:14px;
  padding:1.2rem 1.3rem;
  display:flex;flex-direction:column;gap:.6rem;
  transition:border-color .2s,background .2s,transform .2s,box-shadow .2s;
  position:relative;overflow:hidden;
  cursor:pointer;
}
.card::before{
  content:'';
  position:absolute;top:0;left:0;right:0;height:2px;
  background:var(--cat,#8b5cf6);
  opacity:0;transition:opacity .2s;
}
.card:hover{
  border-color:color-mix(in srgb,var(--cat) 40%,transparent);
  background:var(--card-h);
  transform:translateY(-3px);
  box-shadow:
    0 10px 30px rgba(0,0,0,.4),
    0 0 0 1px color-mix(in srgb,var(--cat) 14%,transparent),
    0 0 20px color-mix(in srgb,var(--cat) 6%,transparent);
}
.card:hover::before{opacity:1}

.card-top{display:flex;align-items:center;justify-content:space-between;gap:.5rem}
.card-age{font-size:.7rem;color:var(--muted);white-space:nowrap;flex-shrink:0}
.card-title{font-size:.92rem;font-weight:600;line-height:1.45}
.card-title a{color:var(--text);transition:color .15s}
.card-title a:hover{color:var(--cat,#a78bfa)}
.card-desc{
  font-size:.8rem;color:var(--sub);line-height:1.58;flex-grow:1;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;
}
.card-foot{display:flex;align-items:center;justify-content:space-between;margin-top:auto}
.card-rt{font-size:.68rem;color:var(--dim)}
.card-link{
  font-size:.76rem;font-weight:500;
  color:color-mix(in srgb,var(--cat) 85%,#fff);
  transition:opacity .15s;
}
.card-link:hover{opacity:.7}

/* ── Source pill ── */
.pill{
  display:inline-block;
  font-size:.66rem;font-weight:700;letter-spacing:.05em;
  padding:.14rem .5rem;border-radius:5px;
  text-transform:uppercase;
  background:color-mix(in srgb,var(--c,#6b7280) 16%,transparent);
  border:1px solid color-mix(in srgb,var(--c,#6b7280) 35%,transparent);
  color:var(--c,#6b7280);
}

/* ── Stats bar ── */
.stats-bar{
  max-width:1200px;margin:0 auto;
  padding:.8rem 1.5rem;
  display:flex;align-items:center;gap:1.5rem;flex-wrap:wrap;
  border-top:1px solid var(--border);
  font-size:.76rem;color:var(--muted);
}
.stat-item{display:flex;align-items:center;gap:.35rem;white-space:nowrap}
.stat-dot{width:6px;height:6px;border-radius:50%;background:var(--c,#6b7280);flex-shrink:0}

/* ── Footer ── */
.site-footer{
  background:var(--surface);
  border-top:1px solid var(--border);
  padding:2.5rem 1.5rem;
  margin-top:1rem;
}
.footer-inner{
  max-width:1200px;margin:0 auto;
  display:grid;grid-template-columns:1fr 1fr;gap:2rem;
  align-items:start;
}
.footer-brand-col{}
.footer-brand{
  font-family:'Space Grotesk',sans-serif;
  font-size:1.2rem;font-weight:700;
  background:linear-gradient(135deg,#a78bfa,#38bdf8);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
  margin-bottom:.5rem;
}
.footer-desc{font-size:.8rem;color:var(--muted);line-height:1.6;max-width:300px}
.footer-links-col{}
.footer-links-title{font-size:.72rem;font-weight:700;letter-spacing:.09em;color:var(--dim);text-transform:uppercase;margin-bottom:.75rem}
.footer-links{display:flex;flex-direction:column;gap:.5rem}
.footer-links a{font-size:.82rem;color:var(--muted);transition:color .15s}
.footer-links a:hover{color:var(--text)}
.footer-bottom{
  max-width:1200px;margin:1.5rem auto 0;
  padding-top:1rem;border-top:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between;
  flex-wrap:wrap;gap:.75rem;
}
.footer-note{font-size:.72rem;color:var(--dim)}
.footer-sources{display:flex;gap:.4rem;flex-wrap:wrap}
.footer-sources .pill{font-size:.62rem}

/* ── Empty state ── */
.empty-state{text-align:center;padding:4rem 1rem;color:var(--muted)}
.empty-icon{font-size:3rem;margin-bottom:1rem}
.empty-state p{max-width:400px;margin:0 auto;line-height:1.7}

/* ── Scroll to top ── */
.scroll-top{
  position:fixed;bottom:1.75rem;right:1.75rem;z-index:200;
  background:rgba(13,13,36,.9);
  border:1px solid rgba(167,139,250,.3);
  color:#a78bfa;width:40px;height:40px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  font-size:1rem;backdrop-filter:blur(10px);
  transition:background .2s,transform .2s,box-shadow .2s;
  box-shadow:0 4px 14px rgba(0,0,0,.35);
}
.scroll-top:hover{
  background:rgba(99,102,241,.28);
  transform:translateY(-2px);
  box-shadow:0 6px 18px rgba(99,102,241,.3);
}

/* ── Responsive ── */
@media(max-width:900px){
  .footer-inner{grid-template-columns:1fr}
}
@media(max-width:768px){
  .header-inner{flex-wrap:wrap}
  .featured-card{padding:1.5rem 1.25rem}
  main{padding:1.5rem 1rem 2.5rem}
  .cat-nav{padding:.65rem 1rem}
}
@media(max-width:500px){
  .card-grid{grid-template-columns:1fr}
  .header-date{display:none}
  .footer-bottom{flex-direction:column;align-items:flex-start}
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

    featured_block = featured_html(featured) if featured else ""

    cat_order    = list(CATEGORIES.keys())
    active_cats  = [c for c in cat_order if sections.get(c)]
    sections_html = "".join(section_html(c, sections[c]) for c in active_cats)

    if not featured_block and not sections_html:
        sections_html = '''\
  <div class="empty-state">
    <div class="empty-icon">🤖</div>
    <p>No articles fetched yet — the scheduled workflow will populate this page automatically every day.</p>
  </div>'''

    nav_block = (
        f'<div class="cat-nav-wrap">{nav_html(active_cats)}</div>'
        if active_cats else ""
    )

    stats_items = "".join(
        f'<span class="stat-item">'
        f'<span class="stat-dot" style="--c:{CATEGORIES[c]["color"]}"></span>'
        f'{CATEGORIES[c]["icon"]} {len(sections.get(c,[]))} {h(CATEGORIES[c]["label"])}'
        f'</span>'
        for c in active_cats if sections.get(c)
    )
    stats_block = f'<div class="stats-bar">{stats_items}</div>' if stats_items else ""

    sources_pills = "".join(
        f'<span class="pill" style="--c:{SOURCE_COLORS.get(s,"#6b7280")}">{h(s)}</span>'
        for s in src_set[:14]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Pulse — Issue #{issue} · {h(now_str)}</title>
  <meta name="description" content="Daily curated AI news: research breakthroughs, AI agents, new products, and industry — Issue #{issue}, {h(now_str)}">
  <meta property="og:title"       content="AI Pulse — Issue #{issue} · {h(now_str)}">
  <meta property="og:description" content="Daily curated AI news covering research breakthroughs, AI agents, new products, and industry.">
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
      <div class="brand">
        <span class="brand-logo">⚡</span>
        <div class="brand-text">
          <div class="brand-name">AI Pulse</div>
          <div class="brand-sub">Daily AI News Digest</div>
        </div>
      </div>
      <div class="header-right">
        <span class="issue-badge">Issue #{issue}</span>
        <span class="header-date">
          <span class="live-dot"></span>{h(now_str)}
        </span>
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
      <div class="footer-brand-col">
        <div class="footer-brand">⚡ AI Pulse</div>
        <p class="footer-desc">
          A daily digest of the most important AI news — research breakthroughs,
          agent developments, new products, and industry moves. Updated automatically
          every morning.
        </p>
      </div>
      <div class="footer-links-col">
        <div class="footer-links-title">Sources &amp; Links</div>
        <div class="footer-links">
          <a href="https://github.com/oeway/ai-news-channel" target="_blank" rel="noopener">
            GitHub Repository
          </a>
          <a href="https://arxiv.org/list/cs.AI/recent" target="_blank" rel="noopener">
            arXiv CS.AI (latest papers)
          </a>
          <a href="https://news.ycombinator.com" target="_blank" rel="noopener">
            Hacker News
          </a>
          <a href="https://huggingface.co/blog" target="_blank" rel="noopener">
            HuggingFace Blog
          </a>
        </div>
      </div>
    </div>
    <div class="footer-bottom">
      <div class="footer-note">
        Auto-generated from {len(src_set)} sources · {total} articles ·
        <time datetime="{gen_iso}">Updated {gen_iso}</time>
      </div>
      <div class="footer-sources">{sources_pills}</div>
    </div>
  </footer>

</div>
<a class="scroll-top" href="#" aria-label="Back to top" title="Back to top">↑</a>
</body>
</html>"""

# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    print("⚡ AI Pulse Newsletter Generator v3.0", flush=True)
    print("─" * 50, flush=True)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    state = load_state()
    issue = state.get("issue", 0) + 1
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
    if total == 0:
        print("  ⚠  No articles fetched — page will show empty state.", flush=True)
    else:
        print(f"  Sections: {', '.join(f'{k}:{len(v)}' for k,v in sections.items() if v)}", flush=True)
        print(f"  Total placed: {total}", flush=True)

    # ── Render ──
    print("\n[4/4] Rendering HTML…", flush=True)
    generated = datetime.now(timezone.utc)
    html_out  = full_page(featured, sections, issue, generated)
    OUTPUT.write_text(html_out, encoding="utf-8")

    state["issue"] = issue
    state["last_generated"] = generated.strftime("%Y-%m-%dT%H:%M:%SZ")
    save_state(state)

    print(f"\n✅  Written → {OUTPUT}", flush=True)
    print(f"    Issue #{issue} · {total} articles · {generated.strftime('%Y-%m-%dT%H:%M:%SZ')}")


if __name__ == "__main__":
    main()
