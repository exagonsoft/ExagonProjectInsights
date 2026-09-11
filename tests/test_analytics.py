import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.analytics import commit_activity, issue_activity, language_statistics, pull_request_activity
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

    def test_language_statistics_use_positive_github_bytes(self):
        result = language_statistics({"Python": 75, "JavaScript": 25, "Empty": 0})
        self.assertEqual(result["total_bytes"], 100)
        self.assertEqual(result["languages"], [
            {"language": "Python", "bytes": 75, "percentage": 75.0},
            {"language": "JavaScript", "bytes": 25, "percentage": 25.0},
        ])

    @patch.dict("os.environ", {"BUS_FACTOR_CONCENTRATION_THRESHOLD": "70"}, clear=True)
    def test_bus_factor_requires_enough_contributors(self):
        repository = {"pushed_at": stamp(1)}
        pulls = {"opened": 0, "merge_rate": 0, "average_open_age_days": None}
        issues = {"opened": 0, "closed": 0, "currently_open": 0, "stale": 0, "stale_after_days": 30}
        insufficient = calculate_health(repository, {"total_commits": 10, "range_days": 30, "active_contributors": [{"login": "a", "commits": 10}]}, pulls, issues)
        concentrated = calculate_health(repository, {"total_commits": 10, "range_days": 30, "active_contributors": [{"login": "a", "commits": 8}, {"login": "b", "commits": 2}]}, pulls, issues)
        self.assertFalse(insufficient["bus_factor"]["warning"])
        self.assertFalse(insufficient["bus_factor"]["sufficient_data"])
        self.assertTrue(concentrated["bus_factor"]["warning"])


if __name__ == "__main__":
    unittest.main()
