import os

def log(message, log_path=None):
    if log_path is None:
        base_dir = os.path.dirname(__file__)
        log_path = os.path.abspath(os.path.join(base_dir, "..", "logs.txt"))

    with open(log_path, 'a') as file:
        file.write(message + '\n')