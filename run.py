from decouple import config
import os

from utils.github_utils import github_connect
from utils.logger import log

from activity.active_repo import find_active
from activity.active_file import check_tf_file, check_cf_file
from activity.keywords import search_keywords

from checkov_check.run_linter import run_linter
from checkov_check.complete_path import replace_file_paths_with_links

from stats.get_stats import get_all_stats
from stats.get_check_data import get_check_data

MONTHS = 12
KEYWORDS_SEARCH = "months"  # or "months"

def run_activity_check(github_client, file_path, dir_path, tool, months=MONTHS):
    # Find active repositories
    log_file = os.path.join(dir_path, "activity/repo/logs.txt")
    active_dump = os.path.join(dir_path, "activity/repo/active_repos.yml")
    inactive_dump = os.path.join(dir_path, "activity/repo/inactive_repos.yml")
    error_dump = os.path.join(dir_path, "activity/repo/error_repos.yml")

    find_active(github_client, file_path, log_file, active_dump, inactive_dump, error_dump, months)

    # Find repositories with active files
    file_path = os.path.join(dir_path, "activity/repo/active_repos.yml")
    log_file = os.path.join(dir_path, "activity/file/logs.txt")
    active_dump = os.path.join(dir_path, "activity/file/active_files.yml")

    if tool == "baseline_tf" or tool == "extended_tf":
        check_tf_file(github_client, file_path, log_file, active_dump, months)
    elif tool == "baseline_cf" or tool == "extended_cf":
        check_cf_file(github_client, file_path, log_file, active_dump, months)

    # Find repositories with keywords in commits
    file_path = os.path.join(dir_path, "activity/file/active_files.yml")

    if (KEYWORDS_SEARCH == "commits"):
        log_file = os.path.join(dir_path, "activity/keywords_10000c/logs.txt")
        keywords_file = os.path.join(dir_path, "activity/keywords_10000c/keywords_repos.yml")
        no_keywords_file = os.path.join(dir_path, "activity/keywords_10000c/no_keywords_repos.yml")
    else:
        log_file = os.path.join(dir_path, "activity/keywords_12m/logs.txt")
        keywords_file = os.path.join(dir_path, "activity/keywords_12m/keywords_repos.yml")
        no_keywords_file = os.path.join(dir_path, "activity/keywords_12m/no_keywords_repos.yml")

    search_keywords(github_client, file_path, log_file, keywords_file, no_keywords_file, search=KEYWORDS_SEARCH, months=months)

def run_linter_check(tool):
    run_linter(tool)
    replace_file_paths_with_links(tool)

if __name__ == "__main__":
    token = config("GITHUB_TOKEN")

    github_client = github_connect(token)

    if github_client:
        run_activity_check(github_client, "results/baseline_tf/original.yml", "results/baseline_tf", "baseline_tf")
        run_activity_check(github_client, "results/baseline_cf/original.yml", "results/baseline_cf", "baseline_cf")
        run_activity_check(github_client, "results/extended_cf/original.yml", "results/extended_cf", "extended_cf")
        run_activity_check(github_client, "results/extended_tf/original.yml", "results/extended_tf", "extended_tf")

        run_linter_check("baseline_tf")
        run_linter_check("baseline_cf")
        run_linter_check("extended_tf")
        run_linter_check("extended_cf")

        get_all_stats()
        
        get_check_data("results", "baseline_tf")
        get_check_data("results", "baseline_cf")
        get_check_data("results", "extended_tf")
        get_check_data("results", "extended_cf")
