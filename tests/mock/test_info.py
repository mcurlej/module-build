import pytest
from pathlib import Path
from module_build.mock.info import MockBuildInfo


@pytest.mark.parametrize("path_as_str", [True, False])
@pytest.mark.parametrize("srpms", [("flatpak", "nginx-devel"), ("office-sr3", "gdb")])
def test_adding_srpm(srpms, path_as_str):
    mock_info = MockBuildInfo()

    for srpm in srpms:
        path = f"/tmp/{srpm}" if path_as_str else Path(f"/tmp/{srpm}")
        mock_info.add_srpm(srpm, path)

    for srpm in srpms:
        assert f"/tmp/{srpm}" == mock_info.get_srpm_path(srpm)

    assert mock_info.get_srpm_count() == 2


@pytest.mark.parametrize("path_as_str", [True, False])
@pytest.mark.parametrize("srpms", [("flatpak", "flatpak"), ("nginx-dev", "nginx-dev")])
def test_adding_srpm_duplicate(srpms, path_as_str):
    mock_info = MockBuildInfo()

    for idx, srpm in enumerate(srpms):
        path = f"/tmp/{srpm}_{idx}" if path_as_str else Path(f"/tmp/{srpm}_{idx}")
        mock_info.add_srpm(srpm, path)

    assert mock_info.get_srpm_count() == 1
    assert "_1" in mock_info.get_srpm_path(srpms[0], "_1")
    assert "_0" in mock_info.get_srpm_path(srpms[0], "_0")
    assert mock_info.get_srpm_path(srpms[0], "_3") is None

    for srpm in srpms:
        assert "/tmp/" in mock_info.get_srpm_path(srpm)


@pytest.mark.parametrize("srpms", [("flatpak", "nginx-devel"), ("office-sr3", "gdb")])
def test_adding_srpm_bad_path(srpms):
    mock_info = MockBuildInfo()

    with pytest.raises(Exception) as e:
        for srpm in srpms:
            invalid_path = 44
            mock_info.add_srpm(srpm, invalid_path)

    err_msg = e.value.args[0]
    assert "Wrong path object" in err_msg
