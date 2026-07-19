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

1. **Daily at 07:00 UTC** — `.github/workflows/update-news.yml` runs `scripts/fetch_news.py` on GitHub's own runners (which have normal internet access)
2. The script fetches RSS feeds + arXiv + HackerNews, deduplicates, classifies, and scores articles, aborting without touching the published page if fewer than 5 articles were gathered
3. It renders a complete `docs/index.html` with the day's top stories and commits it to `main`
4. `.github/workflows/deploy-pages.yml` triggers on that push and publishes `docs/` to the `gh-pages` branch

## Setup

### Enable GitHub Pages

In your repository settings → **Pages** → set source to **Deploy from a branch**, branch `gh-pages`, folder `/ (root)`.

### Manual trigger

Go to **Actions → Update AI News Newsletter → Run workflow** for an immediate refresh.

## Local development

```bash
pip install -r requirements.txt
python scripts/fetch_news.py
open docs/index.html
```

### Curated / offline runs

`scripts/fetch_news.py` also accepts a `--from-json <path>` flag that feeds a hand-curated list of articles through the same dedupe/classify/score/render pipeline as a live fetch — useful when the live sources aren't reachable (e.g. a sandboxed environment) but you still want to publish real, verified stories. Each entry accepts `title`, `url`, `desc`, `source`, `source_color`, `date` (ISO 8601), an explicit `category` (`research` / `agents` / `products` / `industry` / `open_source`), and an optional `featured: true` to force the top story.

## License

MIT
