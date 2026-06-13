#!/usr/bin/env python3
"""AI Pulse Newsletter Generator v3 — daily AI news digest"""

import re, sys, json, time, hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from html import escape as h
from typing import List, Dict, Any, Optional
import urllib.parse, urllib.request, urllib.error

try:
    import feedparser
except ImportError:
    print("feedparser not installed. Run: pip install feedparser", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR   = SCRIPT_DIR.parent
DOCS_DIR   = ROOT_DIR / "docs"
OUTPUT     = DOCS_DIR / "index.html"
STATE_FILE = DOCS_DIR / "state.json"

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
    {"url": "https://huggingface.co/blog/feed.xml",
     "source": "Hugging Face",   "color": "#fbbf24"},
    {"url": "https://openai.com/blog/rss/",
     "source": "OpenAI",         "color": "#10a37f"},
    {"url": "https://www.anthropic.com/rss.xml",
     "source": "Anthropic",      "color": "#cc785c"},
    {"url": "https://deepmind.google/blog/feed/basic/",
     "source": "DeepMind",       "color": "#4285f4"},
    {"url": "https://blogs.nvidia.com/blog/category/ai/feed/",
     "source": "NVIDIA Blog",    "color": "#76b900"},
]

HN_DATE_API  = "https://hn.algolia.com/api/v1/search_by_date"
HN_SCORE_API = "https://hn.algolia.com/api/v1/search"
HN_QUERIES   = ["artificial intelligence", "AI agent", "large language model", "machine learning"]

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
            "paper","arxiv","research","study","benchmark","dataset","training",
            "pretrain","fine-tun","neural","transformer","diffusion","multimodal",
            "evaluation","algorithm","architecture","inference","reasoning",
            "capability","scaling","emergent","alignment","rlhf","reward model",
            "attention","parameter","weight","gradient","loss function","experiment"
        ]
    },
    "agents": {
        "label": "AI Agents & Automation",
        "icon":  "🤖",
        "color": "#c084fc",
        "bg":    "rgba(192,132,252,0.06)",
        "keywords": [
            "agent","autonomous","agentic","multi-agent","planning","memory",
            "tool use","function call","workflow","automation","copilot",
            "computer use","browse","execute","retrieval","rag","orchestrat",
            "task complet","action","mcp","model context protocol",
            "browser use","tool calling","agentic","long-horizon"
        ]
    },
    "products": {
        "label": "New Products & Releases",
        "icon":  "🚀",
        "color": "#60a5fa",
        "bg":    "rgba(96,165,250,0.06)",
        "keywords": [
            "launch","release","introduc","announc","unveil","gpt","claude",
            "gemini","llama","mistral","update","feature","api","version",
            "preview","beta","product","app","platform","service","plugin",
            "integrat","sora","dalle","stable diffusion","cursor","perplexity"
        ]
    },
    "industry": {
        "label": "Industry & Business",
        "icon":  "💼",
        "color": "#4ade80",
        "bg":    "rgba(74,222,128,0.06)",
        "keywords": [
            "funding","million","billion","acqui","ceo","hire","policy",
            "regulat","invest","startup","openai","google","microsoft","meta",
            "nvidia","amazon","apple","partnership","deal","market","revenue",
            "valuat","ipo","lawsuit","safety","govern","anthropic","regulation"
        ]
    },
    "open_source": {
        "label": "Open Source & Community",
        "icon":  "🌐",
        "color": "#fb923c",
        "bg":    "rgba(251,146,60,0.06)",
        "keywords": [
            "open source","open-source","github","hugging face","huggingface",
            "llama","open weight","open model","community","contrib","fork",
            "mit license","apache","open access","weights","permissive","ollama",
            "local model","self-host","freely available","open llm"
        ]
    },
}

DEFAULT_CATEGORY   = "industry"
MAX_PER_CATEGORY   = 8
MAX_HN_TRENDING    = 6
MAX_FEATURED_AGE_H = 72

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
    if dt is None: return "recently"
    delta = datetime.now(timezone.utc) - dt
    if delta.days == 0:
        hv = delta.seconds // 3600
        return f"{delta.seconds // 60}m ago" if hv == 0 else f"{hv}h ago"
    if delta.days == 1: return "yesterday"
    if delta.days < 7:  return f"{delta.days}d ago"
    return dt.strftime("%b %d, %Y")

