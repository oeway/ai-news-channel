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

1. **Daily at 07:00 UTC** — the `Update AI News Newsletter` workflow (`.github/workflows/update-newsletter.yml`) runs `scripts/fetch_news.py` on `main`
2. The script fetches RSS feeds + arXiv + HackerNews, deduplicates, classifies, and scores articles (aborts without publishing if fewer than 5 articles were gathered)
3. It renders a complete `docs/index.html` with the day's top stories and pushes it back to `main`
4. That push triggers `Deploy to GitHub Pages` (`.github/workflows/deploy-pages.yml`), which copies `docs/` onto the `gh-pages` branch

## Setup

### Enable GitHub Pages

In your repository settings → **Pages** → set source to **Deploy from a branch**, branch `gh-pages`, folder `/` (root). The `gh-pages` branch is created/updated automatically by the deploy workflow — don't create it by hand.

### Manual trigger

Go to **Actions → Update AI News Newsletter → Run workflow** for an immediate content refresh, or **Actions → Deploy to GitHub Pages → Run workflow** to just republish the current `docs/` contents.

## Local development

```bash
pip install -r requirements.txt
python scripts/fetch_news.py
open docs/index.html
```

### Curated / offline mode

If live RSS/arXiv/HN access isn't available (e.g. a restricted sandbox), pass a hand-curated article list through the same classify/score/render pipeline:

```bash
python scripts/fetch_news.py --from-json articles.json
```

`articles.json` is an array of objects: `{"title", "url", "source", "date", "desc", "category"}` (`category` and `date` are optional — they'll be inferred/omitted if missing).

## License

MIT
