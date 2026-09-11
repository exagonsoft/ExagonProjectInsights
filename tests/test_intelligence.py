import unittest
from datetime import datetime, timedelta, timezone

from app.intelligence import contributor_details, issue_details, pull_request_details


def stamp(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


class IntelligenceTests(unittest.TestCase):
    def test_every_open_pr_has_exactly_one_bucket(self):
        pulls = [{"number": i, "title": str(i), "html_url": "https://example.test", "created_at": stamp(age), "updated_at": stamp(age), "state": "open", "user": {"login": "dev"}} for i, age in enumerate([1, 5, 10, 20, 40], 1)]
        result = pull_request_details(pulls, {}, 180)
        self.assertEqual(sum(bucket["count"] for bucket in result["age_buckets"]), 5)
        self.assertEqual([bucket["count"] for bucket in result["age_buckets"]], [1, 1, 1, 1, 1])

    def test_merge_mean_and_median(self):
        pulls = [{"number": i, "created_at": stamp(age), "updated_at": stamp(1), "closed_at": stamp(age - duration), "merged_at": stamp(age - duration), "state": "closed", "user": {"login": "dev"}} for i, (age, duration) in enumerate([(10, 2), (20, 4), (30, 6)], 1)]
        metrics = pull_request_details(pulls, {}, 180)["metrics"]
        self.assertAlmostEqual(metrics["average_time_to_merge_days"], 4, places=1)
        self.assertAlmostEqual(metrics["median_time_to_merge_days"], 4, places=1)

    def test_issues_exclude_pull_requests_and_bucket_once(self):
        issues = [{"number": 1, "title": "Issue", "html_url": "https://example.test", "created_at": stamp(9), "updated_at": stamp(2), "state": "open", "user": {"login": "dev"}, "labels": []}, {"number": 2, "created_at": stamp(2), "state": "open", "pull_request": {}}]
        result = issue_details(issues, 180)
        self.assertEqual(result["metrics"]["open"], 1)
        self.assertEqual(sum(bucket["count"] for bucket in result["age_buckets"]), 1)

    def test_contributor_percentages_total_one_hundred(self):
        commits = [{"author": {"login": "a"}, "commit": {"author": {"date": stamp(), "name": "a"}, "message": "A"}, "html_url": "https://example.test"}, {"author": {"login": "b"}, "commit": {"author": {"date": stamp(), "name": "b"}, "message": "B"}, "html_url": "https://example.test"}]
        result = contributor_details(commits, [], [], {}, 30)
        self.assertEqual(result["contributor_count"], 2)
        self.assertAlmostEqual(sum(item["contribution_percentage"] for item in result["contributors"]), 100)


if __name__ == "__main__":
    unittest.main()
