import os
from collections import namedtuple
from unittest.mock import patch

import pytest
from module_build.cli import get_arg_parser, main
from module_build.stream import ModuleStream

from tests import TestException, get_full_data_path


def fake_raise_exception(self):
    raise TestException("Fake Exception Yay!")


@patch("module_build.builders.mock_builder.mockbuild.config.load_config",
       return_value={"target_arch": "x86_64", "dist": "fc35"})
@patch("module_build.builders.mock_builder.MockBuildroot.run", new=fake_raise_exception)
def test_debug_option(mock_config, tmpdir):
    """
    We test if the cli will call the debugger after encountering an exception when the
    `--debug` option is set.
    """
    cwd = tmpdir.mkdir("workdir")

    full_path = get_full_data_path("modulemd/flatpak-runtime.yaml")

    Args = namedtuple("Args", ["modulemd", "mock_cfg", "debug", "workdir", "resume",
                               "module_name", "module_stream", "module_version",
                               "add_repo", "rootdir", "module_context", "srpm_dir", "workers", "no_stdout"])

    args = Args(modulemd=full_path,
                mock_cfg="/etc/mock/fedora-35-x86_64.cfg",
                debug=True,
                workdir=cwd,
                resume=False,
                module_name="flatpak-runtime",
                module_stream="devel",
                module_version=None,
                rootdir=None,
                add_repo=[],
                module_context=None,
                srpm_dir=None,
                workers=1,
                no_stdout=False)

    with patch("module_build.cli.get_arg_parser") as mock_parser:
        mock_parser.return_value.parse_args.return_value = args

        with patch("module_build.cli.pdb") as mock_pdb:
            main()
            mock_pdb.set_trace.assert_called_once()


@patch("module_build.builders.mock_builder.mockbuild.config.load_config",
       return_value={"target_arch": "x86_64", "dist": "fc35"})
@patch("module_build.builders.mock_builder.MockBuildroot.run", new=fake_raise_exception)
def test_reraise_exception(mock_config, tmpdir):
    """
    We test if the cli will reraise the caught exception if there is no debug mode set.
    """
    cwd = tmpdir.mkdir("workdir")

    full_path = get_full_data_path("modulemd/flatpak-runtime.yaml")

    Args = namedtuple("Args", ["modulemd", "mock_cfg", "debug", "workdir", "resume",
                               "module_name", "module_stream", "module_version",
                               "add_repo", "rootdir", "module_context", "srpm_dir", "workers", "no_stdout"])

    args = Args(modulemd=full_path,
                mock_cfg="/etc/mock/fedora-35-x86_64.cfg",
                debug=False,
                workdir=cwd,
                resume=False,
                module_name="flatpak-runtime",
                module_stream="devel",
                module_version=None,
                rootdir=None,
                add_repo=[],
                module_context=None,
                srpm_dir=None,
                workers=1,
                no_stdout=False)

    with patch("module_build.cli.get_arg_parser") as mock_parser:
        mock_parser.return_value.parse_args.return_value = args

        with pytest.raises(TestException) as e:
            main()

    assert type(e.type()) is TestException
    assert "Fake Exception Yay!" in e.exconly()


def test_convert_relative_paths_to_absolute():
    """
    We test that all relative paths provided to the script will be converted to absolute paths.
    """

    dir_path = os.getcwd()
    parser = get_arg_parser()
    input_args = ["-f", "./relative/path", "-c" "./relative/path", "--add-repo",
                  "/not/relative/path", "--add-repo", "./relative/path", "."]
    args = parser.parse_args(input_args)

    assert args.modulemd == dir_path + "/relative/path"
    assert args.mock_cfg == dir_path + "/relative/path"
    assert type(args.add_repo) is list
    expected_paths = ["/not/relative/path", dir_path + "/relative/path"]
    for p in args.add_repo:
        assert p in expected_paths
    assert args.workdir == dir_path


def test_choose_context_to_build(tmpdir):
    """
    We test that the builder is called with a specific context
    """
    cwd = tmpdir.mkdir("workdir")

    full_path = get_full_data_path("modulemd/perl-bootstrap.yaml")

    Args = namedtuple("Args", ["modulemd", "mock_cfg", "debug", "workdir", "resume",
                               "module_name", "module_stream", "module_version",
                               "add_repo", "rootdir", "module_context", "srpm_dir", "workers", "no_stdout"])

    context_to_build = "f26devel"

    args = Args(modulemd=full_path,
                mock_cfg="/etc/mock/fedora-35-x86_64.cfg",
                debug=False,
                workdir=cwd,
                resume=False,
                module_name="flatpak-runtime",
                module_stream="devel",
                module_version=None,
                rootdir=None,
                add_repo=[],
                module_context=context_to_build,
                srpm_dir=None,
                workers=1,
                no_stdout=False)

    with patch("module_build.cli.get_arg_parser") as mock_parser:
        mock_parser.return_value.parse_args.return_value = args

        with patch("module_build.builders.mock_builder.MockBuilder.build") as mock_build:
            main()

    required_args = mock_build.call_args[0]
    optional_args = mock_build.call_args[1]

    assert type(required_args[0]) is ModuleStream
    assert not required_args[1]
    assert "context_to_build" in optional_args
    assert optional_args["context_to_build"] == context_to_build
