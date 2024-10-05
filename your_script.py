import requests
import os
import time
from datetime import datetime

# Pull the webhook URL from environment variables
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

# Define groups and their respective projects
GROUPS = {
    "Group1": {
        "Project1": ["username1/repo1", "username2/repo2"],
        "Project2": ["username3/repo3", "username4/repo4"],
        "Project3": ["username5/repo5", "username6/repo6"]
    },
    "Group2": {
        "Project4": ["username7/repo7", "username8/repo8"],
        "Project5": ["username9/repo9", "username10/repo10"],
        "Project6": ["username11/repo11", "username12/repo12"]
    }
}

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Rate limit settings
RATE_LIMIT = 5000  # Number of requests allowed per hour
RESET_TIME = 3600  # Time in seconds after which rate limit resets
RATE_LIMIT_BUFFER = 50  # Buffer to avoid hitting the limit exactly

class RateLimiter:
    def __init__(self, limit, period):
        self.limit = limit
        self.period = period
        self.requests = []
    
    def check_limit(self):
        now = time.time()
        self.requests = [req for req in self.requests if now - req < self.period]
        if len(self.requests) >= self.limit - RATE_LIMIT_BUFFER:
            sleep_time = self.period - (now - self.requests[0])
            time.sleep(sleep_time)

    def make_request(self, url, headers=None):
        self.check_limit()
        response = requests.get(url, headers=headers)
        self.requests.append(time.time())
        return response

rate_limiter = RateLimiter(RATE_LIMIT, RESET_TIME)

def get_workflow_status(repo):
    url = f"https://api.github.com/repos/{repo}/actions/runs"
    for attempt in range(MAX_RETRIES):
        response = rate_limiter.make_request(url)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 403:
            return "Access Forbidden"
        elif response.status_code == 404:
            return "Not Found"
        else:
            time.sleep(RETRY_DELAY * (2 ** attempt))  # Exponential backoff
    return None

def send_discord_message(content):
    data = {"content": content}
    response = requests.post(DISCORD_WEBHOOK, json=data)
    return response.status_code

def check_project_workflows(group, project, repos):
    today = datetime.now().date()
    project_complete = False
    for repo in repos:
        workflows = get_workflow_status(repo)
        if workflows == "Access Forbidden":
            message = f"Access to {repo} in {project} ({group}) is forbidden (likely private, suspended, or flagged)."
            send_discord_message(message)
            continue
        elif workflows == "Not Found":
            message = f"{repo} in {project} ({group}) not found (possible invalid repository or actions disabled)."
            send_discord_message(message)
            continue
        elif workflows:
            for run in workflows["workflow_runs"]:
                run_date = datetime.strptime(run["created_at"], "%Y-%m-%dT%H:%M:%SZ").date()
                if run_date == today and run["conclusion"] == "success":
                    project_complete = True
                    break
            if project_complete:
                break
        else:
            message = f"Failed to fetch workflow for {repo} in {project} ({group}) after {MAX_RETRIES} attempts."
            send_discord_message(message)
            continue

    if not project_complete:
        message = f"Workflow for {project} in {group} has not completed today."
        send_discord_message(message)

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=5) as executor:
        for group, projects in GROUPS.items():
            for project, repos in projects.items():
                executor.submit(check_project_workflows, group, project, repos)
