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

1. **Daily at 07:00 UTC** — `.github/workflows/update-newsletter.yml` runs `scripts/fetch_news.py` on GitHub's runners
2. The script fetches RSS feeds + arXiv + HackerNews, deduplicates, classifies, and scores articles (aborting without publishing if fewer than 5 articles come back, so a source outage never blanks the page)
3. It renders a complete `docs/index.html` with the day's top stories and commits it straight to `main`
4. `.github/workflows/deploy-pages.yml` republishes `docs/` to the `gh-pages` branch whenever it changes, and GitHub Pages serves it immediately

## Setup

### Enable GitHub Pages

In your repository settings → **Pages** → set source to **Deploy from a branch**, branch `gh-pages`, folder `/ (root)`.

### Manual trigger

Go to **Actions → Update AI News Newsletter → Run workflow** for an immediate update.

## Local development

```bash
pip install -r requirements.txt
python scripts/fetch_news.py
open docs/index.html
```

### Curated / offline mode

If live fetching isn't available (e.g. a sandboxed environment that blocks the RSS/arXiv hosts), feed a hand-curated article list through the same classify/score/render pipeline:

```bash
python scripts/fetch_news.py --from-json articles.json
```

Each entry needs `title`, `url`, `source`; `desc`, `source_color`, `date` (ISO 8601), and `category` (one of `research`, `agents`, `products`, `industry`, `open_source`) are optional.

## License

MIT