def read_time(text: str) -> str:
    mins = max(1, len(text.split()) // 200)
    return f"{mins} min"

# ─── Fetchers ─────────────────────────────────────────────────────────────────

def fetch_rss(cfg: Dict) -> List[Dict]:
    print(f"  RSS  {cfg['source']}…", flush=True)
    raw = fetch(cfg["url"])
    if not raw: return []
    try:
        feed = feedparser.parse(raw)
        out  = []
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
            out.append({"title": title, "url": url, "desc": desc,
                        "source": cfg["source"], "source_color": cfg["color"],
                        "date": dt, "category": None,
                        "read_time": read_time(desc), "hn_points": 0})
        print(f"     → {len(out)} items", flush=True)
        return out
    except Exception as ex:
        print(f"  [!] parse {cfg['source']}: {ex}", file=sys.stderr)
        return []

def fetch_hn_recent() -> List[Dict]:
    print("  HN   recent…", flush=True)
    seen: set = set()
    out:  List[Dict] = []
    for q in HN_QUERIES[:3]:
        url = (f"{HN_DATE_API}?"
               f"{urllib.parse.urlencode({'query': q, 'tags': 'story', 'hitsPerPage': 12})}")
        raw = fetch(url)
        if not raw: continue
        try:
            for hit in json.loads(raw).get("hits", []):
                oid = hit.get("objectID", "")
                if oid in seen: continue
                seen.add(oid)
                title = hit.get("title", "").strip()
                if not title: continue
                pts   = hit.get("points", 0) or 0
                cmnts = hit.get("num_comments", 0) or 0
                story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={oid}"
                out.append({
                    "title": title, "url": story_url,
                    "desc":  f"{pts} points · {cmnts} comments on Hacker News",
                    "source": "HackerNews", "source_color": "#f97316",
                    "date": to_dt(hit.get("created_at_i")), "category": None,
                    "hn_points": pts, "hn_comments": cmnts, "hn_id": oid,
                    "read_time": "2 min"
                })
        except Exception as ex:
            print(f"  [!] HN recent parse: {ex}", file=sys.stderr)
        time.sleep(0.3)
    print(f"     → {len(out)} items", flush=True)
    return out

def fetch_hn_trending() -> List[Dict]:
    print("  HN   trending (by score)…", flush=True)
    seen: set = set()
    out:  List[Dict] = []
    for q in ["artificial intelligence", "LLM", "AI model"]:
        url = (f"{HN_SCORE_API}?"
               f"{urllib.parse.urlencode({'query': q, 'tags': 'story', 'hitsPerPage': 12})}")
        raw = fetch(url)
        if not raw: continue
        try:
            for hit in json.loads(raw).get("hits", []):
                oid = hit.get("objectID", "")
                if oid in seen: continue
                seen.add(oid)
                title = hit.get("title", "").strip()
                if not title: continue
                pts   = hit.get("points", 0) or 0
                cmnts = hit.get("num_comments", 0) or 0
                if pts < 30: continue
                story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={oid}"
                out.append({
                    "title": title, "url": story_url,
                    "desc":  f"{pts} points · {cmnts} comments",
                    "source": "HackerNews", "source_color": "#f97316",
                    "date": to_dt(hit.get("created_at_i")),
                    "hn_points": pts, "hn_comments": cmnts, "hn_id": oid,
                    "read_time": "2 min"
                })
        except Exception as ex:
            print(f"  [!] HN trending parse: {ex}", file=sys.stderr)
        time.sleep(0.3)
    out.sort(key=lambda x: x.get("hn_points", 0), reverse=True)
    # deduplicate by objectID
    seen2: set = set()
    unique = []
    for a in out:
        oid = a.get("hn_id", a["title"])
        if oid not in seen2:
            seen2.add(oid)
            unique.append(a)
    result = unique[:MAX_HN_TRENDING]
    print(f"     → {len(result)} trending", flush=True)
    return result

def fetch_arxiv() -> List[Dict]:
    print("  arXiv papers…", flush=True)
    url = (f"{ARXIV_API}?search_query={ARXIV_QUERY}"
           "&start=0&max_results=15&sortBy=submittedDate&sortOrder=descending")
    raw = fetch(url)
    if not raw: return []
    try:
        ns   = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(raw)
        out  = []
        for entry in root.findall("a:entry", ns):
            title   = (entry.findtext("a:title",   "", ns) or "").replace("\n", " ").strip()
            summ    = (entry.findtext("a:summary", "", ns) or "").replace("\n", " ").strip()[:380]
            link    = (entry.findtext("a:id",      "", ns) or "").strip()
            pub     = entry.findtext("a:published", "", ns)
            cats    = [c.get("term","") for c in entry.findall("a:category", ns)]
            authors = [a.findtext("a:name", "", ns)
                       for a in entry.findall("a:author", ns)][:4]
            if not title or not link: continue
            out.append({
                "title":  title, "url": link, "desc": summ,
                "source": "arXiv", "source_color": "#a78bfa",
                "date": to_dt(pub), "category": "research",
                "arxiv_cats": " · ".join(cats[:3]),
                "authors":    ", ".join(authors),
                "read_time":  "5 min", "hn_points": 0
            })
        print(f"     → {len(out)} papers", flush=True)
        return out
    except Exception as ex:
        print(f"  [!] arXiv parse: {ex}", file=sys.stderr)
        return []

# ─── Classify / score / dedup ────────────────────────────────────────────────

def classify(a: Dict) -> str:
    if a.get("category"):
        return a["category"]
    text   = (a.get("title","") + " " + a.get("desc","")).lower()
    scores = {cat: sum(1 for kw in cfg["keywords"] if kw in text)
              for cat, cfg in CATEGORIES.items()}
    best   = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else DEFAULT_CATEGORY

def score_article(a: Dict) -> float:
    s = 0.0
    dt = a.get("date")
    if dt:
        age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        s  += max(0, 10 - age * 0.08)
    s += {"arXiv":2.5,"IEEE Spectrum":2.0,"MIT Tech Review":1.8,"OpenAI":2.2,
          "Anthropic":2.2,"DeepMind":2.0,"Hugging Face":2.0,"TechCrunch":1.5,
          "VentureBeat":1.3,"Wired":1.3,"The Verge":1.2,"HackerNews":0.8
          }.get(a.get("source",""), 1.0)
    tl = len(a.get("title",""))
    if 40 < tl < 130: s += 0.4
    pts = a.get("hn_points", 0)
    if pts: s += min(pts / 100, 3.0)
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

def load_issue() -> int:
    if STATE_FILE.exists():
        try:    return json.loads(STATE_FILE.read_text()).get("issue", 0)
        except: pass
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
    "Hugging Face":   "#fbbf24",
    "OpenAI":         "#10a37f",
    "Anthropic":      "#cc785c",
    "DeepMind":       "#4285f4",
    "NVIDIA Blog":    "#76b900",
}

