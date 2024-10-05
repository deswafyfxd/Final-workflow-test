from concurrent.futures import ThreadPoolExecutor
import requests
import os
import time
from datetime import datetime
import apprise
from ratelimit import limits, sleep_and_retry

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

NOTIFICATIONS_PER_HOUR = 60  # Apprise notifications limit per hour

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

# Rate limit decorator for Apprise notifications
@sleep_and_retry
@limits(calls=NOTIFICATIONS_PER_HOUR, period=3600)
def send_discord_message(content):
    apobj = apprise.Apprise()
    apobj.add(DISCORD_WEBHOOK)
    apobj.notify(body=content, title="GitHub Action Notification")

def check_project_workflows(group, project, repos):
    today = datetime.now().date()
    project_complete = {repo: False for repo in repos}
    messages = []
    for repo in repos:
        if "username" in repo or "repo" in repo:
            messages.append(f"Placeholder values detected for {repo} in {project} ({group}). Skipping actual check.")
            continue
        workflows = get_workflow_status(repo)
        if workflows == "Access Forbidden":
            messages.append(f"Access to {repo} in {project} ({group}) is forbidden (likely private, suspended, or flagged).")
            continue
        elif workflows == "Not Found":
            messages.append(f"Actions are disabled for {repo} in {project} ({group}). Unable to check workflow status.")
            continue
        elif workflows:
            workflow_triggered_today = False
            for run in workflows["workflow_runs"]:
                run_date = datetime.strptime(run["created_at"], "%Y-%m-%dT%H:%M:%SZ").date()
                if run_date == today:
                    workflow_triggered_today = True
                    if run["conclusion"] == "success":
                        project_complete[repo] = True
                        break
                    else:
                        messages.append(f"No successful workflow run for {repo} in {project} ({group}) today. Last run concluded with {run['conclusion']}.")
            if not workflow_triggered_today:
                messages.append(f"No workflows have been triggered for {repo} in {project} ({group}) today.")
        else:
            messages.append(f"Failed to fetch workflow for {repo} in {project} ({group}) after {MAX_RETRIES} attempts.")
            continue

    if not all(project_complete.values()):
        if all(not status for status in project_complete.values()):
            messages.append(f"No workflows have completed for both accounts in {project} ({group}) today.")
        else:
            for repo, status in project_complete.items():
                if not status:
                    messages.append(f"No successful workflow run for {repo} in {project} ({group}) today.")
    
    if messages:
        send_discord_message("\n".join(messages))

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for group, projects in GROUPS.items():
            for project, repos in projects.items():
                futures.append(executor.submit(check_project_workflows, group, project, repos))
        for future in futures:
            future.result()  # Wait for all threads to complete
