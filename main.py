import argparse
import csv
import os
from collections import defaultdict
from datetime import datetime

from atlassian import Bitbucket

# Obtain an API token from: https://id.atlassian.com/manage-profile/security/api-tokens

BITBUCKET_URL = os.getenv("BITBUCKET_URL", "https://bitbucket.org")
BITBUCKET_USERNAME = os.getenv("BITBUCKET_USERNAME")  # Your Bitbucket username/email
BITBUCKET_API_TOKEN = os.getenv("BITBUCKET_API_TOKEN")  # App password or API token
BITBUCKET_WORKSPACE = os.getenv("BITBUCKET_WORKSPACE")  # Workspace slug (Cloud) or project key (Server)
BITBUCKET_REPO = os.getenv("BITBUCKET_REPO")  # Repository slug

# Validate that all required environment variables are set
missing_vars = []
if not BITBUCKET_USERNAME:
    missing_vars.append("BITBUCKET_USERNAME")
if not BITBUCKET_API_TOKEN:
    missing_vars.append("BITBUCKET_API_TOKEN")
if not BITBUCKET_WORKSPACE:
    missing_vars.append("BITBUCKET_WORKSPACE")
if not BITBUCKET_REPO:
    missing_vars.append("BITBUCKET_REPO")

if missing_vars:
    print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
    print("Please set these environment variables before running the script:")
    for var in missing_vars:
        print(f"  export {var}=your_value_here")
    exit(1)

# Initialize Bitbucket connection
try:
    bitbucket = Bitbucket(
        url=BITBUCKET_URL,
        username=BITBUCKET_USERNAME,
        password=BITBUCKET_API_TOKEN,
        cloud=True  # Set to False if using Bitbucket Server/Data Center
    )
    print("Connected to Bitbucket successfully")
except Exception as e:
    print(f"Failed to connect to Bitbucket: {e}")
    print("Please check your environment variables")
    exit(1)


def get_pr_size(workspace, repo_slug, pr_id):
    """
    Calculate the size of a pull request based on lines added and removed.

    Returns a dict with additions, deletions, and total changes.
    """
    try:
        # Get the PR details first to access the diffstat URL
        pr_details = bitbucket.get_pull_request(workspace, repo_slug, pr_id)
        diffstat_url = pr_details.get('links', {}).get('diffstat', {}).get('href')

        if not diffstat_url:
            print(f"No diffstat URL found for PR #{pr_id}")
            return None

        # Make a direct API call to get diffstat
        import requests
        response = requests.get(diffstat_url, auth=(BITBUCKET_USERNAME, BITBUCKET_API_TOKEN))

        if response.status_code != 200:
            print(f"Failed to get diffstat for PR #{pr_id}: {response.status_code}")
            return None

        diff_stat = response.json()

        total_additions = 0
        total_deletions = 0
        files_changed = 0

        for file_stat in diff_stat.get('values', []):
            total_additions += file_stat.get('lines_added', 0)
            total_deletions += file_stat.get('lines_removed', 0)
            files_changed += 1

        return {
            'additions': total_additions,
            'deletions': total_deletions,
            'total_changes': total_additions + total_deletions,
            'files_changed': files_changed
        }
    except Exception as e:
        print(f"Error getting size for PR #{pr_id}: {e}")
        return None


def get_pr_commits(workspace, repo_slug, pr_id):
    """Get the number of commits in a pull request."""
    try:
        commits = bitbucket.get_pull_requests_commits(workspace, repo_slug, pr_id)
        return len(commits.get('values', []))
    except Exception as e:
        print(f"Error getting commits for PR #{pr_id}: {e}")
        return 0


def get_pr_comments(workspace, repo_slug, pr_id):
    """Get the number of comments on a pull request."""
    try:
        # Get the PR details first to access the comments URL
        pr_details = bitbucket.get_pull_request(workspace, repo_slug, pr_id)
        comments_url = pr_details.get('links', {}).get('comments', {}).get('href')

        if not comments_url:
            return 0

        # Make a direct API call to get comments
        import requests
        response = requests.get(comments_url, auth=(BITBUCKET_USERNAME, BITBUCKET_API_TOKEN))

        if response.status_code != 200:
            return 0

        comments = response.json()
        return len(comments.get('values', []))
    except Exception as e:
        print(f"Error getting comments for PR #{pr_id}: {e}")
        return 0