def pill(source: str, color: str = "") -> str:
    c = color or SOURCE_COLORS.get(source, "#6b7280")
    return (f'<span class="pill" style="background:{c}20;color:{c};border-color:{c}40">'
            f'{h(source)}</span>')

def search_data(a: Dict) -> str:
    return h((a.get("title","") + " " + a.get("desc","") + " " + a.get("source","")).lower())

def card_html(a: Dict, cat_color: str) -> str:
    title   = h(a.get("title","Untitled"))
    url     = h(a.get("url","#"))
    desc    = h((a.get("desc",""))[:240])
    src     = a.get("source","")
    src_c   = a.get("source_color","") or SOURCE_COLORS.get(src,"#6b7280")
    age     = age_str(a.get("date"))
    rt      = a.get("read_time","")
    authors = a.get("authors","")
    extra   = ""
    if authors:
        extra = f'<p class="card-authors">{h(authors[:80])}</p>'
    return f'''<article class="card" style="--cc:{cat_color}" data-search="{search_data(a)}">
      <div class="card-top">
        {pill(src, src_c)}
        <span class="card-meta">{h(age)}{" · " + h(rt) if rt else ""}</span>
      </div>
      <h3 class="card-title"><a href="{url}" target="_blank" rel="noopener">{title}</a></h3>
      {extra}
      <p  class="card-desc">{desc}</p>
      <a  class="card-read" href="{url}" target="_blank" rel="noopener">Read more ↗</a>
    </article>'''

def hn_trend_card(a: Dict) -> str:
    title = h(a.get("title",""))
    url   = h(a.get("url","#"))
    pts   = a.get("hn_points", 0)
    cmnts = a.get("hn_comments", 0)
    age   = age_str(a.get("date"))
    heat  = "hot" if pts >= 300 else "warm" if pts >= 100 else ""
    return f'''<a class="hn-card {heat}" href="{url}" target="_blank" rel="noopener"
        data-search="{search_data(a)}">
      <div class="hn-score">{pts}<span>pts</span></div>
      <div class="hn-body">
        <div class="hn-title">{title}</div>
        <div class="hn-sub">{h(age)} · {cmnts} comments</div>
      </div>
    </a>'''

def section_html(cat: str, articles: List[Dict]) -> str:
    if not articles: return ""
    cfg   = CATEGORIES[cat]
    color = cfg["color"]
    cards = "\n".join(card_html(a, color) for a in articles[:MAX_PER_CATEGORY])
    count = len(articles[:MAX_PER_CATEGORY])
    return f'''<section class="cat-section" id="{cat}"
      style="--cc:{color};--cbg:{cfg['bg']}">
    <header class="sec-hdr">
      <span class="sec-icon">{cfg["icon"]}</span>
      <h2 class="sec-title">{h(cfg["label"])}</h2>
      <span class="sec-count">{count} stories</span>
    </header>
    <div class="card-grid">{cards}</div>
  </section>'''

