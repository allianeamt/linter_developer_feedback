import sys
import os
import random
import copy
from collections import defaultdict
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.logger import log
from utils.yaml_utils import load_yaml, save_to_file, add_to_file
from utils.usage import extract_repo

CHECK_ID_TO_NAME = {
    "CKV_AWS_801": "DynamoDB On-Demand Billing",
    "CKV_AWS_802": "DynamoDB Overprovisioned r/w Capacity",
    "CKV_AWS_803": "DynamoDB GSIs",
    "CKV_AWS_804": "Deprecated Instance/Volume Types",
    "CKV2_AWS_61": "S3 Lifecycle Configurations",
    "CKV_AWS_805": "S3 Lifecycle Configurations",
    "CKV_AWS_806": "DynamoDB On-Demand Billing",
    "CKV_AWS_807": "Deprecated Instance/Volume Types",
}

CHECK_ID_TO_DESCRIPTION = {
    "CKV_AWS_801": "Detects DynamoDB tables that do not use PAY_PER_REQUEST (on-demand) billing. This can lead to over-provisioning, unnecessary costs, or throttling if usage exceeds limits.",
    "CKV_AWS_802": "Detects DynamoDB tables that use provisioned capacity (read_capacity/write_capacity > 1). Provisioned settings can cause higher costs if not properly tuned.",
    "CKV_AWS_803": "Flags DynamoDB tables that define Global Secondary Indexes (GSIs). GSIs add unnecessary costs and complexity if not carefully optimized.",
    "CKV_AWS_804": "Detects use of outdated EC2 instance or EBS volume types (e.g., t2, m4, gp2). Older generations might be less efficient, slower, and more expensive.",
    "CKV2_AWS_61": "Verifies that aws_s3_bucket resources have lifecycle configurations defined via lifecycle_rules or as a linked aws_s3_bucket_lifecycle_configuration. Missing rules may lead to data retention in expensive storage indefinitely, thus increasing costs.",
    "CKV_AWS_805": "Verifies that S3 buckets have lifecycle configurations with at least one rule defined. Missing rules may lead to data retention in expensive storage indefinitely, thus increasing costs.",
    "CKV_AWS_806": "Detects DynamoDB tables that do not use PAY_PER_REQUEST (on-demand) billing. This can lead to over-provisioning, unnecessary costs, or throttling if usage exceeds limits.",
    "CKV_AWS_807": "Detects use of outdated types (e.g., t2, m3, m4, c4) for EC2, RDS and SageMaker instances. Older generations might be less efficient, slower, and more expensive.",
}

LOGS_FILE = "logs.txt"

def check_duplicates():
    baseline_tf = load_yaml("../results/baseline_tf/checkov/results.yml")
    baseline_tf_repos = extract_repo(baseline_tf)

    baseline_cf = load_yaml("../results/baseline_cf/checkov/results.yml")
    baseline_cf_repos = extract_repo(baseline_cf)

    extended_tf = load_yaml("../results/extended_tf/checkov/results.yml")
    extended_tf_repos = extract_repo(extended_tf)

    extended_cf = load_yaml("../results/extended_cf/checkov/results.yml")
    extended_cf_repos = extract_repo(extended_cf)

    all_datasets = baseline_tf_repos + baseline_cf_repos + extended_tf_repos + extended_cf_repos
    unique_datasets = set()

    duplicates = set()
    for dataset in all_datasets:
        if dataset in unique_datasets:
            duplicates.add(dataset)
        else:
            unique_datasets.add(dataset)
    if duplicates:
        log("Duplicates found:", LOGS_FILE)
        for dup in duplicates:
            log(f"\t{dup}", LOGS_FILE)
            # Find out which datasets the duplicate appears in
            sources = []
            if dup in baseline_tf_repos:
                sources.append("baseline_tf")
            if dup in baseline_cf_repos:    
                sources.append("baseline_cf")
            if dup in extended_tf_repos:
                sources.append("extended_tf")
            if dup in extended_cf_repos:
                sources.append("extended_cf")
            log(f"\t\tAppears in: {', '.join(sources)}", LOGS_FILE)

            # remove the duplicate from the extended datasets
            if dup in extended_tf_repos:
                # remove the first entry with that ['repo'] from the extended_tf dataset
                for i, entry in enumerate(extended_tf):
                    if entry['repo'] == dup:
                        extended_tf.pop(i)
                        break

            if dup in extended_cf_repos:
                # remove the first entry with that ['repo'] from the extended_cf dataset
                for i, entry in enumerate(extended_cf):
                    if entry['repo'] == dup:
                        extended_cf.pop(i)
                        break            

        log("Duplicates removed from extended datasets.", LOGS_FILE)
        save_to_file(baseline_tf, "raw_data/baseline_tf.yml")
        save_to_file(baseline_cf, "raw_data/baseline_cf.yml")
        save_to_file(extended_tf, "raw_data/extended_tf.yml")
        save_to_file(extended_cf, "raw_data/extended_cf.yml")

    else:
        log("No duplicates found across datasets.", LOGS_FILE)

