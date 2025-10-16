import argparse
import csv
import os
from collections import defaultdict
from datetime import datetime, timedelta
import statistics

from atlassian.bitbucket import Cloud

# Environment variables
BITBUCKET_USERNAME = os.getenv("BITBUCKET_USERNAME")
BITBUCKET_API_TOKEN = os.getenv("BITBUCKET_API_TOKEN")
BITBUCKET_WORKSPACE = os.getenv("BITBUCKET_WORKSPACE")
BITBUCKET_REPO = os.getenv("BITBUCKET_REPO")

# Validate environment variables
missing_vars = []
for var_name in ["BITBUCKET_USERNAME", "BITBUCKET_API_TOKEN", "BITBUCKET_WORKSPACE", "BITBUCKET_REPO"]:
    if not os.getenv(var_name):
        missing_vars.append(var_name)

if missing_vars:
    print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
    print("Please set these environment variables before running the script:")
    for var in missing_vars:
        print(f"  export {var}=your_value_here")
    exit(1)

def parse_args():
    parser = argparse.ArgumentParser(description='Analyze Bitbucket Pull Requests')
    parser.add_argument('--days', type=int, help='Analyze PRs from the last N days')
    parser.add_argument('--limit', type=int, default=50, help='Analyze the last N merged PRs (default: 50)')
    parser.add_argument('--pr-id', type=int, help='Analyze a specific PR by ID number')
    parser.add_argument('--output', type=str, default='pull_request_data.csv', help='Output CSV file name')
    parser.add_argument('--report', type=str, default='pull_request_analysis.md', help='Output markdown report file name')
    return parser.parse_args()

def get_pr_metrics(cloud, workspace, repo, pr):
    """Get detailed metrics for a single PR"""
    pr_id = pr['id']
    
    # Calculate review time
    created = datetime.fromisoformat(pr['created_on'].replace('Z', '+00:00'))
    if pr['state'] == 'MERGED' and pr.get('updated_on'):
        merged = datetime.fromisoformat(pr['updated_on'].replace('Z', '+00:00'))
        review_time_hours = (merged - created).total_seconds() / 3600
        review_time_days = review_time_hours / 24
    else:
        review_time_hours = None
        review_time_days = None
    
    # Get reviewers count
    participants_url = f"repositories/{workspace}/{repo}/pullrequests/{pr_id}"
    pr_detail = cloud.get(participants_url)
    
    reviewers = []
    if 'participants' in pr_detail:
        reviewers = [p for p in pr_detail['participants'] if p.get('role') == 'REVIEWER']
    reviewer_count = len(reviewers)
    
    # Get commits count
    commits_url = f"repositories/{workspace}/{repo}/pullrequests/{pr_id}/commits"
    commits = list(cloud._get_paged(commits_url))
    commits_count = len(commits)
    
    # Get comments count
    comments_url = f"repositories/{workspace}/{repo}/pullrequests/{pr_id}/comments"
    comments = list(cloud._get_paged(comments_url))
    comments_count = len(comments)
    
    # Get code changes (lines added/removed)
    diffstat_url = f"repositories/{workspace}/{repo}/pullrequests/{pr_id}/diffstat"
    try:
        diffstats = list(cloud._get_paged(diffstat_url))
        lines_added = sum(d.get('lines_added', 0) for d in diffstats)
        lines_removed = sum(d.get('lines_removed', 0) for d in diffstats)
    except:
        lines_added = 0
        lines_removed = 0
    
    return {
        'id': pr_id,
        'title': pr['title'],
        'author': pr['author']['display_name'],
        'state': pr['state'],
        'created_on': pr['created_on'],
        'updated_on': pr.get('updated_on', ''),
        'review_time_hours': review_time_hours,
        'review_time_days': review_time_days,
        'reviewer_count': reviewer_count,
        'commits_count': commits_count,
        'comments_count': comments_count,
        'lines_added': lines_added,
        'lines_removed': lines_removed,
        'total_lines_changed': lines_added + lines_removed,
        'source_branch': pr['source']['branch']['name'],
        'destination_branch': pr['destination']['branch']['name']
    }

