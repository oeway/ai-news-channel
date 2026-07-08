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

1. An AI agent session periodically researches the latest AI news (RSS/arXiv sources when reachable, web search otherwise), curates and categorizes the top stories, and renders a complete `docs/index.html` via `scripts/fetch_news.py`'s templates.
2. The agent commits and pushes the updated newsletter.
3. A GitHub Actions workflow (`.github/workflows/deploy-pages.yml`) redeploys GitHub Pages whenever `docs/` changes on `main`.

`scripts/fetch_news.py` can also be run standalone to pull RSS/arXiv/HackerNews directly and regenerate the page — useful for local development or environments with unrestricted outbound network access.

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

## License

MIT
