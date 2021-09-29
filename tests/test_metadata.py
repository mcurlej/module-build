from unittest.mock import patch

from module_build.metadata import (load_modulemd_file_from_path, generate_module_stream_version)
from module_build.modulemd import Modulemd
from tests import get_full_data_path


def test_load_modulemd_file_from_path():
    """ Test for loading modulemd packager yaml file. """

    modulemd_file_path = get_full_data_path("modulemd/perl-bootstrap.yaml")
    mmd = load_modulemd_file_from_path(modulemd_file_path)

    assert isinstance(mmd, Modulemd.PackagerV3)


@patch("module_build.metadata.time.time")
def test_generate_module_stream_version(mock_time):
    """ Test for generating a module stream version from an arbitrary unix timestamp. """

    mock_time.return_value = 1632575809.6422336
    version = generate_module_stream_version()

    expected_version = 20210925131649

    assert expected_version == version


def test_generate_module_stream_version_from_timestamp():
    """ Test for generating a module stream version from an existing timestamp. """

    git_timestamp = 1632575809
    version = generate_module_stream_version(git_timestamp)

    expected_version = 20210925131649

    assert expected_version == version
