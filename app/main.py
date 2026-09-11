import os

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from .github_client import GitHubClient

app = FastAPI(title="Exagon Project Insights", version="0.1.0")


def client() -> GitHubClient:
    try:
        return GitHubClient()
    except KeyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Missing environment variable: {exc.args[0]}",
        ) from exc


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/repositories")
def repositories() -> list[dict]:
    return client().repositories(os.getenv("GITHUB_ACCOUNT", "exagonsoft"))


@app.get("/api/repositories/{owner}/{repo}")
def repository(owner: str, repo: str) -> dict:
    try:
        data = client().repository(owner, repo)
    except requests.HTTPError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=exc.response.text,
        ) from exc

    return {
        "full_name": data["full_name"],
        "description": data.get("description"),
        "html_url": data["html_url"],
        "stars": data["stargazers_count"],
        "forks": data["forks_count"],
        "open_issues": data["open_issues_count"],
        "default_branch": data["default_branch"],
        "updated_at": data["updated_at"],
    }


@app.get("/api/repositories/{owner}/{repo}/issues")
def issues(owner: str, repo: str, state: str = "open") -> list[dict]:
    return client().issues(owner, repo, state)


@app.get("/api/repositories/{owner}/{repo}/pulls")
def pull_requests(owner: str, repo: str, state: str = "open") -> list[dict]:
    return client().pull_requests(owner, repo, state)


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Exagon Project Insights</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 1100px; margin: 40px auto; padding: 0 20px; }
    header { margin-bottom: 28px; }
    h1 { margin-bottom: 6px; }
    .muted { color: #666; }
    select { padding: 10px; min-width: 320px; }
    .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 24px 0; }
    .card { border: 1px solid #ddd; border-radius: 10px; padding: 18px; }
    .value { font-size: 28px; font-weight: 700; }
    @media (max-width: 700px) { .grid { grid-template-columns: 1fr 1fr; } select { width: 100%; min-width: 0; } }
  </style>
</head>
<body>
  <header>
    <h1>Exagon Project Insights</h1>
    <div class="muted">GitHub repository insights powered by a GitHub App</div>
  </header>

  <label for="repo">Repository</label><br>
  <select id="repo"><option>Loading...</option></select>

  <div class="grid">
    <div class="card"><div>Stars</div><div class="value" id="stars">—</div></div>
    <div class="card"><div>Forks</div><div class="value" id="forks">—</div></div>
    <div class="card"><div>Open Issues</div><div class="value" id="issues">—</div></div>
    <div class="card"><div>Last Updated</div><div class="value" id="updated">—</div></div>
  </div>

  <p id="description" class="muted"></p>

  <script>
    const repoSelect = document.getElementById('repo');

    async function loadRepositories() {
      const response = await fetch('/api/repositories');
      if (!response.ok) throw new Error(await response.text());
      const repos = await response.json();
      repoSelect.innerHTML = '';
      for (const repo of repos) {
        const option = document.createElement('option');
        option.value = repo.full_name;
        option.textContent = repo.full_name;
        repoSelect.appendChild(option);
      }
      await loadRepository();
    }

    async function loadRepository() {
      const [owner, repo] = repoSelect.value.split('/', 2);
      const response = await fetch(`/api/repositories/${owner}/${repo}`);
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      document.getElementById('stars').textContent = data.stars;
      document.getElementById('forks').textContent = data.forks;
      document.getElementById('issues').textContent = data.open_issues;
      document.getElementById('updated').textContent = new Date(data.updated_at).toLocaleDateString();
      document.getElementById('description').textContent = data.description || 'No description';
    }

    repoSelect.addEventListener('change', loadRepository);
    loadRepositories().catch(error => {
      document.body.insertAdjacentHTML('beforeend', `<p>${error.message}</p>`);
    });
  </script>
</body>
</html>"""
