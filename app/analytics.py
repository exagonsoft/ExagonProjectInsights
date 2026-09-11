from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def day_series(items: list[dict], field: str, days: int) -> list[dict]:
    today = datetime.now(timezone.utc).date()
    counts = Counter(
        timestamp.date()
        for item in items
        if (timestamp := parse_time(item.get(field))) is not None
    )
    return [
        {"date": (today - timedelta(days=offset)).isoformat(), "count": counts[today - timedelta(days=offset)]}
        for offset in range(days - 1, -1, -1)
    ]


def average_days(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def commit_activity(commits: list[dict], days: int) -> dict:
    contributor_counts = Counter()
    for item in commits:
        login = (item.get("author") or {}).get("login")
        name = ((item.get("commit") or {}).get("author") or {}).get("name")
        contributor_counts[login or name or "Unknown"] += 1
    series = day_series(
        [{"date": ((item.get("commit") or {}).get("author") or {}).get("date")} for item in commits],
        "date",
        days,
    )
    return {
        "range_days": days,
        "total_commits": len(commits),
        "commits_per_day": series,
        "commits_per_week": _weekly(series),
        "active_contributors": [
            {"login": login, "commits": count}
            for login, count in contributor_counts.most_common()
        ],
        "latest_commits": [
            {
                "sha": item.get("sha"),
                "message": ((item.get("commit") or {}).get("message") or "").splitlines()[0],
                "author": (item.get("author") or {}).get("login")
                or ((item.get("commit") or {}).get("author") or {}).get("name"),
                "date": ((item.get("commit") or {}).get("author") or {}).get("date"),
                "html_url": item.get("html_url"),
            }
            for item in commits[:10]
        ],
    }


def _weekly(series: list[dict]) -> list[dict]:
    weeks: dict[str, int] = {}
    for point in series:
        date = datetime.fromisoformat(point["date"]).date()
        monday = date - timedelta(days=date.weekday())
        weeks[monday.isoformat()] = weeks.get(monday.isoformat(), 0) + point["count"]
    return [{"week": week, "count": count} for week, count in weeks.items()]


def pull_request_activity(pulls: list[dict], days: int) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    pulls = [item for item in pulls if (created := parse_time(item.get("created_at"))) and created >= cutoff]
    opened = len(pulls)
    merged = [item for item in pulls if item.get("merged_at")]
    closed = [item for item in pulls if item.get("closed_at")]
    open_items = [item for item in pulls if item.get("state") == "open"]
    ages = [
        (now - created).total_seconds() / 86400
        for item in open_items
        if (created := parse_time(item.get("created_at")))
    ]
    return {
        "range_days": days,
        "opened": opened,
        "merged": len(merged),
        "closed": len(closed),
        "currently_open": len(open_items),
        "merge_rate": round((len(merged) / opened) * 100, 2) if opened else 0,
        "average_open_age_days": average_days(ages),
        "trend": {"opened": day_series(pulls, "created_at", days), "merged": day_series(merged, "merged_at", days)},
    }


def issue_activity(issues: list[dict], days: int, stale_days: int = 30) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    real_issues = [
        item for item in issues
        if "pull_request" not in item
        and (created := parse_time(item.get("created_at")))
        and created >= cutoff
    ]
    closed = [item for item in real_issues if item.get("closed_at")]
    open_items = [item for item in real_issues if item.get("state") == "open"]
    resolution = [
        (closed_at - created_at).total_seconds() / 86400
        for item in closed
        if (closed_at := parse_time(item.get("closed_at")))
        and (created_at := parse_time(item.get("created_at")))
    ]
    stale = [
        item for item in open_items
        if (updated := parse_time(item.get("updated_at"))) and (now - updated).days >= stale_days
    ]
    return {
        "range_days": days,
        "stale_after_days": stale_days,
        "opened": len(real_issues),
        "closed": len(closed),
        "currently_open": len(open_items),
        "average_resolution_days": average_days(resolution),
        "stale": len(stale),
        "trend": {"opened": day_series(real_issues, "created_at", days), "closed": day_series(closed, "closed_at", days)},
    }