def featured_html(a: Dict) -> str:
    title = h(a.get("title","Untitled"))
    url   = h(a.get("url","#"))
    desc  = h(a.get("desc","")[:480])
    src   = a.get("source","")
    src_c = a.get("source_color","") or SOURCE_COLORS.get(src,"#6b7280")
    age   = age_str(a.get("date"))
    rt    = a.get("read_time","")
    cat   = a.get("category", DEFAULT_CATEGORY)
    cat_c = CATEGORIES.get(cat,{}).get("color","#8b5cf6")
    cat_i = CATEGORIES.get(cat,{}).get("icon","📌")
    cat_l = CATEGORIES.get(cat,{}).get("label","News")
    return f'''<section class="featured" data-search="{search_data(a)}">
    <div class="featured-card">
      <div class="featured-top">
        <span class="feat-badge">✦ Featured Story</span>
        <span class="feat-cat" style="color:{cat_c}">{cat_i} {h(cat_l)}</span>
      </div>
      <h2 class="feat-title">{title}</h2>
      <div class="feat-meta">
        {pill(src, src_c)}
        <span class="feat-age">{h(age)}{" · " + h(rt) if rt else ""}</span>
      </div>
      <p class="feat-body">{desc}</p>
      <a class="feat-btn" href="{url}" target="_blank" rel="noopener">Read Full Story ↗</a>
    </div>
  </section>'''

# ─── CSS ──────────────────────────────────────────────────────────────────────

