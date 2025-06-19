import os
import yaml
import shutil
import stat
from subprocess import Popen
from threading import Thread
from git import Repo as GitRepo
from checkov.terraform.runner import Runner as TfRunner
from checkov.cloudformation.runner import Runner as CfRunner
from checkov.runner_filter import RunnerFilter

from utils.logger import log
from utils.yaml_utils import load_yaml, save_to_file

REPO_CHECK_FILES = 'https://github.com/search-rug/iac-cost-linter'

FILE_BASELINE_TF = 'results/baseline_tf/activity/file/active_files.yml'
FILE_BASELINE_CF = 'results/baseline_cf/activity/file/active_files.yml'
FILE_EXTENDED_TF = 'results/extended_tf/activity/file/active_files.yml'
FILE_EXTENDED_CF = 'results/extended_cf/activity/file/active_files.yml'

CHECKS_TF = ['CKV2_AWS_61', 'CKV_AWS_804', 'CKV_AWS_801', 'CKV_AWS_802', 'CKV_AWS_803']
CHECKS_CF = ['CKV_AWS_805', 'CKV_AWS_806', 'CKV_AWS_807']

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKOV_CHECK_DIR = os.path.join(CURRENT_DIR, 'checkov_check')
CHECKS_TF_DIR = os.path.join(CHECKOV_CHECK_DIR, 'checks', 'terraform')
CHECKS_CF_DIR = os.path.join(CHECKOV_CHECK_DIR, 'checks', 'cloudformation')
CHECKS_CLONE_PATH = os.path.join(CHECKOV_CHECK_DIR, 'checks')

LOGS_BASELINE_TF = 'results/baseline_tf/checkov/logs.txt'
LOGS_BASELINE_CF = 'results/baseline_cf/checkov/logs.txt'
LOGS_EXTENDED_TF = 'results/extended_tf/checkov/logs.txt'
LOGS_EXTENDED_CF = 'results/extended_cf/checkov/logs.txt'

RESULTS_BASELINE_TF = 'results/baseline_tf/checkov/results.yml'
RESULTS_BASELINE_CF = 'results/baseline_cf/checkov/results.yml'
RESULTS_EXTENDED_TF = 'results/extended_tf/checkov/results.yml'
RESULTS_EXTENDED_CF = 'results/extended_cf/checkov/results.yml'

def force_remove_readonly(func, path, _):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def delete_repo(log_file):
    if os.path.exists("temp_repo"):
        try:
            shutil.rmtree("temp_repo", onerror=force_remove_readonly)
        except PermissionError as e:
            log("Permission denied." + str(e), log_file)
        except FileNotFoundError:
            log("Already deleted.", log_file)
        except Exception as e:
            log("Other error:" + str(e), log_file)

def cloneRepoThread(repoUrl, log_file):
    try:
        delete_repo(log_file)
        log(f"\tCloning repository {repoUrl}", log_file)
        GitRepo.clone_from(repoUrl, "temp_repo", depth=1)
        log(f"\t\tCloned repository {repoUrl}", log_file)
    except Exception as e:
        log(f"\t\tError cloning repository {repoUrl}: {e}", log_file)

def find_terraform_files():
    terraform_files = []
    for root, _, files in os.walk("temp_repo"):
        for file in files:
            if file.endswith('.tf'):
                terraform_files.append(os.path.join(root, file))
    return terraform_files

def is_cf_file(file_path):
    try:
        with open(file_path, 'r') as file:
            content = file.read()
            try:
                yaml_file = yaml.safe_load(content)
                if isinstance(yaml_file, dict) and "Resources" in yaml_file:
                    for resource in yaml_file["Resources"].values():
                        if isinstance(resource, dict) and "Type" in resource:
                            if str(resource["Type"]).startswith("AWS::"):
                                return True
                            
                return False

            except yaml.YAMLError as e:
                # check if the content starts with "AWSTemplateFormatVersion: 2010-09-09"
                if content.startswith("AWSTemplateFormatVersion: 2010-09-09"):
                    return True
                
                elif "Resources" in content and "AWS::" in content:
                    return True
    except Exception as e:
        return False

def find_cf_files():
    cf_files = []
    for root, _, files in os.walk("temp_repo"):
        for file in files:
            if file.endswith('.yaml') or file.endswith('.yml'):
                file_path = os.path.join(root, file)
                if is_cf_file(file_path):
                    cf_files.append(file_path)
    return cf_files

def serialize_check(check_list):
    serialized_checks = []
    for check in check_list:
        serialized_check = {
            'check_id': check.check_id,
            'resource': check.resource,
            'file_path': check.file_path,
            'file_line_range': f"{check.file_line_range[0]}-{check.file_line_range[1]}" if check.file_line_range else None
        }

        serialized_checks.append(serialized_check)
    return serialized_checks

