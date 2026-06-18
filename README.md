# ⚡ AI Pulse — Daily AI News Digest

A fully automated, daily newsletter that scrapes and curates the most important AI developments from 10+ trusted sources, rendered as a beautiful dark-themed static site served via GitHub Pages.

## Live Site

→ **[oeway.github.io/ai-news-channel](https://oeway.github.io/ai-news-channel)**

Updated automatically every day at **07:00 UTC** by GitHub Actions.

## What it covers

| Category | Topics |
|---|---|
| 🔬 Research & Breakthroughs | arXiv CS.AI/LG/CL papers, new model architectures, benchmarks, alignment |
| 🤖 AI Agents & Automation | Agent frameworks, tool use, MCP, multi-agent systems, planning & memory |
| 🚀 New Products & Releases | Model launches, API updates, developer tools, new apps |
| 💼 Industry & Business | Funding, acquisitions, regulation, AI policy, big-tech moves |
| 🌐 Open Source & Community | Open-weight models, frameworks, community projects, local AI |

## Sources

| Source | Type |
|---|---|
| TechCrunch AI | RSS |
| VentureBeat AI | RSS |
| The Verge | RSS |
| Wired | RSS |
| IEEE Spectrum | RSS |
| MIT Tech Review | RSS |
| Hugging Face Blog | RSS/Atom |
| The Gradient | RSS |
| Simon Willison's blog | Atom |
| arXiv (cs.AI, cs.LG, cs.CL, cs.NE) | XML API |
| HackerNews | Algolia JSON API |

## How it works

1. **Daily at 07:00 UTC** — `fetch-news.yml` GitHub Action runs `scripts/fetch_news.py`
2. The script fetches all RSS/Atom feeds, arXiv papers, and HackerNews stories
3. Articles are deduplicated (URL + title fingerprint), classified into 5 categories, and scored by recency × source authority
4. A complete `docs/index.html` is generated with the day's top stories
5. The action commits the updated HTML to `main`
6. `deploy-pages.yml` detects the change and deploys `docs/` to GitHub Pages

## Setup for your own fork

### 1. Enable GitHub Pages

Repository **Settings → Pages → Source**: choose **GitHub Actions** (not "branch").

### 2. That's it

The two workflows handle everything. Trigger a manual run to populate the first issue:

**Actions → Fetch AI News & Update Newsletter → Run workflow**

## Local development

```bash
# No dependencies needed — uses Python stdlib only
python scripts/fetch_news.py
open docs/index.html  # or: python -m http.server 8080 -d docs
```

## Workflows

| Workflow | Trigger | Purpose |
|---|---|---|
| `fetch-news.yml` | Daily 07:00 UTC + manual | Fetch news, generate HTML, commit |
| `deploy-pages.yml` | Push to `docs/**` on main | Deploy docs/ to GitHub Pages |

## License

MIT