CSS = r"""
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#07071a;--surface:#0d0d24;--card:#111128;--card-h:#16163a;
  --border:rgba(255,255,255,.065);--border-h:rgba(255,255,255,.13);
  --text:#e8eaf6;--sub:#94a3b8;--muted:#64748b;--dim:#334155;
  font-size:15px;
}
html{scroll-behavior:smooth}
body{
  background:var(--bg);color:var(--text);
  font-family:'Inter',system-ui,-apple-system,sans-serif;
  line-height:1.6;min-height:100vh;
}
a{color:inherit;text-decoration:none}
body::before{
  content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background:
    radial-gradient(ellipse 70% 50% at 10% 0%,rgba(99,102,241,.09) 0%,transparent 65%),
    radial-gradient(ellipse 55% 45% at 90% 85%,rgba(6,182,212,.07) 0%,transparent 65%),
    radial-gradient(ellipse 40% 30% at 55% 45%,rgba(139,92,246,.04) 0%,transparent 60%);
}
.page{position:relative;z-index:1}

/* ── Header ── */
.site-header{
  border-bottom:1px solid var(--border);
  background:linear-gradient(180deg,rgba(13,13,36,.98) 0%,rgba(7,7,26,.92) 100%);
  backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
  position:sticky;top:0;z-index:100;
}
.header-inner{
  max-width:1180px;margin:0 auto;padding:.85rem 1.5rem;
  display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;
}
.brand{display:flex;align-items:center;gap:.7rem}
.brand-logo{font-size:1.7rem;line-height:1}
.brand-name{
  font-family:'Space Grotesk',sans-serif;font-size:1.3rem;font-weight:700;
  background:linear-gradient(130deg,#a78bfa 0%,#38bdf8 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.brand-sub{font-size:.7rem;color:var(--muted);margin-top:2px}
.header-right{display:flex;align-items:center;gap:.6rem;flex-shrink:0}
.issue-badge{
  font-size:.7rem;font-weight:700;letter-spacing:.07em;
  background:linear-gradient(135deg,rgba(167,139,250,.14),rgba(56,189,248,.12));
  border:1px solid rgba(167,139,250,.28);color:#a78bfa;
  padding:.22rem .65rem;border-radius:20px;
}
.header-date{font-size:.78rem;color:var(--muted)}
.live-dot{
  display:inline-block;width:7px;height:7px;border-radius:50%;
  background:#22c55e;margin-right:.3rem;
  animation:blink 2.4s ease-in-out infinite;
}
@keyframes blink{
  0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(34,197,94,.5)}
  50%     {opacity:.6;box-shadow:0 0 0 5px rgba(34,197,94,0)}
}

/* ── Nav ── */
.cat-nav{
  max-width:1180px;margin:0 auto;padding:.75rem 1.5rem;
  display:flex;gap:.4rem;flex-wrap:wrap;
  border-bottom:1px solid var(--border);
}
.nav-pill{
  font-size:.75rem;font-weight:500;padding:.26rem .7rem;border-radius:20px;
  border:1px solid color-mix(in srgb,var(--cc) 28%,transparent);
  color:var(--cc);transition:background .15s,transform .15s;white-space:nowrap;
}
.nav-pill:hover{background:color-mix(in srgb,var(--cc) 12%,transparent);transform:translateY(-1px)}

/* ── Main ── */
main{max-width:1180px;margin:0 auto;padding:1.75rem 1.5rem}

/* ── Search ── */
.search-wrap{margin-bottom:1.75rem;position:relative}
.search-wrap svg{
  position:absolute;left:1rem;top:50%;transform:translateY(-50%);
  width:16px;height:16px;color:var(--muted);pointer-events:none;
}
#search{
  width:100%;background:var(--card);border:1px solid var(--border);
  border-radius:12px;padding:.65rem 1rem .65rem 2.6rem;
  color:var(--text);font-size:.875rem;font-family:inherit;
  transition:border-color .2s,box-shadow .2s;
}
#search::placeholder{color:var(--muted)}
#search:focus{
  outline:none;border-color:rgba(167,139,250,.45);
  box-shadow:0 0 0 3px rgba(167,139,250,.1);
}
.search-hint{
  position:absolute;right:1rem;top:50%;transform:translateY(-50%);
  font-size:.7rem;color:var(--dim);pointer-events:none;
}

/* ── Featured ── */
.featured{margin-bottom:2.25rem}
.featured-card{
  background:linear-gradient(135deg,#140f3c 0%,#0e0e2c 55%,#091428 100%);
  border:1px solid rgba(167,139,250,.2);border-radius:20px;
  padding:2rem 2.5rem;position:relative;overflow:hidden;
}
.featured-card::before{
  content:'';position:absolute;top:-90px;right:-90px;
  width:400px;height:400px;border-radius:50%;pointer-events:none;
  background:radial-gradient(circle,rgba(99,102,241,.13) 0%,transparent 65%);
}
.featured-card::after{
  content:'';position:absolute;bottom:-60px;left:15%;
  width:280px;height:280px;border-radius:50%;pointer-events:none;
  background:radial-gradient(circle,rgba(6,182,212,.07) 0%,transparent 65%);
}
.featured-top{display:flex;align-items:center;gap:.85rem;margin-bottom:1rem;position:relative;z-index:1}
.feat-badge{font-size:.7rem;font-weight:700;letter-spacing:.1em;color:#a78bfa;text-transform:uppercase}
.feat-cat{font-size:.76rem;font-weight:500}
.feat-title{
  font-family:'Space Grotesk',sans-serif;
  font-size:clamp(1.25rem,3.5vw,1.9rem);font-weight:700;line-height:1.28;
  margin-bottom:1rem;position:relative;z-index:1;
}
.feat-meta{display:flex;align-items:center;gap:.7rem;margin-bottom:1rem;flex-wrap:wrap;position:relative;z-index:1}
.feat-age{font-size:.78rem;color:var(--muted)}
.feat-body{color:var(--sub);line-height:1.75;margin-bottom:1.5rem;max-width:700px;position:relative;z-index:1}
.feat-btn{
  display:inline-flex;align-items:center;gap:.4rem;
  background:linear-gradient(135deg,#6d28d9,#4f46e5);
  color:#fff;padding:.6rem 1.3rem;border-radius:9px;
  font-size:.875rem;font-weight:600;
  box-shadow:0 4px 18px rgba(99,102,241,.38);
  transition:opacity .2s,transform .15s;position:relative;z-index:1;
}
.feat-btn:hover{opacity:.87;transform:translateY(-1px)}

/* ── Stats ── */
.stats-bar{
  display:flex;gap:1.25rem;flex-wrap:wrap;margin-bottom:2rem;
  font-size:.76rem;color:var(--muted);
}
.stat{display:flex;align-items:center;gap:.3rem}
.stat-dot{width:6px;height:6px;border-radius:50%;background:var(--c,#6b7280);flex-shrink:0}

/* ── HN Trending ── */
.hn-section{margin-bottom:2.5rem}
.hn-hdr{
  display:flex;align-items:center;gap:.55rem;
  margin-bottom:1.1rem;padding-bottom:.65rem;
  border-bottom:1px solid var(--border);
}
.hn-hdr-icon{font-size:1.2rem}
.hn-hdr-title{
  font-family:'Space Grotesk',sans-serif;
  font-size:1rem;font-weight:600;color:#f97316;
}
.hn-hdr-sub{margin-left:auto;font-size:.72rem;color:var(--muted)}
.hn-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(280px,1fr));
  gap:.75rem;
}
.hn-card{
  background:var(--card);border:1px solid var(--border);
  border-radius:12px;padding:.9rem 1rem;
  display:flex;align-items:flex-start;gap:.85rem;
  transition:border-color .2s,background .2s,transform .2s;
  position:relative;overflow:hidden;
}
.hn-card::before{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:#f97316;opacity:0;transition:opacity .2s;
}
.hn-card:hover{
  border-color:rgba(249,115,22,.35);background:var(--card-h);
  transform:translateY(-2px);
}
.hn-card:hover::before{opacity:1}
.hn-score{
  flex-shrink:0;min-width:52px;text-align:center;
  background:rgba(249,115,22,.1);border:1px solid rgba(249,115,22,.25);
  border-radius:8px;padding:.4rem .3rem;
  font-size:1.05rem;font-weight:700;color:#fb923c;line-height:1.1;
}
.hn-score span{display:block;font-size:.6rem;font-weight:500;color:#f97316;opacity:.8}
.hn-card.warm .hn-score{background:rgba(251,146,60,.14);border-color:rgba(251,146,60,.3);color:#fbbf24}
.hn-card.hot  .hn-score{
  background:rgba(239,68,68,.12);border-color:rgba(239,68,68,.3);color:#f87171;
  animation:score-pulse 3s ease-in-out infinite;
}
@keyframes score-pulse{
  0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.2)}
  50%    {box-shadow:0 0 0 6px rgba(239,68,68,0)}
}
.hn-title{
  font-size:.855rem;font-weight:600;line-height:1.45;
  color:var(--text);transition:color .15s;
}
.hn-card:hover .hn-title{color:#fb923c}
.hn-sub{font-size:.72rem;color:var(--muted);margin-top:.3rem}

/* ── Sections ── */
.cat-section{margin-bottom:3rem}
.sec-hdr{
  display:flex;align-items:center;gap:.55rem;
  margin-bottom:1.2rem;padding-bottom:.65rem;
  border-bottom:1px solid var(--border);
}
.sec-icon{font-size:1.2rem}
.sec-title{
  font-family:'Space Grotesk',sans-serif;
  font-size:1.05rem;font-weight:600;color:var(--cc);
}
.sec-count{
  margin-left:auto;font-size:.7rem;color:var(--muted);
  background:var(--card);border:1px solid var(--border);
  padding:.13rem .52rem;border-radius:12px;
}

/* ── Cards ── */
.card-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(320px,1fr));
  gap:.9rem;
}
.card{
  background:var(--card);border:1px solid var(--border);
  border-radius:14px;padding:1.05rem 1.15rem;
  display:flex;flex-direction:column;gap:.5rem;
  transition:border-color .2s,background .2s,transform .2s,box-shadow .2s;
  position:relative;overflow:hidden;
}
.card::before{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:var(--cc,#8b5cf6);opacity:0;transition:opacity .2s;
}
.card:hover{
  border-color:color-mix(in srgb,var(--cc) 38%,transparent);
  background:var(--card-h);transform:translateY(-3px);
  box-shadow:0 10px 30px rgba(0,0,0,.4),0 0 0 1px color-mix(in srgb,var(--cc) 12%,transparent);
}
.card:hover::before{opacity:1}
.card-top{display:flex;align-items:center;justify-content:space-between;gap:.5rem}
.card-meta{font-size:.7rem;color:var(--muted);white-space:nowrap}
.card-title{font-size:.9rem;font-weight:600;line-height:1.45}
.card-title a{color:var(--text);transition:color .15s}
.card-title a:hover{color:var(--cc,#a78bfa)}
.card-authors{font-size:.74rem;color:var(--dim);font-style:italic;line-height:1.4}
.card-desc{
  font-size:.8rem;color:var(--muted);line-height:1.55;flex-grow:1;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;
}
.card-read{
  font-size:.76rem;font-weight:500;margin-top:.1rem;
  color:color-mix(in srgb,var(--cc) 85%,#fff);
  transition:opacity .15s;
}
.card-read:hover{opacity:.7}

/* ── Pills ── */
.pill{
  display:inline-block;font-size:.65rem;font-weight:700;letter-spacing:.04em;
  padding:.12rem .46rem;border-radius:5px;border:1px solid;text-transform:uppercase;
  white-space:nowrap;
}

/* ── Empty ── */
.empty{text-align:center;padding:3rem 1rem;color:var(--muted)}
.empty-icon{font-size:3rem;margin-bottom:1rem}

/* ── Footer ── */
.site-footer{
  background:var(--surface);border-top:1px solid var(--border);
  padding:2rem 1.5rem;margin-top:3rem;
}
.footer-inner{
  max-width:1180px;margin:0 auto;
  display:flex;flex-direction:column;align-items:center;gap:.9rem;text-align:center;
}
.footer-name{
  font-family:'Space Grotesk',sans-serif;font-size:1.05rem;font-weight:700;
  background:linear-gradient(130deg,#a78bfa,#38bdf8);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.footer-links{display:flex;gap:1.2rem;flex-wrap:wrap;justify-content:center}
.footer-links a{font-size:.82rem;color:var(--muted);transition:color .15s}
.footer-links a:hover{color:var(--text)}
.footer-sources{display:flex;gap:.5rem;flex-wrap:wrap;justify-content:center;font-size:.74rem;color:var(--dim)}
.footer-sources span::after{content:'·';margin-left:.5rem}
.footer-sources span:last-child::after{content:''}
.footer-note{font-size:.74rem;color:var(--dim)}

/* ── Scroll top ── */
.scroll-top{
  position:fixed;bottom:1.5rem;right:1.5rem;z-index:200;
  background:rgba(13,13,36,.9);border:1px solid rgba(167,139,250,.3);
  color:#a78bfa;width:38px;height:38px;border-radius:50%;
  display:none;align-items:center;justify-content:center;
  font-size:1.1rem;cursor:pointer;backdrop-filter:blur(8px);
  transition:background .2s,transform .2s;
  box-shadow:0 4px 12px rgba(0,0,0,.35);
}
.scroll-top:hover{background:rgba(99,102,241,.25);transform:translateY(-2px)}
.scroll-top.visible{display:flex}

/* ── No results ── */
.no-results{
  display:none;text-align:center;padding:2.5rem;
  color:var(--muted);font-size:.9rem;
}
.no-results.visible{display:block}

/* ── Responsive ── */
@media(max-width:768px){
  .header-inner{flex-wrap:wrap}
  .featured-card{padding:1.5rem}
  main{padding:1.25rem 1rem}
  .cat-nav{padding:.7rem 1rem}
  .search-hint{display:none}
}
@media(max-width:520px){
  .card-grid{grid-template-columns:1fr}
  .hn-grid{grid-template-columns:1fr}
  .header-date{display:none}
}
"""

