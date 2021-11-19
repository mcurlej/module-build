import os
from unittest.mock import patch

from module_build.metadata import load_modulemd_file_from_path, generate_module_stream_version


class TestException(Exception):
    pass


def get_full_data_path(path):
    dir_path = os.path.dirname(os.path.abspath(__file__))

    full_path = os.path.join(dir_path, "data", path)

    return full_path


def mock_mmdv3_and_version(modulemd_path="modulemd/perl-bootstrap.yaml",
                           timestamp=1632575809.6422336):

    modulemd_full_path = get_full_data_path(modulemd_path)
    mmd = load_modulemd_file_from_path(modulemd_full_path)

    with patch("module_build.metadata.time.time") as mock_time:
        mock_time.return_value = timestamp
        version = generate_module_stream_version()

    return mmd, version
