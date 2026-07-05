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

1. **Daily at 07:00 UTC** — the `Update AI News Newsletter` GitHub Action runs `scripts/fetch_news.py`
2. The script fetches RSS feeds + arXiv + HackerNews, deduplicates, classifies, and scores articles
3. It renders a complete `docs/index.html` with the day's top stories and commits it to `main`
4. That commit triggers the `Deploy to GitHub Pages` action, which copies `docs/` onto the `gh-pages` branch so Pages can serve it

## Setup

### Enable GitHub Pages

In your repository settings → **Pages** → set source to **Deploy from a branch**, branch `gh-pages`, folder `/ (root)`.
(The `gh-pages` branch is created automatically the first time the deploy workflow runs.)

### Manual trigger

Go to **Actions → Update AI News Newsletter → Run workflow** to fetch fresh articles immediately, or **Actions → Deploy to GitHub Pages → Run workflow** to just republish the current `docs/` contents.

## Local development

```bash
pip install -r requirements.txt
python scripts/fetch_news.py
open docs/index.html
```

## License

MIT
