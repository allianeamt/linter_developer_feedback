import yaml
from collections import defaultdict

from utils.yaml_utils import load_yaml, add_to_file

STATS_FILE = "results/stats/check_stats.yml"
OUTPUT_FILE = "results/stats/check_stats.txt"

def get_check_stats(filename, tool):
    total_with_checks = 0
    total_without_checks = 0
    only_passed = 0
    only_failed = 0

    check_pass_counts = defaultdict(int)
    check_fail_counts = defaultdict(int)

    data = load_yaml(filename)
    for entry in data:
        checks = entry.get("checks")
        if not checks:
            total_without_checks += 1
            continue

        total_with_checks += 1
        passed = checks.get("passed_checks", [])
        failed = checks.get("failed_checks", [])

        if passed and not failed:
            only_passed += 1
        elif failed and not passed:
            only_failed += 1

        for passed_check in passed:
            check_pass_counts[passed_check["check_id"]] += 1
        
        for failed_check in failed:
            check_fail_counts[failed_check["check_id"]] += 1

    stats = {
        "tool": tool,
        "total_with_checks": total_with_checks,
        "total_without_checks": total_without_checks,
        "only_passed": only_passed,
        "only_failed": only_failed,
        "check_pass_counts": dict(check_pass_counts),
        "check_fail_counts": dict(check_fail_counts),
    }

    # add the stats to the file
    add_to_file(stats, STATS_FILE)

    # write the stats to a text file
    with open(OUTPUT_FILE, 'a') as file:
        file.write(f"Check statistics for: {tool}\n")
        file.write(f"\tTotal with checks: {total_with_checks}\n")
        file.write(f"\tTotal without checks: {total_without_checks}\n")
        file.write(f"\tOnly passed: {only_passed}\n")
        file.write(f"\tOnly failed: {only_failed}\n")
        file.write("\tCheck pass counts:\n")
        for check, count in check_pass_counts.items():
            file.write(f"\t\t  {check}: {count}\n")
        file.write("\tCheck fail counts:\n")
        for check, count in check_fail_counts.items():
            file.write(f"\t\t  {check}: {count}\n")
        file.write("\n")

def get_awareness_stats(results_file, keyword_file, tool):
    checkov_data = load_yaml(results_file)
    keyword_data = load_yaml(keyword_file)

    keyword_repos = {repo["repo"] for repo in keyword_data if repo.get("repo")}

    check_counts = defaultdict(lambda: {
        "aware": {"passed": 0, "failed": 0},
        "unaware": {"passed": 0, "failed": 0}
    })

    for entry in checkov_data:
        repo_url = entry.get("repo")
        category = "aware" if repo_url in keyword_repos else "unaware"

        for check in entry.get("checks", {}).get("passed_checks", []):
            check_id = check.get("check_id")
            if check_id:
                check_counts[check_id][category]["passed"] += 1

        for check in entry.get("checks", {}).get("failed_checks", []):
            check_id = check.get("check_id")
            if check_id:
                check_counts[check_id][category]["failed"] += 1

    awareness_stats = {
        "tool": tool,
        "check_counts": {check_id: counts for check_id, counts in check_counts.items()}
    }

    # Save awareness stats to the stats file
    add_to_file(awareness_stats, STATS_FILE)

    # Write awareness stats to the output file
    with open(OUTPUT_FILE, 'a') as file:
        file.write(f"Awareness statistics for: {tool}\n")
        for check_id, counts in awareness_stats["check_counts"].items():
            file.write(f"\tCheck ID: {check_id}\n")
            file.write(f"\t\tAware - Passed: {counts['aware']['passed']}, Failed: {counts['aware']['failed']}\n")
            file.write(f"\t\tUnaware - Passed: {counts['unaware']['passed']}, Failed: {counts['unaware']['failed']}\n")
        file.write("\n")

def get_stats(results_file, keyword_file_12m, keyword_file_10000c, tool):
    get_check_stats(results_file, tool)
    get_awareness_stats(results_file, keyword_file_12m, f"{tool} (12m)")
    get_awareness_stats(results_file, keyword_file_10000c, f"{tool} (10000c)")

def get_all_stats():
    with open(STATS_FILE, 'w') as file:
        yaml.dump([], file)
    with open(OUTPUT_FILE, 'w') as file:
        file.write("Check statistics\n\n")

    get_stats("results/baseline_tf/checkov/results_full_link.yml", "results/baseline_tf/activity/keywords_12m/keywords_repos.yml", "results/baseline_tf/activity/keywords_10000c/keywords_repos.yml", "baseline_tf")
    get_stats("results/baseline_cf/checkov/results_full_link.yml", "results/baseline_cf/activity/keywords_12m/keywords_repos.yml", "results/baseline_cf/activity/keywords_10000c/keywords_repos.yml", "baseline_cf")
    get_stats("results/extended_tf/checkov/results_full_link.yml", "results/extended_tf/activity/keywords_12m/keywords_repos.yml", "results/extended_tf/activity/keywords_10000c/keywords_repos.yml", "extended_tf")
    get_stats("results/extended_cf/checkov/results_full_link.yml", "results/extended_cf/activity/keywords_12m/keywords_repos.yml", "results/extended_cf/activity/keywords_10000c/keywords_repos.yml", "extended_cf")