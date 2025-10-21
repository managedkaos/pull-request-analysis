# Pull Request Analysis Tool

A Python tool for analyzing Bitbucket pull requests to gain insights into code review processes, development velocity, and team collaboration patterns.

The tool retrieves pull request data from Bitbucket Cloud, calculates various metrics, and generates detailed reports in both CSV and Markdown formats.

## Overview

This tool connects to Bitbucket Cloud via API to analyze pull requests in a repository. It provides insights into:

- Review time analysis (creation to merge)
- Code change metrics (lines added/removed, files changed)
- Collaboration patterns (reviewers, comments, commits)
- Development velocity trends

## Prerequisites

Before running the tool, you need:

1. **Docker**: Install Docker on your system
2. **Bitbucket API Access**: Obtain an API token from [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)
3. **Environment Variables**: Set the following environment variables:
   - `BITBUCKET_USERNAME`: Your Bitbucket username
   - `BITBUCKET_API_TOKEN`: Your Bitbucket API token/app password
   - `BITBUCKET_WORKSPACE`: Your Bitbucket workspace name
   - `BITBUCKET_REPO`: The repository name to analyze

## Installation

1. Clone or download this repository
2. Install required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Basic Usage

```bash
python main.py
```

This will analyze the last 50 merged pull requests and generate reports in the current directory.

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--days N` | Analyze PRs from the last N days | All available PRs |
| `--limit N` | Analyze the last N PRs | 50 |
| `--pr-id N` | Analyze a specific PR by ID number | All PRs |
| `--openprs` | Analyze only PRs in OPEN state (default: analyze MERGED PRs) | False |
| `--output FILENAME` | Specify CSV output filename | `pull_request_data.csv` |
| `--report FILENAME` | Specify Markdown report filename | `pull_request_analysis.md` |

### Examples

```bash
# Analyze PRs from the last 30 days
python main.py --days 30

# Analyze the last 100 PRs
python main.py --limit 100

# Analyze a specific PR
python main.py --pr-id 123

# Custom output files
python main.py --output my_analysis.csv --report my_report.md

# Combine options: last 20 PRs from the past 7 days
python main.py --days 7 --limit 20

# Analyze specific PR with custom report name
python main.py --pr-id 456 --report pr_456_analysis.md

# Analyze only open PRs
python main.py --openprs

# Analyze open PRs from the last 7 days
python main.py --openprs --days 7

# Analyze the last 20 open PRs
python main.py --openprs --limit 20

# Analyze open PRs with custom output files
python main.py --openprs --output open_prs.csv --report open_prs_report.md
```

## Output

### Console Output

The script provides detailed console output including:

1. **Connection Status**: Confirms successful Bitbucket connection
2. **PR Fetching Progress**: Shows progress while retrieving PR data
3. **Analysis Progress**: Shows progress while analyzing each PR
4. **Summary Statistics**: Comprehensive metrics including:
   - Total PRs analyzed
   - Review time statistics (average, median, min, max)
   - Commits per PR statistics
   - Comments per PR statistics
   - Reviewers per PR statistics
   - Code changes statistics (lines added/removed, files changed)

### CSV Report

The script generates a CSV file with detailed data for each PR:

| Column | Description |
|--------|-------------|
| `id` | Pull request ID |
| `title` | Pull request title |
| `author` | PR author display name |
| `state` | PR state (MERGED, OPEN, etc.) |
| `created_on` | Creation timestamp |
| `updated_on` | Last update timestamp |
| `review_time_days` | Time from creation to merge (fractional days) |
| `reviewer_count` | Number of reviewers |
| `commits_count` | Number of commits |
| `comments_count` | Number of comments |
| `lines_added` | Lines of code added |
| `lines_removed` | Lines of code removed |
| `total_lines_changed` | Total lines changed |
| `files_changed` | Number of files modified |
| `source_branch` | Source branch name |
| `destination_branch` | Destination branch name |

### Markdown Report

The script generates a comprehensive Markdown report with:

- **Summary**: Total PRs analyzed with breakdown by state
- **Review Time**: Statistical analysis of review times
- **Commits per PR**: Analysis of commit patterns
- **Comments per PR**: Analysis of discussion activity
- **Reviewers per PR**: Analysis of review participation
- **Code Changes**: Detailed analysis of code modifications and files changed

### Sample Output

```text
Connecting to Bitbucket Cloud...
Fetching merged pull requests...
Found 25 PR(s) to analyze
Analyzing PR 1/25: #123 - Fix authentication bug...
Analyzing PR 2/25: #124 - Add new feature...

================================================================================
PULL REQUEST ANALYSIS SUMMARY
================================================================================

Total PRs analyzed: 25

Review Time (days):
  Average: 0.77 days (18.5 hours)
  Median:  0.50 days (12.0 hours)
  Min:     0.08 days (2.0 hours)
  Max:     3.00 days (72.0 hours)

Commits per PR:
  Average: 3.2
  Median:  2
  Min:     1
  Max:     15

Comments per PR:
  Average: 4.8
  Median:  3
  Min:     0
  Max:     25

Reviewers per PR:
  Average: 2.1
  Median:  2
  Min:     1
  Max:     5

Lines Added per PR:
  Average: 45.2
  Median:  28
  Total:   1130

Lines Removed per PR:
  Average: 12.8
  Median:  8
  Total:   320

Total Lines Changed per PR:
  Average: 58.0
  Median:  36
  Total:   1450

Files Changed per PR:
  Average: 3.2
  Median:  2
  Min:     1
  Max:     12
  Total:   80

Writing results to pull_request_data.csv...
Analysis complete! Results saved to pull_request_data.csv

Markdown report saved to pull_request_analysis.md
```

## Troubleshooting

### Common Issues

1. **"Missing required environment variables"**
   - Ensure all four environment variables are set in your shell
   - Verify the API token is valid and has appropriate permissions
   - Check that workspace and repository names are correct

2. **"Failed to connect to Bitbucket"**
   - Check that your Bitbucket credentials are correct
   - Verify the workspace and repository names exist
   - Ensure your API token has read permissions for the repository

3. **"No PRs to analyze"**
   - Check if the repository has any pull requests
   - Verify the date range or limit parameters
   - Try using `--days` with a larger number

4. **"Error analyzing PR"**
   - Some PRs may have missing data or API access issues
   - The script will continue with other PRs and report errors
   - Check the console output for specific error details

5. **Empty or missing output files**
   - Ensure you have write permissions in the current directory
   - Check that the analysis completed successfully
   - Verify the custom filenames are valid

## Features

- **Flexible Filtering**: Filter by date range, limit results, or analyze specific PRs
- **PR State Analysis**: Analyze merged PRs (default) or open PRs using the `--openprs` flag
- **Comprehensive Metrics**: Detailed analysis of review times, code changes, file modifications, and collaboration
- **Multiple Output Formats**: Both CSV data and Markdown reports
- **Robust Error Handling**: Continues processing even when individual PRs fail
- **Interrupt-Safe**: Gracefully handles user interruptions while preserving partial results
- **Real-time Progress**: Shows progress during long-running analyses

## Use Cases

- **Team Performance Analysis**: Understand review velocity and collaboration patterns
- **Process Improvement**: Identify bottlenecks in the code review process
- **Code Quality Insights**: Analyze code change patterns, file modification scope, and review engagement
- **Historical Analysis**: Track trends over time with date-based filtering
- **Individual PR Analysis**: Deep dive into specific pull requests
- **Open PR Monitoring**: Track currently open PRs and their age to identify stale reviews