# ─── JS ───────────────────────────────────────────────────────────────────────

JS = r"""
(function() {
  // Search
  const inp = document.getElementById('search');
  const noR = document.getElementById('no-results');
  if (inp) {
    inp.addEventListener('input', function() {
      const q = this.value.trim().toLowerCase();
      let totalVisible = 0;
      document.querySelectorAll('[data-search]').forEach(el => {
        const match = !q || el.dataset.search.includes(q);
        el.style.display = match ? '' : 'none';
        if (match && el.classList.contains('card')) totalVisible++;
        if (match && el.classList.contains('hn-card')) totalVisible++;
      });
      // hide empty sections
      document.querySelectorAll('.cat-section').forEach(sec => {
        const v = sec.querySelectorAll('.card:not([style*="none"])').length;
        sec.style.display = v === 0 ? 'none' : '';
      });
      const hnGrid = document.querySelector('.hn-grid');
      if (hnGrid) {
        const v = hnGrid.querySelectorAll('.hn-card:not([style*="none"])').length;
        if (hnGrid.closest('.hn-section'))
          hnGrid.closest('.hn-section').style.display = v === 0 ? 'none' : '';
      }
      if (noR) noR.classList.toggle('visible', q && totalVisible === 0);
    });
  }
  // Keyboard shortcut / to focus
  document.addEventListener('keydown', function(e) {
    if (e.key === '/' && document.activeElement !== inp) {
      e.preventDefault(); inp && inp.focus();
    }
    if (e.key === 'Escape' && document.activeElement === inp) {
      inp.value = ''; inp.dispatchEvent(new Event('input')); inp.blur();
    }
  });
  // Scroll-to-top button
  const btn = document.querySelector('.scroll-top');
  if (btn) {
    window.addEventListener('scroll', function() {
      btn.classList.toggle('visible', window.scrollY > 400);
    }, {passive: true});
  }
})();
"""

