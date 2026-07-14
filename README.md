# ⚡ AI Pulse — Daily AI News Digest

A fully automated, daily newsletter that scrapes and curates the most important AI developments from 8+ trusted sources, rendered as a beautiful static site served via GitHub Pages.

## What it covers

| Category | Topics |
|---|---|
| 🔬 Research & Breakthroughs | arXiv CS.AI/LG/CL papers, new model architectures, benchmarks |
| 🤖 AI Agents & Automation | Agent frameworks, tool use, multi-agent systems, agentic products |
| 🚀 New Products & Releases | Model launches, API updates, developer tools |
| 💼 Industry & Business | Funding, acquisitions, regulation, AI policy |
| 🌐 Open Source & Community | Open-weight models, frameworks, community projects |

## Sources

- TechCrunch AI · VentureBeat AI · The Verge · Wired · IEEE Spectrum · MIT Tech Review
- arXiv (cs.AI, cs.LG, cs.CL, cs.NE)
- HackerNews via Algolia API

## How it works

1. **Daily at 07:00 UTC** — GitHub Actions runs `scripts/fetch_news.py`
2. The script fetches RSS feeds + arXiv + HackerNews, deduplicates, classifies, and scores articles
3. It renders a complete `docs/index.html` with the day's top stories
4. The action commits the new HTML and GitHub Pages serves it immediately

## Setup

### Enable GitHub Pages

In your repository settings → **Pages** → set source to **Deploy from a branch**, branch `main`, folder `/docs`.

### Manual trigger

Go to **Actions → Update AI News Newsletter → Run workflow** for an immediate update.

## Local development

```bash
pip install -r requirements.txt
python scripts/fetch_news.py
open docs/index.html
```

If your network blocks the RSS/arXiv/HN hosts directly (e.g. a sandboxed dev
environment), you can render from a hand-curated article list instead — it
flows through the same dedup/classify/score/render pipeline so the output is
visually identical to a live run:

```bash
python scripts/fetch_news.py --from-json path/to/articles.json
```

Each entry needs `title`, `url`, and optionally `desc`, `source`,
`source_color`, `date` (ISO 8601), and `category` (one of `research`,
`agents`, `products`, `industry`, `open_source` — auto-classified from
keywords if omitted).

## License

MIT
