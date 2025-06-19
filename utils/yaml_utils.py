import yaml

def load_yaml(file_path):
    with open(file_path, 'r') as file:
        data = yaml.safe_load(file)
    return data

def save_to_file(data, filename):
    with open(filename, 'w') as file:
        yaml.dump(data, file)

def add_to_file(data, filename):
    with open(filename, 'a') as file:
        yaml.dump(data, file, default_flow_style=False)