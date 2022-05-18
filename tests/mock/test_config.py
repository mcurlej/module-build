
import tempfile

from module_build.constants import (KEY_MACROS_PREFIX, KEY_SCM_BRANCH,
                                    KEY_SCM_ENABLE, KEY_SCM_METHOD,
                                    KEY_SCM_PACKAGE)


def test_enable_disable_mbs(mock_cfg):
    """
        Test enabling/disabling MBS funtionality in mock config.
    """
    mock_cfg.enable_mbs("dist", "pkg_name", "branch_name")

    mbs_keys = {KEY_SCM_ENABLE, KEY_SCM_METHOD, KEY_SCM_PACKAGE,
                KEY_SCM_BRANCH}

    assert 4 == len(mock_cfg.content)
    assert mbs_keys.issubset(mock_cfg.content)

    mock_cfg.disable_mbs()

    assert 0 == len(mock_cfg.content)
    for key in mbs_keys:
        assert key not in mock_cfg.content


def test_adding_macros(mock_cfg):
    """
        Test adding macros to mock config using add_macros method.
    """
    macros = ("__kick_runtime true", "_modify go")

    mock_cfg.add_macros(macros)

    for macro in macros:
        key, value = macro.split(" ")
        key = f"{KEY_MACROS_PREFIX}['{key}']"
        assert key in mock_cfg.content
        assert mock_cfg.content[key] == value


def test_write_config(mock_cfg):
    """
        Test writing mock config file to directory and validate file content.
    """
    mock_cfg.enable_mbs("gistgit", "nginx", "f55")

    with tempfile.TemporaryDirectory() as tmp_dir:
        mock_cfg_path = mock_cfg.write_config(tmp_dir, "nginx")

        with open(mock_cfg_path) as f:
            lines = f.readlines()

            assert KEY_SCM_ENABLE in lines[0]
            assert "include" in lines[4]
