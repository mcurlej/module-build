import os
import shutil
from unittest.mock import patch

import pytest

from module_build.builders.mock_builder import MockBuilder
from module_build.stream import ModuleStream
from tests import (fake_buildroot_run, fake_get_artifacts, get_full_data_path,
                   mock_mmdv3_and_version)


@patch("module_build.builders.mock_builder.MockBuilder.get_artifacts_nevra", new=fake_get_artifacts)
@patch("module_build.builders.mock_builder.mockbuild.config.load_config",
       return_value={"target_arch": "x86_64", "dist": "fc35"})
def test_resume_module_build_failed_first_component(mock_config, tmpdir):
    """ We test to resume the module build from the first failed component """
    cwd = tmpdir.mkdir("workdir").strpath
    rootdir = None
    mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
    external_repos = []

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    # wrapper function which sets the `fake_buildroot_run` function to fail on the perl component
    def die_on_perl(self):
        return fake_buildroot_run(self, component_to_fail="perl")

    with patch("module_build.builders.mock_builder.MockBuildroot.run",
               new=die_on_perl):
        with pytest.raises(Exception) as e:
            builder.build(module_stream, resume=False)

    err_msg = e.value.args[0]
    assert "Build of component 'perl' failed!!" == err_msg

    cntx_names = os.listdir(cwd)
    assert len(cntx_names) == 1

    build_batches_path = cwd + "/" + cntx_names[0] + "/build_batches"
    build_batches_dir = os.listdir(build_batches_path)
    assert len(build_batches_dir) == 2
    assert 'batch_1' in build_batches_dir
    assert 'batch_2' not in build_batches_dir
    assert 'repodata' in build_batches_dir

    batch_path = build_batches_path + "/batch_1"
    batch_dir = os.listdir(batch_path)
    assert len(batch_dir) == 1
    assert "perl" in batch_dir

    perl_comp_path = batch_path + "/perl"
    perl_comp_dir = os.listdir(perl_comp_path)
    assert len(perl_comp_dir) == 1
    assert "finished" not in perl_comp_dir
    assert "perl_mock.cfg" in perl_comp_dir
    assert "perl-0:1.0-1.module_fc35+f26devel.x86_64.rpm" not in perl_comp_dir

    # we run the build again on the same working directory with the resume option on
    builder_resumed = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)
    with patch("module_build.builders.mock_builder.MockBuildroot.run",
               new=fake_buildroot_run):
        builder_resumed.build(module_stream, resume=True)

    cntx_names = os.listdir(cwd)
    assert len(cntx_names) == 2

    for name in cntx_names:
        context_path = cwd + "/" + name
        context_dir = os.listdir(context_path)
        build_batches_path = context_path + "/build_batches"
        build_batches_dir = os.listdir(build_batches_path)
        for i in range(12):
            batch_name = "batch_{position}".format(position=i + 1)
            assert batch_name in build_batches_dir
        assert "repodata" in build_batches_dir
        assert "finished" in context_dir
        assert "final_repo" in context_dir

    perl_comp_dir = os.listdir(perl_comp_path)
    assert "finished" in perl_comp_dir
    assert "perl-0:1.0-1.module_fc35+f26devel.x86_64.rpm" in perl_comp_dir


@patch("module_build.builders.mock_builder.MockBuilder.get_artifacts_nevra", new=fake_get_artifacts)
@patch("module_build.builders.mock_builder.mockbuild.config.load_config",
       return_value={"target_arch": "x86_64", "dist": "fc35"})