def clean_data(data, tool, dataset, keywords_dataset):
    cleaned_data = []
    aware_repos = {entry["repo"] for entry in keywords_dataset}

    for entry in data:
        failed_checks = entry.get("checks", {}).get("failed_checks", [])
        if not failed_checks:
            continue

        for check in failed_checks:
            check_id = check.get("check_id")
            check["check_name"] = CHECK_ID_TO_NAME.get(check_id, "Unknown Check")

        failed_checks_count = len(failed_checks)
        unique_files = set(check.get("file_path") for check in failed_checks if "file_path" in check)
        unique_files_count = len(unique_files)

        preferred_checks = [check for check in failed_checks if check["check_id"] in {"CKV_AWS_801", "CKV_AWS_806"}]
        example_check = random.choice(preferred_checks if preferred_checks else failed_checks)
        example_check_decopy = copy.deepcopy(example_check)

        example_check_decopy["check_description"] = CHECK_ID_TO_DESCRIPTION.get(example_check["check_id"], "No description available")

        repo_url = entry.get("repo")
        cost_awareness = "aware" if repo_url in aware_repos else "unaware"

        cleaned_entry = {
            "repo": entry.get("repo"),
            "tool": tool,
            "dataset": dataset,
            "failed_checks": failed_checks,
            "failed_checks_count": failed_checks_count,
            "files_count": unique_files_count,
            "example_check": example_check_decopy,
            "cost_awareness": cost_awareness,
        }

        cleaned_data.append(cleaned_entry)

    return cleaned_data

def clean_datasets():
    log("Cleaning datasets...", LOGS_FILE)

    baseline_tf = load_yaml("raw_data/baseline_tf.yml")
    baseline_cf = load_yaml("raw_data/baseline_cf.yml")
    extended_tf = load_yaml("raw_data/extended_tf.yml")
    extended_cf = load_yaml("raw_data/extended_cf.yml")

    keywords_baseline_tf = load_yaml("../results/baseline_tf/activity/keywords_12m/keywords_repos.yml")
    keywords_baseline_cf = load_yaml("../results/baseline_cf/activity/keywords_12m/keywords_repos.yml")
    keywords_extended_tf = load_yaml("../results/extended_tf/activity/keywords_12m/keywords_repos.yml")
    keywords_extended_cf = load_yaml("../results/extended_cf/activity/keywords_12m/keywords_repos.yml")

    cleaned_baseline_tf = clean_data(baseline_tf, "terraform", "baseline", keywords_baseline_tf)
    cleaned_baseline_cf = clean_data(baseline_cf, "cloudformation", "baseline", keywords_baseline_cf)
    cleaned_extended_tf = clean_data(extended_tf, "terraform", "extended", keywords_extended_tf)
    cleaned_extended_cf = clean_data(extended_cf, "cloudformation", "extended", keywords_extended_cf)

    save_to_file(cleaned_baseline_tf, "data/cleaned_baseline_tf.yml")
    save_to_file(cleaned_baseline_cf, "data/cleaned_baseline_cf.yml")
    save_to_file(cleaned_extended_tf, "data/cleaned_extended_tf.yml")
    save_to_file(cleaned_extended_cf, "data/cleaned_extended_cf.yml")

    # combine all cleaned datasets into one
    combined_cleaned_data = cleaned_baseline_tf + cleaned_baseline_cf + cleaned_extended_tf + cleaned_extended_cf
    save_to_file(combined_cleaned_data, "data/combined_data.yml")

def get_check_combinations():
    data = load_yaml("data/combined_data.yml")
    unique_combos = defaultdict(lambda: {"count": 0, "repos": set()})

    for entry in data:
        repo = entry["repo"]
        checks = {check["check_id"] for check in entry.get("failed_checks", [])}

        key = tuple(sorted(checks))
        unique_combos[key]["count"] += 1
        unique_combos[key]["repos"].add(repo)

    result = []
    for checks, info in unique_combos.items():
        result.append({
            "checks": list(checks),
            "count": info["count"],
            "repos": sorted(info["repos"]),
        })

    save_to_file(result, "check_combinations.yml")

