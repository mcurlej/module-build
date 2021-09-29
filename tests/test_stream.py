from unittest.mock import patch

import pytest

from module_build.metadata import load_modulemd_file_from_path, generate_module_stream_version
from module_build.stream import ModuleStream, ModuleStreamContext
from tests import get_full_data_path


@patch("module_build.metadata.time.time")
def _mock_mmdv3_and_version(mock_time):
    modulemd_file_path = get_full_data_path("modulemd/perl-bootstrap.yaml")
    mmd = load_modulemd_file_from_path(modulemd_file_path)

    mock_time.return_value = 1632575809.6422336
    version = generate_module_stream_version()

    return mmd, version


def test_create_module_steam():

    mmd, version = _mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    expected_version = 20210925131649

    assert module_stream.name == "perl-bootstrap"
    assert module_stream.stream == "devel"
    assert len(module_stream.contexts) == 2
    assert module_stream.version == expected_version
    assert len(module_stream.components) == 178
    assert module_stream.description


def test_create_module_stream_missing_stream():
    mmd, version = _mock_mmdv3_and_version()

    with pytest.raises(Exception):
        mmd.set_stream_name("")
        ModuleStream(mmd, version)


def test_create_module_stream_missing_name():
    mmd, version = _mock_mmdv3_and_version()

    with pytest.raises(Exception):
        mmd.set_module_name("")
        ModuleStream(mmd, version)


def test_create_module_stream_context():

    mmd, version = _mock_mmdv3_and_version()
    index = mmd.convert_to_index()
    streams = index.search_streams()

    module_stream_context = ModuleStreamContext(streams[0], version)

    assert module_stream_context.mmd
    assert module_stream_context.mmd == streams[0]
    assert module_stream_context.build_opts
    assert module_stream_context.version
    assert module_stream_context.version == version
    assert module_stream_context.rpm_macros
    assert module_stream_context.name
    assert module_stream_context.name == streams[0].get_context()
    assert module_stream_context.static_context
    assert module_stream_context.dependencies
    assert type(module_stream_context.dependencies) is list
    assert type(module_stream_context.demodularized_rpms) is list
    assert module_stream_context.rpm_macros
    assert type(module_stream_context.rpm_whitelist) is list


def test_msc_get_nsvca():
    mmd, version = _mock_mmdv3_and_version()
    index = mmd.convert_to_index()
    streams = index.search_streams()

    module_stream_context = ModuleStreamContext(streams[0], version)

    assert module_stream_context.get_NSVCA() == "perl-bootstrap:devel:20210925131649:f26devel"


def test_msc_set_arch():
    mmd, version = _mock_mmdv3_and_version()
    index = mmd.convert_to_index()
    streams = index.search_streams()

    module_stream_context = ModuleStreamContext(streams[0], version)
    arch = "x86_64"
    module_stream_context.set_arch(arch)

    assert module_stream_context.arch == arch
    assert module_stream_context.mmd.get_arch() == arch
    nsvca = "perl-bootstrap:devel:20210925131649:f26devel:x86_64"
    assert module_stream_context.get_NSVCA() == nsvca
