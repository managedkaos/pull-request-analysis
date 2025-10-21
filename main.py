import argparse
import csv
import os
import statistics
from datetime import datetime, timedelta

from atlassian.bitbucket import Cloud

# Environment variables
BITBUCKET_USERNAME = os.getenv("BITBUCKET_USERNAME")
BITBUCKET_API_TOKEN = os.getenv("BITBUCKET_API_TOKEN")
BITBUCKET_WORKSPACE = os.getenv("BITBUCKET_WORKSPACE")
BITBUCKET_REPO = os.getenv("BITBUCKET_REPO")

# Validate environment variables
missing_vars = []
for var_name in [
    "BITBUCKET_USERNAME",
    "BITBUCKET_API_TOKEN",
    "BITBUCKET_WORKSPACE",
    "BITBUCKET_REPO",
]:
    if not os.getenv(var_name):
        missing_vars.append(var_name)

if missing_vars:
    print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
    print("Please set these environment variables before running the script:")
    for var in missing_vars:
        print(f"  export {var}=your_value_here")
    exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Analyze Bitbucket Pull Requests")
    parser.add_argument("--days", type=int, help="Analyze PRs from the last N days")
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Analyze the last N merged PRs (default: 50)",
    )
    parser.add_argument("--pr-id", type=int, help="Analyze a specific PR by ID number")
    parser.add_argument(
        "--output",
        type=str,
        default="pull_request_data.csv",
        help="Output CSV file name",
    )
    parser.add_argument(
        "--report",
        type=str,
        default="pull_request_analysis.md",
        help="Output markdown report file name",
    )
    parser.add_argument(
        "--openprs",
        action="store_true",
        help="Analyze only PRs in OPEN state (default: analyze MERGED PRs)",
    )
    return parser.parse_args()


def get_pr_metrics(cloud, workspace, repo, pr):
    """Get detailed metrics for a single PR"""
    pr_id = pr["id"]

    # Calculate review time in fractional days
    created = datetime.fromisoformat(pr["created_on"].replace("Z", "+00:00"))
    if pr["state"] == "MERGED" and pr.get("updated_on"):
        merged = datetime.fromisoformat(pr["updated_on"].replace("Z", "+00:00"))
        review_time_days = (merged - created).total_seconds() / (24 * 3600)
    elif pr["state"] == "OPEN":
        # For open PRs, calculate time since creation
        now = datetime.now(tz=created.tzinfo)
        review_time_days = (now - created).total_seconds() / (24 * 3600)
    else:
        review_time_days = None

    # Get reviewers count
    participants_url = f"repositories/{workspace}/{repo}/pullrequests/{pr_id}"
    pr_detail = cloud.get(participants_url)

    reviewers = []
    if "participants" in pr_detail:
        reviewers = [
            p for p in pr_detail["participants"] if p.get("role") == "REVIEWER"
        ]
    reviewer_count = len(reviewers)

    # Get commits count
    commits_url = f"repositories/{workspace}/{repo}/pullrequests/{pr_id}/commits"
    commits = list(cloud._get_paged(commits_url))
    commits_count = len(commits)

    # Get comments count
    comments_url = f"repositories/{workspace}/{repo}/pullrequests/{pr_id}/comments"
    comments = list(cloud._get_paged(comments_url))
    comments_count = len(comments)

    # Get code changes (lines added/removed and files changed)
    diffstat_url = f"repositories/{workspace}/{repo}/pullrequests/{pr_id}/diffstat"
    try:
        diffstats = list(cloud._get_paged(diffstat_url))
        lines_added = sum(d.get("lines_added", 0) for d in diffstats)
        lines_removed = sum(d.get("lines_removed", 0) for d in diffstats)
        files_changed = len(diffstats)
    except Exception:
        lines_added = 0
        lines_removed = 0
        files_changed = 0

    return {
        "id": pr_id,
        "title": pr["title"],
        "author": pr["author"]["display_name"],
        "state": pr["state"],
        "created_on": pr["created_on"],
        "updated_on": pr.get("updated_on", ""),
        "review_time_days": review_time_days,
        "reviewer_count": reviewer_count,
        "commits_count": commits_count,
        "comments_count": comments_count,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "total_lines_changed": lines_added + lines_removed,
        "files_changed": files_changed,
        "source_branch": pr["source"]["branch"]["name"],
        "destination_branch": pr["destination"]["branch"]["name"],
    }


