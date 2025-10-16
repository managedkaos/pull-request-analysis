import argparse
import csv
import os
from datetime import datetime

from atlassian import Jira

# Obtain an API token from: https://id.atlassian.com/manage-profile/security/api-tokens
# You cannot log-in with your regular password to these services.

JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_URL = os.getenv("JIRA_URL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_ID = os.getenv("JIRA_PROJECT_ID")

# Validate that all required environment variables are set
missing_vars = []
if not JIRA_URL:
    missing_vars.append("JIRA_URL")
if not JIRA_API_TOKEN:
    missing_vars.append("JIRA_API_TOKEN")
if not JIRA_EMAIL:
    missing_vars.append("JIRA_EMAIL")
if not JIRA_PROJECT_ID:
    missing_vars.append("JIRA_PROJECT_ID")

if missing_vars:
    print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
    print("Please set these environment variables before running the script:")
    for var in missing_vars:
        print(f"  export {var}=your_value_here")
    exit(1)

# Initialize Jira connection
try:
    jira = Jira(url=JIRA_URL, username=JIRA_EMAIL, password=JIRA_API_TOKEN, cloud=True)
    print("Connected to Jira successfully")
except Exception as e:
    print(f"Failed to connect to Jira: {e}")
    print(
        "Please check your environment variables: JIRA_URL, JIRA_API_TOKEN, JIRA_EMAIL, JIRA_PROJECT_ID"
    )
    exit(1)

# Parse command line arguments
parser = argparse.ArgumentParser(description="Retrieve Jira work items for releases")
parser.add_argument(
    "--include-unreleased",
    action="store_true",
    help="Include unreleased versions in the results (default: only released versions)",
)
parser.add_argument(
    "--verbose",
    action="store_true",
    help="Show detailed work item information (default: only show summaries)",
)
parser.add_argument(
    "--csv",
    default="release_analysis.csv",
    help="CSV file to write the summary report (default: release_analysis.csv)",
)
args = parser.parse_args()

# Get all releases (versions) for the JIRA_PROJECT_ID project
print(f"\n=== All Available Releases (Versions) in {JIRA_PROJECT_ID} Project ===")

try:
    versions = jira.get_project_versions(JIRA_PROJECT_ID)

    # Filter versions based on command line argument
    if args.include_unreleased:
        print("- Including both released and unreleased versions")
        filtered_versions = versions
    else:
        print("- Showing only released versions (use --include-unreleased to see all)")
        filtered_versions = [v for v in versions if v.get("released", False)]

    for version in filtered_versions:
        status = version.get("released", False)
        status_text = "Released" if status else "Unreleased"
        print(
            f"- ID: {version['id']}, Name: '{version['name']}', Status: {status_text}"
        )

    if not filtered_versions:
        print("No versions found matching the criteria")

except Exception as e:
    print(f"Error getting versions: {e}")

# Loop through each release and find attached work items
print("\n=== Work Items for Each Release ===")

# Initialize data collection for CSV report
summary_data = []

# Apply the same filtering logic for work items
if args.include_unreleased:
    filtered_versions = versions
else:
    filtered_versions = [v for v in versions if v.get("released", False)]

for version in filtered_versions:
    version_id = version["id"]
    version_name = version["name"]
    is_released = version.get("released", False)
    status = "Released" if is_released else "Unreleased"

    # Extract version date - use release date if present, otherwise start date
    release_date_str = version.get("releaseDate")
    start_date_str = version.get("startDate")
    version_date = None
    date_str = release_date_str or start_date_str

    if date_str:
        try:
            version_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception as e:
            if args.verbose:
                print(
                    f"\tWarning: Could not parse version date for {version_name}: {e}"
                )

    print(f"\n--- {version_name} (ID: {version_id})", end=" ")

    if is_released:
        print()
    else:
        print(status)

    # Show version date information in verbose mode
    if args.verbose and version_date:
        print(f"Version Date: {version_date.strftime('%Y-%m-%d')}")
    elif args.verbose:
        print("Version Date: Not available")

    # JQL query to get all issues with this fix version
    jql_request = f"project = {JIRA_PROJECT_ID} AND fixVersion = {version_id} ORDER BY created DESC"
    issues = jira.jql(
        jql_request,
        fields=[
            "key",
            "summary",
            "issuetype",
            "status",
            "assignee",
            "created",
            "resolutiondate",
        ],
    )

    if issues["issues"]:
        # Track lead times for analysis
        lead_times = []

        for issue in issues["issues"]:
            assignee = issue["fields"].get("assignee")
            assignee_name = assignee["displayName"] if assignee else "Unassigned"
            issue_type = issue["fields"]["issuetype"]["name"]
            status_name = issue["fields"]["status"]["name"]

            # Get created and resolved dates
            created_date_str = issue["fields"].get("created")
            resolved_date_str = issue["fields"].get("resolutiondate")

            # Parse dates and calculate lead time
            lead_time_days = None
            if created_date_str and resolved_date_str:
                try:
                    created_date = datetime.fromisoformat(
                        created_date_str.replace("Z", "+00:00")
                    )
                    resolved_date = datetime.fromisoformat(
                        resolved_date_str.replace("Z", "+00:00")
                    )
                    lead_time_days = (resolved_date - created_date).days
                    lead_times.append(lead_time_days)
                except Exception as e:
                    if args.verbose:
                        print(
                            f"\tWarning: Could not parse dates for {issue['key']}: {e}"
                        )
            elif created_date_str and not resolved_date_str:
                # Work item is not yet resolved
                try:
                    created_date = datetime.fromisoformat(
                        created_date_str.replace("Z", "+00:00")
                    )
                    days_since_created = (
                        datetime.now(created_date.tzinfo) - created_date
                    ).days
                    lead_time_days = (
                        f"Open for {days_since_created} days (not resolved)"
                    )
                except Exception as e:
                    if args.verbose:
                        print(
                            f"\tWarning: Could not parse created date for {issue['key']}: {e}"
                        )

            # Only show individual work item details if verbose mode is enabled
            if args.verbose:
                print(f"\n- {issue['key']}: {issue['fields']['summary']}")
                print(
                    f"\tType: {issue_type}, Status: {status_name}, Assignee: {assignee_name}"
                )

                # Display lead time information
                if lead_time_days is not None:
                    if isinstance(lead_time_days, int):
                        print(f"\tLead Time: {lead_time_days} days")
                    else:
                        print(f"\tLead Time: {lead_time_days}")
                else:
                    print("\tLead Time: Unable to calculate (missing date information)")

        print(f"\nWork items found   : {len(issues['issues'])}")

        # Always display summary statistics for this release
        if lead_times:
            print(f"Work items resolved: {len(lead_times)}")
            avg_lead_time = sum(lead_times) / len(lead_times)
            min_lead_time = min(lead_times)
            max_lead_time = max(lead_times)
            print(f"\nLead Time Summary for {version_name}:")
            print(f"\tAverage: {avg_lead_time:.1f} days")
            print(f"\tMinimum: {min_lead_time} days")
            print(f"\tMaximum: {max_lead_time} days")

            # Store summary data for CSV report
            summary_data.append(
                {
                    "release_name": version_name,
                    "release_id": version_id,
                    "status": status,
                    "version_date": (
                        version_date.strftime("%Y-%m-%d") if version_date else "N/A"
                    ),
                    "work_items_found": len(issues["issues"]),
                    "work_items_resolved": len(lead_times),
                    "average_lead_time_days": round(avg_lead_time, 1),
                    "min_lead_time_days": min_lead_time,
                    "max_lead_time_days": max_lead_time,
                }
            )
        else:
            print(f"\tNo resolved work items found for {version_name}")

            # Store summary data for releases with no resolved items
            summary_data.append(
                {
                    "release_name": version_name,
                    "release_id": version_id,
                    "status": status,
                    "version_date": (
                        version_date.strftime("%Y-%m-%d") if version_date else "N/A"
                    ),
                    "work_items_found": len(issues["issues"]),
                    "work_items_resolved": 0,
                    "average_lead_time_days": "N/A",
                    "min_lead_time_days": "N/A",
                    "max_lead_time_days": "N/A",
                }
            )
    else:
        print("\tNo work items found for this release")

        # Store summary data for releases with no work items
        summary_data.append(
            {
                "release_name": version_name,
                "release_id": version_id,
                "status": status,
                "version_date": (
                    version_date.strftime("%Y-%m-%d") if version_date else "N/A"
                ),
                "work_items_found": 0,
                "work_items_resolved": 0,
                "average_lead_time_days": "N/A",
                "min_lead_time_days": "N/A",
                "max_lead_time_days": "N/A",
            }
        )

# Write CSV report
if summary_data:
    print(f"\n=== Writing Summary Report to {args.csv} ===")
    try:
        with open(args.csv, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "release_name",
                "release_id",
                "status",
                "version_date",
                "work_items_found",
                "work_items_resolved",
                "average_lead_time_days",
                "min_lead_time_days",
                "max_lead_time_days",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # Write header
            writer.writeheader()

            # Write data rows
            for row in summary_data:
                writer.writerow(row)

        print(f"Summary report written successfully to {args.csv}")
        print(f"Total releases analyzed: {len(summary_data)}")

        # Display summary of the report
        total_work_items = sum(row["work_items_found"] for row in summary_data)
        total_resolved = sum(row["work_items_resolved"] for row in summary_data)
        resolved_releases = [
            row for row in summary_data if row["work_items_resolved"] > 0
        ]

        if resolved_releases:
            overall_avg = sum(
                row["average_lead_time_days"]
                for row in resolved_releases
                if isinstance(row["average_lead_time_days"], (int, float))
            ) / len(resolved_releases)
            print("Overall summary:")
            print(f"\tTotal work items found: {total_work_items}")
            print(f"\tTotal work items resolved: {total_resolved}")
            print(f"\tOverall average lead time: {overall_avg:.1f} days")

    except Exception as e:
        print(f"Error writing CSV report: {e}")
else:
    print("No data available to write to CSV report")