def print_summary_stats(metrics_list, output_file='pull_request_analysis.md'):
    """Print summary statistics to console and markdown file"""
    if not metrics_list:
        print("No PRs to analyze")
        return
    
    # Prepare output lines
    output_lines = []
    
    def add_line(line=""):
        print(line)
        output_lines.append(line)
    
    add_line("\n" + "="*80)
    add_line("PULL REQUEST ANALYSIS SUMMARY")
    add_line("="*80)
    
    add_line(f"\nTotal PRs analyzed: {len(metrics_list)}")
    
    # Review time statistics
    review_times = [m['review_time_hours'] for m in metrics_list if m['review_time_hours'] is not None]
    if review_times:
        add_line(f"\nReview Time (hours):")
        add_line(f"  Average: {statistics.mean(review_times):.2f} hours ({statistics.mean(review_times)/24:.2f} days)")
        add_line(f"  Median:  {statistics.median(review_times):.2f} hours ({statistics.median(review_times)/24:.2f} days)")
        add_line(f"  Min:     {min(review_times):.2f} hours ({min(review_times)/24:.2f} days)")
        add_line(f"  Max:     {max(review_times):.2f} hours ({max(review_times)/24:.2f} days)")
    
    # Commits statistics
    commits = [m['commits_count'] for m in metrics_list]
    add_line(f"\nCommits per PR:")
    add_line(f"  Average: {statistics.mean(commits):.2f}")
    add_line(f"  Median:  {statistics.median(commits):.0f}")
    add_line(f"  Min:     {min(commits)}")
    add_line(f"  Max:     {max(commits)}")
    
    # Comments statistics
    comments = [m['comments_count'] for m in metrics_list]
    add_line(f"\nComments per PR:")
    add_line(f"  Average: {statistics.mean(comments):.2f}")
    add_line(f"  Median:  {statistics.median(comments):.0f}")
    add_line(f"  Min:     {min(comments)}")
    add_line(f"  Max:     {max(comments)}")
    
    # Reviewers statistics
    reviewers = [m['reviewer_count'] for m in metrics_list]
    add_line(f"\nReviewers per PR:")
    add_line(f"  Average: {statistics.mean(reviewers):.2f}")
    add_line(f"  Median:  {statistics.median(reviewers):.0f}")
    add_line(f"  Min:     {min(reviewers)}")
    add_line(f"  Max:     {max(reviewers)}")
    
    # Code changes statistics
    lines_added = [m['lines_added'] for m in metrics_list]
    lines_removed = [m['lines_removed'] for m in metrics_list]
    total_lines = [m['total_lines_changed'] for m in metrics_list]
    
    add_line(f"\nLines Added per PR:")
    add_line(f"  Average: {statistics.mean(lines_added):.2f}")
    add_line(f"  Median:  {statistics.median(lines_added):.0f}")
    add_line(f"  Total:   {sum(lines_added)}")
    
    add_line(f"\nLines Removed per PR:")
    add_line(f"  Average: {statistics.mean(lines_removed):.2f}")
    add_line(f"  Median:  {statistics.median(lines_removed):.0f}")
    add_line(f"  Total:   {sum(lines_removed)}")
    
    add_line(f"\nTotal Lines Changed per PR:")
    add_line(f"  Average: {statistics.mean(total_lines):.2f}")
    add_line(f"  Median:  {statistics.median(total_lines):.0f}")
    add_line(f"  Total:   {sum(total_lines)}")
    
    add_line("\n" + "="*80)
    
    # Write markdown file
    with open(output_file, 'w') as f:
        f.write(f"# Pull Request Analysis Report\n\n")
        f.write(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"**Total PRs analyzed:** {len(metrics_list)}\n\n")
        
        if review_times:
            f.write(f"## Review Time\n\n")
            f.write(f"| Metric | Hours | Days |\n")
            f.write(f"|--------|-------|------|\n")
            f.write(f"| Average | {statistics.mean(review_times):.2f} | {statistics.mean(review_times)/24:.2f} |\n")
            f.write(f"| Median | {statistics.median(review_times):.2f} | {statistics.median(review_times)/24:.2f} |\n")
            f.write(f"| Min | {min(review_times):.2f} | {min(review_times)/24:.2f} |\n")
            f.write(f"| Max | {max(review_times):.2f} | {max(review_times)/24:.2f} |\n\n")
        
        f.write(f"## Commits per PR\n\n")
        f.write(f"| Metric | Value |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| Average | {statistics.mean(commits):.2f} |\n")
        f.write(f"| Median | {statistics.median(commits):.0f} |\n")
        f.write(f"| Min | {min(commits)} |\n")
        f.write(f"| Max | {max(commits)} |\n\n")
        
        f.write(f"## Comments per PR\n\n")
        f.write(f"| Metric | Value |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| Average | {statistics.mean(comments):.2f} |\n")
        f.write(f"| Median | {statistics.median(comments):.0f} |\n")
        f.write(f"| Min | {min(comments)} |\n")
        f.write(f"| Max | {max(comments)} |\n\n")
        
        f.write(f"## Reviewers per PR\n\n")
        f.write(f"| Metric | Value |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| Average | {statistics.mean(reviewers):.2f} |\n")
        f.write(f"| Median | {statistics.median(reviewers):.0f} |\n")
        f.write(f"| Min | {min(reviewers)} |\n")
        f.write(f"| Max | {max(reviewers)} |\n\n")
        
        f.write(f"## Code Changes\n\n")
        f.write(f"### Lines Added per PR\n\n")
        f.write(f"| Metric | Value |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| Average | {statistics.mean(lines_added):.2f} |\n")
        f.write(f"| Median | {statistics.median(lines_added):.0f} |\n")
        f.write(f"| Total | {sum(lines_added):,} |\n\n")
        
        f.write(f"### Lines Removed per PR\n\n")
        f.write(f"| Metric | Value |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| Average | {statistics.mean(lines_removed):.2f} |\n")
        f.write(f"| Median | {statistics.median(lines_removed):.0f} |\n")
        f.write(f"| Total | {sum(lines_removed):,} |\n\n")
        
        f.write(f"### Total Lines Changed per PR\n\n")
        f.write(f"| Metric | Value |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| Average | {statistics.mean(total_lines):.2f} |\n")
        f.write(f"| Median | {statistics.median(total_lines):.0f} |\n")
        f.write(f"| Total | {sum(total_lines):,} |\n\n")
    
    print(f"\nMarkdown report saved to {output_file}")

