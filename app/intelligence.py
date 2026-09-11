from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median

from .analytics import average_days, parse_time


def _age_days(item: dict, now: datetime) -> float:
    created = parse_time(item.get("created_at"))
    return round((now - created).total_seconds() / 86400, 2) if created else 0


def _bucket(value: float, boundaries: list[tuple[int, str]]) -> str:
    for maximum, label in boundaries:
        if value <= maximum:
            return label
    return boundaries[-1][1]


def pull_request_details(pulls: list[dict], reviews: dict[int, list[dict]], days: int, stale_days: int = 14) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    items = [item for item in pulls if (created := parse_time(item.get("created_at"))) and created >= cutoff]
    open_items = [item for item in items if item.get("state") == "open"]
    merged = [item for item in items if item.get("merged_at")]
    closed_unmerged = [item for item in items if item.get("closed_at") and not item.get("merged_at")]
    merge_times = [
        (merged_at - created_at).total_seconds() / 86400
        for item in merged
        if (merged_at := parse_time(item.get("merged_at"))) and (created_at := parse_time(item.get("created_at")))
    ]
    rows = []
    buckets = {label: [] for _, label in PR_BUCKETS}
    for item in open_items:
        age = _age_days(item, now)
        bucket = _bucket(age, PR_BUCKETS)
        row = _pr_row(item, age, len(reviews.get(item["number"], [])))
        buckets[bucket].append(row)
        rows.append(row)
    oldest = max(rows, key=lambda row: row["age_days"], default=None)
    inactive = [row for row in rows if row["inactive_days"] >= stale_days]
    return {
        "range_days": days,
        "inactive_after_days": stale_days,
        "metrics": {
            "open": len(open_items), "merged": len(merged), "closed_unmerged": len(closed_unmerged),
            "average_time_to_merge_days": average_days(merge_times),
            "median_time_to_merge_days": round(median(merge_times), 2) if merge_times else None,
            "oldest_open": oldest, "inactive": len(inactive),
        },
        "age_buckets": [{"label": label, "count": len(buckets[label]), "items": buckets[label]} for _, label in PR_BUCKETS],
        "items": sorted(rows, key=lambda row: row["age_days"], reverse=True),
    }


PR_BUCKETS = [(3, "0–3 days"), (7, "4–7 days"), (14, "8–14 days"), (30, "15–30 days"), (10**9, "30+ days")]
ISSUE_BUCKETS = [(7, "0–7 days"), (14, "8–14 days"), (30, "15–30 days"), (60, "30–60 days"), (10**9, "60+ days")]


def _pr_row(item: dict, age: float, reviews: int) -> dict:
    updated = parse_time(item.get("updated_at"))
    now = datetime.now(timezone.utc)
    return {
        "number": item.get("number"), "title": item.get("title"), "html_url": item.get("html_url"),
        "author": (item.get("user") or {}).get("login"), "avatar_url": (item.get("user") or {}).get("avatar_url"),
        "created_at": item.get("created_at"), "age_days": age, "reviews": reviews,
        "status": "draft" if item.get("draft") else item.get("state"),
        "inactive_days": (now - updated).days if updated else 0,
    }


def issue_details(issues: list[dict], days: int, stale_days: int = 30) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    items = [item for item in issues if "pull_request" not in item and (created := parse_time(item.get("created_at"))) and created >= cutoff]
    open_items = [item for item in items if item.get("state") == "open"]
    closed = [item for item in items if item.get("closed_at")]
    resolution = [(closed_at - created_at).total_seconds() / 86400 for item in closed if (closed_at := parse_time(item.get("closed_at"))) and (created_at := parse_time(item.get("created_at")))]
    rows, buckets = [], {label: [] for _, label in ISSUE_BUCKETS}
    for item in open_items:
        age = _age_days(item, now)
        updated = parse_time(item.get("updated_at"))
        row = {
            "number": item.get("number"), "title": item.get("title"), "html_url": item.get("html_url"),
            "author": (item.get("user") or {}).get("login"), "avatar_url": (item.get("user") or {}).get("avatar_url"),
            "age_days": age, "comments": item.get("comments", 0), "status": item.get("state"),
            "labels": [label.get("name") for label in item.get("labels", [])],
            "stale": bool(updated and (now - updated).days >= stale_days),
        }
        buckets[_bucket(age, ISSUE_BUCKETS)].append(row)
        rows.append(row)
    oldest = max(rows, key=lambda row: row["age_days"], default=None)
    return {
        "range_days": days, "stale_after_days": stale_days,
        "metrics": {"open": len(open_items), "closed": len(closed), "stale": sum(row["stale"] for row in rows), "average_resolution_days": average_days(resolution), "oldest_open": oldest},
        "age_buckets": [{"label": label, "count": len(buckets[label]), "items": buckets[label]} for _, label in ISSUE_BUCKETS],
        "items": sorted(rows, key=lambda row: row["age_days"], reverse=True),
    }


def contributor_details(commits: list[dict], pulls: list[dict], issues: list[dict], reviews: dict[int, list[dict]], days: int) -> dict:
    counts = defaultdict(lambda: {"commits": 0, "pull_requests": 0, "reviews": 0, "issues": 0, "avatar_url": None, "recent_activity": []})
    for item in commits:
        identity = (item.get("author") or {}).get("login") or ((item.get("commit") or {}).get("author") or {}).get("name") or "Unknown"
        counts[identity]["commits"] += 1
        counts[identity]["avatar_url"] = (item.get("author") or {}).get("avatar_url")
        counts[identity]["recent_activity"].append({"type": "commit", "title": ((item.get("commit") or {}).get("message") or "").splitlines()[0], "date": ((item.get("commit") or {}).get("author") or {}).get("date"), "url": item.get("html_url")})
    for item in pulls:
        identity = (item.get("user") or {}).get("login") or "Unknown"
        counts[identity]["pull_requests"] += 1
        counts[identity]["avatar_url"] = (item.get("user") or {}).get("avatar_url")
    for item in issues:
        if "pull_request" in item:
            continue
        identity = (item.get("user") or {}).get("login") or "Unknown"
        counts[identity]["issues"] += 1
        counts[identity]["avatar_url"] = (item.get("user") or {}).get("avatar_url")
    for review_items in reviews.values():
        for item in review_items:
            identity = (item.get("user") or {}).get("login") or "Unknown"
            counts[identity]["reviews"] += 1
            counts[identity]["avatar_url"] = (item.get("user") or {}).get("avatar_url")
    total = sum(sum(data[key] for key in ("commits", "pull_requests", "reviews", "issues")) for data in counts.values())
    contributors = []
    for identity, data in counts.items():
        contribution = sum(data[key] for key in ("commits", "pull_requests", "reviews", "issues"))
        contributors.append({"login": identity, **data, "contribution_percentage": round(contribution / total * 100, 2) if total else 0, "recent_activity": sorted(data["recent_activity"], key=lambda row: row.get("date") or "", reverse=True)[:5]})
    return {"range_days": days, "contributor_count": len(contributors), "calculation": "Equal-weight share of commits + opened PRs + submitted reviews + opened issues in the selected period.", "contributors": sorted(contributors, key=lambda row: row["contribution_percentage"], reverse=True)}