def print_summary_stats(metrics_list, output_file="pull_request_analysis.md"):
    """Print summary statistics to console and markdown file"""
    if not metrics_list:
        print("No PRs to analyze")
        return

    # Prepare output lines
    output_lines = []

    def add_line(line=""):
        print(line)
        output_lines.append(line)

    add_line("\n" + "=" * 80)
    add_line("PULL REQUEST ANALYSIS SUMMARY")
    add_line("=" * 80)

    add_line(f"\nTotal PRs analyzed: {len(metrics_list)}")

    # Review time statistics (or time since creation for open PRs)
    review_times = [
        m["review_time_days"] for m in metrics_list if m["review_time_days"] is not None
    ]
    if review_times:
        # Check if we're analyzing open PRs by looking at the state
        is_open_analysis = any(m["state"] == "OPEN" for m in metrics_list)
        time_label = "Time Since Creation" if is_open_analysis else "Review Time"

        add_line(f"\n{time_label} (days):")
        add_line(
            f"  Average: {statistics.mean(review_times):.2f} days ({statistics.mean(review_times) * 24:.2f} hours)"
        )
        add_line(
            f"  Median:  {statistics.median(review_times):.2f} days ({statistics.median(review_times) * 24:.2f} hours)"
        )
        add_line(
            f"  Min:     {min(review_times):.2f} days ({min(review_times) * 24:.2f} hours)"
        )
        add_line(
            f"  Max:     {max(review_times):.2f} days ({max(review_times) * 24:.2f} hours)"
        )

    # Commits statistics
    commits = [m["commits_count"] for m in metrics_list]
    add_line("\nCommits per PR:")
    add_line(f"  Average: {statistics.mean(commits):.2f}")
    add_line(f"  Median:  {statistics.median(commits):.0f}")
    add_line(f"  Min:     {min(commits)}")
    add_line(f"  Max:     {max(commits)}")

    # Comments statistics
    comments = [m["comments_count"] for m in metrics_list]
    add_line("\nComments per PR:")
    add_line(f"  Average: {statistics.mean(comments):.2f}")
    add_line(f"  Median:  {statistics.median(comments):.0f}")
    add_line(f"  Min:     {min(comments)}")
    add_line(f"  Max:     {max(comments)}")

    # Reviewers statistics
    reviewers = [m["reviewer_count"] for m in metrics_list]
    add_line("\nReviewers per PR:")
    add_line(f"  Average: {statistics.mean(reviewers):.2f}")
    add_line(f"  Median:  {statistics.median(reviewers):.0f}")
    add_line(f"  Min:     {min(reviewers)}")
    add_line(f"  Max:     {max(reviewers)}")

    # Code changes statistics
    lines_added = [m["lines_added"] for m in metrics_list]
    lines_removed = [m["lines_removed"] for m in metrics_list]
    total_lines = [m["total_lines_changed"] for m in metrics_list]
    files_changed = [m["files_changed"] for m in metrics_list]

    add_line("\nLines Added per PR:")
    add_line(f"  Average: {statistics.mean(lines_added):.2f}")
    add_line(f"  Median:  {statistics.median(lines_added):.0f}")
    add_line(f"  Total:   {sum(lines_added)}")

    add_line("\nLines Removed per PR:")
    add_line(f"  Average: {statistics.mean(lines_removed):.2f}")
    add_line(f"  Median:  {statistics.median(lines_removed):.0f}")
    add_line(f"  Total:   {sum(lines_removed)}")

    add_line("\nTotal Lines Changed per PR:")
    add_line(f"  Average: {statistics.mean(total_lines):.2f}")
    add_line(f"  Median:  {statistics.median(total_lines):.0f}")
    add_line(f"  Total:   {sum(total_lines)}")

    add_line("\nFiles Changed per PR:")
    add_line(f"  Average: {statistics.mean(files_changed):.2f}")
    add_line(f"  Median:  {statistics.median(files_changed):.0f}")
    add_line(f"  Min:     {min(files_changed)}")
    add_line(f"  Max:     {max(files_changed)}")
    add_line(f"  Total:   {sum(files_changed)}")

    add_line("\n" + "=" * 80)

    # Write markdown file
    with open(output_file, "w") as f:
        f.write("# Pull Request Analysis Report\n\n")
        f.write(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
        f.write("## Summary\n\n")
        f.write(f"**Total PRs analyzed:** {len(metrics_list)}\n\n")

        if review_times:
            # Check if we're analyzing open PRs by looking at the state
            is_open_analysis = any(m["state"] == "OPEN" for m in metrics_list)
            time_label = "Time Since Creation" if is_open_analysis else "Review Time"

            f.write(f"## {time_label}\n\n")
            f.write("| Metric | Days | Hours |\n")
            f.write("|--------|------|-------|\n")
            f.write(
                f"| Average | {statistics.mean(review_times):.2f} | {statistics.mean(review_times) * 24:.2f} |\n"
            )
            f.write(
                f"| Median | {statistics.median(review_times):.2f} | {statistics.median(review_times) * 24:.2f} |\n"
            )
            f.write(
                f"| Min | {min(review_times):.2f} | {min(review_times) * 24:.2f} |\n"
            )
            f.write(
                f"| Max | {max(review_times):.2f} | {max(review_times) * 24:.2f} |\n\n"
            )

        f.write("## Commits per PR\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Average | {statistics.mean(commits):.2f} |\n")
        f.write(f"| Median | {statistics.median(commits):.0f} |\n")
        f.write(f"| Min | {min(commits)} |\n")
        f.write(f"| Max | {max(commits)} |\n\n")

        f.write("## Comments per PR\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Average | {statistics.mean(comments):.2f} |\n")
        f.write(f"| Median | {statistics.median(comments):.0f} |\n")
        f.write(f"| Min | {min(comments)} |\n")
        f.write(f"| Max | {max(comments)} |\n\n")

        f.write("## Reviewers per PR\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Average | {statistics.mean(reviewers):.2f} |\n")
        f.write(f"| Median | {statistics.median(reviewers):.0f} |\n")
        f.write(f"| Min | {min(reviewers)} |\n")
        f.write(f"| Max | {max(reviewers)} |\n\n")

        f.write("## Code Changes\n\n")
        f.write("### Lines Added per PR\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Average | {statistics.mean(lines_added):.2f} |\n")
        f.write(f"| Median | {statistics.median(lines_added):.0f} |\n")
        f.write(f"| Total | {sum(lines_added):,} |\n\n")

        f.write("### Lines Removed per PR\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Average | {statistics.mean(lines_removed):.2f} |\n")
        f.write(f"| Median | {statistics.median(lines_removed):.0f} |\n")
        f.write(f"| Total | {sum(lines_removed):,} |\n\n")

        f.write("### Total Lines Changed per PR\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Average | {statistics.mean(total_lines):.2f} |\n")
        f.write(f"| Median | {statistics.median(total_lines):.0f} |\n")
        f.write(f"| Total | {sum(total_lines):,} |\n\n")

        f.write("### Files Changed per PR\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Average | {statistics.mean(files_changed):.2f} |\n")
        f.write(f"| Median | {statistics.median(files_changed):.0f} |\n")
        f.write(f"| Min | {min(files_changed)} |\n")
        f.write(f"| Max | {max(files_changed)} |\n")
        f.write(f"| Total | {sum(files_changed):,} |\n\n")

    print(f"\nMarkdown report saved to {output_file}")


def main():
    args = parse_args()

    # Initialize Bitbucket Cloud connection
    print("Connecting to Bitbucket Cloud...")
    cloud = Cloud(username=BITBUCKET_USERNAME, password=BITBUCKET_API_TOKEN, cloud=True)

    # Handle specific PR ID
    if args.pr_id:
        print(f"Fetching PR #{args.pr_id}...")
        url = f"repositories/{BITBUCKET_WORKSPACE}/{BITBUCKET_REPO}/pullrequests/{args.pr_id}"
        try:
            pr = cloud.get(url)
            filtered_prs = [pr]
            print(f"Found PR #{pr['id']}: {pr['title']}")
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            return
        except Exception as e:
            print(f"Error fetching PR #{args.pr_id}: {e}")
            return
    else:
        # Get pull requests based on state
        if args.openprs:
            print("Fetching open pull requests...")
            state = "OPEN"
        else:
            print("Fetching merged pull requests...")
            state = "MERGED"

        url = f"repositories/{BITBUCKET_WORKSPACE}/{BITBUCKET_REPO}/pullrequests"
        try:
            prs = cloud._get_paged(url, params={"state": state})
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user during PR fetching.")
            return
        except Exception as e:
            print(f"Error fetching pull requests: {e}")
            return

        # Filter PRs based on criteria
        filtered_prs = []
        cutoff_date = None

        if args.days:
            cutoff_date = datetime.now(
                tz=datetime.now().astimezone().tzinfo
            ) - timedelta(days=args.days)
            if args.openprs:
                print(
                    f"Filtering PRs created after {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                print(
                    f"Filtering PRs merged after {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}"
                )

        try:
            for pr in prs:
                if args.limit and len(filtered_prs) >= args.limit:
                    break

                if args.days:
                    if args.openprs:
                        # For open PRs, use created_on date
                        date_field = datetime.fromisoformat(
                            pr["created_on"].replace("Z", "+00:00")
                        )
                    else:
                        # For merged PRs, use updated_on date
                        date_field = datetime.fromisoformat(
                            pr["updated_on"].replace("Z", "+00:00")
                        )
                    if date_field < cutoff_date:
                        continue

                filtered_prs.append(pr)
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user during PR iteration.")
            print(f"Partial results: {len(filtered_prs)} PRs fetched so far.")
            # Continue with whatever PRs we managed to fetch

    print(f"Found {len(filtered_prs)} PR(s) to analyze")

    # Collect metrics for each PR
    all_metrics = []
    try:
        for i, pr in enumerate(filtered_prs, 1):
            print(
                f"Analyzing PR {i}/{len(filtered_prs)}: #{pr['id']} - {pr['title'][:50]}..."
            )
            try:
                metrics = get_pr_metrics(cloud, BITBUCKET_WORKSPACE, BITBUCKET_REPO, pr)
                all_metrics.append(metrics)
            except KeyboardInterrupt:
                print(
                    f"\n\nOperation cancelled by user while analyzing PR #{pr['id']}."
                )
                print(f"Partial results: {len(all_metrics)} PRs analyzed so far.")
                break
            except Exception as e:
                print(f"  Error analyzing PR #{pr['id']}: {e}")
                continue
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user during analysis.")
        print(f"Partial results: {len(all_metrics)} PRs analyzed so far.")

    # Print summary statistics
    print_summary_stats(all_metrics, args.report)

    # Write to CSV
    if all_metrics:
        print(f"\nWriting results to {args.output}...")
        try:
            with open(args.output, "w", newline="") as csvfile:
                fieldnames = [
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
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_metrics)

            print(f"Analysis complete! Results saved to {args.output}")
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user while writing results.")
            print(f"Partial results may have been saved to {args.output}")
    else:
        print("No metrics collected.")


if __name__ == "__main__":
    main()