def get_awareness_stats():
    data = load_yaml("data/combined_data.yml")
    awareness_stats = defaultdict(lambda: {"aware": 0, "unaware": 0})

    for entry in data:
        awareness_stats[entry["tool"]][entry["cost_awareness"]] += 1

    result = []
    for tool, stats in awareness_stats.items():
        result.append({
            "tool": tool,
            "aware": stats["aware"],
            "unaware": stats["unaware"],
        })

    save_to_file(result, "awareness_stats_tool.yml")

    # Calculate awareness stats for each dataset
    dataset_stats = defaultdict(lambda: {"aware": 0, "unaware": 0})

    for entry in data:
        key = (entry["tool"], entry["dataset"])
        dataset_stats[key][entry["cost_awareness"]] += 1
    
    result = []
    for (tool, dataset), stats in dataset_stats.items():
        result.append({
            "tool": tool,
            "dataset": dataset,
            "aware": stats["aware"],
            "unaware": stats["unaware"],
        })

    save_to_file(result, "awareness_stats_dataset.yml")

def aggregate_totals():
    data = load_yaml("data/combined_data.yml")

    stats = defaultdict(lambda: {
        "total_checks": 0,
        "unique_files": 0,
        "total_repos": 0,
    })

    for entry in data:
        key = (entry["tool"], entry["dataset"])
        stats[key]["total_checks"] += entry.get("failed_checks_count", 0)
        stats[key]["unique_files"] += entry.get("files_count", 0)
        stats[key]["total_repos"] += 1

    result = []
    for (tool, dataset), values in stats.items():
        result.append({
            "tool": tool,
            "dataset": dataset,
            "total_checks": values["total_checks"],
            "unique_files": values["unique_files"],
            "total_repos": values["total_repos"],
        })

    save_to_file(result, "aggregated_totals.yml")

def sample(filename, size=4):
    data = load_yaml("data/gh_issues/unopened.yml")

    # Filter only baseline + terraform/cloudformation + more than 1 failed check
    filtered = [
        entry for entry in data
        if (
            # entry['dataset'] == 'baseline' and
            entry['tool'] in ['terraform', 'cloudformation'] and
            len(entry.get('failed_checks', [])) > 1
        )
    ]

    # Create buckets by (tool, awareness)
    buckets = {
        ('terraform', 'aware'): [],
        ('terraform', 'unaware'): [],
        ('cloudformation', 'aware'): [],
        ('cloudformation', 'unaware'): [],
    }

    for entry in filtered:
        key = (entry['tool'], entry['cost_awareness'])
        if key in buckets:
            buckets[key].append(entry)

    eligible_buckets = {
        key: entries for key, entries in buckets.items() if len(entries) >= 10
    }

    if not eligible_buckets:
        print("No buckets with at least 10 entries found.")
        return
    
        # Distribute `size` samples fairly among eligible buckets
    buckets_to_sample = list(eligible_buckets.keys())
    num_buckets = len(buckets_to_sample)

    # Calculate fair base samples per bucket
    base_per_bucket = size // num_buckets
    remainder = size % num_buckets

    # Assign samples per bucket
    samples_per_bucket = {key: base_per_bucket for key in buckets_to_sample}

    # Distribute the remainder fairly
    for key in random.sample(buckets_to_sample, remainder):
        samples_per_bucket[key] += 1

    selected_sample = {}
    sampled_count = 0

    for key in buckets_to_sample:
        entries = eligible_buckets[key]
        sample_count = min(samples_per_bucket[key], len(entries))
        samples = random.sample(entries, sample_count)
        for i, entry in enumerate(samples):
            label = f"{key[0]}_{key[1]}_{i}"
            selected_sample[label] = entry
            data.remove(entry)
            sampled_count += 1

    # Remove the sample from the original data
    for entry in selected_sample.values():
        if entry in data:
            data.remove(entry)

    save_to_file(selected_sample, f"data/gh_issues/{filename}")
    save_to_file(data, "data/gh_issues/unopened.yml")

