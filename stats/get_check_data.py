import csv

from utils.yaml_utils import load_yaml
from utils.usage import extract_repo

def create_csv(repos, keyword_repos, tool, dir_path, search="months"):
    rows = []

    for repo in repos:
        repo_url = repo.get("repo")
        failed_checks = repo.get("checks", {}).get("failed_checks", [])
        if repo_url not in keyword_repos:
            repo["cost_label"] = "unaware"
        else:
            repo["cost_label"] = "aware"

        for check in failed_checks:
            rows.append({
                "repo_url": repo_url,
                "check_id": check.get("check_id"),
                "resource": check.get("resource"),
                "file_path": check.get("file_path"),
                "file_line_range": check.get("file_line_range"),
                "commits": repo.get("commits", 0),
                "issues": repo.get("issues", 0),
                "pulls": repo.get("pulls", 0),
                "average_activity": repo.get("average_activity", 0),
                "cost_label": repo["cost_label"]
            })
    
    csv_file_path = f"{dir_path}/checks/failed_{tool}_{search}.csv"
    with open(csv_file_path, mode="w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

def get_check_data(dir_path, tool):
    checkov_data = load_yaml(f"{dir_path}/{tool}/checkov/results_full_link.yml")
    keywords_12m_data = load_yaml(f"{dir_path}/{tool}/activity/keywords_12m/keywords_repos.yml")
    keywords_12m_data = extract_repo(keywords_12m_data)
    keywords_10000c_data = load_yaml(f"{dir_path}/{tool}/activity/keywords_10000c/keywords_repos.yml")
    keywords_10000c_data = extract_repo(keywords_10000c_data)

    create_csv(checkov_data, keywords_12m_data, tool, dir_path, search="months")
    create_csv(checkov_data, keywords_10000c_data, tool, dir_path, search="commits")