# ─── Full page ────────────────────────────────────────────────────────────────

def full_page(featured: Optional[Dict],
              sections: Dict[str, List[Dict]],
              hn_trending: List[Dict],
              issue: int,
              generated: datetime) -> str:

    now_str = generated.strftime("%B %d, %Y")
    gen_iso = generated.strftime("%Y-%m-%dT%H:%M:%SZ")
    total   = sum(len(v) for v in sections.values())
    src_set = sorted({a["source"] for v in sections.values() for a in v})

    # Featured
    feat_block = featured_html(featured) if featured else ""

    # HN trending
    hn_block = ""
    if hn_trending:
        hn_cards = "\n".join(hn_trend_card(a) for a in hn_trending)
        hn_block = f'''<section class="hn-section">
    <header class="hn-hdr">
      <span class="hn-hdr-icon">🔥</span>
      <h2 class="hn-hdr-title">Trending on Hacker News</h2>
      <span class="hn-hdr-sub">{len(hn_trending)} stories by score</span>
    </header>
    <div class="hn-grid">{hn_cards}</div>
  </section>'''

    # Category sections
    cat_order   = list(CATEGORIES.keys())
    active_cats = [c for c in cat_order if sections.get(c)]
    secs_block  = "".join(section_html(c, sections[c]) for c in active_cats)

    if not feat_block and not secs_block and not hn_block:
        secs_block = '''<div class="empty">
      <div class="empty-icon">🤖</div>
      <p>No articles fetched yet. The workflow will populate this soon.</p>
    </div>'''

    # Nav
    nav_links = "".join(
        f'<a class="nav-pill" href="#{c}" style="--cc:{CATEGORIES[c]["color"]}">'
        f'{CATEGORIES[c]["icon"]}&thinsp;{h(CATEGORIES[c]["label"])}</a>'
        for c in active_cats
    )
    nav_block = f'<nav class="cat-nav">{nav_links}</nav>' if nav_links else ""

    # Stats
    stats_items = "".join(
        f'<span class="stat"><span class="stat-dot" style="--c:{CATEGORIES[c]["color"]}"></span>'
        f'{CATEGORIES[c]["icon"]} <b>{len(sections.get(c,[]))}</b>&nbsp;{h(CATEGORIES[c]["label"])}</span>'
        for c in active_cats if sections.get(c)
    )
    if hn_trending:
        stats_items += (f'<span class="stat"><span class="stat-dot" style="--c:#f97316"></span>'
                        f'🔥 <b>{len(hn_trending)}</b>&nbsp;HN Trending</span>')
    stats_block = f'<div class="stats-bar">{stats_items}</div>' if stats_items else ""

    sources_pills = "".join(f'<span>{h(s)}</span>' for s in src_set[:14])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>AI Pulse — Daily AI News Digest · Issue #{issue}</title>
  <meta name="description" content="Daily curated AI news: research, agents, products &amp; industry — Issue #{issue}, {now_str}">
  <meta property="og:title"       content="AI Pulse — Issue #{issue} · {now_str}">
  <meta property="og:description" content="Daily AI news: breakthroughs, agents, products, open source, and industry.">
  <meta property="og:type"        content="website">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
  <style>{CSS}</style>