def test_resume_module_build_failed_not_first_component(mock_config, tmpdir):
    """ We test to resume the module build from a failed component in the 4th batch """
    cwd = tmpdir.mkdir("workdir").strpath
    rootdir = None
    mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
    external_repos = []

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    # wrapper function which sets the `fake_buildroot_run` function to fail on the perl-Digest
    # component
    def die_on_perl_digest(self):
        return fake_buildroot_run(self, component_to_fail="perl-Digest")

    with patch("module_build.builders.mock_builder.MockBuildroot.run",
               new=die_on_perl_digest):
        with pytest.raises(Exception) as e:
            builder.build(module_stream, resume=False)

    err_msg = e.value.args[0]
    assert "Build of component 'perl-Digest' failed!!" == err_msg

    cntx_names = os.listdir(cwd)
    assert len(cntx_names) == 1

    build_batches_path = cwd + "/" + cntx_names[0] + "/build_batches"
    build_batches_dir = os.listdir(build_batches_path)
    assert len(build_batches_dir) == 5
    assert 'batch_1' in build_batches_dir
    assert 'batch_2' in build_batches_dir
    assert 'batch_3' in build_batches_dir
    assert 'batch_4' in build_batches_dir
    assert 'batch_5' not in build_batches_dir
    assert 'repodata' in build_batches_dir

    batch_path = build_batches_path + "/batch_4"
    batch_dir = os.listdir(batch_path)
    assert len(batch_dir) == 19
    assert "perl-Digest" in batch_dir

    perl_digest_comp_path = batch_path + "/perl-Digest"
    perl_digest_comp_dir = os.listdir(perl_digest_comp_path)
    assert len(perl_digest_comp_dir) == 1
    assert "finished" not in perl_digest_comp_dir
    assert "perl-Digest_mock.cfg" in perl_digest_comp_dir
    assert "perl-Digest-0:1.0-1.module_fc35+f26devel.x86_64.rpm" not in perl_digest_comp_dir

    # we run the build again on the same working directory with the resume option on
    builder_resumed = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)
    with patch("module_build.builders.mock_builder.MockBuildroot.run",
               new=fake_buildroot_run):
        builder_resumed.build(module_stream, resume=True)

    cntx_names = os.listdir(cwd)
    assert len(cntx_names) == 2

    for name in cntx_names:
        context_path = cwd + "/" + name
        context_dir = os.listdir(context_path)
        build_batches_path = context_path + "/build_batches"
        build_batches_dir = os.listdir(build_batches_path)
        for i in range(12):
            batch_name = "batch_{position}".format(position=i + 1)
            assert batch_name in build_batches_dir
        assert "repodata" in build_batches_dir
        assert "finished" in context_dir
        assert "final_repo" in context_dir

    perl_digest_comp_dir = os.listdir(perl_digest_comp_path)
    assert "perl-Digest-0:1.0-1.module_fc35+f26devel.x86_64.rpm" in perl_digest_comp_dir
    assert "finished" in perl_digest_comp_dir


@patch("module_build.builders.mock_builder.MockBuilder.get_artifacts_nevra", new=fake_get_artifacts)
@patch("module_build.builders.mock_builder.mockbuild.config.load_config",
       return_value={"target_arch": "x86_64", "dist": "fc35"})
def test_resume_module_build_failed_to_create_batch_yaml_file(mock_config, tmpdir):
    """ We test to resume the module build on a failed batch closure, where only the yaml file is
    missing """
    cwd = tmpdir.mkdir("workdir").strpath
    rootdir = None
    mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
    external_repos = []

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    # wrapper function which sets the `fake_buildroot_run` function to fail on the perl-generators
    # component
    def die_on_perl_generators(self):
        return fake_buildroot_run(self, component_to_fail="perl-generators")

    with patch("module_build.builders.mock_builder.MockBuildroot.run",
               new=die_on_perl_generators):
        with pytest.raises(Exception):
            builder.build(module_stream, resume=False)

    cntx_names = os.listdir(cwd)
    assert len(cntx_names) == 1

    build_batches_path = cwd + "/" + cntx_names[0] + "/build_batches"
    build_batches_dir = os.listdir(build_batches_path)
    assert len(build_batches_dir) == 4
    assert 'batch_1' in build_batches_dir
    assert 'batch_2' in build_batches_dir
    assert 'batch_3' in build_batches_dir
    assert 'repodata' in build_batches_dir
    # we prepare the directories to the state we want to resume from.
    batch_3_path = build_batches_path + "/batch_3"
    shutil.rmtree(batch_3_path)
    batch_2_path = build_batches_path + "/batch_2"
    finished_file_path = batch_2_path + '/finished'
    os.remove(finished_file_path)

    # the version on a batch yaml file is dynamic, so we have to search for it.
    for file_name in os.listdir(batch_2_path):
        if file_name.endswith("yaml"):
            yaml_file_path = batch_2_path + "/" + file_name

    assert yaml_file_path
    os.remove(yaml_file_path)

    # we run the build again on the same working directory with the resume option on
    builder_resumed = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)
    with patch("module_build.builders.mock_builder.MockBuildroot.run",
               new=fake_buildroot_run):
        builder_resumed.build(module_stream, resume=True)

    cntx_names = os.listdir(cwd)
    assert len(cntx_names) == 2

    for name in cntx_names:
        context_path = cwd + "/" + name
        context_dir = os.listdir(context_path)
        build_batches_path = context_path + "/build_batches"
        build_batches_dir = os.listdir(build_batches_path)
        for i in range(12):
            batch_name = "batch_{position}".format(position=i + 1)
            assert batch_name in build_batches_dir
        assert "repodata" in build_batches_dir
        assert "finished" in context_dir
        assert "final_repo" in context_dir

    # the version on a batch yaml file is dynamic, so we have to search for it.
    for file_name in os.listdir(batch_2_path):
        if file_name.endswith("yaml"):
            yaml_file_path = batch_2_path + "/" + file_name

    assert yaml_file_path
    assert os.path.isfile(yaml_file_path)
    assert os.path.isfile(finished_file_path)


