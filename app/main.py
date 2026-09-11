import os
from datetime import datetime, timedelta, timezone

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from .github_client import GitHubClient
from .analytics import commit_activity, issue_activity, language_statistics, pull_request_activity
from .health import calculate_health
from .intelligence import contributor_details, issue_details, pull_request_details

app = FastAPI(title="Exagon Project Insights", version="0.2.0")


def client() -> GitHubClient:
    try:
        return GitHubClient()
    except KeyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Missing environment variable: {exc.args[0]}",
        ) from exc


def github_error(exc: requests.HTTPError) -> HTTPException:
    status = exc.response.status_code if exc.response is not None else 502
    detail = exc.response.text if exc.response is not None else str(exc)
    return HTTPException(status_code=status, detail=detail)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/repositories")
def repositories() -> list[dict]:
    try:
        return client().repositories(os.getenv("GITHUB_ACCOUNT", "exagonsoft"))
    except requests.HTTPError as exc:
        raise github_error(exc) from exc


@app.get("/api/repositories/{owner}/{repo}")
def repository(owner: str, repo: str) -> dict:
    try:
        data = client().repository(owner, repo)
    except requests.HTTPError as exc:
        raise github_error(exc) from exc

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
    try:
        return client().issues(owner, repo, state)
    except requests.HTTPError as exc:
        raise github_error(exc) from exc


@app.get("/api/repositories/{owner}/{repo}/pulls")
def pull_requests(owner: str, repo: str, state: str = "open") -> list[dict]:
    try:
        return client().pull_requests(owner, repo, state)
    except requests.HTTPError as exc:
        raise github_error(exc) from exc


def analytics_data(owner: str, repo: str, days: int) -> tuple[dict, dict, dict, dict]:
    github = client()
    repository_data = github.repository(owner, repo)
    commits = commit_activity(github.commits(owner, repo, days), days)
    pulls = pull_request_activity(github.pull_requests(owner, repo, "all"), days)
    issues = issue_activity(github.issues(owner, repo, "all"), days)
    return repository_data, commits, pulls, issues


@app.get("/api/repositories/{owner}/{repo}/analytics/commits")
def commits_analytics(owner: str, repo: str, days: int = Query(30, enum=[30, 90, 180])) -> dict:
    try:
        return commit_activity(client().commits(owner, repo, days), days)
    except requests.HTTPError as exc:
        raise github_error(exc) from exc


@app.get("/api/repositories/{owner}/{repo}/analytics/pulls")
def pulls_analytics(owner: str, repo: str, days: int = Query(180, ge=1, le=180)) -> dict:
    try:
        return pull_request_activity(client().pull_requests(owner, repo, "all"), days)
    except requests.HTTPError as exc:
        raise github_error(exc) from exc


@app.get("/api/repositories/{owner}/{repo}/analytics/issues")
def issues_analytics(owner: str, repo: str, days: int = Query(180, ge=1, le=180)) -> dict:
    try:
        return issue_activity(client().issues(owner, repo, "all"), days)
    except requests.HTTPError as exc:
        raise github_error(exc) from exc


@app.get("/api/repositories/{owner}/{repo}/health")
def repository_health(owner: str, repo: str, days: int = Query(180, ge=30, le=180)) -> dict:
    try:
        repository_data, commits, pulls, issues = analytics_data(owner, repo, days)
        return calculate_health(repository_data, commits, pulls, issues)
    except requests.HTTPError as exc:
        raise github_error(exc) from exc


