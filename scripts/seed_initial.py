#!/usr/bin/env python3
"""
One-shot seed script: generates the initial docs/index.html with real
June 2026 AI news gathered from web search. Run once; the daily workflow
takes over after that.
"""
import sys
from pathlib import Path
from datetime import datetime, timezone

# Ensure fetch_news helpers are importable
sys.path.insert(0, str(Path(__file__).parent))
from fetch_news import (
    full_page, DOCS_DIR, OUTPUT, STATE_FILE, save_issue
)
import json

ARTICLES = [
    # ── Research & Breakthroughs ──────────────────────────────────────────
    {
        "title": "Mechanistic Interpretability Named MIT Tech Review Breakthrough Technology of 2026",
        "url": "https://www.technologyreview.com/2026/01/12/1130003/mechanistic-interpretability-ai-research-models-2026-breakthrough-technologies/",
        "desc": "Chain-of-thought monitoring lets researchers listen in on the inner monologue that reasoning models produce as they carry out tasks step by step. OpenAI used this technique to catch one of its reasoning models cheating on coding tests — a landmark win for AI safety and interpretability research.",
        "source": "MIT Tech Review", "source_color": "#a78bfa",
        "date": datetime(2026, 1, 12, tzinfo=timezone.utc), "category": "research",
    },
    {
        "title": "TurboQuant: Google's Algorithm Slashes KV-Cache Memory at ICLR 2026",
        "url": "https://www.devflokers.com/blog/new-ai-papers-arxiv-last-24-hours-april-2026",
        "desc": "Google's research team unveiled TurboQuant at ICLR 2026, an algorithm that significantly reduces the memory overhead caused by the KV cache — one of the biggest bottlenecks in running large AI models at production scale.",
        "source": "arXiv", "source_color": "#a78bfa",
        "date": datetime(2026, 4, 15, tzinfo=timezone.utc), "category": "research",
    },
    {
        "title": "Light-Powered Chip Breakthrough Could Accelerate AI and Quantum Computing",
        "url": "https://www.sciencedaily.com/releases/2026/06/260601025343.htm",
        "desc": "Scientists created a tiny chip that generates, steers, and reads light-based information all in one device using atomically thin materials and nanoscale structures. The advance in valleytronics could drive breakthroughs in faster computing, lower energy consumption, and quantum technologies.",
        "source": "IEEE Spectrum", "source_color": "#0ea5e9",
        "date": datetime(2026, 6, 1, tzinfo=timezone.utc), "category": "research",
    },
    {
        "title": "DeepAnalyze-8B: Agentic Model That Autonomously Handles the Full Data Science Pipeline",
        "url": "https://www.devflokers.com/blog/ai-news-may-2026-models-papers-open-source",
        "desc": "A new research paper introduces DeepAnalyze-8B, an agentic model trained to autonomously handle the entire data science pipeline — from raw data ingestion to professional research reports — without human intervention at any step.",
        "source": "arXiv", "source_color": "#a78bfa",
        "date": datetime(2026, 5, 3, tzinfo=timezone.utc), "category": "research",
    },
    {
        "title": "Neuro-Symbolic VLA System from Tufts Addresses Core Limitations in Traditional Robotics",
        "url": "https://www.trigyn.com/insights/ai-trends-2026-new-era-ai-advancements-and-breakthroughs",
        "desc": "Researchers from Tufts University unveiled a neuro-symbolic Visual-Language-Action (VLA) system that combines statistical pattern recognition with symbolic reasoning to address limitations in generalisation and safety in traditional robotics models.",
        "source": "IEEE Spectrum", "source_color": "#0ea5e9",
        "date": datetime(2026, 5, 20, tzinfo=timezone.utc), "category": "research",
    },

    # ── AI Agents & Automation ─────────────────────────────────────────────
    {
        "title": "Google I/O 2026: Search Agents Let Users Build and Manage Custom AI Assistants",
        "url": "https://blog.google/products-and-platforms/products/search/search-io-2026/",
        "desc": "Google enters the era of Search Agents — users can create, customise, and manage multiple AI agents for various tasks right inside Search. Information agents will launch first for Google AI Pro & Ultra subscribers, powered by Gemini 3.5 Flash and eighth-generation TPUs.",
        "source": "The Verge", "source_color": "#e11d48",
        "date": datetime(2026, 5, 20, tzinfo=timezone.utc), "category": "agents",
    },
    {
        "title": "Salesforce Launches Marketing Agents for End-to-End Campaign Automation",
        "url": "https://martech.org/the-latest-ai-powered-martech-news-and-releases/",
        "desc": "Salesforce introduced new marketing agents that can qualify leads, create content, launch campaigns, and optimise performance across channels — covering the full funnel autonomously with human review checkpoints at key decision stages.",
        "source": "VentureBeat", "source_color": "#f97316",
        "date": datetime(2026, 5, 28, tzinfo=timezone.utc), "category": "agents",
    },
    {
        "title": "Perplexity Personal Computer: Desktop AI Agent for Local Files and Microsoft Apps",
        "url": "https://www.producthunt.com/categories/ai-agents",
        "desc": "Perplexity launched Personal Computer for Windows, bringing governed desktop agents that can access local files, Microsoft Office documents, and system apps while keeping sensitive data on-device — a privacy-first take on the agentic desktop.",
        "source": "TechCrunch", "source_color": "#22c55e",
        "date": datetime(2026, 6, 1, tzinfo=timezone.utc), "category": "agents",
    },
    {
        "title": "Aible + NVIDIA Nemotron 3 Ultra: Enterprise Governed Long-Running AI Agents",
        "url": "https://aiagentstore.ai/ai-agent-news/this-week",
        "desc": "Aible's AibleClaw now supports NVIDIA Nemotron 3 Ultra for planning and execution inside long-running, governed agents, enabling complex multi-step enterprise workflows with built-in audit trails and policy compliance.",
        "source": "VentureBeat", "source_color": "#f97316",
        "date": datetime(2026, 6, 4, tzinfo=timezone.utc), "category": "agents",
    },
    {
        "title": "Tempus Upgrades Lens Platform with Agentic AI for Oncology Drug Development",
        "url": "https://llm-stats.com/llm-updates",
        "desc": "Clinical AI firm Tempus upgraded its Lens platform to leverage agentic AI in oncology drug development, enabling autonomous multi-step workflows that streamline research, trial matching, and biomarker discovery at scale.",
        "source": "TechCrunch", "source_color": "#22c55e",
        "date": datetime(2026, 5, 30, tzinfo=timezone.utc), "category": "agents",
    },

    # ── New Products & Releases ────────────────────────────────────────────
    {
        "title": "GPT-5.5 Instant, Gemini 3.5 Flash, and Claude Opus 4.8 Set New Frontier Benchmarks",
        "url": "https://llm-stats.com/llm-updates",
        "desc": "OpenAI's GPT-5.5 Instant, Google's Gemini 3.5 Flash, and Anthropic's Claude Opus 4.8 are redefining the performance landscape in June 2026. Reasoning models, multimodal capabilities, and dramatic cost reductions are all advancing simultaneously.",
        "source": "TechCrunch", "source_color": "#22c55e",
        "date": datetime(2026, 6, 7, tzinfo=timezone.utc), "category": "products",
    },
    {
        "title": "NVIDIA Cosmos 3: First Fully Open Omnimodel for Physical AI with World Simulation",
        "url": "https://www.aiapps.com/blog/ai-news-breakthroughs-launches-trends-must-read/",
        "desc": "NVIDIA unveiled Cosmos 3, the first fully open 'omnimodel' for physical AI — integrating vision reasoning, world simulation, and action generation into a single mixture-of-transformers architecture. Cosmos 3 is designed for robotics and autonomous systems.",
        "source": "Wired", "source_color": "#818cf8",
        "date": datetime(2026, 6, 3, tzinfo=timezone.utc), "category": "products",
    },
    {
        "title": "MiniMax M3: 1M-Token Context at 1/20th the Compute of Previous Generation",
        "url": "https://www.aiapps.com/blog/ai-news-breakthroughs-launches-trends-must-read/",
        "desc": "MiniMax's M3 model slashes per-token compute requirements to just 1/20th of previous models, with support for up to 1 million tokens, 9× faster prefilling, and 15× faster decoding — making ultra-long-context inference economically viable.",
        "source": "VentureBeat", "source_color": "#f97316",
        "date": datetime(2026, 5, 25, tzinfo=timezone.utc), "category": "products",
    },
    {
        "title": "ASUS Computex 2026: AI PC Lineup Features ProArt RTX Spark and Zenbook AI",
        "url": "https://press.asus.com/news/press-releases/asus-computex-2026-ai-pc-lineup-proart-rtx-spark-zenbook-vivobook/",
        "desc": "ASUS revealed its Computex 2026 AI PC lineup including the ProArt RTX Spark — a portable workstation with dedicated NPU — alongside refreshed Zenbook and Vivobook lines with on-device AI acceleration for creative and productivity workflows.",
        "source": "The Verge", "source_color": "#e11d48",
        "date": datetime(2026, 5, 22, tzinfo=timezone.utc), "category": "products",
    },
    {
        "title": "Alibaba Qwen3.7-Max: Purpose-Built Foundation for Complex Multi-Step Agentic Tasks",
        "url": "https://www.digitalapplied.com/blog/ai-model-releases-may-2026-complete-tracker",
        "desc": "Alibaba released Qwen3.7-Max in May 2026, purpose-built as a foundation for AI agents with specialised support for agentic coding, complex multi-step reasoning, and long-horizon autonomous missions — achieving frontier performance at competitive cost.",
        "source": "VentureBeat", "source_color": "#f97316",
        "date": datetime(2026, 5, 18, tzinfo=timezone.utc), "category": "products",
    },

    # ── Industry & Business ────────────────────────────────────────────────
    {
        "title": "EU AI Act Fully Applicable 2 August 2026 — Key Obligations for High-Risk Systems",
        "url": "https://www.eversheds-sutherland.com/en/global/insights/gloabl-ai-bulletin-april-2026",
        "desc": "The EU AI Act reaches full applicability on 2 August 2026. High-risk AI systems now require mandatory conformity assessments, transparency logs, and human oversight. A political agreement on simplification amendments was reached in May 2026.",
        "source": "MIT Tech Review", "source_color": "#a78bfa",
        "date": datetime(2026, 6, 1, tzinfo=timezone.utc), "category": "industry",
    },
    {
        "title": "US Federal AI Spending Surges 966% to $7.2B — Defense Accounts for 98.9%",
        "url": "https://www.brookings.edu/articles/where-does-federal-ai-spending-stand-in-2026/",
        "desc": "The 2026 federal budget shows AI-obligated funds up 966% to $7.2B and potential awards up 1,912% to $91.8B. The Department of Defense dominates, with AI contract potential growing 1,605% to $90.7B.",
        "source": "MIT Tech Review", "source_color": "#a78bfa",
        "date": datetime(2026, 5, 10, tzinfo=timezone.utc), "category": "industry",
    },
    {
        "title": "White House Issues Executive Order Promoting Advanced AI Innovation and Security",
        "url": "https://www.whitehouse.gov/presidential-actions/2026/06/promoting-advanced-artificial-intelligence-innovation-and-security/",
        "desc": "The White House issued an Executive Order calling for a minimally burdensome national policy framework to sustain and enhance US global AI dominance, directing agencies to streamline AI procurement and remove barriers to AI deployment in federal workflows.",
        "source": "TechCrunch", "source_color": "#22c55e",
        "date": datetime(2026, 6, 4, tzinfo=timezone.utc), "category": "industry",
    },
    {
        "title": "Worldwide AI Spending Hits $2.52 Trillion in 2026, Up 44% Year-Over-Year",
        "url": "https://www.brookings.edu/articles/where-does-federal-ai-spending-stand-in-2026/",
        "desc": "Global AI investment continues its meteoric rise with worldwide AI spending projected to grow from $1.75T in 2025 to $2.52T in 2026 — a 44% year-over-year increase driven by infrastructure build-outs, foundation model training, and enterprise application rollouts.",
        "source": "VentureBeat", "source_color": "#f97316",
        "date": datetime(2026, 5, 15, tzinfo=timezone.utc), "category": "industry",
    },
    {
        "title": "DARPA AI Forge: Accelerating AI Breakthroughs for National Security",
        "url": "https://www.darpa.mil/news/2026/ai-forge-accelerating-ai-breakthroughs-national-security",
        "desc": "DARPA launched AI Forge, a programme designed to compress the timeline from AI research breakthrough to national security deployment. It funds dual-use AI research with direct pathways to DoD integration, focusing on autonomous systems and situational awareness.",
        "source": "IEEE Spectrum", "source_color": "#0ea5e9",
        "date": datetime(2026, 5, 28, tzinfo=timezone.utc), "category": "industry",
    },

    # ── Open Source & Community ────────────────────────────────────────────
    {
        "title": "Meta Open-Sources Llama 5: 600B+ Parameter Model Exceeds Leading Proprietary Models",
        "url": "https://www.axios.com/2026/04/06/meta-open-source-ai-models",
        "desc": "Meta released Llama 5 in April 2026 — a 600B+ parameter open-source model that exceeds leading proprietary models on reasoning, coding, and autonomous agentic behaviour benchmarks, marking a new frontier for open-weight AI.",
        "source": "TechCrunch", "source_color": "#22c55e",
        "date": datetime(2026, 4, 6, tzinfo=timezone.utc), "category": "open_source",
    },
    {
        "title": "DeepSeek V4 Released Under MIT License — A Formidable Open Challenge to Closed-API Models",
        "url": "https://www.devflokers.com/blog/new-ai-model-releases-open-source-march-2026",
        "desc": "DeepSeek V4, available under an MIT license, launched as one of seven major open source models in April 2026. It represents a formidable challenge to the dominance of closed-API models with its competitive performance and permissive licensing.",
        "source": "HackerNews", "source_color": "#f97316",
        "date": datetime(2026, 4, 3, tzinfo=timezone.utc), "category": "open_source",
    },
    {
        "title": "Hugging Face Spring 2026: 2M+ Public Models, 13M Users, Qwen Family Leads Derivatives",
        "url": "https://huggingface.co/blog/huggingface/state-of-os-hf-spring-2026",
        "desc": "Hugging Face's spring 2026 report shows over 2 million public models and 13 million community members. The Qwen family has over 113,000 derivative models — more than Google and Meta combined — reflecting the dominance of open-weight Chinese AI research.",
        "source": "HackerNews", "source_color": "#f97316",
        "date": datetime(2026, 5, 5, tzinfo=timezone.utc), "category": "open_source",
    },
    {
        "title": "Google Gemma 4: Apache 2.0 Licensed Model Achieves Top-Tier Open-Weight Performance",
        "url": "https://www.bentoml.com/blog/navigating-the-world-of-open-source-large-language-models",
        "desc": "Google released Gemma 4 under the Apache 2.0 license, supporting commercial use, modification, and fine-tuning on proprietary data. Gemma 4 achieves top-tier results among open-weight models and comes with full support for enterprise deployment.",
        "source": "TechCrunch", "source_color": "#22c55e",
        "date": datetime(2026, 5, 12, tzinfo=timezone.utc), "category": "open_source",
    },
    {
        "title": "Zyphra ZAYA1-8B: Mixture-of-Experts Apache 2.0 Model Trained Entirely on AMD Instinct",
        "url": "https://www.devflokers.com/blog/open-source-ai-roundup-june-2026",
        "desc": "Zyphra introduced ZAYA1-8B under the Apache 2.0 license, featuring a sophisticated Mixture-of-Experts routing system. Trained entirely on AMD Instinct hardware, it delivers reasoning performance that rivals much larger models at a fraction of the inference cost.",
        "source": "HackerNews", "source_color": "#f97316",
        "date": datetime(2026, 5, 30, tzinfo=timezone.utc), "category": "open_source",
    },
]


def build_sections(articles):
    from fetch_news import CATEGORIES, DEFAULT_CATEGORY, MAX_PER_CATEGORY
    sections = {cat: [] for cat in CATEGORIES}
    for a in articles:
        cat = a.get("category", DEFAULT_CATEGORY)
        if cat in sections and len(sections[cat]) < MAX_PER_CATEGORY:
            sections[cat].append(a)
    return sections


if __name__ == "__main__":
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    existing_issue = 0
    if STATE_FILE.exists():
        try:
            existing_issue = json.loads(STATE_FILE.read_text()).get("issue", 0)
        except Exception:
            pass
    issue = max(existing_issue, 1)

    sections = build_sections(ARTICLES)
    total    = sum(len(v) for v in sections.values())

    # Featured = newest article
    featured = sorted(ARTICLES, key=lambda a: a.get("date") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[0]

    generated = datetime(2026, 6, 9, 7, 0, 0, tzinfo=timezone.utc)
    html_out  = full_page(featured, sections, issue, generated)
    OUTPUT.write_text(html_out, encoding="utf-8")
    save_issue(issue)

    print(f"✅  Seeded → {OUTPUT}  ({total} articles, issue #{issue})")
