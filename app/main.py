import os

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from .github_client import GitHubClient

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
    footer { color:#59647a; text-align:center; font-size:11px; margin-top:30px; }
    @keyframes pulse { 50% { opacity:.45; } }
    @media (max-width: 980px) { .hero, .workspace { grid-template-columns:1fr; } .selector-wrap { justify-self:stretch; max-width:none; } }
    @media (max-width: 700px) { .shell { width:min(100% - 24px, 1440px); padding-top:18px; } .topbar { margin-bottom:30px; } .status { display:none; } .stats { grid-template-columns:1fr 1fr; } .repository-tools { grid-template-columns:1fr 1fr; } .repository-tools .control-shell:first-child { grid-column:1 / -1; } h1 { font-size:39px; } }
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
          <a class="repo-link" id="github-link" href="#" target="_blank" rel="noreferrer">Open on GitHub ↗</a>
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
      return visible.sort(sorters[repoSort.value] || sorters.name);
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
      repoSelect.innerHTML = visible.map(repo => `<option value="${escapeHtml(repo.full_name)}">${escapeHtml(repo.full_name)}</option>`).join('');
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
        updateHealth();
        await loadTab('issues');
      } catch (error) { showError(error); }
    }

    function updateHealth() {
      const open = current.open_issues || 0;
      $('health-message').textContent = open === 0 ? 'Clean workspace' : `${open} open issue${open === 1 ? '' : 's'}`;
      $('health-detail').textContent = open === 0 ? 'No open issues are currently reported by GitHub.' : 'Review the issue queue to keep project work moving.';
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

    document.querySelectorAll('.tab').forEach(button => button.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(item => item.classList.remove('active'));
      button.classList.add('active');
      loadTab(button.dataset.tab);
    }));
    repoSelect.addEventListener('change', loadRepository);
    repoSearch.addEventListener('input', () => renderRepositories());
    repoFilter.addEventListener('change', () => renderRepositories());
    repoSort.addEventListener('change', () => renderRepositories());
    loadRepositories();
  </script>
</body>
</html>'''
