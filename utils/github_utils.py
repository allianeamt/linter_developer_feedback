from github import Github
import datetime
import time
import sys

from utils.logger import log

def github_connect(token):
    try:
        github_client = Github(login_or_token=token, per_page=100)

        user = github_client.get_user()
        log(f"Connected to GitHub as {user.login}")
        return github_client
    
    except Exception as e:
        log(f"Error connecting to GitHub: {e}")
        sys.exit(1)

def github_limit(github_client, log_file):
    try:
        rate_limit = github_client.get_rate_limit().core
        log(f"Remaining requests: {rate_limit.remaining}", log_file)

        if rate_limit.remaining <= 250:
            reset_time = rate_limit.reset.timestamp() - datetime.datetime.now().timestamp()
            log(f"Rate limit exceeded. Reset in {reset_time} seconds.", log_file)
            time.sleep(reset_time + 10)
    
    except Exception as e:
        log(f"Error fetching rate limit: {e}", log_file)
        sys.exit(1)