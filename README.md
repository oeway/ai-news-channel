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
3. It renders a complete `docs/index.html` with the day's top stories
4. The action commits the new HTML to `main`; GitHub Pages serves it automatically
5. The `Deploy to GitHub Pages` workflow also mirrors `docs/` to a `gh-pages` branch as backup

## Setup

### Enable GitHub Pages

In your repository settings → **Pages** → set source to **Deploy from a branch**, branch `main`, folder `/docs`.

Alternatively set source to the `gh-pages` branch (root) if you prefer the mirrored approach.

### Manual trigger

Go to **Actions → Update AI News Newsletter → Run workflow** for an immediate update.

> **First-time setup:** `docs/index.html` ships with an empty placeholder — the
> newsletter generator needs outbound internet access (RSS/arXiv/HN) that only
> the GitHub-hosted Actions runner has, not every dev environment. Run the
> workflow once manually (above) after merging to `main` to populate the first
> real issue.

## Dependencies

The newsletter generator uses **Python stdlib only** — no external packages or pip installs required.

## Local development

```bash
# No dependencies needed — stdlib only
python scripts/fetch_news.py
open docs/index.html   # macOS; use xdg-open on Linux
```

## License

MIT