def main():
    args = parse_args()
    
    # Initialize Bitbucket Cloud connection
    print(f"Connecting to Bitbucket Cloud...")
    cloud = Cloud(
        username=BITBUCKET_USERNAME,
        password=BITBUCKET_API_TOKEN,
        cloud=True
    )
    
    # Handle specific PR ID
    if args.pr_id:
        print(f"Fetching PR #{args.pr_id}...")
        url = f"repositories/{BITBUCKET_WORKSPACE}/{BITBUCKET_REPO}/pullrequests/{args.pr_id}"
        try:
            pr = cloud.get(url)
            filtered_prs = [pr]
            print(f"Found PR #{pr['id']}: {pr['title']}")
        except Exception as e:
            print(f"Error fetching PR #{args.pr_id}: {e}")
            return
    else:
        # Get merged pull requests
        print(f"Fetching merged pull requests...")
        url = f"repositories/{BITBUCKET_WORKSPACE}/{BITBUCKET_REPO}/pullrequests"
        prs = cloud._get_paged(url, params={'state': 'MERGED'})
        
        # Filter PRs based on criteria
        filtered_prs = []
        cutoff_date = None
        
        if args.days:
            cutoff_date = datetime.now(tz=datetime.now().astimezone().tzinfo) - timedelta(days=args.days)
            print(f"Filtering PRs merged after {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
        
        for pr in prs:
            if args.limit and len(filtered_prs) >= args.limit:
                break
            
            if args.days:
                updated = datetime.fromisoformat(pr['updated_on'].replace('Z', '+00:00'))
                if updated < cutoff_date:
                    continue
            
            filtered_prs.append(pr)
    
    print(f"Found {len(filtered_prs)} PR(s) to analyze")
    
    # Collect metrics for each PR
    all_metrics = []
    for i, pr in enumerate(filtered_prs, 1):
        print(f"Analyzing PR {i}/{len(filtered_prs)}: #{pr['id']} - {pr['title'][:50]}...")
        try:
            metrics = get_pr_metrics(cloud, BITBUCKET_WORKSPACE, BITBUCKET_REPO, pr)
            all_metrics.append(metrics)
        except Exception as e:
            print(f"  Error analyzing PR #{pr['id']}: {e}")
            continue
    
    # Print summary statistics
    print_summary_stats(all_metrics, args.report)
    
    # Write to CSV
    if all_metrics:
        print(f"\nWriting results to {args.output}...")
        with open(args.output, 'w', newline='') as csvfile:
            fieldnames = [
                'id', 'title', 'author', 'state', 'created_on', 'updated_on',
                'review_time_hours', 'review_time_days', 'reviewer_count',
                'commits_count', 'comments_count', 'lines_added', 'lines_removed',
                'total_lines_changed', 'source_branch', 'destination_branch'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_metrics)
        
        print(f"Analysis complete! Results saved to {args.output}")
    else:
        print("No metrics collected.")

if __name__ == "__main__":
    main()