import argparse
import csv
import os
from collections import defaultdict
from datetime import datetime

from atlassian import Bitbucket

# Obtain an API token from: https://id.atlassian.com/manage-profile/security/api-tokens
# For Bitbucket Cloud, or use your Bitbucket Server credentials

BITBUCKET_URL = os.getenv("BITBUCKET_URL")  # e.g., "https://bitbucket.org" for Cloud
BITBUCKET_USERNAME = os.getenv("BITBUCKET_USERNAME")  # Your Bitbucket username/email
BITBUCKET_API_TOKEN = os.getenv("BITBUCKET_API_TOKEN")  # App password or API token
BITBUCKET_WORKSPACE = os.getenv("BITBUCKET_WORKSPACE")  # Workspace slug (Cloud) or project key (Server)
BITBUCKET_REPO = os.getenv("BITBUCKET_REPO")  # Repository slug

# Validate that all required environment variables are set
missing_vars = []
if not BITBUCKET_URL:
    missing_vars.append("BITBUCKET_URL")
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
print(f"Connecting to Bitbucket...")
print(f"URL: {BITBUCKET_URL}")
print(f"Username: {BITBUCKET_USERNAME}")
print(f"Workspace: {BITBUCKET_WORKSPACE}")
print(f"Repository: {BITBUCKET_REPO}")

try:
    bitbucket = Bitbucket(
        url=BITBUCKET_URL,
        username=BITBUCKET_USERNAME,
        password=BITBUCKET_API_TOKEN,
        cloud=True  # Set to False if using Bitbucket Server/Data Center
    )
    print("✅ Connected to Bitbucket successfully")

    # Test basic connectivity
    print("Testing basic API connectivity...")
    try:
        # Try to get user info
        user_info = bitbucket.get_user()
        print(f"✅ User info retrieved: {user_info.get('display_name', 'Unknown')}")
    except Exception as user_error:
        print(f"⚠️  Could not retrieve user info: {user_error}")

except Exception as e:
    print(f"❌ Failed to connect to Bitbucket: {e}")
    print("Please check your environment variables")
    exit(1)

# Fetch pull requests
print(f"Fetching pull requests from {BITBUCKET_WORKSPACE}/{BITBUCKET_REPO}...")
print(f"Using credentials: {BITBUCKET_USERNAME} (token: {'*' * 8 if BITBUCKET_API_TOKEN else 'None'})")

try:
    bitbucket_prs = bitbucket.get_pull_requests(BITBUCKET_WORKSPACE, BITBUCKET_REPO, state='OPEN', limit=10)
    print(f"\nType of returned data: {type(bitbucket_prs)}")
    print("This is a generator object - we need to iterate through it to get the actual PRs")

    # Convert generator to list to examine the structure
    print("Attempting to fetch PRs...")
    prs_list = list(bitbucket_prs)
    print(f"\nNumber of PRs returned: {len(prs_list)}")

except Exception as e:
    print(f"\nError fetching pull requests: {e}")
    print(f"Error type: {type(e).__name__}")

    # Check if it's an authentication error
    if "401" in str(e) or "Unauthorized" in str(e):
        print("\n🔐 AUTHENTICATION ERROR:")
        print("This is likely an authentication issue. Please check:")
        print("1. Your BITBUCKET_USERNAME is correct")
        print("2. Your BITBUCKET_API_TOKEN is valid and not expired")
        print("3. Your token has the necessary permissions (repositories:read, pullrequests:read)")
        print("4. You have access to the repository eshyft/eshyftnew")

        # Try to test basic connectivity
        print("\nTesting basic repository access...")
        try:
            # Try a simpler API call first
            repo_info = bitbucket.get_repo(BITBUCKET_WORKSPACE, BITBUCKET_REPO)
            print(f"✅ Repository access successful: {repo_info.get('name', 'Unknown')}")
        except Exception as repo_error:
            print(f"❌ Repository access failed: {repo_error}")
            if "404" in str(repo_error):
                print("   This suggests the repository doesn't exist or you don't have access to it")
            elif "401" in str(repo_error):
                print("   This confirms an authentication issue")

    # Exit gracefully
    exit(1)

if prs_list:
    print(f"\nFirst PR structure:")
    first_pr = prs_list[0]
    print(f"PR ID: {first_pr.get('id')}")
    print(f"Title: {first_pr.get('title')}")
    print(f"Author: {first_pr.get('author', {}).get('display_name', 'Unknown')}")
    print(f"State: {first_pr.get('state')}")
    print(f"Created: {first_pr.get('created_on')}")
    print(f"Updated: {first_pr.get('updated_on')}")

    print(f"\nAll available keys in first PR:")
    for key in sorted(first_pr.keys()):
        print(f"  - {key}")

    print(f"\nLinks available:")
    if 'links' in first_pr:
        for link_name, link_data in first_pr['links'].items():
            if isinstance(link_data, dict) and 'href' in link_data:
                print(f"  - {link_name}: {link_data['href']}")
            else:
                print(f"  - {link_name}: {link_data}")

    print(f"\nAll PRs summary:")
    for i, pr in enumerate(prs_list, 1):
        print(f"{i}. PR #{pr.get('id')}: {pr.get('title')} (State: {pr.get('state')})")

    print(f"\nExample of iterating through the generator directly:")
    # Reset the generator (create a new one)
    bitbucket_prs_2 = bitbucket.get_pull_requests(BITBUCKET_WORKSPACE, BITBUCKET_REPO, state='OPEN', limit=5)
    for i, pr in enumerate(bitbucket_prs_2, 1):
        print(f"{i}. PR #{pr.get('id')}: {pr.get('title')}")
        if i >= 3:  # Just show first 3
            break
else:
    print("No PRs found")
