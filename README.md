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