@patch("module_build.builders.mock_builder.MockBuilder.get_artifacts_nevra", new=fake_get_artifacts)
@patch("module_build.builders.mock_builder.mockbuild.config.load_config",
       return_value={"target_arch": "x86_64", "dist": "fc35"})
def test_resume_module_build_continue_with_new_batch(mock_config, tmpdir):
    """ We test to resume module build when a new batch directory has failed to create. """
    cwd = tmpdir.mkdir("workdir").strpath
    rootdir = None
    mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
    external_repos = []

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    # wrapper function which sets the `fake_buildroot_run` function to fail on the perl-generators
    # component
    def die_on_perl_generators(self):
        return fake_buildroot_run(self, component_to_fail="perl-generators")

    with patch("module_build.builders.mock_builder.MockBuildroot.run",
               new=die_on_perl_generators):
        with pytest.raises(Exception):
            builder.build(module_stream, resume=False)

    cntx_names = os.listdir(cwd)
    assert len(cntx_names) == 1

    build_batches_path = cwd + "/" + cntx_names[0] + "/build_batches"
    build_batches_dir = os.listdir(build_batches_path)
    assert len(build_batches_dir) == 4
    assert 'batch_1' in build_batches_dir
    assert 'batch_2' in build_batches_dir
    assert 'batch_3' in build_batches_dir
    assert 'repodata' in build_batches_dir
    # we prepare the directories to the state we want to resume from.
    batch_3_path = build_batches_path + "/batch_3"
    shutil.rmtree(batch_3_path)

    # we run the build again on the same working directory with the resume option on
    builder_resumed = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)
    with patch("module_build.builders.mock_builder.MockBuildroot.run",
               new=fake_buildroot_run):
        builder_resumed.build(module_stream, resume=True)

    cntx_names = os.listdir(cwd)
    assert len(cntx_names) == 2

    for name in cntx_names:
        context_path = cwd + "/" + name
        context_dir = os.listdir(context_path)
        build_batches_path = context_path + "/build_batches"
        build_batches_dir = os.listdir(build_batches_path)
        for i in range(12):
            batch_name = "batch_{position}".format(position=i + 1)
            assert batch_name in build_batches_dir
        assert "repodata" in build_batches_dir
        assert "finished" in context_dir
        assert "final_repo" in context_dir

    assert os.path.isdir(batch_3_path)
    finished_file_path = batch_3_path + "/finished"
    # the version on a batch yaml file is dynamic, so we have to search for it.
    for file_name in os.listdir(batch_3_path):
        if file_name.endswith("yaml"):
            yaml_file_path = batch_3_path + "/" + file_name

    assert yaml_file_path
    assert os.path.isfile(yaml_file_path)
    assert os.path.isfile(finished_file_path)


@patch("module_build.builders.mock_builder.MockBuilder.get_artifacts_nevra", new=fake_get_artifacts)
@patch("module_build.builders.mock_builder.mockbuild.config.load_config",
       return_value={"target_arch": "x86_64", "dist": "fc35"})
def test_resume_module_build_continue_with_next_context(mock_config, tmpdir):
    cwd = tmpdir.mkdir("workdir").strpath
    rootdir = None
    mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
    external_repos = []

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    # wrapper function which sets the `fake_buildroot_run` function to fail on the perl-generators
    # component
    def die_on_perl_second_context(self):
        return fake_buildroot_run(self, component_to_fail="perl", context="f27devel")

    with patch("module_build.builders.mock_builder.MockBuildroot.run",
               new=die_on_perl_second_context):
        with pytest.raises(Exception):
            builder.build(module_stream, resume=False)

    cntx_names = os.listdir(cwd)
    assert len(cntx_names) == 2

    second_context_path = cwd + "/" + cntx_names[0]
    shutil.rmtree(second_context_path)

    first_context_path = cwd + "/" + cntx_names[1]
    first_context_dir = os.listdir(first_context_path)
    assert "finished" in first_context_dir

    # we run the build again on the same working directory with the resume option on
    builder_resumed = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)
    with patch("module_build.builders.mock_builder.MockBuildroot.run",
               new=fake_buildroot_run):
        builder_resumed.build(module_stream, resume=True)

    cntx_names = os.listdir(cwd)
    assert len(cntx_names) == 2

    for name in cntx_names:
        context_path = cwd + "/" + name
        context_dir = os.listdir(context_path)
        build_batches_path = context_path + "/build_batches"
        build_batches_dir = os.listdir(build_batches_path)
        for i in range(12):
            batch_name = "batch_{position}".format(position=i + 1)
            assert batch_name in build_batches_dir
        assert "repodata" in build_batches_dir
        assert "finished" in context_dir
        assert "final_repo" in context_dir


