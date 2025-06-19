import datetime

from utils.yaml_utils import load_yaml, save_to_file
from utils.logger import log
from utils.github_utils import github_connect, github_limit
from utils.usage import extract_repo_name

def check_active_repos(github_client, repositories, log_file, months=6):
    log(f"Checking {len(repositories)} repositories for activity in the last {months} months...", log_file)

    active_repos = []
    inactive_repos = []
    error_repos = []

    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=months * 30)

    for repo in repositories:
        activity = {"repo": repo, "commits": 0, "issues": 0, "pulls": 0}
        repo_name = extract_repo_name(repo)
        try:
            github_limit(github_client, log_file)

            checking_repo = github_client.get_repo(repo_name)
            if checking_repo:
                log(f"\tChecking repository: {repo}", log_file)

            # Check commits
            commits = github_client.get_repo(repo_name).get_commits(since=since)
            commits_count = commits.totalCount
            log(f"\t\tCommits found: {commits_count}", log_file)
            if commits_count > 0:
                activity["commits"] = commits_count

            # Check issues
            issues = github_client.get_repo(repo_name).get_issues(state='all', since=since)
            issues_count = issues.totalCount
            log(f"\t\tIssues found: {issues_count}", log_file)
            if issues_count > 0:
                activity["issues"] = issues_count

            # Check pull requests
            pulls = github_client.get_repo(repo_name).get_pulls(state='all', sort='updated', direction='desc', base='main')
            recent_pulls = [pr for pr in pulls if pr.updated_at >= since]
            log(f"\t\tPull requests found: {len(recent_pulls)}", log_file)
            if len(recent_pulls) > 0:
                activity["pulls"] = len(recent_pulls)

        except Exception as e:
            log(f"\tError checking repo {repo}: {e}", log_file)
            error_repos.append(repo)
            continue

        if activity["commits"] or activity["issues"] or activity["pulls"]:
            active_repos.append({
                "repo": repo,
                "commits": activity["commits"],
                "issues": activity["issues"],
                "pulls": activity["pulls"]
            })
        else:
            inactive_repos.append(repo)

    return active_repos, inactive_repos, error_repos

def find_active(github_client, file_path, log_file, active_dump, inactive_dump, error_dump, months=6):
    repositories = load_yaml(file_path)
    active_repos, inactive_repos, error_repos = check_active_repos(github_client, repositories, log_file, months)

    save_to_file(active_repos, active_dump)
    save_to_file(inactive_repos, inactive_dump)
    save_to_file(error_repos, error_dump)