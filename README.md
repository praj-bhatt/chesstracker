# Chess.com Puzzle Rating Tracker

A Python tracker for the **current rated-puzzle rating** on Chess.com for `praj-bhatt`. GitHub Actions collects a snapshot daily, appends it to a CSV history, updates a JSON file with the latest successfully fetched rating, and renders a compact, all-time puzzle-history graph with only the current rating and progress line for your GitHub profile README. It runs once on the first push to `main`, then automatically every day; you can also trigger an immediate refresh from the Actions tab.

> **Important data-source note:** Chess.com's official Published-Data API (`/pub/player/{username}/stats`) exposes `tactics.highest` and `tactics.lowest`, but not the current tactics rating. This project uses the publicly accessible endpoint used by the Chess.com puzzle stats page and reads only `statsInfo.stats.rating`. That endpoint is undocumented and may change. If the expected field is missing or Chess.com blocks the request, the run fails without guessing or recording a number.

## What is included

- `scripts/update_tracker.py` — fetches, validates, records and plots the rating.
- `data/puzzle_rating_history.csv` — persistent observations; historical rows are retained.
- `data/latest_rating.json` — most recent successfully fetched exact rating and timestamp.
- `assets/puzzle-rating.png` — minimal current-rating and all-time puzzle-history graph for the profile README.
- `.github/workflows/update-puzzle-rating.yml` — first-push trigger, daily schedule, manual refresh, retry logic, and automatic commits.
- `profile-readme-snippet.md` — snippet to embed the chart in your GitHub profile README.
- `tests/` — offline tests ensuring the parser takes the current-rating field rather than a highest/lowest value.

## History policy

No rating history is invented. One user-reported observation is included: **1169 on 2026-10-24**, with the source explicitly marked as user-reported and its exact time left blank because the time was not available. The current-rating number displays an em dash until the first successful automated fetch, so the old user-reported point is never mistaken for today's rating. After that, each successful run appends a timestamped snapshot in UTC. Repeated ratings are recorded too, so a flat line means the latest rating stayed the same between observations.

The source files start with a historical date-only row plus an empty/current-state JSON file. If you prefer a strictly automated-only history, remove that one user-reported CSV row before the first run.

## Setup

### 1. Create the tracker repository

1. Sign in to GitHub and create a **public** repository named `chesscom-puzzle-rating-tracker` (or choose another name and use it consistently in the links below).
2. Do **not** initialize it with a README, `.gitignore` or license, because these are already included in this project folder.
3. Download and extract the project ZIP, then open a terminal in the extracted `chesscom_puzzle_rating_tracker` folder.

### 2. Push the project to GitHub

Install Git if it is not already available. Replace `YOUR_GITHUB_USERNAME` in the commands below with your GitHub username:

```bash
git init -b main
git add .
git commit -m "Add Chess.com puzzle rating tracker"
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/chesscom-puzzle-rating-tracker.git
git push -u origin main
```

If you chose a different repository name, replace `chesscom-puzzle-rating-tracker` in the remote URL and later image links.

### 3. Allow the workflow to commit updates

The workflow declares `contents: write` and uses GitHub's built-in `GITHUB_TOKEN`; no personal access token or repository secret is required for the standard setup.

1. Open the tracker repository on GitHub.
2. Go to **Settings → Actions → General → Workflow permissions**.
3. Select **Read and write permissions**, then save if GitHub requires it.
4. Confirm `main` is the default branch. Scheduled workflows run from the default branch.

No Chess.com password, session cookie, or Chess.com API token is needed. Do not add any of those to GitHub Secrets. The username is public and is set in the workflow as `CHESSCOM_USERNAME: praj-bhatt`.

### 4. Automatic collection and refresh

The workflow starts automatically when you push the project to the `main` branch. That first push triggers the initial live collection, so you do not need to manually start the first run. After that, GitHub Actions runs it every day at **03:17 UTC (08:47 India Standard Time)**.

To refresh it immediately at any time:

1. Open the repository's **Actions** tab.
2. Select **Update Chess.com puzzle rating**.
3. Click **Run workflow**, select `main`, and confirm.

Open the run and check the “Fetch current puzzle rating and update chart” step. After success, the workflow commits updates to the CSV, JSON and PNG files. The script retries temporary connection errors, timeouts and common rate-limit/server responses before failing. If all attempts fail or Chess.com changes its response, the workflow reports an error and preserves the previous valid history and graph.

GitHub may delay scheduled jobs during busy periods. Scheduled workflows run from the repository's default branch, and GitHub may automatically disable schedules in public repositories after 60 days without repository activity. Successful daily runs commit a fresh timestamped sample, keeping this repository active; check the Actions tab if runs stop.

### 5. Add it to your GitHub profile README

A GitHub profile README lives in a repository whose name matches your GitHub username. If that repository does not exist, create a public repository named exactly `YOUR_GITHUB_USERNAME` and add a `README.md` file.

Copy the contents of `profile-readme-snippet.md` into your profile `README.md`. Replace `YOUR_GITHUB_USERNAME` in the image URL with your real GitHub username. Keep the marker comments if you want to recognize the block later. The PNG is served from the public tracker repository, so the tracker repository must remain public for the profile image to be visible to everyone.

The profile snippet contains only one image: the current puzzle rating and the all-time history line. The graph includes every saved observation from the beginning of tracking; it does not use a 30-day, 90-day, or other rolling window. The detailed CSV remains in the tracker repository, not in the profile section.

## Run or test locally (optional)

Requires Python 3.10+.

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/update_tracker.py
```

Regenerate the graph from already saved data without contacting Chess.com:

```bash
python scripts/update_tracker.py --render-only
```

To use a different public Chess.com username for a local run:

```bash
python scripts/update_tracker.py --username SOME_USERNAME
```

## Data and limitations

- The exact current rating is taken from `statsInfo.stats.rating`, not the `highest` or `lowest` fields.
- The tracker does not try to reconstruct prior daily ratings. Existing historical points are only those collected by this project plus clearly labeled genuine user-reported data included at setup.
- The fallback endpoint is undocumented and is identified in a public Home Assistant integration discussion; Chess.com may change it or block automated requests. A changed response causes a visible failed run and preserves the last good dataset; update `extract_current_rating()` only after checking the new response structure.
- The official API can be useful for profile and game ratings, but its public stats payload does not expose the current puzzle rating required here.
- A failed collection does not append a point. The graph and latest JSON continue to show the last successful reading.
- A public repository makes your rating history public as well. No secret credentials are stored by the project.
- The parser is tested with offline fixtures. This environment could not reach Chess.com to verify a live request. The first push to `main` automatically tests the live endpoint from GitHub Actions. If it fails, inspect the run log; no guessed value is written.

## Sources

- [Chess.com Published-Data API help](https://support.chess.com/en/articles/9650547-what-is-the-pubapi-and-how-do-i-use-it)
- [Chess.com puzzle stats page for praj-bhatt](https://www.chess.com/member/praj-bhatt/stats/puzzles?time=0)
- [Public discussion identifying the puzzle stats endpoint and `statsInfo.stats.rating` field](https://github.com/orgs/home-assistant/discussions/3385)
