import yaml
import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils.logger import log
from utils.yaml_utils import load_yaml, save_to_file
from utils.usage import extract_repo, extract_repo_name
from utils.github_utils import github_limit

SESSION = requests.Session()
RETRIES = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)

ADAPTER = HTTPAdapter(max_retries=RETRIES)
SESSION.mount('https://', ADAPTER)
SESSION.mount('http://', ADAPTER)

def check_tf_file(github_client, file_path, log_file, active_dump, months=12):
    repositories = load_yaml(file_path)
    repositories = extract_repo(repositories)

    since = datetime.datetime.now() - datetime.timedelta(days=30 * months)
    active_repos = []

    for repo in repositories:
        repo_name = extract_repo_name(repo)
        try:
            github_limit(github_client, log_file)
            repository = github_client.get_repo(repo_name)
            log(f"\tChecking repository: {repo}", log_file)

            tf_changed = False
            commits = repository.get_commits(since=since)
            for commit in commits:
                try:
                    files = commit.files
                    for file in files:
                        if file.filename.endswith('.tf'):
                            tf_changed = True
                            log(f"\t\tTerraform file changed: {file.filename}", log_file)
                            break
                    if tf_changed:
                        active_repos.append(repo)
                        break

                except Exception as e:
                    log(f"\t\t\tError checking files in commit {commit.sha} of {repo_name}: {e}", log_file)
                    continue
            if not tf_changed:
                log(f"\t\tNo Terraform files changed in the last {months} months for {repo_name}", log_file)

        except Exception as e:
            log(f"\t\tError checking repository {repo_name}: {e}", log_file)

    log(f"\nActive repositories with Terraform files changed in the last {months} months: {len(active_repos)}", log_file)
    save_to_file(active_repos, active_dump)

def is_cloudformation_yaml_file(raw_url, log_file):
    try:
        response = SESSION.get(raw_url, timeout=10)
        if response.status_code != 200:
            return False
        content = response.text

        try:
            yaml_file = yaml.safe_load(content)
            if isinstance(yaml_file, dict) and "Resources" in yaml_file:
                for resource in yaml_file["Resources"].values():
                    if isinstance(resource, dict) and "Type" in resource:
                        if str(resource["Type"]).startswith("AWS::"):
                            log(f"\t\tFound CF resource", log_file)
                            return True

            return False

        except yaml.YAMLError as e:
            # check if the content starts with "AWSTemplateFormatVersion: 2010-09-09"
            if content.startswith("AWSTemplateFormatVersion: 2010-09-09"):
                log(f"\t\tStarts with header", log_file)
                return True
            
            elif "Resources" in content and "AWS::" in content:
                log(f"\t\tContains AWS resources", log_file)
                return True

    except Exception as e:
        log(f"\t\tError checking CloudFormation file: {e}", log_file)
        return False

def check_cf_file(github_client, file_path, log_file, active_dump, months=12):
    repositories = load_yaml(file_path)
    repositories = extract_repo(repositories)

    since = datetime.datetime.now() - datetime.timedelta(days=30 * months)
    active_repos = []

    for repo in repositories:
        repo_name = extract_repo_name(repo)
        try:
            github_limit(github_client, log_file)
            repository = github_client.get_repo(repo_name)
            log(f"\tChecking repository: {repo}", log_file)

            cf_changed = False
            commits = repository.get_commits(since=since)
            for commit in commits:
                try:
                    files = commit.files
                    for file in files:
                        if file.filename.endswith(('.yaml', '.yml')):

                            result = is_cloudformation_yaml_file(file.raw_url, log_file)
                            if result:
                                cf_changed = True
                                active_repos.append(repo)
                                log(f"\t\tCloudFormation file changed: {file.raw_url}", log_file)
                                break

                    if cf_changed:
                        break
                except Exception as e:
                    log(f"\t\t\tError checking files in commit {commit.sha} of {repo_name}: {e}", log_file)
                    continue

            if not cf_changed:
                log(f"\t\tNo CloudFormation files changed in the last {months} months for {repo_name}", log_file)

        except Exception as e:
            log(f"\t\tError checking repository {repo_name}: {e}", log_file)

    log(f"\nActive repositories with CloudFormation files changed in the last {months} months: {len(active_repos)}", log_file)

    save_to_file(active_repos, active_dump)