def run_linter(tool):
    if not os.path.exists(CHECKS_CLONE_PATH):
        log("Cloning checks repository...")
        GitRepo.clone_from(REPO_CHECK_FILES, CHECKS_CLONE_PATH, depth=1)
    if (tool == 'baseline_tf'):
        file_path = FILE_BASELINE_TF
        log_file = LOGS_BASELINE_TF
    elif (tool == 'baseline_cf'):
        file_path = FILE_BASELINE_CF
        log_file = LOGS_BASELINE_CF
    elif (tool == 'extended_tf'):
        file_path = FILE_EXTENDED_TF
        log_file = LOGS_EXTENDED_TF
    elif (tool == 'extended_cf'):
        file_path = FILE_EXTENDED_CF
        log_file = LOGS_EXTENDED_CF
    else:
        log(f"Unsupported tool: {tool}. Please use 'tf' for Terraform, 'cf' for CloudFormation, or 'unaware' for unaware repositories.", log_file)
        exit(1)
    data = load_yaml(file_path)
    for entry in data:
        repo = entry['repo']
        log(f"Processing repository: {repo}", log_file)
        cloningThread = Thread(target=cloneRepoThread, args=(repo, log_file))
        cloningThread.start()
        # timeout after 30 minutes if the cloning process is stuck
        cloningThread.join(timeout=1800)
        if cloningThread.is_alive():
            cloningThread.terminate()
            log(f"\t\tCloning repository {repo} timed out after 30 minutes.", log_file)
            continue
        log(f"\t\tSuccessfully cloned repository {repo}", log_file)

        if tool == 'baseline_tf' or tool == 'extended_tf':
            terraform_files = find_terraform_files()
            if terraform_files:
                log(f"\t\tFound {len(terraform_files)} Terraform files in repository {repo}.", log_file)
                passed_checks = []
                failed_checks = []
                for file in terraform_files:
                    try:
                        runner_filter = RunnerFilter(checks=CHECKS_TF)
                        runner = TfRunner()
                        report = runner.run(root_folder=None, files=[file], runner_filter=runner_filter, external_checks_dir=[CHECKS_TF_DIR])
                    
                        passed = report.passed_checks
                        failed = report.failed_checks

                        for check in passed:
                            check.file_path = file
                        for check in failed:
                            check.file_path = file

                        passed_checks.extend(report.passed_checks)
                        failed_checks.extend(report.failed_checks)

                    except Exception as e:
                        log(f"\t\tError running checks on: {e}")
                        continue
                
                # Print the results
                log("\t\t\tPassed checks:")
                for check in passed_checks:
                    log(f"\t\t\t\t- {check.check_id}: {check.resource} - {check.file_path}:{check.file_line_range}")

                log("\t\t\tFailed checks:")
                for check in failed_checks:
                    log(f"\t\t\t\t- {check.check_id}: {check.resource} - {check.file_path}:{check.file_line_range}")

                # Append to the entry
                entry['checks'] = {
                    'passed_checks': serialize_check(passed_checks),
                    'failed_checks': serialize_check(failed_checks)
                }

            else:
                log(f"\t\tNo Terraform files found in repository {repo}.")
        elif tool == 'baseline_cf' or tool == 'extended_cf':
            cf_files = find_cf_files()
            if cf_files:
                log(f"\t\tFound {len(cf_files)} CloudFormation files in repository {repo}.")
                passed_checks = []
                failed_checks = []
                for file in cf_files:
                    try:
                        runner_filter = RunnerFilter(checks=CHECKS_CF)
                        runner = CfRunner()
                        report = runner.run(root_folder=None, files=[file], runner_filter=runner_filter, external_checks_dir=[CHECKS_CF_DIR])

                        passed = report.passed_checks
                        failed = report.failed_checks

                        for check in passed:
                            check.file_path = file

                        for check in failed:
                            check.file_path = file
                            
                        passed_checks.extend(report.passed_checks)
                        failed_checks.extend(report.failed_checks)

                    except Exception as e:
                        log(f"\t\tError running checks on: {e}")
                        continue

                # Print the results
                log("\t\t\tPassed checks:", log_file)
                for check in passed_checks:
                    log(f"\t\t\t\t- {check.check_id}: {check.resource} - {check.file_path}:{check.file_line_range}", log_file)
                log("\t\t\tFailed checks:", log_file)
                for check in failed_checks:
                    log(f"\t\t\t\t- {check.check_id}: {check.resource} - {check.file_path}:{check.file_line_range}", log_file)

                # Append to the entry
                entry['checks'] = {
                    'passed_checks': serialize_check(passed_checks),
                    'failed_checks': serialize_check(failed_checks)
                }

            else:
                log(f"\t\tNo CloudFormation files found in repository {repo}.", log_file)

    # Save the results to the respective files
    if tool == 'tf':
        save_to_file(data, RESULTS_BASELINE_TF)
        log(f"Results saved to {RESULTS_BASELINE_TF}", log_file)
    elif tool == 'cf':
        save_to_file(data, RESULTS_BASELINE_CF)
        log(f"Results saved to {RESULTS_BASELINE_CF}", log_file)
    elif tool == 'unaware':
        save_to_file(data, RESULTS_EXTENDED_TF)
        log(f"Results saved to {RESULTS_EXTENDED_TF}", log_file)
    elif tool == 'extended_tf':
        save_to_file(data, RESULTS_EXTENDED_TF)
        log(f"Results saved to {RESULTS_EXTENDED_TF}", log_file)
    elif tool == 'extended_cf':
        save_to_file(data, RESULTS_EXTENDED_CF)
        log(f"Results saved to {RESULTS_EXTENDED_CF}", log_file)

    log("Finished processing repositories.", log_file)