</head>
<body>
<div class="page">

  <header class="site-header">
    <div class="header-inner">
      <div class="brand">
        <span class="brand-logo">⚡</span>
        <div>
          <div class="brand-name">AI Pulse</div>
          <div class="brand-sub">Daily AI News Digest</div>
        </div>
      </div>
      <div class="header-right">
        <span class="issue-badge">Issue #{issue}</span>
        <span class="header-date"><span class="live-dot"></span>{now_str}</span>
      </div>
    </div>
    {nav_block}
  </header>

  <main>
    <div class="search-wrap">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
      </svg>
      <input id="search" type="search" placeholder="Search articles… (press / to focus)" autocomplete="off">
      <span class="search-hint">/ to search · Esc to clear</span>
    </div>

    {feat_block}
    {stats_block}
    {hn_block}
    {secs_block}
    <p id="no-results">No articles match your search. Try a different keyword.</p>
  </main>

  <footer class="site-footer">
    <div class="footer-inner">
      <div class="footer-name">⚡ AI Pulse</div>
      <div class="footer-links">
        <a href="https://github.com/oeway/ai-news-channel" target="_blank" rel="noopener">GitHub</a>
        <a href="https://arxiv.org/list/cs.AI/recent" target="_blank" rel="noopener">arXiv CS.AI</a>
        <a href="https://news.ycombinator.com" target="_blank" rel="noopener">Hacker News</a>
      </div>
      <div class="footer-sources">{sources_pills}</div>
      <div class="footer-note">
        Auto-generated from {len(src_set)} sources · {total} articles · Last updated {now_str}
        · <time datetime="{gen_iso}">{gen_iso}</time>
      </div>
    </div>
  </footer>

</div>
<button class="scroll-top" onclick="window.scrollTo({{top:0,behavior:'smooth'}})" aria-label="Back to top">↑</button>
<script>{JS}</script>
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
    all_articles.extend(fetch_hn_recent())
    all_articles.extend(fetch_arxiv())
    print(f"  Total raw: {len(all_articles)}", flush=True)

    print("\n[2/4] Fetching HN trending…", flush=True)
    hn_trending = fetch_hn_trending()

    print("\n[3/4] Deduplicating & classifying…", flush=True)
    articles = dedup(all_articles)
    for a in articles:
        a["category"] = classify(a)
    articles.sort(key=score_article, reverse=True)
    print(f"  After dedup: {len(articles)}", flush=True)

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
    print(f"  Sections: {', '.join(f'{k}:{len(v)}' for k,v in sections.items() if v)}",
          flush=True)
    print(f"  Total placed: {total}", flush=True)

    print("\n[4/4] Rendering HTML…", flush=True)
    generated = datetime.now(timezone.utc)
    html_out  = full_page(featured, sections, hn_trending, issue, generated)
    OUTPUT.write_text(html_out, encoding="utf-8")
    save_issue(issue)

    print(f"\n✅ Written → {OUTPUT}", flush=True)
    print(f"   Issue #{issue} · {total} articles · {generated.strftime('%Y-%m-%dT%H:%M:%SZ')}")


if __name__ == "__main__":
    main()
