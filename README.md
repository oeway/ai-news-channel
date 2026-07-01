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

1. **Daily at 07:00 UTC** — the `Update AI News Newsletter` workflow runs `scripts/fetch_news.py`
2. The script fetches RSS feeds + arXiv + HackerNews, deduplicates, classifies, and scores articles
3. It renders a complete `docs/index.html` with the day's top stories and commits it to `main`
4. The commit to `docs/` triggers the `Deploy to GitHub Pages` workflow, which publishes the site

## Setup

### Enable GitHub Pages

In your repository settings → **Pages** → set source to **GitHub Actions**. The `Deploy to GitHub Pages` workflow (`.github/workflows/deploy-pages.yml`) takes care of building and publishing `docs/` from there.

### Manual trigger

Go to **Actions → Update AI News Newsletter → Run workflow** for an immediate content refresh, or **Actions → Deploy to GitHub Pages → Run workflow** to just republish the current `docs/`.

## Local development

```bash
pip install -r requirements.txt
python scripts/fetch_news.py
open docs/index.html
```

## License

MIT
