def extract_repo_name(url):
    # Convert URL to "owner/repo" format
    if url.startswith("https://github.com/"):
        return url.replace("https://github.com/", "").strip("/")
    return url

def extract_repo(data):
    repos = [entry['repo'] for entry in data]
    return repos