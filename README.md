# Release Work Item Analysis

A Python tool for analyzing Jira work items across releases in a given project.

The tool retrieves work items associated with each release in the project, calculates lead times, and generates summary reports.

## Overview

This tool connects to Jira via API to analyze work items (issues) across different releases/versions in a Jira project. It provides insights into:

- Work items per release
- Lead time analysis (creation to resolution)

## Prerequisites

Before running the tool, you need:

1. **Docker**: Install Docker on your system
2. **Jira API Access**: Obtain an API token from [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)
3. **Environment Variables**: Set the following environment variables:
   - `JIRA_URL`: Your Jira instance URL (e.g., `https://yourcompany.atlassian.net`)
   - `JIRA_EMAIL`: Your Jira account email
   - `JIRA_API_TOKEN`: Your Jira API token
   - `JIRA_PROJECT_ID`: The ID of the project being analyzed

## Usage

### Basic Usage

```bash
docker run --rm \
  --env JIRA_API_TOKEN \
  --env JIRA_EMAIL \
  --env JIRA_URL \
  --env JIRA_PROJECT_ID \
  --mount $(PWD):/data \
  ghcr.io/managedkaos/release-work-item-analysis:main
```

This will analyze only released versions and generate a summary report in the current directory.

**Note**: The `--mount $(PWD):/data` flag mounts your current directory to `/data` inside the container, allowing the CSV report to be saved to your local filesystem.

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--include-unreleased` | Include unreleased versions in analysis | Only released versions |
| `--verbose` | Show detailed work item information | Summary only |
| `--csv FILENAME` | Specify CSV output filename | `release_analysis.csv` |

### Examples

```bash
# Analyze only released versions (default)
docker run --rm \
  --env JIRA_API_TOKEN \
  --env JIRA_EMAIL \
  --env JIRA_URL \
  --env JIRA_PROJECT_ID \
  --mount $(PWD):/data \
  ghcr.io/managedkaos/release-work-item-analysis:main

# Include unreleased versions
docker run --rm \
  --env JIRA_API_TOKEN \
  --env JIRA_EMAIL \
  --env JIRA_URL \
  --env JIRA_PROJECT_ID \
  --mount $(PWD):/data \
  ghcr.io/managedkaos/release-work-item-analysis:main \
  --include-unreleased

# Show detailed work item information
docker run --rm \
  --env JIRA_API_TOKEN \
  --env JIRA_EMAIL \
  --env JIRA_URL \
  --env JIRA_PROJECT_ID \
  --mount $(PWD):/data \
  ghcr.io/managedkaos/release-work-item-analysis:main \
  --verbose

# Specify custom CSV report filename
docker run --rm \
  --env JIRA_API_TOKEN \
  --env JIRA_EMAIL \
  --env JIRA_URL \
  --env JIRA_PROJECT_ID \
  --mount $(PWD):/data \
  ghcr.io/managedkaos/release-work-item-analysis:main \
  --csv my_analysis.csv

# Combine multiple options
docker run --rm \
  --env JIRA_API_TOKEN \
  --env JIRA_EMAIL \
  --env JIRA_URL \
  --env JIRA_PROJECT_ID \
  --mount $(PWD):/data \
  ghcr.io/managedkaos/release-work-item-analysis:main \
  --include-unreleased --verbose --csv detailed_report.csv
```

## Output

### Console Output

The script provides detailed console output including:

1. **Connection Status**: Confirms successful Jira connection
2. **Available Releases**: Lists all releases (filtered by options)
3. **Work Items per Release**: Shows count and details for each release
4. **Lead Time Analysis**: For each release with resolved items:
   - Average lead time (creation to resolution)
   - Minimum and maximum lead times
   - Number of resolved work items
5. **Overall Summary**: Total work items and overall average lead time

### CSV Report

The script generates a CSV file with the following columns:

| Column | Description |
|--------|-------------|
| `release_name` | Name of the release/version |
| `release_id` | Jira internal ID of the release |
| `status` | Released or Unreleased |
| `version_date` | Release date if available, otherwise start date (YYYY-MM-DD format) |
| `work_items_found` | Total work items in this release |
| `work_items_resolved` | Number of resolved work items |
| `average_lead_time_days` | Average lead time in days |
| `min_lead_time_days` | Minimum lead time in days |
| `max_lead_time_days` | Maximum lead time in days |

### Sample Output

```text
Connected to Jira successfully

=== All Available Releases (Versions) in SHFT Project ===
- Showing only released versions (use --include-unreleased to see all)
- ID: 12345, Name: 'v1.2.0', Status: Released
- ID: 12346, Name: 'v1.1.0', Status: Released

=== Work Items for Each Release ===

--- v1.2.0 (ID: 12345)
Work items found   : 15
Work items resolved: 12

Lead Time Summary for v1.2.0:
  Average: 8.5 days
  Minimum: 2 days
  Maximum: 18 days

=== Writing Summary Report to release_analysis.csv ===
Summary report written successfully to release_analysis.csv
Total releases analyzed: 2
Overall summary:
  Total work items found: 25
  Total work items resolved: 20
  Overall average lead time: 7.2 days
```

## Error Handling

The script includes comprehensive error handling:

- **Missing Environment Variables**: The script will exit with clear instructions if required environment variables are not set
- **Jira Connection Issues**: Detailed error messages for connection failures
- **Date Parsing Errors**: Warnings for work items with invalid date formats (shown in verbose mode)
- **CSV Writing Errors**: Graceful handling of file writing issues

## Troubleshooting

### Common Issues

1. **"Missing required environment variables"**
   - Ensure all four environment variables (`JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_ID`) are set in your shell
   - Verify the API token is valid and has appropriate permissions
   - Check that `JIRA_PROJECT_ID` matches the project key in your Jira instance (e.g., "SHFT", "PROJ", etc.)

2. **"Failed to connect to Jira"**
   - Check that `JIRA_URL` is correct and accessible
   - Verify `JIRA_EMAIL` and `JIRA_API_TOKEN` are correct
   - Ensure your Jira instance allows API access

3. **"No versions found matching the criteria"**
   - Check if the project exists and has versions
   - Try using `--include-unreleased` to see all versions

4. **Empty CSV report**
   - Verify the project has work items associated with releases
   - Check if work items have the correct fix version set

5. **CSV file not found after running**
   - Ensure the volume mount `-v $(PWD):/data` is included in your Docker command
   - Check that you have write permissions in the current directory
   - The CSV file will be created in the current directory where you run the Docker command
