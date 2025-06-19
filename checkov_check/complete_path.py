import requests

from utils.logger import log
from utils.yaml_utils import save_to_file, load_yaml

LOG_PATH = 'logs.txt'

BASELINE_TF_INPUT = 'results/baseline_tf/checkov/results.yml'
BASELINE_TF_OUTPUT = 'results/baseline_tf/checkov/results_full_link.yml'

BASELINE_CF_INPUT = 'results/baseline_cf/checkov/results.yml'
BASELINE_CF_OUTPUT = 'results/baseline_cf/checkov/results_full_link.yml'

EXTENDED_TF_INPUT = 'results/extended_tf/checkov/results.yml'
EXTENDED_TF_OUTPUT = 'results/extended_tf/checkov/results_full_link.yml'

EXTENDED_CF_INPUT = 'results/extended_cf/checkov/results.yml'
EXTENDED_CF_OUTPUT = 'results/extended_cf/checkov/results_full_link.yml'

def get_default_branch(repo_url):
    try:
        owner_repo = "/".join(repo_url.split("github.com/")[1].split("/")[:2])
        api_url = f"https://api.github.com/repos/{owner_repo}"
        response = requests.get(api_url)
        if response.status_code == 200:
            return response.json().get("default_branch", "main")
    except Exception:
        log(f"Error fetching default branch for {repo_url}")
    return "main"

def replace_file_paths_with_links(tool):
    if tool == "baseline_tf":
        input_file = BASELINE_TF_INPUT
        output_file = BASELINE_TF_OUTPUT
    elif tool == "baseline_cf":
        input_file = BASELINE_CF_INPUT
        output_file = BASELINE_CF_OUTPUT
    elif tool == "extended_tf":
        input_file = EXTENDED_TF_INPUT
        output_file = EXTENDED_TF_OUTPUT
    elif tool == "extended_cf":
        input_file = EXTENDED_CF_INPUT
        output_file = EXTENDED_CF_OUTPUT

    data = load_yaml(input_file)

    for repo_entry in data:
        repo_url = repo_entry.get("repo")
        default_branch = get_default_branch(repo_url)

        for section in ("failed_checks", "passed_checks"):
            checks = repo_entry.get("checks", {}).get(section, [])
            for check in checks:
                raw_path = check.get("file_path", "").lstrip("/").replace("\\", "/")
                # delete the "temp_repo" prefix if it exists
                if raw_path.startswith("temp_repo/"):
                    raw_path = raw_path.replace("temp_repo/", "", 1)
                    
                full_url = f"{repo_url}/blob/{default_branch}/{raw_path}"

                check["file_path"] = full_url
    
    save_to_file(data, output_file)
    