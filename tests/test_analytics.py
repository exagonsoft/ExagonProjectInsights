import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.analytics import commit_activity, issue_activity, pull_request_activity
from app.health import calculate_health


def stamp(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


class AnalyticsTests(unittest.TestCase):
    def test_commit_activity_is_stable_for_empty_repository(self):
        result = commit_activity([], 30)
        self.assertEqual(result["total_commits"], 0)
        self.assertEqual(len(result["commits_per_day"]), 30)
        self.assertEqual(result["active_contributors"], [])

    def test_pull_request_metrics(self):
        pulls = [
            {"created_at": stamp(4), "merged_at": stamp(2), "closed_at": stamp(2), "state": "closed"},
            {"created_at": stamp(3), "merged_at": None, "closed_at": None, "state": "open"},
        ]
        result = pull_request_activity(pulls, 30)
        self.assertEqual(result["opened"], 2)
        self.assertEqual(result["merged"], 1)
        self.assertEqual(result["currently_open"], 1)
        self.assertEqual(result["merge_rate"], 50)

    def test_issue_metrics_exclude_pull_requests_and_detect_stale(self):
        issues = [
            {"created_at": stamp(40), "updated_at": stamp(35), "closed_at": None, "state": "open"},
            {"created_at": stamp(10), "updated_at": stamp(1), "closed_at": stamp(1), "state": "closed"},
            {"created_at": stamp(1), "updated_at": stamp(1), "state": "open", "pull_request": {}},
        ]
        result = issue_activity(issues, 90)
        self.assertEqual(result["opened"], 2)
        self.assertEqual(result["closed"], 1)
        self.assertEqual(result["stale"], 1)

    @patch.dict("os.environ", {}, clear=True)
    def test_health_is_deterministic_and_bounded(self):
        repository = {"pushed_at": stamp(1)}
        commits = {"total_commits": 20, "range_days": 30, "active_contributors": [{"login": "a", "commits": 12}, {"login": "b", "commits": 8}]}
        pulls = {"opened": 4, "merge_rate": 75, "average_open_age_days": 3}
        issues = {"opened": 5, "closed": 4, "currently_open": 1, "stale": 0, "stale_after_days": 30}
        first = calculate_health(repository, commits, pulls, issues)
        second = calculate_health(repository, commits, pulls, issues)
        self.assertEqual(first, second)
        self.assertGreaterEqual(first["score"], 0)
        self.assertLessEqual(first["score"], 100)


if __name__ == "__main__":
    unittest.main()
