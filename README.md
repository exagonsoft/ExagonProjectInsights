# Exagon Project Insights

A developer dashboard for exploring GitHub repositories, issues, pull requests, and project activity.

The application uses a **GitHub App** and GitHub's REST API with installation access tokens. It is intentionally small at this stage so the integration remains easy to understand and extend.

## Current features

- GitHub App authentication with an RS256 App JWT
- Installation access token generation
- Repository discovery for the `exagonsoft` installation
- Repository overview API
- Issues API
- Pull requests API
- Minimal browser dashboard
- Health endpoint

## Requirements

- Python 3.11+
- A GitHub App installation with access to the repositories you want to inspect
- The GitHub App private key stored outside Git

## Configuration

PowerShell example:

```powershell
$env:GITHUB_APP_ID="YOUR_GITHUB_APP_ID"
$env:GITHUB_PRIVATE_KEY_PATH="C:\path\to\github-app.private-key.pem"
$env:GITHUB_ACCOUNT="exagonsoft"
```

Do not commit the private key. `.gitignore` excludes `*.pem` files.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

Open `http://127.0.0.1:8000`.

## GitHub App permissions

The current application only needs read access to:

- Metadata
- Contents
- Issues
- Pull requests

The project follows GitHub's principle of requesting the minimum permissions required for its functionality.

## Analytics API

Analytics are calculated from GitHub App installation data and never use mocked values.

- `GET /api/repositories/{owner}/{repo}/analytics/commits?days=30|90|180` returns daily and weekly commit series, active contributors, and the ten latest commits.
- `GET /api/repositories/{owner}/{repo}/analytics/pulls?days=1..180` returns opened, merged, closed, currently open, merge rate, average age of currently open PRs, and daily trends.
- `GET /api/repositories/{owner}/{repo}/analytics/issues?days=1..180` returns opened, closed, currently open, average resolution time, stale count, and daily trends. Issues are stale after 30 days without an update.
- `GET /api/repositories/{owner}/{repo}/health?days=30..180` returns the deterministic 0–100 health score, state, thresholds, weighted signals, and metric-backed recommendations.
- `GET /api/repositories/{owner}/{repo}/analytics/pulls/details?days=1..180` returns PR dashboard metrics, aging buckets, sortable rows, and reviews. Average time-to-merge is the arithmetic mean from creation to merge; median is the middle duration (or mean of the two middle durations).
- `GET /api/repositories/{owner}/{repo}/analytics/issues/details?days=1..180` returns issue dashboard metrics, aging buckets, sortable rows, and stale markers. Resolution time is measured from creation to closure.
- `GET /api/repositories/{owner}/{repo}/analytics/contributors?days=1..180` returns normalized contributor identities and activity. Contribution percentage is each contributor's equal-weight share of commits, opened PRs, submitted reviews, and opened issues in the period.

Durations are reported in days. Rates and signal scores are percentages. Health weights can be overridden with `HEALTH_WEIGHT_<SIGNAL>` environment variables; thresholds use `HEALTHY_THRESHOLD` and `ATTENTION_THRESHOLD`.

PR aging buckets are inclusive: 0–3, 4–7, 8–14, 15–30, and over 30 days. Issue buckets are 0–7, 8–14, 15–30, 31–60, and over 60 days. PR inactivity is 14 days without an update; issue staleness is 30 days.