def generate_issue_message_survey(entry):
    check = entry["example_check"]
    issues_count = entry["failed_checks_count"]
    files_count = entry["files_count"]
    check_name = check["check_name"]
    check_description = check["check_description"]
    resource = check["resource"]
    file_path = check["file_path"]
    if issues_count > 1:
        resource_file_block = f"⚙️ **Resource:** `{resource}`  \n🔎 **File:** `{file_path}`"
    else:
        resource_file_block = ""

    message = f"""
Hi there! 👋

I’m a master’s student researching **cost considerations in cloud infrastructure**. As part of this project, we ran a static analysis tool (linter) on your repository to identify potential cost-related misconfigurations.

We found **{issues_count} potential issue{'s' if issues_count != 1 else ''}** across **{files_count} file{'s' if files_count != 1 else ''}**. Here’s an example:

✔️ **Issue:** {check_name}  
📃 **Description:** {check_description}  
{resource_file_block}

Are you interested in **more linter results**? Reply here. We’ll send **the report along with a short follow-up survey** (~5 min) to evaluate our tool and better understand cost considerations in open-source projects for our research. All data will be treated confidentially.

If you’re curious about our work, we are investigating how developers approach cost in cloud infrastructure, specifically Terraform and AWS CloudFormation. Our goal is to identify **patterns and anti-patterns** to help developers make **more cost-aware infrastructure decisions**. You can check out what we’ve discovered so far here: [https://search-rug.github.io/iac-cost-patterns/](https://search-rug.github.io/iac-cost-patterns/). If you have any questions or would like to discuss our research, don’t hesitate to reach out!

Thank you for your time and support! 🤗

Allia Neamt, MSc Student (Computing Science)  
Faculty of Science and Engineering  
Rijksuniversiteit, Groningen
"""
    return message.strip()

def generate_issue_message_example(entry):
    check = entry["example_check"]
    issues_count = entry["failed_checks_count"]
    files_count = entry["files_count"]
    check_name = check["check_name"]
    check_description = check["check_description"]
    resource = check["resource"]
    file_path = check["file_path"]
    line_range = check["file_line_range"]

    message = f"""
Hi there! 👋

I’m a master’s student researching **cost considerations in cloud infrastructure**. As part of this project, we ran a static analysis tool (linter) on your repository and found the following potential misconfiguration that could lead to unnecessary costs:

✔️ **Issue:** {check_name}  
📃 **Description:** {check_description}  
⚙️ **Resource:** `{resource}`  
🔎 **File:** `{file_path}`
📍 **Line Range:** `{line_range}`

Please let me know if this is helpful or if it makes sense for your project. If you have any questions or would like to discuss this further, feel free to reach out! Thanks for your time! 🤗

Allia Neamt, MSc Student (Computing Science)  
Faculty of Science and Engineering  
Rijksuniversiteit, Groningen
"""
    return message.strip()

def repo_url_to_owner_repo(repo_url):
    # Extract owner and repo name from URL
    parts = repo_url.rstrip('/').split('/')
    owner = parts[-2]
    repo = parts[-1]
    return owner, repo

def open_issues_survey(filename, message_type="survey"):
    log(f"Opening issues from {filename} with message type '{message_type}'", "data/gh_issues/logs.txt")
    data = load_yaml(f"data/gh_issues/{filename}")
    opened_issues = []
    not_opened_issues = []

    for key, entry in data.items():
        owner, repo = repo_url_to_owner_repo(entry["repo"])
        issue_title = f"Cost-Related Misconfigurations Findings"
        if message_type == "survey":
            issue_body = generate_issue_message_survey(entry)
        elif message_type == "example":
            issue_body = generate_issue_message_example(entry)
        github_token = os.getenv("GITHUB_TOKEN")

        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/issues"
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github+json"
            }

            response = requests.post(url, json={
                "title": issue_title,
                "body": issue_body
            }, headers=headers)

            if response.status_code == 201:
                log(f"\tIssue created successfully for {entry['repo']}", "data/gh_issues/logs.txt")
                opened_issues.append(entry["repo"])
            else:
                log(f"\tFailed to create issue for {entry['repo']}: {response.status_code} - {response.text}", "data/gh_issues/logs.txt")
                not_opened_issues.append({
                    "repo": entry["repo"],
                    "error": "Issues disabled" if response.status_code == 410 else response.text
                })
        except Exception as e:
            log(f"Error creating issue for {entry['repo']}: {str(e)}", "data/gh_issues/logs.txt")

    if opened_issues:
        add_to_file(opened_issues, "data/gh_issues/issues_opened.yml")
    if not_opened_issues:
        add_to_file(not_opened_issues, "data/gh_issues/issues_not_opened.yml")
    log("\n", "data/gh_issues/logs.txt")

if __name__ == "__main__":
    # check_duplicates()
    # clean_datasets()
    # get_check_combinations()
    # get_awareness_stats()
    # aggregate_totals()
    # sample("pilot_survey2.yml", 5)
    open_issues_survey("extra.yml", message_type="example")

    