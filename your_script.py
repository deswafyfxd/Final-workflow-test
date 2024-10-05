import requests
import os
from datetime import datetime

# Pull the webhook URL from environment variables
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
REPOS = ["username/repo1", "username/repo2", "username/repo3", "username/repo4", "username/repo5"]

def get_workflow_status(repo):
    url = f"https://api.github.com/repos/{repo}/actions/runs"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

def send_discord_message(content):
    data = {"content": content}
    response = requests.post(DISCORD_WEBHOOK, json=data)
    return response.status_code

def check_workflows():
    today = datetime.now().date()
    for repo in REPOS:
        workflows = get_workflow_status(repo)
        if workflows:
            for run in workflows["workflow_runs"]:
                run_date = datetime.strptime(run["created_at"], "%Y-%m-%dT%H:%M:%SZ").date()
                if run_date == today:
                    if run["conclusion"] is None:
                        message = f"Workflow for {repo} has started but not completed today."
                        send_discord_message(message)
                        break
                    elif run["conclusion"] == "success":
                        break
            else:
                message = f"Workflow for {repo} has not started today."
                send_discord_message(message)
        else:
            message = f"Failed to fetch workflow for {repo}."
            send_discord_message(message)

if __name__ == "__main__":
    check_workflows()
