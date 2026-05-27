# ⚡ AI Pulse — Daily AI News Digest

A fully automated, daily newsletter that scrapes and curates the most important AI developments from 11+ trusted sources, rendered as a beautiful static site served via GitHub Pages.

**Live site:** https://oeway.github.io/ai-news-channel/

## What it covers

| Category | Topics |
|---|---|
| 🔬 Research & Breakthroughs | arXiv CS.AI/LG/CL papers, new model architectures, benchmarks, hardware |
| 🤖 AI Agents & Automation | Agent frameworks, tool use, multi-agent systems, agentic products |
| 🚀 New Products & Releases | Model launches, API updates, developer tools, new capabilities |
| 💼 Industry & Business | Funding, acquisitions, regulation, AI policy, enterprise deals |
| 🌐 Open Source & Community | Open-weight models, frameworks, Hugging Face, community projects |

## Sources

- **RSS feeds:** TechCrunch AI · VentureBeat AI · The Verge · Wired · IEEE Spectrum · MIT Tech Review
- **arXiv:** cs.AI, cs.LG, cs.CL, cs.NE (latest papers, sorted by submission date)
- **HackerNews:** via Algolia API, filtered for AI/ML/LLM topics

## How it works

```
07:00 UTC daily
    ↓
GitHub Actions runs scripts/fetch_news.py
    ↓
Fetches RSS + arXiv + HackerNews → deduplicates → classifies → scores
    ↓
Renders docs/index.html with top stories per category
    ↓
Commits new HTML → push triggers deploy workflow
    ↓
GitHub Pages serves the updated newsletter
```

### Workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `fetch-news.yml` | Daily 07:00 UTC + manual | Runs the Python fetcher, commits & pushes updated HTML |
| `deploy-pages.yml` | Push to `docs/**` on main | Deploys `docs/` to GitHub Pages |

## Setup

### 1. Enable GitHub Pages

In your repository settings → **Pages**:
- Set source to **Deploy from a branch**
- Branch: `main`, folder: `/docs`

> Alternatively, if the deploy workflow uses the GitHub Pages API (requires Pages to be enabled as a GitHub Actions source), it will deploy automatically via the workflow.

### 2. First run

The newsletter is bootstrapped with a hand-curated Issue #1. After enabling Pages, trigger the first automated update:

**Actions tab → "Fetch AI News & Update Newsletter" → Run workflow**

### 3. That's it

The `fetch-news.yml` workflow runs every morning at 07:00 UTC automatically.

## Local development

```bash
pip install -r requirements.txt
python scripts/fetch_news.py
open docs/index.html
```

## Project structure

```
.
├── docs/
│   ├── index.html        ← Generated newsletter (auto-updated daily)
│   ├── state.json        ← Tracks current issue number
│   └── .nojekyll         ← Prevents Jekyll processing on gh-pages
├── scripts/
│   └── fetch_news.py     ← News fetcher + HTML renderer
├── .github/workflows/
│   ├── fetch-news.yml    ← Daily news fetch → commit → push
│   └── deploy-pages.yml  ← Deploy docs/ to GitHub Pages
└── requirements.txt
```

## License

MIT