def reviews_for_period(github: GitHubClient, owner: str, repo: str, pulls: list[dict], days: int) -> dict[int, list[dict]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent = [item for item in pulls if item.get("created_at") and datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")) >= cutoff]
    return {item["number"]: github.reviews(owner, repo, item["number"]) for item in recent[:100]}


@app.get("/api/repositories/{owner}/{repo}/analytics/pulls/details")
def pulls_details(owner: str, repo: str, days: int = Query(180, ge=1, le=180)) -> dict:
    try:
        github = client()
        pulls = github.pull_requests(owner, repo, "all")
        return pull_request_details(pulls, reviews_for_period(github, owner, repo, pulls, days), days)
    except requests.HTTPError as exc:
        raise github_error(exc) from exc


@app.get("/api/repositories/{owner}/{repo}/analytics/issues/details")
def issues_details(owner: str, repo: str, days: int = Query(180, ge=1, le=180)) -> dict:
    try:
        return issue_details(client().issues(owner, repo, "all"), days)
    except requests.HTTPError as exc:
        raise github_error(exc) from exc


@app.get("/api/repositories/{owner}/{repo}/analytics/contributors")
def contributors(owner: str, repo: str, days: int = Query(180, ge=1, le=180)) -> dict:
    try:
        github = client()
        commits = github.commits(owner, repo, days)
        pulls = github.pull_requests(owner, repo, "all")
        issues = github.issues(owner, repo, "all")
        reviews = reviews_for_period(github, owner, repo, pulls, days)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent = lambda items: [item for item in items if item.get("created_at") and datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")) >= cutoff]
        return contributor_details(commits, recent(pulls), recent(issues), reviews, days)
    except requests.HTTPError as exc:
        raise github_error(exc) from exc


@app.get("/api/repositories/{owner}/{repo}/languages")
def repository_languages(owner: str, repo: str) -> dict:
    try:
        return language_statistics(client().languages(owner, repo))
    except requests.HTTPError as exc:
        raise github_error(exc) from exc


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0b1020">
  <title>Exagon Project Insights</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #080b14;
      --panel: rgba(17, 23, 39, .78);
      --panel-strong: #111727;
      --border: rgba(148, 163, 184, .14);
      --text: #f5f7fb;
      --muted: #8d98ad;
      --accent: #8b5cf6;
      --accent-2: #06b6d4;
      --green: #34d399;
      --shadow: 0 24px 70px rgba(0,0,0,.32);
    }
    * { box-sizing: border-box; }
    html { min-height: 100%; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 12% 0%, rgba(139,92,246,.20), transparent 32%),
        radial-gradient(circle at 88% 8%, rgba(6,182,212,.13), transparent 28%),
        var(--bg);
    }
    button, input, select { font: inherit; }
    a { color: inherit; text-decoration: none; }
    .shell { width: min(1440px, calc(100% - 40px)); margin: 0 auto; padding: 28px 0 52px; }
    .topbar { display:flex; align-items:center; justify-content:space-between; gap:24px; margin-bottom:42px; }
    .brand { display:flex; align-items:center; gap:13px; }
    .brand-mark {
      width:42px; height:42px; border-radius:13px; display:grid; place-items:center;
      background: linear-gradient(135deg, #8b5cf6, #4f46e5); box-shadow: 0 10px 35px rgba(99,102,241,.28);
      font-weight:900; font-size:18px;
    }
    .brand-title { font-weight:750; letter-spacing:-.02em; }
    .brand-sub { color:var(--muted); font-size:12px; margin-top:2px; }
    .status { display:flex; align-items:center; gap:8px; color:#a7f3d0; font-size:13px; padding:9px 13px; border:1px solid rgba(52,211,153,.16); border-radius:999px; background:rgba(52,211,153,.06); }
    .dot { width:7px; height:7px; border-radius:50%; background:var(--green); box-shadow:0 0 12px var(--green); }
    .hero { display:grid; grid-template-columns:1.35fr .65fr; gap:28px; align-items:end; margin-bottom:28px; }
    .eyebrow { color:#a78bfa; text-transform:uppercase; letter-spacing:.16em; font-size:11px; font-weight:800; margin-bottom:12px; }
    h1 { margin:0; font-size:clamp(34px, 5vw, 62px); line-height:.98; letter-spacing:-.055em; max-width:780px; }
    .hero-copy { margin:17px 0 0; color:var(--muted); font-size:16px; line-height:1.65; max-width:720px; }
    .selector-wrap { justify-self:end; width:100%; max-width:540px; }
    .repository-tools { display:grid; grid-template-columns:minmax(0, 1.35fr) minmax(130px, .65fr) minmax(150px, .8fr); gap:9px; }
    .control-shell { position:relative; }
    .control-icon { position:absolute; left:14px; top:50%; transform:translateY(-50%); color:#778399; pointer-events:none; }
    input, select {
      width:100%; color:var(--text); background:rgba(17,23,39,.9); border:1px solid var(--border);
      border-radius:12px; padding:13px 38px 13px 14px; outline:none; box-shadow:var(--shadow);
    }
    input { padding-left:39px; }
    input::placeholder { color:#68748a; }
    input:focus, select:focus { border-color:rgba(139,92,246,.65); box-shadow:0 0 0 4px rgba(139,92,246,.11); }
    .repository-count { color:var(--muted); font-size:11px; margin:8px 3px 0; min-height:16px; }
    .favorite-button { border:1px solid var(--border); background:rgba(148,163,184,.06); color:#94a3b8; border-radius:10px; padding:8px 11px; cursor:pointer; }
    .favorite-button.active { color:#facc15; border-color:rgba(250,204,21,.3); background:rgba(250,204,21,.08); }
    .label { display:block; color:#9aa5ba; font-size:11px; text-transform:uppercase; letter-spacing:.12em; font-weight:800; margin:0 0 8px 4px; }
    .select-shell { position:relative; }
    select { appearance:none; cursor:pointer; }
    .chevron { position:absolute; right:16px; top:50%; transform:translateY(-50%); pointer-events:none; color:#9aa5ba; }
    .stats { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:28px; }
    .stat, .panel { background:linear-gradient(180deg, rgba(20,27,45,.82), rgba(13,18,31,.82)); border:1px solid var(--border); box-shadow:var(--shadow); backdrop-filter:blur(18px); }
    .stat { min-height:142px; padding:20px; border-radius:18px; position:relative; overflow:hidden; }
    .stat::after { content:""; position:absolute; width:90px; height:90px; right:-34px; bottom:-40px; border-radius:50%; background:rgba(139,92,246,.11); }
    .stat-head { display:flex; align-items:center; justify-content:space-between; color:var(--muted); font-size:12px; font-weight:650; }
    .icon { width:31px; height:31px; border-radius:10px; display:grid; place-items:center; background:rgba(139,92,246,.11); color:#c4b5fd; }
    .stat-value { font-size:34px; font-weight:800; letter-spacing:-.045em; margin-top:18px; }
    .workspace { display:grid; grid-template-columns:1.55fr .75fr; gap:18px; }
    .panel { border-radius:20px; overflow:hidden; }
    .panel-head { display:flex; justify-content:space-between; align-items:center; gap:15px; padding:21px 22px; border-bottom:1px solid var(--border); }
    .panel-title { font-size:15px; font-weight:760; }
    .panel-sub { color:var(--muted); font-size:12px; margin-top:3px; }
    .repo-link { color:#a78bfa; font-size:12px; font-weight:700; }
    .repo-description { padding:22px; color:#aeb7c8; line-height:1.7; font-size:14px; min-height:118px; }
    .meta { display:flex; flex-wrap:wrap; gap:8px; padding:0 22px 22px; }
    .pill { color:#aeb7c8; background:rgba(148,163,184,.06); border:1px solid var(--border); padding:7px 10px; border-radius:9px; font-size:11px; }
    .tabs { display:flex; gap:6px; padding:14px 22px 0; }
    .tab { border:0; background:transparent; color:var(--muted); padding:9px 12px; border-radius:9px; cursor:pointer; font-size:12px; font-weight:700; }
    .tab.active { color:#fff; background:rgba(139,92,246,.13); }
    .list { padding:8px 22px 18px; }
    .item { display:flex; gap:12px; align-items:flex-start; padding:14px 0; border-bottom:1px solid rgba(148,163,184,.08); }
    .item:last-child { border-bottom:0; }
    .item-icon { flex:0 0 auto; width:29px; height:29px; display:grid; place-items:center; border-radius:9px; background:rgba(52,211,153,.08); color:#6ee7b7; }
    .item-title { font-size:13px; font-weight:650; line-height:1.45; }
    .item-meta { color:var(--muted); font-size:11px; margin-top:4px; }
    .empty { color:var(--muted); text-align:center; padding:32px 10px; font-size:13px; }
    .loading { animation:pulse 1.4s ease-in-out infinite; color:#667085; }
    .error { margin-top:20px; padding:14px 16px; border:1px solid rgba(248,113,113,.2); background:rgba(248,113,113,.06); border-radius:12px; color:#fca5a5; font-size:13px; }
    .analytics { margin-top:18px; }
    .analytics-grid { display:grid; grid-template-columns:1.5fr .85fr; gap:18px; }
    .chart-wrap { padding:18px 22px 22px; min-height:260px; }
    .chart { width:100%; height:190px; overflow:visible; }
    .chart-line { fill:none; stroke:url(#chartGradient); stroke-width:3; vector-effect:non-scaling-stroke; }
    .chart-area { fill:url(#areaGradient); }
    .chart-dot { fill:#22d3ee; stroke:#0f172a; stroke-width:2; }
    .range-buttons { display:flex; gap:5px; }
    .range-button { border:0; color:var(--muted); background:transparent; padding:7px 9px; border-radius:8px; cursor:pointer; font-size:11px; font-weight:750; }
    .range-button.active { color:#fff; background:rgba(139,92,246,.16); }
    .health-score { font-size:48px; line-height:1; font-weight:850; letter-spacing:-.06em; }
    .health-state { display:inline-block; margin:9px 0 14px; padding:6px 9px; border-radius:999px; font-size:11px; font-weight:800; text-transform:uppercase; }
    .health-state.healthy { color:#6ee7b7; background:rgba(52,211,153,.1); }
    .health-state.needs_attention { color:#fde68a; background:rgba(250,204,21,.1); }
    .health-state.at_risk { color:#fca5a5; background:rgba(248,113,113,.1); }
    .signal-row { display:grid; grid-template-columns:1fr auto; gap:12px; padding:8px 0; border-bottom:1px solid rgba(148,163,184,.08); font-size:11px; color:var(--muted); }
    .recommendation { padding:10px 0; border-bottom:1px solid rgba(148,163,184,.08); color:#cbd5e1; font-size:12px; line-height:1.5; }
    .intelligence { margin-top:18px; }
    .intelligence-body { padding:20px 22px 24px; }
    .metric-grid { display:grid; grid-template-columns:repeat(5,1fr); gap:10px; margin-bottom:18px; }
    .metric-card { padding:14px; border:1px solid var(--border); border-radius:13px; background:rgba(148,163,184,.04); }
    .metric-label { color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:.08em; }
    .metric-value { font-size:21px; font-weight:800; margin-top:7px; }
    .buckets { display:grid; grid-template-columns:repeat(5,1fr); gap:8px; margin:16px 0; }
    .bucket { border:1px solid var(--border); color:var(--muted); background:rgba(148,163,184,.04); padding:11px; border-radius:11px; text-align:left; cursor:pointer; }
    .bucket.active { color:#fff; border-color:rgba(139,92,246,.55); background:rgba(139,92,246,.12); }
    .bucket strong { display:block; color:var(--text); font-size:18px; margin-top:4px; }
    .table-wrap { overflow:auto; border:1px solid var(--border); border-radius:13px; }
    table { width:100%; border-collapse:collapse; min-width:720px; }
    th, td { padding:11px 13px; text-align:left; border-bottom:1px solid rgba(148,163,184,.08); font-size:11px; }
    th { color:var(--muted); text-transform:uppercase; letter-spacing:.07em; background:rgba(8,11,20,.45); cursor:pointer; }
    td { color:#cbd5e1; }
    .person { display:flex; align-items:center; gap:8px; }
    .avatar { width:25px; height:25px; border-radius:50%; background:#1e293b; }
    .analytics-filter { color:var(--text); background:rgba(17,23,39,.9); border:1px solid var(--border); border-radius:9px; padding:8px 10px; }
    .language-layout { display:grid; grid-template-columns:220px 1fr; gap:26px; align-items:center; padding:22px; }
    .language-ring { width:180px; aspect-ratio:1; border-radius:50%; position:relative; margin:auto; }
    .language-ring::after { content:"Languages"; position:absolute; inset:31px; border-radius:50%; display:grid; place-items:center; background:var(--panel-strong); color:var(--muted); font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.08em; }
    .language-row { display:grid; grid-template-columns:auto 1fr auto; gap:10px; align-items:center; padding:8px 0; font-size:12px; }
    .language-dot { width:9px; height:9px; border-radius:50%; }
    .language-bar { height:6px; background:rgba(148,163,184,.08); border-radius:999px; overflow:hidden; }
    .language-bar span { display:block; height:100%; border-radius:inherit; }
    .bus-factor { margin-top:14px; padding:12px; border:1px solid var(--border); border-radius:12px; font-size:11px; line-height:1.55; color:var(--muted); }
    .bus-factor.warning { color:#fde68a; border-color:rgba(250,204,21,.25); background:rgba(250,204,21,.06); }
    footer { color:#59647a; text-align:center; font-size:11px; margin-top:30px; }
    @keyframes pulse { 50% { opacity:.45; } }
    @media (max-width: 980px) { .hero, .workspace, .analytics-grid { grid-template-columns:1fr; } .selector-wrap { justify-self:stretch; max-width:none; } }
    @media (max-width: 700px) { .shell { width:min(100% - 24px, 1440px); padding-top:18px; } .topbar { margin-bottom:30px; } .status { display:none; } .stats { grid-template-columns:1fr 1fr; } .repository-tools { grid-template-columns:1fr 1fr; } .repository-tools .control-shell:first-child { grid-column:1 / -1; } .metric-grid { grid-template-columns:1fr 1fr; } .buckets { grid-template-columns:1fr 1fr; } .language-layout { grid-template-columns:1fr; } h1 { font-size:39px; } }
    @media (max-width: 430px) { .stats { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <main class="shell">
    <nav class="topbar">
      <div class="brand">
        <div class="brand-mark">E</div>
        <div><div class="brand-title">Exagon Project Insights</div><div class="brand-sub">Developer intelligence for GitHub</div></div>
      </div>
      <div class="status"><span class="dot"></span> GitHub App connected</div>
    </nav>

    <section class="hero">
      <div>
        <div class="eyebrow">Project overview</div>
        <h1>See your codebase<br>at a glance.</h1>
        <p class="hero-copy">A focused workspace for repository health, collaboration signals, issues and pull requests — powered directly by GitHub.</p>
      </div>
      <div class="selector-wrap">
        <label class="label" for="repo-search">Find a repository</label>
        <div class="repository-tools">
          <div class="control-shell">
            <span class="control-icon">⌕</span>
            <input id="repo-search" type="search" placeholder="Search by name…" autocomplete="off">
          </div>
          <div class="select-shell">
            <select id="repo-filter" aria-label="Filter repositories">
              <option value="all">All repositories</option>
              <option value="active">Active</option>
              <option value="archived">Archived</option>
              <option value="public">Public</option>
              <option value="private">Private</option>
            </select>
            <span class="chevron">⌄</span>
          </div>
          <div class="select-shell">
            <select id="repo-sort" aria-label="Sort repositories">
              <option value="name">Name</option>
              <option value="stars">Stars</option>
              <option value="forks">Forks</option>
              <option value="updated">Last updated</option>
              <option value="issues">Open issues</option>
            </select>
            <span class="chevron">⌄</span>
          </div>
        </div>
        <div class="select-shell">
          <select id="repo" aria-label="Repository"><option>Loading repositories…</option></select>
          <span class="chevron">⌄</span>
        </div>
        <div class="repository-count" id="repository-count" aria-live="polite"></div>
      </div>
    </section>

    <section class="stats">
      <article class="stat"><div class="stat-head"><span>Stars</span><span class="icon">★</span></div><div class="stat-value" id="stars">—</div></article>
      <article class="stat"><div class="stat-head"><span>Forks</span><span class="icon">⑂</span></div><div class="stat-value" id="forks">—</div></article>
      <article class="stat"><div class="stat-head"><span>Open issues</span><span class="icon">○</span></div><div class="stat-value" id="issues">—</div></article>
      <article class="stat"><div class="stat-head"><span>Last updated</span><span class="icon">↻</span></div><div class="stat-value" id="updated">—</div></article>
    </section>

    <section class="workspace">
      <article class="panel">
        <div class="panel-head">
          <div><div class="panel-title" id="repo-name">Repository overview</div><div class="panel-sub" id="branch">Loading…</div></div>
          <div><button class="favorite-button" id="favorite" type="button" aria-label="Favorite repository">☆</button> <a class="repo-link" id="github-link" href="#" target="_blank" rel="noreferrer">Open on GitHub ↗</a></div>
        </div>
        <div class="repo-description" id="description">Loading repository details…</div>
        <div class="meta"><span class="pill" id="repo-id">—</span><span class="pill">GitHub App</span><span class="pill">Live data</span></div>
        <div class="tabs"><button class="tab active" data-tab="issues">Open issues</button><button class="tab" data-tab="pulls">Pull requests</button></div>
        <div class="list" id="activity"><div class="empty loading">Loading activity…</div></div>
      </article>

      <aside class="panel">
        <div class="panel-head"><div><div class="panel-title">Signal summary</div><div class="panel-sub">A quick read on this repository</div></div></div>
        <div class="repo-description">
          <div style="font-size:12px;color:#8d98ad;text-transform:uppercase;letter-spacing:.1em;font-weight:800;margin-bottom:9px">Repository health</div>
          <div id="health-message" style="font-size:20px;font-weight:780;letter-spacing:-.03em">Analyzing…</div>
          <p id="health-detail" style="font-size:12px;color:#8d98ad;line-height:1.7;margin:9px 0 0">Live repository metrics will appear here.</p>
        </div>
      </aside>
    </section>

    <section class="analytics analytics-grid">
      <article class="panel">
        <div class="panel-head">
          <div><div class="panel-title">Commit activity</div><div class="panel-sub" id="commit-summary">Real GitHub commit history</div></div>
          <div class="range-buttons"><button class="range-button active" data-days="30">30d</button><button class="range-button" data-days="90">90d</button><button class="range-button" data-days="180">180d</button></div>
        </div>
        <div class="chart-wrap" id="commit-chart"><div class="empty loading">Loading commit activity…</div></div>
      </article>
      <article class="panel">
        <div class="panel-head"><div><div class="panel-title">Health intelligence</div><div class="panel-sub">Deterministic repository signals</div></div></div>
        <div class="repo-description" id="health-panel"><div class="empty loading">Calculating health…</div></div>
      </article>
    </section>

    <section class="panel intelligence">
      <div class="panel-head">
        <div><div class="panel-title">Activity intelligence</div><div class="panel-sub">Detailed repository workflows and contributors</div></div>
        <div class="tabs"><button class="tab intelligence-tab active" data-view="pulls">Pull requests</button><button class="tab intelligence-tab" data-view="issues">Issues</button><button class="tab intelligence-tab" data-view="contributors">Contributors</button></div>
      </div>
      <div class="intelligence-body" id="intelligence-body"><div class="empty loading">Loading analytics…</div></div>
    </section>

    <section class="panel intelligence">
      <div class="panel-head"><div><div class="panel-title">Technology distribution</div><div class="panel-sub">GitHub-detected language bytes and percentages</div></div></div>
      <div id="language-breakdown"><div class="empty loading">Loading language statistics…</div></div>
    </section>

    <div id="error"></div>
    <footer>Exagon Project Insights · GitHub App integration · Built by ExagonSoft</footer>
  </main>

  <script>
    const $ = (id) => document.getElementById(id);
    const repoSelect = $('repo');
    const repoSearch = $('repo-search');
    const repoFilter = $('repo-filter');
    const repoSort = $('repo-sort');
    let repositories = [];
    let current = null;
    let analyticsDays = 30;
    let intelligenceView = 'pulls';
    let intelligenceData = null;
    let favorites = new Set(JSON.parse(localStorage.getItem('exagon-favorite-repositories') || '[]'));

    const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
    const shortNumber = (value) => new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(value ?? 0);

    async function api(url) {
      const response = await fetch(url);
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    }

    async function loadRepositories() {
      try {
        repositories = await api('/api/repositories');
        renderRepositories(true);
      } catch (error) {
        repoSelect.innerHTML = '<option value="">Repositories unavailable</option>';
        $('repository-count').textContent = 'Could not load repositories.';
        showError(error);
      }
    }

    function filteredRepositories() {
      const query = repoSearch.value.trim().toLocaleLowerCase();
      const filter = repoFilter.value;
      const visible = repositories.filter(repo => {
        const matchesSearch = !query || repo.full_name.toLocaleLowerCase().includes(query);
        const matchesFilter = filter === 'all'
          || (filter === 'active' && !repo.archived)
          || (filter === 'archived' && repo.archived)
          || (filter === 'public' && !repo.private)
          || (filter === 'private' && repo.private);
        return matchesSearch && matchesFilter;
      });

      const sorters = {
        name: (a, b) => a.full_name.localeCompare(b.full_name),
        stars: (a, b) => (b.stargazers_count || 0) - (a.stargazers_count || 0),
        forks: (a, b) => (b.forks_count || 0) - (a.forks_count || 0),
        updated: (a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0),
        issues: (a, b) => (b.open_issues_count || 0) - (a.open_issues_count || 0),
      };
      return visible.sort((a, b) => {
        const favoriteOrder = Number(favorites.has(b.full_name)) - Number(favorites.has(a.full_name));
        return favoriteOrder || (sorters[repoSort.value] || sorters.name)(a, b);
      });
    }

    async function renderRepositories(loadSelected = false) {
      const previous = repoSelect.value;
      const visible = filteredRepositories();
      $('repository-count').textContent = `${visible.length} of ${repositories.length} accessible repositories`;

      if (!visible.length) {
        repoSelect.innerHTML = '<option value="">No repositories match these filters</option>';
        repoSelect.disabled = true;
        return;
      }

      repoSelect.disabled = false;
      repoSelect.innerHTML = visible.map(repo => `<option value="${escapeHtml(repo.full_name)}">${favorites.has(repo.full_name) ? '★ ' : ''}${escapeHtml(repo.full_name)}</option>`).join('');
      if (visible.some(repo => repo.full_name === previous)) repoSelect.value = previous;
      if (loadSelected || repoSelect.value !== previous) await loadRepository();
    }

    async function loadRepository() {
      if (!repoSelect.value) return;
      const [owner, repo] = repoSelect.value.split('/', 2);
      $('activity').innerHTML = '<div class="empty loading">Loading activity…</div>';
      $('error').innerHTML = '';
      try {
        current = await api(`/api/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`);
        $('repo-name').textContent = current.full_name;
        $('branch').textContent = `Default branch · ${current.default_branch}`;
        $('stars').textContent = shortNumber(current.stars);
        $('forks').textContent = shortNumber(current.forks);
        $('issues').textContent = shortNumber(current.open_issues);
        $('updated').textContent = new Date(current.updated_at).toLocaleDateString(undefined, { month:'short', day:'numeric' });
        $('description').textContent = current.description || 'No description has been added to this repository yet.';
        $('repo-id').textContent = current.default_branch;
        $('github-link').href = current.html_url;
        updateFavoriteButton();
        await Promise.all([loadTab('issues'), loadCommitActivity(), loadHealth(), loadIntelligence(), loadLanguages()]);
      } catch (error) { showError(error); }
    }

    function updateFavoriteButton() {
      const active = current && favorites.has(current.full_name);
      $('favorite').classList.toggle('active', active);
      $('favorite').textContent = active ? '★' : '☆';
      $('favorite').setAttribute('aria-label', active ? 'Unfavorite repository' : 'Favorite repository');
    }

    function toggleFavorite() {
      if (!current) return;
      favorites.has(current.full_name) ? favorites.delete(current.full_name) : favorites.add(current.full_name);
      localStorage.setItem('exagon-favorite-repositories', JSON.stringify([...favorites]));
      updateFavoriteButton();
      renderRepositories();
    }

    async function loadCommitActivity() {
      if (!current) return;
      const [owner, repo] = current.full_name.split('/', 2);
      $('commit-chart').innerHTML = '<div class="empty loading">Loading commit activity…</div>';
      try {
        const data = await api(`/api/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/analytics/commits?days=${analyticsDays}`);
        $('commit-summary').textContent = `${data.total_commits} commits · ${data.active_contributors.length} active contributors`;
        renderCommitChart(data.commits_per_day);
      } catch (error) {
        $('commit-chart').innerHTML = '<div class="empty">Commit activity is unavailable.</div>';
        showError(error);
      }
    }

    function renderCommitChart(points) {
      if (!points.some(point => point.count)) {
        $('commit-chart').innerHTML = '<div class="empty">No commits in this period.</div>';
        return;
      }
      const width = 800, height = 190, pad = 12;
      const max = Math.max(...points.map(point => point.count), 1);
      const coords = points.map((point, index) => ({
        ...point,
        x: pad + index * (width - pad * 2) / Math.max(points.length - 1, 1),
        y: height - pad - point.count / max * (height - pad * 2),
      }));
      const line = coords.map(point => `${point.x},${point.y}`).join(' ');
      const area = `${pad},${height - pad} ${line} ${width - pad},${height - pad}`;
      $('commit-chart').innerHTML = `<svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Commit activity over ${analyticsDays} days">
        <defs><linearGradient id="chartGradient"><stop stop-color="#8b5cf6"/><stop offset="1" stop-color="#22d3ee"/></linearGradient><linearGradient id="areaGradient" x2="0" y2="1"><stop stop-color="#8b5cf6" stop-opacity=".25"/><stop offset="1" stop-color="#8b5cf6" stop-opacity="0"/></linearGradient></defs>
        <polygon class="chart-area" points="${area}"/><polyline class="chart-line" points="${line}"/>
        ${coords.filter(point => point.count).map(point => `<circle class="chart-dot" cx="${point.x}" cy="${point.y}" r="4"><title>${escapeHtml(point.date)}: ${point.count} commits</title></circle>`).join('')}
      </svg>`;
    }

    async function loadHealth() {
      if (!current) return;
      const [owner, repo] = current.full_name.split('/', 2);
      $('health-panel').innerHTML = '<div class="empty loading">Calculating health…</div>';
      try {
        const health = await api(`/api/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/health?days=180`);
        const label = health.state === 'healthy' ? 'Healthy' : health.state === 'needs_attention' ? 'Needs attention' : 'At risk';
        $('health-message').textContent = `${health.score}/100 · ${label}`;
        $('health-detail').textContent = health.recommendations.length ? health.recommendations[0].message : 'No concerning health signals detected.';
        $('health-panel').innerHTML = `<div class="health-score">${health.score}</div><span class="health-state ${health.state}">${label}</span>
          ${health.signals.map(signal => `<div class="signal-row"><span>${escapeHtml(signal.name.replaceAll('_', ' '))}</span><strong>${signal.score}</strong></div>`).join('')}
          <div class="bus-factor ${health.bus_factor.warning ? 'warning' : ''}"><strong>Bus-factor signal:</strong> ${escapeHtml(health.bus_factor.explanation)} ${health.bus_factor.sufficient_data ? `Top contributor: ${health.bus_factor.top_contributor_percentage}% · threshold: ${health.bus_factor.threshold_percentage}%` : ''}</div>
          <div style="margin-top:15px;font-weight:750;font-size:12px">Recommendations</div>
          ${health.recommendations.length ? health.recommendations.map(item => `<div class="recommendation">${escapeHtml(item.message)} <span style="color:#8d98ad">(${escapeHtml(item.signal)}: ${escapeHtml(item.metric)})</span></div>`).join('') : '<div class="empty">No action needed.</div>'}`;
      } catch (error) {
        $('health-panel').innerHTML = '<div class="empty">Health data is unavailable.</div>';
        $('health-message').textContent = 'Unavailable';
        showError(error);
      }
    }

    async function loadLanguages() {
      if (!current) return;
      const [owner, repo] = current.full_name.split('/', 2);
      $('language-breakdown').innerHTML = '<div class="empty loading">Loading language statistics…</div>';
      try {
        const data = await api(`/api/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/languages`);
        if (!data.languages.length) {
          $('language-breakdown').innerHTML = '<div class="empty">GitHub detected no language data for this repository.</div>';
          return;
        }
        const colors = ['#8b5cf6','#22d3ee','#34d399','#f59e0b','#f472b6','#60a5fa','#a3e635','#fb7185'];
        let offset = 0;
        const stops = data.languages.map((item, index) => {
          const start = offset; offset += item.percentage;
          return `${colors[index % colors.length]} ${start}% ${offset}%`;
        }).join(', ');
        $('language-breakdown').innerHTML = `<div class="language-layout"><div class="language-ring" style="background:conic-gradient(${stops})" role="img" aria-label="Repository language distribution"></div><div>${data.languages.map((item, index) => `<div class="language-row"><span class="language-dot" style="background:${colors[index % colors.length]}"></span><div><div>${escapeHtml(item.language)} · ${item.percentage}%</div><div class="language-bar"><span style="width:${item.percentage}%;background:${colors[index % colors.length]}"></span></div></div><span>${shortNumber(item.bytes)} B</span></div>`).join('')}</div></div>`;
      } catch (error) {
        $('language-breakdown').innerHTML = '<div class="empty">Language statistics are unavailable.</div>';
        showError(error);
      }
    }

    async function loadIntelligence() {
      if (!current) return;
      const [owner, repo] = current.full_name.split('/', 2);
      $('intelligence-body').innerHTML = '<div class="empty loading">Loading analytics…</div>';
      const endpoint = intelligenceView === 'pulls' ? 'pulls/details' : intelligenceView === 'issues' ? 'issues/details' : 'contributors';
      try {
        intelligenceData = await api(`/api/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/analytics/${endpoint}?days=180`);
        renderIntelligence();
      } catch (error) {
        $('intelligence-body').innerHTML = '<div class="empty">Analytics are unavailable.</div>';
        showError(error);
      }
    }

    function renderIntelligence(bucketLabel = '') {
      if (intelligenceView === 'contributors') return renderContributors();
      const data = intelligenceData;
      const isPull = intelligenceView === 'pulls';
      const metrics = isPull
        ? [['Open', data.metrics.open], ['Merged', data.metrics.merged], ['Closed', data.metrics.closed_unmerged], ['Avg. merge', days(data.metrics.average_time_to_merge_days)], ['Median merge', days(data.metrics.median_time_to_merge_days)]]
        : [['Open', data.metrics.open], ['Closed', data.metrics.closed], ['Stale', data.metrics.stale], ['Avg. resolution', days(data.metrics.average_resolution_days)], ['Oldest open', days(data.metrics.oldest_open?.age_days)]];
      const rows = bucketLabel ? data.age_buckets.find(bucket => bucket.label === bucketLabel)?.items || [] : data.items;
      $('intelligence-body').innerHTML = `<div class="metric-grid">${metrics.map(([label, value]) => `<div class="metric-card"><div class="metric-label">${label}</div><div class="metric-value">${value ?? '—'}</div></div>`).join('')}</div>
        ${data.metrics.oldest_open ? `<a class="repo-link" href="${escapeHtml(data.metrics.oldest_open.html_url)}" target="_blank" rel="noreferrer">Oldest open: #${data.metrics.oldest_open.number} · ${escapeHtml(data.metrics.oldest_open.title)} ↗</a>` : ''}
        <div class="buckets">${data.age_buckets.map(bucket => `<button class="bucket ${bucketLabel === bucket.label ? 'active' : ''}" data-bucket="${escapeHtml(bucket.label)}">${escapeHtml(bucket.label)}<strong>${bucket.count}</strong></button>`).join('')}</div>
        ${activityTable(rows, isPull)}`;
      document.querySelectorAll('.bucket').forEach(button => button.addEventListener('click', () => renderIntelligence(button.classList.contains('active') ? '' : button.dataset.bucket)));
      bindTableSorting();
    }

    function days(value) { return value == null ? '—' : `${Number(value).toFixed(1)}d`; }

    function activityTable(rows, isPull) {
      if (!rows.length) return '<div class="empty">No matching activity.</div>';
      return `<div class="table-wrap"><table><thead><tr>${(isPull ? ['PR','Author','Created','Age','Reviews','Status'] : ['Issue','Labels','Author','Age','Comments','Status']).map((label, index) => `<th data-column="${index}">${label}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>
        <td><a class="repo-link" href="${escapeHtml(row.html_url)}" target="_blank" rel="noreferrer">#${row.number} · ${escapeHtml(row.title)}</a></td>
        ${isPull ? `<td>${escapeHtml(row.author)}</td><td>${new Date(row.created_at).toLocaleDateString()}</td><td data-sort="${row.age_days}">${days(row.age_days)}</td><td data-sort="${row.reviews}">${row.reviews}</td>` : `<td>${escapeHtml(row.labels.join(', ') || '—')}</td><td>${escapeHtml(row.author)}</td><td data-sort="${row.age_days}">${days(row.age_days)}</td><td data-sort="${row.comments}">${row.comments}</td>`}
        <td>${escapeHtml(row.stale ? 'stale' : row.status)}</td></tr>`).join('')}</tbody></table></div>`;
    }

    function bindTableSorting() {
      document.querySelectorAll('#intelligence-body th').forEach(header => header.addEventListener('click', () => {
        const body = header.closest('table').tBodies[0];
        const index = Number(header.dataset.column);
        [...body.rows].sort((a, b) => {
          const left = a.cells[index].dataset.sort ?? a.cells[index].textContent.trim();
          const right = b.cells[index].dataset.sort ?? b.cells[index].textContent.trim();
          return !isNaN(left) && !isNaN(right) ? Number(left) - Number(right) : left.localeCompare(right);
        }).forEach(row => body.appendChild(row));
      }));
    }

    function renderContributors() {
      const rows = intelligenceData.contributors;
      $('intelligence-body').innerHTML = `<div class="metric-grid"><div class="metric-card"><div class="metric-label">Contributors</div><div class="metric-value">${intelligenceData.contributor_count}</div></div></div>
        ${rows.length ? `<div class="table-wrap"><table><thead><tr><th>Contributor</th><th>Commits</th><th>PRs</th><th>Reviews</th><th>Issues</th><th>Share</th><th>Recent activity</th></tr></thead><tbody>${rows.map(row => `<tr><td><span class="person">${row.avatar_url ? `<img class="avatar" src="${escapeHtml(row.avatar_url)}" alt="">` : ''}${escapeHtml(row.login)}</span></td><td>${row.commits}</td><td>${row.pull_requests}</td><td>${row.reviews}</td><td>${row.issues}</td><td>${row.contribution_percentage}%</td><td>${escapeHtml(row.recent_activity[0]?.title || 'No recent commits')}</td></tr>`).join('')}</tbody></table></div>` : '<div class="empty">No contributor activity in this period.</div>'}`;
    }

    async function loadTab(tab) {
      if (!current) return;
      const [owner, repo] = current.full_name.split('/', 2);
      $('activity').innerHTML = '<div class="empty loading">Loading…</div>';
      try {
        const data = await api(`/api/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/${tab === 'issues' ? 'issues' : 'pulls'}?state=open`);
        const items = tab === 'issues' ? data.filter(item => !item.pull_request) : data;
        if (!items.length) {
          $('activity').innerHTML = `<div class="empty">No open ${tab === 'issues' ? 'issues' : 'pull requests'} 🎉</div>`;
          return;
        }
        $('activity').innerHTML = items.slice(0, 8).map(item => `
          <a class="item" href="${escapeHtml(item.html_url)}" target="_blank" rel="noreferrer">
            <span class="item-icon">${tab === 'issues' ? '○' : '↗'}</span>
            <span><div class="item-title">#${escapeHtml(item.number)} · ${escapeHtml(item.title)}</div><div class="item-meta">${escapeHtml(item.user?.login || 'Unknown')} · updated ${new Date(item.updated_at).toLocaleDateString()}</div></span>
          </a>`).join('');
      } catch (error) { showError(error); $('activity').innerHTML = '<div class="empty">Could not load activity.</div>'; }
    }

    function showError(error) {
      $('error').innerHTML = `<div class="error">${escapeHtml(error.message || 'Something went wrong.')}</div>`;
    }

    document.querySelectorAll('[data-tab]').forEach(button => button.addEventListener('click', () => {
      document.querySelectorAll('[data-tab]').forEach(item => item.classList.remove('active'));
      button.classList.add('active');
      loadTab(button.dataset.tab);
    }));
    repoSelect.addEventListener('change', loadRepository);
    repoSearch.addEventListener('input', () => renderRepositories());
    repoFilter.addEventListener('change', () => renderRepositories());
    repoSort.addEventListener('change', () => renderRepositories());
    $('favorite').addEventListener('click', toggleFavorite);
    document.querySelectorAll('.range-button').forEach(button => button.addEventListener('click', () => {
      document.querySelectorAll('.range-button').forEach(item => item.classList.remove('active'));
      button.classList.add('active');
      analyticsDays = Number(button.dataset.days);
      loadCommitActivity();
    }));
    document.querySelectorAll('.intelligence-tab').forEach(button => button.addEventListener('click', () => {
      document.querySelectorAll('.intelligence-tab').forEach(item => item.classList.remove('active'));
      button.classList.add('active');
      intelligenceView = button.dataset.view;
      loadIntelligence();
    }));
    loadRepositories();
  </script>
</body>
</html>'''