def get_pr_reviewers(workspace, repo_slug, pr_id):
    """Get the number of reviewers for a pull request."""
    try:
        pr_details = bitbucket.get_pull_request(workspace, repo_slug, pr_id)
        participants = pr_details.get('participants', [])

        # Count participants who were reviewers (not just the author)
        reviewers = [p for p in participants if p.get('role') == 'REVIEWER']
        return len(reviewers)
    except Exception as e:
        print(f"Error getting reviewers for PR #{pr_id}: {e}")
        return 0


def calculate_review_time(pr):
    """
    Calculate review time in hours from creation to merge/close.

    Returns None if PR is still open or doesn't have required dates.
    """
    try:
        created = datetime.fromisoformat(pr['created_on'].replace('Z', '+00:00'))

        # Check for updated_on (when PR was merged/closed)
        if 'updated_on' in pr:
            updated = datetime.fromisoformat(pr['updated_on'].replace('Z', '+00:00'))
            review_time_hours = (updated - created).total_seconds() / 3600
            return round(review_time_hours, 2)

        return None
    except Exception as e:
        print(f"Error calculating review time: {e}")
        return None


def analyze_pull_requests(workspace, repo_slug, state='MERGED', limit=100):
    """
    Analyze pull requests in a repository.

    Args:
        workspace: Bitbucket workspace slug
        repo_slug: Repository slug
        state: PR state filter (MERGED, OPEN, DECLINED, SUPERSEDED)
        limit: Maximum number of PRs to analyze
    """
    pr_data = []

    try:
        # Get pull requests (returns a generator)
        prs = bitbucket.get_pull_requests(workspace, repo_slug, state=state)

        count = 0
        for pr in prs:
            if count >= limit:
                break

            pr_id = pr['id']
            title = pr['title']
            author = pr['author']['display_name']
            created_date = pr['created_on']

            print(f"Analyzing PR #{pr_id}: {title}")

            # Get PR size
            size_info = get_pr_size(workspace, repo_slug, pr_id)

            # Get additional metrics
            num_commits = get_pr_commits(workspace, repo_slug, pr_id)
            num_comments = get_pr_comments(workspace, repo_slug, pr_id)
            num_reviewers = get_pr_reviewers(workspace, repo_slug, pr_id)
            review_time = calculate_review_time(pr)

            if size_info:
                pr_data.append({
                    'id': pr_id,
                    'title': title,
                    'author': author,
                    'created_date': created_date,
                    'additions': size_info['additions'],
                    'deletions': size_info['deletions'],
                    'total_changes': size_info['total_changes'],
                    'files_changed': size_info['files_changed'],
                    'num_commits': num_commits,
                    'num_comments': num_comments,
                    'num_reviewers': num_reviewers,
                    'review_time_hours': review_time
                })

            count += 1

        return pr_data

    except Exception as e:
        print(f"Error analyzing pull requests: {e}")
        return []


def categorize_pr_size(total_changes):
    """Categorize PR size based on total line changes."""
    if total_changes < 10:
        return 'XS'
    elif total_changes < 50:
        return 'S'
    elif total_changes < 200:
        return 'M'
    elif total_changes < 500:
        return 'L'
    else:
        return 'XL'


def export_to_csv(pr_data, filename='pr_analysis.csv'):
    """Export PR data to CSV file."""
    if not pr_data:
        print("No data to export")
        return

    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['id', 'title', 'author', 'created_date', 'additions',
                      'deletions', 'total_changes', 'files_changed', 'size_category',
                      'num_commits', 'num_comments', 'num_reviewers', 'review_time_hours']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for pr in pr_data:
            pr['size_category'] = categorize_pr_size(pr['total_changes'])
            writer.writerow(pr)

    print(f"\nData exported to {filename}")


