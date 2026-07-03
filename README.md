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

1. **Daily at 07:00 UTC** — the `Update AI News Newsletter` GitHub Actions workflow runs `scripts/fetch_news.py`
2. The script fetches RSS feeds + arXiv + HackerNews, deduplicates, classifies, and scores articles
3. It renders a complete `docs/index.html` with the day's top stories
4. The workflow commits the new HTML to `main`, then publishes `docs/` to the `gh-pages` branch in the same run
5. A second workflow, `Deploy to GitHub Pages`, republishes `docs/` to `gh-pages` whenever it changes on `main` (e.g. from a manual edit) — it's a safety net independent of the fetch job

## Setup

### Enable GitHub Pages

In your repository settings → **Pages** → set source to **Deploy from a branch**, branch `gh-pages`, folder `/` (root). The `gh-pages` branch is created/updated automatically by the workflows above — you don't need to create it by hand.

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