@pytest.mark.parametrize("context", ["f26devel", "f27devel"])
@patch("module_build.builders.mock_builder.MockBuilder.get_artifacts_nevra", new=fake_get_artifacts)
@patch("module_build.builders.mock_builder.mockbuild.config.load_config",
       return_value={"target_arch": "x86_64", "dist": "fc35"})
def test_resume_module_build_do_not_continue_with_next_context_when_context_specified(mock_config,
                                                                                      context,
                                                                                      tmpdir):
    """ We test that the resume function will only resumes the specified context and does not build
    anything else """

    cwd = tmpdir.mkdir("workdir").strpath
    rootdir = None
    mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
    external_repos = []

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    # wrapper function which sets the `fake_buildroot_run` function to fail on the perl-generators
    # component
    def die_on_perl_generators(self):
        return fake_buildroot_run(self, component_to_fail="perl-generators")

    with patch("module_build.builders.mock_builder.MockBuildroot.run",
               new=die_on_perl_generators):
        with pytest.raises(Exception):
            builder.build(module_stream, resume=False, context_to_build=context)

    cntx_names = os.listdir(cwd)
    assert len(cntx_names) == 1

    build_batches_path = cwd + "/" + cntx_names[0] + "/build_batches"
    build_batches_dir = os.listdir(build_batches_path)
    assert len(build_batches_dir) == 4
    assert 'batch_1' in build_batches_dir
    assert 'batch_2' in build_batches_dir
    assert 'batch_3' in build_batches_dir
    assert 'repodata' in build_batches_dir
    # we prepare the directories to the state we want to resume from.
    batch_3_path = build_batches_path + "/batch_3"
    shutil.rmtree(batch_3_path)

    # we run the build again on the same working directory with the resume option on
    builder_resumed = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)
    with patch("module_build.builders.mock_builder.MockBuildroot.run",
               new=fake_buildroot_run):
        builder_resumed.build(module_stream, resume=True, context_to_build=context)

    cntx_names = os.listdir(cwd)
    assert len(cntx_names) == 1
    assert context in cntx_names[0]

    for name in cntx_names:
        context_path = cwd + "/" + name
        context_dir = os.listdir(context_path)
        build_batches_path = context_path + "/build_batches"
        build_batches_dir = os.listdir(build_batches_path)
        for i in range(12):
            batch_name = "batch_{position}".format(position=i + 1)
            assert batch_name in build_batches_dir
        assert "repodata" in build_batches_dir
        assert "finished" in context_dir
        assert "final_repo" in context_dir


@pytest.mark.parametrize("context", ["f26devel", "f27devel"])
@patch("module_build.builders.mock_builder.MockBuilder.get_artifacts_nevra", new=fake_get_artifacts)
@patch("module_build.builders.mock_builder.mockbuild.config.load_config",
       return_value={"target_arch": "x86_64", "dist": "fc35"})
def test_resume_module_build_first_specify_context_and_resume_without(mock_config, context, tmpdir):
    cwd = tmpdir.mkdir("workdir").strpath
    rootdir = None
    mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
    external_repos = []

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    # wrapper function which sets the `fake_buildroot_run` function to fail on the perl-generators
    # component
    def die_on_perl_generators(self):
        return fake_buildroot_run(self, component_to_fail="perl-generators")

    with patch("module_build.builders.mock_builder.MockBuildroot.run",
               new=die_on_perl_generators):
        with pytest.raises(Exception):
            builder.build(module_stream, resume=False, context_to_build=context)

    cntx_names = os.listdir(cwd)
    assert len(cntx_names) == 1

    build_batches_path = cwd + "/" + cntx_names[0] + "/build_batches"
    build_batches_dir = os.listdir(build_batches_path)
    assert len(build_batches_dir) == 4
    assert 'batch_1' in build_batches_dir
    assert 'batch_2' in build_batches_dir
    assert 'batch_3' in build_batches_dir
    assert 'repodata' in build_batches_dir
    # we prepare the directories to the state we want to resume from.
    batch_3_path = build_batches_path + "/batch_3"
    shutil.rmtree(batch_3_path)

    # we run the build again on the same working directory with the resume option on
    builder_resumed = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)
    with patch("module_build.builders.mock_builder.MockBuildroot.run",
               new=fake_buildroot_run):
        builder_resumed.build(module_stream, resume=True)

    cntx_names = os.listdir(cwd)
    assert len(cntx_names) == 2

    for name in cntx_names:
        context_path = cwd + "/" + name
        context_dir = os.listdir(context_path)
        build_batches_path = context_path + "/build_batches"
        build_batches_dir = os.listdir(build_batches_path)
        for i in range(12):
            batch_name = "batch_{position}".format(position=i + 1)
            assert batch_name in build_batches_dir
        assert "repodata" in build_batches_dir
        assert "finished" in context_dir
        assert "final_repo" in context_dir
