#!/usr/bin/env python3
"""
One-off generator for a curated newsletter issue, used when live scraping
is unavailable (e.g. sandboxed environments without access to news sites).
Reuses the render pipeline from fetch_news.py with hand-verified articles
gathered via web search instead of RSS/API fetches.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import fetch_news as fn

def d(s):
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)

ARTICLES = [
    # ── Research & Breakthroughs ──
    dict(title="A global workspace in language models",
         url="https://www.anthropic.com/research/global-workspace",
         desc="Anthropic interpretability researchers found a small internal “J-space” in Claude that "
              "functions like a shared workspace for reasoning — information becomes accessible to the rest "
              "of the model only after passing through it. Their new “Jacobian lens” can read, and sometimes "
              "intervene on, that space — a potential tool for auditing hidden reasoning and catching "
              "misbehavior before it reaches the final answer.",
         source="Anthropic Research", source_color="#c084fc", date=d("2026-07-06"), category="research"),
    dict(title="Ames Lab scientist provides AI-driven roadmap for future permanent magnet design",
         url="https://www.ameslab.gov/news/ames-lab-scientist-provides-ai-driven-roadmap-for-future-permanent-magnet-design",
         desc="A DOE-backed team is combining physics-based modeling, high-throughput simulation, and AI-driven "
              "reasoning to predict magnetic properties directly from atomic structure — part of the Genesis "
              "Mission push to discover rare-earth-free permanent magnets and secure America's critical mineral supply.",
         source="Ames National Laboratory", source_color="#22d3ee", date=d("2026-06-24"), category="research"),
    dict(title="Google DeepMind and Isomorphic Labs launch bioresilience program",
         url="https://www.axios.com/2026/07/16/google-deepmind-biosecurity-safety",
         desc="DeepMind unveiled a new bioresilience initiative aimed at pathogen surveillance, faster vaccine and "
              "therapeutic design, and stronger outbreak response — an early example of frontier AI capability "
              "aimed squarely at biosecurity.",
         source="Axios", source_color="#f97316", date=d("2026-07-16"), category="research"),

    # ── AI Agents & Automation ──
    dict(title="The coding agent wars are spilling into the rest of the office: Claude Cowork",
         url="https://techcrunch.com/2026/07/07/the-coding-agent-wars-are-spilling-into-the-rest-of-the-office-claude-cowork/",
         desc="Anthropic expanded Claude Cowork, its autonomous desktop agent, to web and mobile — it can now "
              "run scheduled tasks and keep working even when no device is online, pushing the “coding agent” "
              "pattern into general office work.",
         source="TechCrunch", source_color="#22c55e", date=d("2026-07-07"), category="agents"),
    dict(title="Microsoft merges Semantic Kernel and AutoGen into Agent Framework 1.0",
         url="https://github.com/microsoft/agent-framework/releases",
         desc="Microsoft folded its two agent SDKs, Semantic Kernel and AutoGen, into a single Microsoft Agent "
              "Framework 1.0 — consolidating orchestration, memory, and multi-agent workflow tooling into one "
              "library after a quarter that saw more agent-framework feature releases than any before it.",
         source="Microsoft / GitHub", source_color="#60a5fa", date=d("2026-04-03"), category="agents"),
    dict(title="Peraton unveils Peraton[x], an enterprise agentic AI platform for critical missions",
         url="https://www.peraton.com/news/peraton-unveils-peraton-x-the-first-true-enterprise-agentic-ai-platform-built-for-the-nations-most-critical-operations-and-missions",
         desc="Built inside Peraton Labs, Peraton[x] is pitched as a full-spectrum agentic platform — deployable "
              "in hours and programmable in plain English — for intelligence, risk management, and operational "
              "automation in government and defense settings.",
         source="Peraton", source_color="#c084fc", date=d("2026-07-07"), category="agents"),

    # ── New Products & Releases ──
    dict(title="OpenAI launches its new family of models with GPT-5.6",
         url="https://techcrunch.com/2026/07/09/openai-launches-its-new-family-of-models-with-gpt-5-6/",
         desc="OpenAI shipped GPT-5.6 as a three-tier lineup — Luna, Terra, and flagship Sol — targeting coding, "
              "enterprise work, and what OpenAI calls its “strongest cybersecurity model yet.” Sol reportedly "
              "tops the Artificial Analysis Coding Agent Index with a score of 80.",
         source="TechCrunch", source_color="#22c55e", date=d("2026-07-09"), category="products"),
    dict(title="Introducing Claude Sonnet 5",
         url="https://www.anthropic.com/news/claude-sonnet-5",
         desc="Anthropic's most agentic Sonnet yet lands near Opus 4.8-level performance at a fraction of the "
              "price — $2/$10 per million tokens through August — with a lower rate of undesirable behavior "
              "in agentic settings than Sonnet 4.6.",
         source="Anthropic", source_color="#c084fc", date=d("2026-06-30"), category="products"),
    dict(title="SpaceXAI releases Grok 4.5, which Elon describes as an ‘Opus-class model’",
         url="https://techcrunch.com/2026/07/08/spacexai-releases-grok-4-5-which-elon-describes-as-an-opus-class-model/",
         desc="xAI's first release since acquiring Cursor, Grok 4.5 is pitched as a coding- and agent-first model "
              "— “Opus-class, but faster and cheaper,” at $2/$6 per million tokens versus Opus 4.8's $5/$25.",
         source="TechCrunch", source_color="#22c55e", date=d("2026-07-08"), category="products"),
    dict(title="Gemini 3.5: frontier intelligence with action",
         url="https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-5/",
         desc="Google scrapped Gemini 2.5 Pro's base architecture for a full rebuild, targeting a 2M-token context "
              "window and a new “Deep Think” reasoning layer. Flash shipped first; Pro's general release "
              "slipped into mid-July after extra quality tuning from enterprise feedback.",
         source="Google", source_color="#60a5fa", date=d("2026-07-14"), category="products"),
    dict(title="OpenAI releases GPT-5.6 and ChatGPT Work tool",
         url="https://www.axios.com/2026/07/09/ai-openai-gpt-release",
         desc="Alongside the GPT-5.6 model family, OpenAI introduced ChatGPT Work, a new enterprise-focused agent "
              "tool bundled into the same release.",
         source="Axios", source_color="#f97316", date=d("2026-07-09"), category="products"),

    # ── Industry & Business ──
    dict(title="The real AI race may no longer be at the frontier",
         url="https://techcrunch.com/2026/07/14/the-real-ai-race-may-no-longer-be-at-the-frontier-open-models-hugging-face/",
         desc="Chinese open-weight models now account for 41% of Hugging Face downloads, and the six most-downloaded "
              "models on OpenRouter are all open models from Chinese firms — Tencent, Xiaomi, DeepSeek, MiniMax "
              "and Z.ai — a sign competition has shifted from frontier labs to who ships the best open weights.",
         source="TechCrunch", source_color="#22c55e", date=d("2026-07-14"), category="industry"),
    dict(title="Satya Nadella has issued a warning to companies using AI",
         url="https://techcrunch.com/2026/07/13/satya-nadella-has-issued-a-shocking-warning-to-companies-using-ai/",
         desc="Microsoft's CEO warned that AI users “pay twice” — once in subscription fees, again by handing "
              "over data — and pushed for “orchestration layers” that let companies switch between model "
              "providers instead of locking into one.",
         source="TechCrunch", source_color="#22c55e", date=d("2026-07-13"), category="industry"),
    dict(title="The week's biggest funding rounds: Helsing raises $1.8B",
         url="https://news.crunchbase.com/venture/biggest-funding-rounds-ai-energy-biotech-joulent/",
         desc="European defense-AI company Helsing raised $1.8B led by JPMorgan, Lightspeed and Iconiq — one of "
              "the week's largest rounds as AI-defense spending accelerates.",
         source="Crunchbase News", source_color="#4ade80", date=d("2026-07-13"), category="industry"),
    dict(title="Global startup investment hits record $510B in H1 2026 as AI boom accelerates",
         url="https://news.crunchbase.com/venture/global-startup-exits-ipo-ma-soar-ai-q2-h1-2026/",
         desc="H1 2026 venture funding blew past all of 2025 combined — with OpenAI and Anthropic alone soaking "
              "up $217B, 43% of every venture dollar raised this year.",
         source="Crunchbase News", source_color="#4ade80", date=d("2026-07-01"), category="industry"),
    dict(title="These AI startups are growing revenue at faster and faster rates",
         url="https://techcrunch.com/2026/07/08/these-ai-startups-are-growing-revenue-at-faster-and-faster-rates/",
         desc="AI-native startups are compounding revenue at unprecedented speed: recruiting platform Mercor hit "
              "$2B in annualized revenue just four months after crossing $1B, and legal-software startup Clio "
              "reached $500M ARR.",
         source="TechCrunch", source_color="#22c55e", date=d("2026-07-08"), category="industry"),

    # ── Open Source & Community ──
    dict(title="State of Open Source on Hugging Face: Spring 2026",
         url="https://huggingface.co/blog/huggingface/state-of-os-hf-spring-2026",
         desc="Hugging Face's spring roundup shows the open ecosystem's scale: nearly 3M public models and 1M "
              "public datasets, with a new repository created roughly every seven seconds.",
         source="Hugging Face", source_color="#fb923c", date=d("2026-06-15"), category="open_source"),
    dict(title="LongCat-2.0 ships as one of the largest open MoE releases yet",
         url="https://huggingface.co/blog/Svngoku/ai-models-week-july-09-2026",
         desc="LongCat-2.0 landed under an MIT license with 1.6T total parameters (~48B active per token) — "
              "one of the largest openly downloadable mixture-of-experts models released so far.",
         source="Hugging Face", source_color="#fb923c", date=d("2026-07-09"), category="open_source"),
    dict(title="Sber releases GigaChat 3.5 Ultra as new open flagship",
         url="https://huggingface.co/blog/Svngoku/ai-models-week-july-09-2026",
         desc="GigaChat 3.5 Ultra is tuned for coding, math, long-document analysis, and autonomous workflows, "
              "joining a wave of open releases arriving weekly on Hugging Face.",
         source="Hugging Face", source_color="#fb923c", date=d("2026-07-06"), category="open_source"),
]

FEATURED_URL = "https://www.anthropic.com/research/global-workspace"

def main():
    issue = fn.load_issue() + 1
    for a in ARTICLES:
        a["category"] = a.get("category") or fn.classify(a)
    articles = ARTICLES
    articles.sort(key=fn.score, reverse=True)

    sections = {cat: [] for cat in fn.CATEGORIES}
    for a in articles:
        cat = a.get("category", fn.DEFAULT_CATEGORY)
        if cat in sections and len(sections[cat]) < fn.MAX_PER_CATEGORY:
            sections[cat].append(a)

    featured = next((a for a in articles if a["url"] == FEATURED_URL), articles[0])

    generated = datetime.now(timezone.utc)
    html_out = fn.full_page(featured, sections, issue, generated)
    fn.OUTPUT.write_text(html_out, encoding="utf-8")
    fn.save_issue(issue)
    total = sum(len(v) for v in sections.values())
    print(f"Written Issue #{issue} · {total} articles · {generated.isoformat()}")

if __name__ == "__main__":
    main()
