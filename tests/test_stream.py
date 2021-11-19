import pytest

from module_build.stream import ModuleStream, ModuleStreamContext
from tests import mock_mmdv3_and_version


def test_create_module_steam():

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    expected_version = 20210925131649

    assert module_stream.name == "perl-bootstrap"
    assert module_stream.stream == "devel"
    assert len(module_stream.contexts) == 2
    assert module_stream.version == expected_version
    assert len(module_stream.components) == 178
    assert module_stream.description


def test_create_module_stream_missing_stream():
    mmd, version = mock_mmdv3_and_version()

    with pytest.raises(Exception):
        mmd.set_stream_name("")
        ModuleStream(mmd, version)


def test_create_module_stream_missing_name():
    mmd, version = mock_mmdv3_and_version()

    with pytest.raises(Exception):
        mmd.set_module_name("")
        ModuleStream(mmd, version)


def test_create_module_stream_context():

    mmd, version = mock_mmdv3_and_version()
    index = mmd.convert_to_index()
    streams = index.search_streams()
    platform = "f34"

    module_stream_context = ModuleStreamContext(streams[0], version, platform)

    assert module_stream_context.mmd
    assert module_stream_context.mmd == streams[0]
    assert module_stream_context.build_opts
    assert module_stream_context.version
    assert module_stream_context.version == version
    assert module_stream_context.rpm_macros
    assert module_stream_context.context_name
    assert module_stream_context.context_name == streams[0].get_context()
    assert module_stream_context.module_name
    assert module_stream_context.module_name == streams[0].get_module_name()
    assert module_stream_context.static_context
    assert module_stream_context.dependencies
    assert type(module_stream_context.dependencies) is dict
    assert "buildtime" in module_stream_context.dependencies
    assert "runtime" in module_stream_context.dependencies
    assert module_stream_context.stream
    assert module_stream_context.stream == streams[0].get_stream_name()
    assert type(module_stream_context.demodularized_rpms) is list
    assert type(module_stream_context.rpm_macros) is list
    assert type(module_stream_context.rpm_whitelist) is list
    assert module_stream_context.platform == platform


def test_msc_get_nsvca():
    mmd, version = mock_mmdv3_and_version()
    index = mmd.convert_to_index()
    streams = index.search_streams()
    platform = "f34"

    module_stream_context = ModuleStreamContext(streams[0], version, platform)

    assert module_stream_context.get_NSVCA() == "perl-bootstrap:devel:20210925131649:f26devel"


def test_msc_set_arch():
    mmd, version = mock_mmdv3_and_version()
    index = mmd.convert_to_index()
    streams = index.search_streams()
    platform = "f34"

    module_stream_context = ModuleStreamContext(streams[0], version, platform)
    arch = "x86_64"
    module_stream_context.set_arch(arch)

    assert module_stream_context.arch == arch
    assert module_stream_context.mmd.get_arch() == arch
    nsvca = "perl-bootstrap:devel:20210925131649:f26devel:x86_64"
    assert module_stream_context.get_NSVCA() == nsvca
