from __future__ import annotations

import os
from datetime import datetime, timezone

from .analytics import parse_time

DEFAULT_WEIGHTS = {
    "pr_freshness": 15,
    "issue_freshness": 15,
    "commit_activity": 20,
    "issue_closure_rate": 15,
    "pr_merge_rate": 15,
    "contributor_distribution": 10,
    "repository_activity": 10,
}


def _weights() -> dict[str, int]:
    return {name: int(os.getenv(f"HEALTH_WEIGHT_{name.upper()}", value)) for name, value in DEFAULT_WEIGHTS.items()}


def _freshness(average_age: float | None) -> float:
    if average_age is None:
        return 100
    return max(0, 100 - min(average_age, 90) / 90 * 100)


def calculate_health(repository: dict, commits: dict, pulls: dict, issues: dict) -> dict:
    contributors = commits["active_contributors"]
    total = commits["total_commits"]
    top_share = (contributors[0]["commits"] / total * 100) if contributors and total else 0
    concentration_threshold = int(os.getenv("BUS_FACTOR_CONCENTRATION_THRESHOLD", "70"))
    sufficient_contributors = len(contributors) >= 2
    issue_total = issues["opened"]
    updated = parse_time(repository.get("pushed_at") or repository.get("updated_at"))
    inactivity = (datetime.now(timezone.utc) - updated).days if updated else None
    signals = {
        "pr_freshness": _freshness(pulls["average_open_age_days"]),
        "issue_freshness": 100 if not issues["currently_open"] else max(0, 100 - issues["stale"] / issues["currently_open"] * 100),
        "commit_activity": min(100, total / max(commits["range_days"], 1) * 700),
        "issue_closure_rate": (issues["closed"] / issue_total * 100) if issue_total else 100,
        "pr_merge_rate": pulls["merge_rate"] if pulls["opened"] else 100,
        "contributor_distribution": 100 if not sufficient_contributors else max(0, 100 - max(0, top_share - 40) * (100 / 60)),
        "repository_activity": 100 if inactivity is None else max(0, 100 - min(inactivity, 180) / 180 * 100),
    }
    weights = _weights()
    total_weight = sum(weights.values()) or 1
    score = round(sum(signals[name] * weights[name] for name in weights) / total_weight)
    healthy = int(os.getenv("HEALTHY_THRESHOLD", "80"))
    attention = int(os.getenv("ATTENTION_THRESHOLD", "60"))
    state = "healthy" if score >= healthy else "needs_attention" if score >= attention else "at_risk"
    details = [
        {"name": name, "score": round(value, 1), "weight": weights[name]}
        for name, value in signals.items()
    ]
    return {
        "score": score,
        "state": state,
        "thresholds": {"healthy": healthy, "needs_attention": attention},
        "signals": details,
        "bus_factor": {
            "warning": sufficient_contributors and top_share >= concentration_threshold,
            "threshold_percentage": concentration_threshold,
            "top_contributor_percentage": round(top_share, 1) if total else None,
            "contributors_analyzed": len(contributors),
            "sufficient_data": sufficient_contributors,
            "top_contributors": contributors[:5],
            "explanation": "Warning when the top contributor meets or exceeds the configured share threshold." if sufficient_contributors else "At least two active contributors are required before concentration is assessed.",
        },
        "recommendations": recommendations(signals, pulls, issues, total, top_share, inactivity, sufficient_contributors, concentration_threshold),
    }


def recommendations(signals, pulls, issues, commits, top_share, inactivity, sufficient_contributors, concentration_threshold) -> list[dict]:
    result = []
    if signals["commit_activity"] < 50:
        result.append({"signal": "commit_activity", "metric": commits, "message": "Review delivery blockers and restore a consistent commit cadence."})
    if issues["stale"]:
        result.append({"signal": "issue_freshness", "metric": issues["stale"], "message": f"Triage {issues['stale']} stale issue(s) that have not changed in {issues['stale_after_days']} days."})
    if pulls["average_open_age_days"] is not None and pulls["average_open_age_days"] >= 14:
        result.append({"signal": "pr_freshness", "metric": pulls["average_open_age_days"], "message": "Review aging pull requests and assign a clear next action."})
    if pulls["opened"] and pulls["merge_rate"] < 50:
        result.append({"signal": "pr_merge_rate", "metric": pulls["merge_rate"], "message": "Investigate the low pull-request merge rate and reduce review bottlenecks."})
    if sufficient_contributors and top_share >= concentration_threshold:
        result.append({"signal": "contributor_distribution", "metric": round(top_share, 1), "message": "Reduce contributor concentration by sharing ownership and review responsibilities."})
    if inactivity is not None and inactivity >= 30:
        result.append({"signal": "repository_activity", "metric": inactivity, "message": "Confirm repository status; no push activity has occurred for at least 30 days."})
    return result
