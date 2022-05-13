import pytest
from module_build.mock.config import MockConfig
from tests import get_full_data_path


@pytest.fixture
def mock_cfg(path="mock_cfg/fedora-35-x86_64.cfg"):
    mock_cfg_path = get_full_data_path(path)
    return MockConfig(mock_cfg_path)