def print_summary(pr_data, markdown_file='pr_size_analysis.md'):
    """Print summary statistics of PR sizes and write to markdown file."""
    if not pr_data:
        print("No data to summarize")
        return

    size_categories = defaultdict(int)
    total_changes_list = []
    review_times = []
    commits_list = []
    comments_list = []
    reviewers_list = []

    for pr in pr_data:
        total_changes = pr['total_changes']
        total_changes_list.append(total_changes)
        size_categories[categorize_pr_size(total_changes)] += 1

        if pr.get('review_time_hours') is not None:
            review_times.append(pr['review_time_hours'])
        if pr.get('num_commits'):
            commits_list.append(pr['num_commits'])
        if pr.get('num_comments') is not None:
            comments_list.append(pr['num_comments'])
        if pr.get('num_reviewers') is not None:
            reviewers_list.append(pr['num_reviewers'])

    # Build summary content
    summary_lines = []
    summary_lines.append(f"# Pull Request Size Analysis")
    summary_lines.append(f"\n**Repository:** {BITBUCKET_WORKSPACE}/{BITBUCKET_REPO}")
    summary_lines.append(f"**Analysis Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    summary_lines.append(f"**Total PRs Analyzed:** {len(pr_data)}\n")

    summary_lines.append("## PR Size Distribution\n")
    summary_lines.append("| Size | Count | Percentage |")
    summary_lines.append("|------|-------|------------|")
    for size in ['XS', 'S', 'M', 'L', 'XL']:
        count = size_categories[size]
        percentage = (count / len(pr_data)) * 100 if pr_data else 0
        summary_lines.append(f"| {size} | {count} | {percentage:.1f}% |")

    if total_changes_list:
        avg_changes = sum(total_changes_list) / len(total_changes_list)
        summary_lines.append("\n## Code Changes\n")
        summary_lines.append("| Metric | Value |")
        summary_lines.append("|--------|-------|")
        summary_lines.append(f"| Average changes per PR | {avg_changes:.1f} lines |")
        summary_lines.append(f"| Median changes per PR | {sorted(total_changes_list)[len(total_changes_list)//2]} lines |")
        summary_lines.append(f"| Largest PR | {max(total_changes_list)} lines |")
        summary_lines.append(f"| Smallest PR | {min(total_changes_list)} lines |")

    if review_times:
        avg_review_time = sum(review_times) / len(review_times)
        median_review_time = sorted(review_times)[len(review_times)//2]
        summary_lines.append("\n## Review Time\n")
        summary_lines.append("| Metric | Hours | Days |")
        summary_lines.append("|--------|-------|------|")
        summary_lines.append(f"| Average | {avg_review_time:.1f} | {avg_review_time/24:.1f} |")
        summary_lines.append(f"| Median | {median_review_time:.1f} | {median_review_time/24:.1f} |")
        summary_lines.append(f"| Longest | {max(review_times):.1f} | {max(review_times)/24:.1f} |")
        summary_lines.append(f"| Shortest | {min(review_times):.1f} | {min(review_times)/24:.1f} |")

    if commits_list:
        avg_commits = sum(commits_list) / len(commits_list)
        summary_lines.append("\n## Commits\n")
        summary_lines.append("| Metric | Value |")
        summary_lines.append("|--------|-------|")
        summary_lines.append(f"| Average commits per PR | {avg_commits:.1f} |")
        summary_lines.append(f"| Median commits per PR | {sorted(commits_list)[len(commits_list)//2]} |")
        summary_lines.append(f"| Most commits in a PR | {max(commits_list)} |")

    if comments_list:
        avg_comments = sum(comments_list) / len(comments_list)
        summary_lines.append("\n## Comments\n")
        summary_lines.append("| Metric | Value |")
        summary_lines.append("|--------|-------|")
        summary_lines.append(f"| Average comments per PR | {avg_comments:.1f} |")
        summary_lines.append(f"| Median comments per PR | {sorted(comments_list)[len(comments_list)//2]} |")
        summary_lines.append(f"| Most comments on a PR | {max(comments_list)} |")

    if reviewers_list:
        avg_reviewers = sum(reviewers_list) / len(reviewers_list)
        summary_lines.append("\n## Reviewers\n")
        summary_lines.append("| Metric | Value |")
        summary_lines.append("|--------|-------|")
        summary_lines.append(f"| Average reviewers per PR | {avg_reviewers:.1f} |")
        summary_lines.append(f"| Median reviewers per PR | {sorted(reviewers_list)[len(reviewers_list)//2]} |")
        summary_lines.append(f"| Most reviewers on a PR | {max(reviewers_list)} |")

    # Write to markdown file
    markdown_content = '\n'.join(summary_lines)
    with open(markdown_file, 'w') as f:
        f.write(markdown_content)

    # Print to console (simplified version)
    print("\n" + "="*50)
    print(f"Analysis Summary ({len(pr_data)} PRs)")
    print("="*50)

    print("\nPR Size Distribution:")
    for size in ['XS', 'S', 'M', 'L', 'XL']:
        count = size_categories[size]
        percentage = (count / len(pr_data)) * 100 if pr_data else 0
        print(f"  {size}: {count} ({percentage:.1f}%)")

    if total_changes_list:
        avg_changes = sum(total_changes_list) / len(total_changes_list)
        print(f"\nCode Changes:")
        print(f"  Average changes per PR: {avg_changes:.1f} lines")
        print(f"  Median changes per PR: {sorted(total_changes_list)[len(total_changes_list)//2]} lines")
        print(f"  Largest PR: {max(total_changes_list)} lines")
        print(f"  Smallest PR: {min(total_changes_list)} lines")

    if review_times:
        avg_review_time = sum(review_times) / len(review_times)
        median_review_time = sorted(review_times)[len(review_times)//2]
        print(f"\nReview Time:")
        print(f"  Average: {avg_review_time:.1f} hours ({avg_review_time/24:.1f} days)")
        print(f"  Median: {median_review_time:.1f} hours ({median_review_time/24:.1f} days)")
        print(f"  Longest: {max(review_times):.1f} hours ({max(review_times)/24:.1f} days)")
        print(f"  Shortest: {min(review_times):.1f} hours")

    if commits_list:
        avg_commits = sum(commits_list) / len(commits_list)
        print(f"\nCommits:")
        print(f"  Average commits per PR: {avg_commits:.1f}")
        print(f"  Median commits per PR: {sorted(commits_list)[len(commits_list)//2]}")
        print(f"  Most commits in a PR: {max(commits_list)}")

    if comments_list:
        avg_comments = sum(comments_list) / len(comments_list)
        print(f"\nComments:")
        print(f"  Average comments per PR: {avg_comments:.1f}")
        print(f"  Median comments per PR: {sorted(comments_list)[len(comments_list)//2]}")
        print(f"  Most comments on a PR: {max(comments_list)}")

    if reviewers_list:
        avg_reviewers = sum(reviewers_list) / len(reviewers_list)
        print(f"\nReviewers:")
        print(f"  Average reviewers per PR: {avg_reviewers:.1f}")
        print(f"  Median reviewers per PR: {sorted(reviewers_list)[len(reviewers_list)//2]}")
        print(f"  Most reviewers on a PR: {max(reviewers_list)}")

    print(f"\nSummary written to {markdown_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze Bitbucket pull request sizes')
    parser.add_argument('--state', default='MERGED',
                        choices=['MERGED', 'OPEN', 'DECLINED', 'SUPERSEDED'],
                        help='PR state to analyze (default: MERGED)')
    parser.add_argument('--limit', type=int, default=100,
                        help='Maximum number of PRs to analyze (default: 100)')
    parser.add_argument('--output', default='pr_analysis.csv',
                        help='Output CSV filename (default: pr_analysis.csv)')

    args = parser.parse_args()

    # Analyze PRs
    print(f"\nAnalyzing {args.state} pull requests in {BITBUCKET_WORKSPACE}/{BITBUCKET_REPO}...")
    pr_data = analyze_pull_requests(
        BITBUCKET_WORKSPACE,
        BITBUCKET_REPO,
        state=args.state,
        limit=args.limit
    )

    # Print summary
    print_summary(pr_data)

    # Export to CSV
    export_to_csv(pr_data, args.output)
