"""
Unit tests
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

# Mock environment variables before importing main module
with patch.dict(
    os.environ,
    {
        "BITBUCKET_USERNAME": "test_user",
        "BITBUCKET_API_TOKEN": "test_token",
        "BITBUCKET_WORKSPACE": "test_workspace",
        "BITBUCKET_REPO": "test_repo",
    },
):
    # Mock the atlassian import to avoid dependency issues
    sys.modules["atlassian"] = MagicMock()
    sys.modules["atlassian.bitbucket"] = MagicMock()

    from main import get_pr_metrics, parse_args, print_summary_stats


class TestArgumentParsing(unittest.TestCase):
    def test_parse_args_with_openprs(self):
        """
        Test that --openprs argument is properly parsed
        """
        test_args = ["--openprs"]
        with patch.object(sys, "argv", ["main.py"] + test_args):
            args = parse_args()
            self.assertTrue(args.openprs)

    def test_parse_args_without_openprs(self):
        """
        Test that openprs is False when not specified
        """
        test_args = []
        with patch.object(sys, "argv", ["main.py"] + test_args):
            args = parse_args()
            self.assertFalse(args.openprs)

    def test_parse_args_with_other_options(self):
        """
        Test that --openprs works with other options
        """
        test_args = ["--openprs", "--days", "30", "--limit", "10"]
        with patch.object(sys, "argv", ["main.py"] + test_args):
            args = parse_args()
            self.assertTrue(args.openprs)
            self.assertEqual(args.days, 30)
            self.assertEqual(args.limit, 10)


class TestGetPrMetrics(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.mock_cloud = MagicMock()
        self.workspace = "test-workspace"
        self.repo = "test-repo"

        # Base PR data for testing
        self.base_pr = {
            "id": 123,
            "title": "Test PR",
            "author": {"display_name": "Test Author"},
            "state": "MERGED",
            "created_on": "2024-01-01T10:00:00Z",
            "updated_on": "2024-01-02T14:30:00Z",
            "source": {"branch": {"name": "feature-branch"}},
            "destination": {"branch": {"name": "main"}},
        }

    def test_merged_pr_review_time_calculation(self):
        """Test review time calculation for merged PR"""
        # Create PR with known dates: 1 day, 4.5 hours = 1.1875 days
        pr = self.base_pr.copy()
        pr["created_on"] = "2024-01-01T10:00:00Z"
        pr["updated_on"] = "2024-01-02T14:30:00Z"

        # Mock API responses
        self.mock_cloud.get.return_value = {"participants": []}
        self.mock_cloud._get_paged.side_effect = [
            [],  # commits
            [],  # comments
            [],  # diffstat
        ]

        result = get_pr_metrics(self.mock_cloud, self.workspace, self.repo, pr)

        # Should be 1 day + 4.5 hours = 1.1875 days
        expected_days = 1 + 4.5 / 24  # 1.1875
        self.assertAlmostEqual(result["review_time_days"], expected_days, places=4)
        self.assertEqual(result["state"], "MERGED")

    def test_open_pr_time_calculation(self):
        """Test time since creation calculation for open PR"""
        pr = self.base_pr.copy()
        pr["state"] = "OPEN"
        pr["created_on"] = "2024-01-01T10:00:00Z"
        # Remove updated_on for open PR
        del pr["updated_on"]

        # Mock API responses
        self.mock_cloud.get.return_value = {"participants": []}
        self.mock_cloud._get_paged.side_effect = [
            [],  # commits
            [],  # comments
            [],  # diffstat
        ]

        # Mock current time to be 2 days later (timezone-aware)
        from datetime import timezone

        with patch("main.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(
                2024, 1, 3, 10, 0, 0, tzinfo=timezone.utc
            )
            mock_datetime.fromisoformat.side_effect = lambda x: datetime.fromisoformat(
                x.replace("Z", "+00:00")
            )

            result = get_pr_metrics(self.mock_cloud, self.workspace, self.repo, pr)

            # Should be exactly 2 days
            self.assertAlmostEqual(result["review_time_days"], 2.0, places=4)
            self.assertEqual(result["state"], "OPEN")

    def test_pr_with_no_updated_on(self):
        """Test PR with missing updated_on field"""
        pr = self.base_pr.copy()
        del pr["updated_on"]

        # Mock API responses
        self.mock_cloud.get.return_value = {"participants": []}
        self.mock_cloud._get_paged.side_effect = [
            [],  # commits
            [],  # comments
            [],  # diffstat
        ]

        result = get_pr_metrics(self.mock_cloud, self.workspace, self.repo, pr)

        self.assertIsNone(result["review_time_days"])

    def test_reviewer_count_extraction(self):
        """Test reviewer count extraction from participants"""
        pr = self.base_pr.copy()

        # Mock participants with reviewers
        participants = [
            {"role": "REVIEWER", "user": {"display_name": "Reviewer 1"}},
            {"role": "REVIEWER", "user": {"display_name": "Reviewer 2"}},
            {"role": "PARTICIPANT", "user": {"display_name": "Author"}},
        ]

        self.mock_cloud.get.return_value = {"participants": participants}
        self.mock_cloud._get_paged.side_effect = [
            [],  # commits
            [],  # comments
            [],  # diffstat
        ]

        result = get_pr_metrics(self.mock_cloud, self.workspace, self.repo, pr)

        self.assertEqual(result["reviewer_count"], 2)

    def test_commits_count_extraction(self):
        """Test commits count extraction"""
        pr = self.base_pr.copy()

        # Mock commits response
        commits = [{"id": "1"}, {"id": "2"}, {"id": "3"}]

        self.mock_cloud.get.return_value = {"participants": []}
        self.mock_cloud._get_paged.side_effect = [
            commits,  # commits
            [],  # comments
            [],  # diffstat
        ]

        result = get_pr_metrics(self.mock_cloud, self.workspace, self.repo, pr)

        self.assertEqual(result["commits_count"], 3)

    def test_comments_count_extraction(self):
        """Test comments count extraction"""
        pr = self.base_pr.copy()

        # Mock comments response
        comments = [{"id": "1"}, {"id": "2"}]

        self.mock_cloud.get.return_value = {"participants": []}
        self.mock_cloud._get_paged.side_effect = [
            [],  # commits
            comments,  # comments
            [],  # diffstat
        ]

        result = get_pr_metrics(self.mock_cloud, self.workspace, self.repo, pr)

        self.assertEqual(result["comments_count"], 2)

    def test_diffstat_extraction(self):
        """Test diffstat extraction for lines and files"""
        pr = self.base_pr.copy()

        # Mock diffstat response
        diffstats = [
            {"lines_added": 10, "lines_removed": 5},
            {"lines_added": 15, "lines_removed": 3},
            {"lines_added": 0, "lines_removed": 2},
        ]

        self.mock_cloud.get.return_value = {"participants": []}
        self.mock_cloud._get_paged.side_effect = [
            [],  # commits
            [],  # comments
            diffstats,  # diffstat
        ]

        result = get_pr_metrics(self.mock_cloud, self.workspace, self.repo, pr)

        self.assertEqual(result["lines_added"], 25)  # 10 + 15 + 0
        self.assertEqual(result["lines_removed"], 10)  # 5 + 3 + 2
        self.assertEqual(result["total_lines_changed"], 35)  # 25 + 10
        self.assertEqual(result["files_changed"], 3)

    def test_diffstat_api_failure(self):
        """Test handling of diffstat API failure"""
        pr = self.base_pr.copy()

        self.mock_cloud.get.return_value = {"participants": []}
        self.mock_cloud._get_paged.side_effect = [
            [],  # commits
            [],  # comments
            Exception("API Error"),  # diffstat fails
        ]

        result = get_pr_metrics(self.mock_cloud, self.workspace, self.repo, pr)

        # Should default to zeros on failure
        self.assertEqual(result["lines_added"], 0)
        self.assertEqual(result["lines_removed"], 0)
        self.assertEqual(result["total_lines_changed"], 0)
        self.assertEqual(result["files_changed"], 0)

    def test_return_dictionary_structure(self):
        """Test that return dictionary has all expected keys"""
        pr = self.base_pr.copy()

        # Mock API responses
        self.mock_cloud.get.return_value = {"participants": []}
        self.mock_cloud._get_paged.side_effect = [
            [],  # commits
            [],  # comments
            [],  # diffstat
        ]

        result = get_pr_metrics(self.mock_cloud, self.workspace, self.repo, pr)

        expected_keys = [
            "id",
            "title",
            "author",
            "state",
            "created_on",
            "updated_on",
            "review_time_days",
            "reviewer_count",
            "commits_count",
            "comments_count",
            "lines_added",
            "lines_removed",
            "total_lines_changed",
            "files_changed",
            "source_branch",
            "destination_branch",
        ]

        for key in expected_keys:
            self.assertIn(key, result)

        # Test data types
        self.assertIsInstance(result["id"], int)
        self.assertIsInstance(result["title"], str)
        self.assertIsInstance(result["author"], str)
        self.assertIsInstance(result["state"], str)
        self.assertIsInstance(result["reviewer_count"], int)
        self.assertIsInstance(result["commits_count"], int)
        self.assertIsInstance(result["comments_count"], int)


class TestPrintSummaryStats(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.sample_metrics = [
            {
                "id": 1,
                "title": "Test PR 1",
                "author": "Author 1",
                "state": "MERGED",
                "review_time_days": 1.5,
                "reviewer_count": 2,
                "commits_count": 3,
                "comments_count": 5,
                "lines_added": 100,
                "lines_removed": 50,
                "total_lines_changed": 150,
                "files_changed": 10,
            },
            {
                "id": 2,
                "title": "Test PR 2",
                "author": "Author 2",
                "state": "MERGED",
                "review_time_days": 2.0,
                "reviewer_count": 1,
                "commits_count": 2,
                "comments_count": 3,
                "lines_added": 200,
                "lines_removed": 100,
                "total_lines_changed": 300,
                "files_changed": 15,
            },
        ]

    def test_empty_metrics_list(self):
        """Test handling of empty metrics list"""
        with patch("builtins.print") as mock_print:
            print_summary_stats([])
            mock_print.assert_called_with("No PRs to analyze")

    def test_console_output_generation(self):
        """Test console output format and content"""
        with patch("builtins.print") as mock_print:
            print_summary_stats(self.sample_metrics)

            # Check that key statistics are printed
            printed_output = " ".join(
                [call[0][0] for call in mock_print.call_args_list]
            )

            # Should contain summary statistics
            self.assertIn("Total PRs analyzed: 2", printed_output)
            self.assertIn("Review Time (days):", printed_output)
            self.assertIn("Commits per PR:", printed_output)
            self.assertIn("Comments per PR:", printed_output)
            self.assertIn("Reviewers per PR:", printed_output)

    def test_markdown_file_generation(self):
        """Test markdown file generation"""
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".md"
        ) as temp_file:
            temp_filename = temp_file.name

        try:
            print_summary_stats(self.sample_metrics, temp_filename)

            with open(temp_filename, "r") as f:
                content = f.read()

            # Check markdown structure
            self.assertIn("# Pull Request Analysis Report", content)
            self.assertIn("## Summary", content)
            self.assertIn("## Review Time", content)
            self.assertIn("## Commits per PR", content)
            self.assertIn("## Comments per PR", content)
            self.assertIn("## Reviewers per PR", content)
            self.assertIn("## Code Changes", content)

            # Check that data is included
            self.assertIn("**Total PRs analyzed:** 2", content)
            self.assertIn("| Metric | Days | Hours |", content)

        finally:
            import os

            if os.path.exists(temp_filename):
                os.unlink(temp_filename)

    def test_review_time_statistics_merged_prs(self):
        """Test review time statistics for merged PRs"""
        with patch("builtins.print") as mock_print:
            print_summary_stats(self.sample_metrics)

            printed_output = " ".join(
                [call[0][0] for call in mock_print.call_args_list]
            )

            # Should show "Review Time" label for merged PRs
            self.assertIn("Review Time (days):", printed_output)
            self.assertIn("Average: 1.75 days", printed_output)  # (1.5 + 2.0) / 2

    def test_review_time_statistics_open_prs(self):
        """Test review time statistics for open PRs"""
        open_metrics = [
            {
                "id": 1,
                "title": "Open PR",
                "author": "Author",
                "state": "OPEN",
                "review_time_days": 3.0,
                "reviewer_count": 1,
                "commits_count": 1,
                "comments_count": 1,
                "lines_added": 50,
                "lines_removed": 25,
                "total_lines_changed": 75,
                "files_changed": 5,
            }
        ]

        with patch("builtins.print") as mock_print:
            print_summary_stats(open_metrics)

            printed_output = " ".join(
                [call[0][0] for call in mock_print.call_args_list]
            )

            # Should show "Time Since Creation" label for open PRs
            self.assertIn("Time Since Creation (days):", printed_output)

    def test_review_time_with_none_values(self):
        """Test handling of None review_time_days values"""
        metrics_with_none = [
            {
                "id": 1,
                "title": "PR with no time",
                "author": "Author",
                "state": "MERGED",
                "review_time_days": None,
                "reviewer_count": 1,
                "commits_count": 1,
                "comments_count": 1,
                "lines_added": 10,
                "lines_removed": 5,
                "total_lines_changed": 15,
                "files_changed": 2,
            }
        ]

        with patch("builtins.print") as mock_print:
            print_summary_stats(metrics_with_none)

            printed_output = " ".join(
                [call[0][0] for call in mock_print.call_args_list]
            )

            # Should not include review time section when all values are None
            self.assertNotIn("Review Time", printed_output)
            self.assertNotIn("Time Since Creation", printed_output)

    def test_single_pr_metrics(self):
        """Test summary with single PR"""
        single_metric = [self.sample_metrics[0]]

        with patch("builtins.print") as mock_print:
            print_summary_stats(single_metric)

            printed_output = " ".join(
                [call[0][0] for call in mock_print.call_args_list]
            )

            self.assertIn("Total PRs analyzed: 1", printed_output)
            self.assertIn("Average: 1.50 days", printed_output)  # Single value

    def test_statistics_calculations(self):
        """Test that statistics are calculated correctly"""
        with patch("builtins.print") as mock_print:
            print_summary_stats(self.sample_metrics)

            printed_output = " ".join(
                [call[0][0] for call in mock_print.call_args_list]
            )

            # Test specific calculations (more flexible matching)
            self.assertIn("Average: 1.75 days", printed_output)  # (1.5 + 2.0) / 2
            self.assertIn("Median:", printed_output)
            self.assertIn("1.75 days", printed_output)  # Median of 1.5, 2.0
            self.assertIn("Min:", printed_output)
            self.assertIn("1.50 days", printed_output)  # Min of 1.5, 2.0
            self.assertIn("Max:", printed_output)
            self.assertIn("2.00 days", printed_output)  # Max of 1.5, 2.0

            # Test other statistics
            self.assertIn("Average: 2.50", printed_output)  # Commits: (3 + 2) / 2
            self.assertIn("Average: 4.00", printed_output)  # Comments: (5 + 3) / 2
            self.assertIn("Average: 1.50", printed_output)  # Reviewers: (2 + 1) / 2


if __name__ == "__main__":
    unittest.main()
