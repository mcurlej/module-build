import os


def get_full_data_path(path):
    dir_path = os.path.dirname(os.path.abspath(__file__))

    full_path = os.path.join(dir_path, "data", path)

    return full_path
