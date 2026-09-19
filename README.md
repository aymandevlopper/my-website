# G10 macro dashboard

A single-page dashboard rating the ten G10 currencies (USD, EUR, GBP, JPY,
CHF, CAD, AUD, NZD, NOK, SEK) on central bank stance, rates, inflation,
jobs, growth, energy exposure, risk regime, and CFTC positioning — plus a
week-ahead calendar. It refreshes itself automatically every weekday.

**Live structure**
```
index.html                          the page: design + rendering logic only
data.json                           all the numbers, scores and text shown on the page
scripts/update_data.py              calls the Claude API (with web search) to refresh data.json
.github/workflows/update-dashboard.yml   runs update_data.py on a daily schedule
requirements.txt                    Python dependency for the update script
```

`index.html` never needs to change day to day — it just `fetch()`es
`data.json` at load time. All the automation does is overwrite `data.json`.

## 1. Put this on GitHub

Create a new repository and push these files (or use "Upload files" in the
GitHub web UI if you don't want to use git locally):

```bash
git init
git add .
git commit -m "Initial G10 dashboard"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

## 2. Turn on GitHub Pages (so it's a live URL)

Repo → **Settings → Pages** → under "Build and deployment", set **Source**
to "Deploy from a branch", branch **main**, folder **/ (root)** → Save.
GitHub will give you a URL like `https://<your-username>.github.io/<your-repo>/`.

## 3. Add your Anthropic API key as a secret

The daily refresh calls the Claude API with web search, so it needs its own
key (this is separate from your claude.ai login):

1. Get a key at [console.anthropic.com](https://console.anthropic.com) → API Keys.
2. In the repo: **Settings → Secrets and variables → Actions → New repository secret**.
3. Name it `ANTHROPIC_API_KEY`, paste the key, save.

## 4. That's it — it updates itself

The workflow in `.github/workflows/update-dashboard.yml` runs automatically
at **11:00 UTC, Monday–Friday**. Each run:

1. Sends the current `data.json` plus instructions to Claude with web
   search turned on.
2. Claude re-checks every market level, central bank stance, CPI/jobs/GDP
   print, and the CFTC positioning report, then re-scores the nine rating
   components and rewrites the "why" text.
3. The script validates the response has the right shape before touching
   anything — if the output is malformed, the run fails loudly and
   `data.json` is left untouched (check the Actions tab for a red X, and
   `scripts/last_failed_output.txt` for what the model actually returned).
4. If validation passes, it commits the new `data.json` straight to `main`.
   GitHub Pages redeploys automatically within a minute or two.

**To change the schedule:** edit the `cron` line in the workflow file
(cron is always UTC — [crontab.guru](https://crontab.guru) helps).

**To run it right now** instead of waiting: repo → **Actions** tab →
"Update G10 dashboard data" → **Run workflow**.

**To run it locally:**
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python scripts/update_data.py
```

## Cost

Each run is one Claude API call (model `claude-sonnet-5`) with up to ~25
web searches. At normal usage this is a small fraction of a cent to a few
cents per run in API cost, billed to whichever Anthropic account owns the
key — worth checking your usage dashboard the first week.

## Honesty about limits

This automates the same research a person would do by hand, but it's still
an LLM doing web research on a timer with no human in the loop. Treat the
central-bank-stance scores and "why" text as a fast, structured first pass,
not gospel — the page itself always shows how stale the data is (the chip
next to the date) and marks anything the model couldn't verify as
`"update"`. For anything you're actually trading on, the page's own
confirmation column (does live price/volume agree) is there on purpose so
a human check is always the last step before the final score.

If you'd rather not run unattended automation at all, the "Manual update
prompt" in the page's **Method** section still works — copy it into a
Claude conversation together with your current `data.json` and paste the
result back in.
