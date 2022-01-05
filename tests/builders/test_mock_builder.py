import os
from unittest.mock import patch

import pytest

from module_build.builders.mock_builder import MockBuilder
from module_build.stream import ModuleStream
from module_build.metadata import load_modulemd_file_from_path
from tests import (mock_mmdv3_and_version, get_full_data_path, fake_get_artifacts,
                   assert_modular_dependencies, fake_buildroot_run)


def test_create_mock_builder(tmpdir):
    """ Test for an instance of MockBuilder. This serves as a sanity test. """
    cwd = tmpdir.mkdir("workdir")
    rootdir = cwd + "/rootdir"
    mock_cfg_path = "/etc/mock/fedora-35-x86_64.cfg"
    external_repos = ["/repo1", "/repo2"]

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    expected_states = ["init", "building", "failed", "finished"]

    assert builder.workdir == str(cwd)
    assert builder.states == expected_states
    assert builder.mock_cfg_path == mock_cfg_path
    assert builder.external_repos == external_repos
    assert builder.rootdir == rootdir


def test_generate_buildbatches(tmpdir):
    """ Test the generation of build batches for the build process of a module. This serves as a
    sanity test. """
    cwd = tmpdir.mkdir("workdir")
    rootdir = None
    mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
    external_repos = []

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    build_batches = builder.generate_build_batches(module_stream.components)

    assert len(build_batches) == 12

    expected_num_comps = 178
    num_comps = 0

    for b in build_batches:
        num_comps += len(build_batches[b]["components"])
        assert "components" in build_batches[b]
        assert "curr_comp" in build_batches[b]
        assert build_batches[b]["curr_comp"] == 0
        assert "curr_comp_state" in build_batches[b]
        assert "finished_builds" in build_batches[b]
        assert "batch_state" in build_batches[b]
        assert "modular_batch_deps" in build_batches[b]
        assert type(build_batches[b]["modular_batch_deps"]) is list
        assert build_batches[b]["curr_comp_state"] == "init"
        assert build_batches[b]["batch_state"] == "init"

    assert expected_num_comps == num_comps


def test_generate_buildbatches_with_empty_buildorder_property(tmpdir):
    """ Test the generation of build batches when some components are missing buildorders """
    cwd = tmpdir.mkdir("workdir")
    rootdir = None
    mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
    external_repos = []

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    mmd, version = mock_mmdv3_and_version("modulemd/perl-bootstrap-miss-buildorder.yaml")

    module_stream = ModuleStream(mmd, version)

    build_batches = builder.generate_build_batches(module_stream.components)

    assert len(build_batches) == 11

    expected_num_comps = 178
    num_comps = 0
    for b in build_batches:
        num_comps += len(build_batches[b]["components"])

    assert expected_num_comps == num_comps
    assert len(build_batches[0]["components"]) == 4

    expected_comps = ["perl", "perl-Capture-Tiny", "perl-Test-Output", "perl-generators"]
    for c in build_batches[0]["components"]:
        assert c["name"] in expected_comps


def test_generate_buildbatches_with_no_buildorder(tmpdir):
    """ Test the generation of build batches when there is no buildorder set """
    cwd = tmpdir.mkdir("workdir")
    rootdir = None
    mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
    external_repos = []

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    mmd, version = mock_mmdv3_and_version("modulemd/perl-bootstrap-no-buildorder.yaml")

    module_stream = ModuleStream(mmd, version)

    build_batches = builder.generate_build_batches(module_stream.components)

    assert len(build_batches) == 1

    expected_num_comps = 178

    assert expected_num_comps == len(build_batches[0]["components"])


@patch("module_build.builders.mock_builder.mockbuild.config.load_config",
       return_value={"target_arch": "x86_64", "dist": "fc26"})
def test_create_build_contexts(mock_config, tmpdir):
    """ Test for creation and initialization of the metadata which will keep track and the state of
    build process for each context defined in a module stream. This serves as a sanity test.
    """
    cwd = tmpdir.mkdir("workdir")
    rootdir = None
    mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
    external_repos = []

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    builder.create_build_contexts(module_stream)

    assert len(builder.build_contexts) == 2

    expected_context_names = ["f26devel", "f27devel"]
    expected_nsvca = [
        "perl-bootstrap:devel:20210925131649:f26devel:x86_64",
        "perl-bootstrap:devel:20210925131649:f27devel:x86_64",
    ]
    expected_modularity_label = [
        "perl-bootstrap:devel:20210925131649:f26devel",
        "perl-bootstrap:devel:20210925131649:f27devel",
    ]
    expected_rpm_suffixes = [
        ".module_fc26+f26devel",
        ".module_fc26+f27devel",
    ]
    for c, bc in builder.build_contexts.items():
        assert "name" in bc
        assert bc["name"] in expected_context_names
        assert "nsvca" in bc
        assert bc["nsvca"] in expected_nsvca
        assert "metadata" in bc
        assert "status" in bc
        assert "state" in bc["status"]
        assert "current_build_batch" in bc["status"]
        assert "num_finished_comps" in bc["status"]
        assert bc["status"]["state"] == "init"
        assert bc["status"]["current_build_batch"] == 0
        assert bc["status"]["num_components"] == 178
        assert "build_batches" in bc
        assert len(bc["build_batches"]) == 12
        assert "modularity_label" in bc
        assert bc["modularity_label"] in expected_modularity_label
        assert "rpm_macros" in bc
        assert "modular_deps" in bc
        assert "rpm_suffix" in bc
        assert bc["rpm_suffix"] in expected_rpm_suffixes


@patch("module_build.builders.mock_builder.mockbuild.config.load_config",
       return_value={"target_arch": "x86_64", "dist": "fc35"})
def test_create_build_context_dir(mock_config, tmpdir):
    """ Test for the creating a `context` dir inside our working directory """
    cwd = tmpdir.mkdir("workdir")
    rootdir = None
    mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
    external_repos = []

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    context_names = [c.context_name for c in module_stream.contexts]

    builder.create_build_contexts(module_stream)

    expected_dir_names = [context.get_NSVCA() for context in module_stream.contexts]

    for name in context_names:
        builder.create_build_context_dir(name)

    for directory in cwd.listdir():
        assert directory.basename in expected_dir_names


def test_create_build_context_dir_raises_no_build_context_metadata(tmpdir):
    """ Test the builder to raise when creating a `context` directory when the builder was not
    initialized correctly.
    """
    cwd = tmpdir.mkdir("workdir")
    rootdir = None
    mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
    external_repos = []

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    with pytest.raises(Exception):
        builder.create_build_context_dir(module_stream.contexts[0].name)


@patch("module_build.builders.mock_builder.mockbuild.config.load_config",
       return_value={"target_arch": "x86_64", "dist": "fc35"})
def test_create_build_batch_dir(mock_config, tmpdir):
    """ Test for the creating a `build_batches` and `batch` directory """
    cwd = tmpdir.mkdir("workdir")
    rootdir = None
    mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
    external_repos = []

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    context_names = [c.context_name for c in module_stream.contexts]

    builder.create_build_contexts(module_stream)

    builder.create_build_batch_dir(context_names[0], 0)

    batch_dir = cwd.listdir()[0].listdir()[0]

    for directory in batch_dir.listdir():
        assert "batch_0" == directory.basename
        expected_path = "perl-bootstrap:devel:20210925131649:f26devel:x86_64/build_batches/batch_0"
        assert expected_path in str(directory)


def test_create_build_batch_dir_raises_no_build_context_metadata(tmpdir):
    """ Test the builder to raise when creating a `batch` directory when the builder was not
    initialized correctly.
    """
    cwd = tmpdir.mkdir("workdir")
    rootdir = None
    mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
    external_repos = []

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    with pytest.raises(Exception):
        builder.create_build_batch_dir(module_stream.contexts[0].name, 0)


@patch("module_build.builders.mock_builder.MockBuilder.get_artifacts_nevra", new=fake_get_artifacts)
@patch("module_build.builders.mock_builder.mockbuild.config.load_config",
       return_value={"target_arch": "x86_64", "dist": "fc35"})
def test_build_perl_bootstrap(mock_config, tmpdir):
    """ This is a sanity test for the build process. We are testing here if everything is created
    as expected. We will use `fake_buildroot_run` to fake the actual build in a mock buildroot. """

    cwd = tmpdir.mkdir("workdir")
    rootdir = None
    mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
    external_repos = []

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    with patch("module_build.builders.mock_builder.MockBuildroot.run", new=fake_buildroot_run):
        builder.build(module_stream, resume=False)

    expected_platform = {
        "f26devel": "platform:f26",
        "f27devel": "platform:f27",
    }
    for n, c in builder.build_contexts.items():
        finished_builds_count = 0
        # if the context dir exists
        assert os.path.isdir(c["dir"])
        # if the build_batches dir exists
        assert os.path.isdir(c["dir"] + "/build_batches")

        for i, b in c["build_batches"].items():
            # if the current batch dir exists
            assert os.path.isdir(b["dir"])
            # if the current batch dir has the correct name
            assert "batch_{num}".format(num=i) == b["dir"].split("/")[-1]

            for comp in b["components"]:
                # if the current component dir exists
                comp_dir = b["dir"] + "/{name}".format(name=comp["name"])
                assert os.path.isdir(comp_dir)
                # if the mock.cfg has been created for the current component
                mock_file_path = comp_dir + "/{name}_mock.cfg".format(name=comp["name"])
                assert os.path.isfile(mock_file_path)
            # the last batch does not have a yaml file as there is no other batch that it could
            # be a modular dependency for
            if i != 12:
                # if the batch yaml file has been correctly created for the current batch
                batch_yaml_name_stream = "batch{num}:{num}".format(num=i)
                batch_yaml_context = "b{num}".format(num=i)
                batch_yaml_file = [f for f in os.listdir(b["dir"]) if f.endswith("yaml")][0]
                assert batch_yaml_name_stream in batch_yaml_file
                assert batch_yaml_context in batch_yaml_file

                mmd = load_modulemd_file_from_path(b["dir"] + "/" + batch_yaml_file)
                artifacts = mmd.get_rpm_artifacts()
                assert len(artifacts) == len(b["finished_builds"])

                # we check dependencies if they are correct
                context_deps = c["modular_deps"]["buildtime"]
                batch_deps = b["modular_batch_deps"]
                expected_modular_deps = context_deps + batch_deps
                modular_deps = mmd.get_dependencies()[0]

                assert_modular_dependencies(modular_deps, expected_modular_deps)

            # count the finished builds for each batch
            for f in b["finished_builds"]:
                assert os.path.isfile(f)

            finished_builds_count += len(b["finished_builds"])
        # compare if we have the same number of RPMs in the final repo as we have in their
        # respective buid batches. This is only a sanity test. Right now 1 component produces 1
        # RPM file for the sake of the test, in reality one component can produce multiple RPMs.
        final_rpm_count = len([f for f in os.listdir(c["final_repo_path"]) if f.endswith("rpm")])
        assert finished_builds_count == final_rpm_count

        # we check the final_repo

        mmd = load_modulemd_file_from_path(c["final_yaml_path"])
        modular_deps = mmd.get_dependencies()[0]
        expected_modular_deps = c["modular_deps"]["buildtime"]
        expected_modular_deps.append(expected_platform[n])
        assert_modular_dependencies(modular_deps, expected_modular_deps)


@patch("module_build.builders.mock_builder.MockBuilder.get_artifacts_nevra", new=fake_get_artifacts)
@patch("module_build.builders.mock_builder.mockbuild.config.load_config",
       return_value={"target_arch": "x86_64", "dist": "fc35"})
def test_build_specific_context(mock_config, tmpdir):

    cwd = tmpdir.mkdir("workdir")
    rootdir = None
    mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
    external_repos = []

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    context_to_build = "f26devel"

    with patch("module_build.builders.mock_builder.MockBuildroot.run", new=fake_buildroot_run):
        builder.build(module_stream, resume=False, context_to_build=context_to_build)

    context_dirs = os.listdir(cwd)
    assert len(context_dirs) == 1
    assert context_dirs[0] == "perl-bootstrap:devel:20210925131649:f26devel:x86_64"

    # Metadata provided with the modulemd yaml file are processed whole. The builder has always
    # information about all contexts. During buildtime it chooses which contexts to build, if
    # specified by the user. That is why there are existing metadata for the `f27devel` context
    # even it was not choosen for build.
    # The `f27devel` context only contains metadata provided from the modulemd file. The `f26devel`
    # context contains also extra metadata added by the build process.
    f27devel_keys = builder.build_contexts["f27devel"].keys()

    missing_keys = ['dir', 'final_repo_path', 'final_yaml_path']

    for k in missing_keys:
        assert k not in f27devel_keys


@patch("module_build.builders.mock_builder.mockbuild.config.load_config",
       return_value={"target_arch": "x86_64", "dist": "fc35"})
def test_build_invalid_context(mock_config, tmpdir):
    """
    We test to raise an exception when the choosen context does not exist in the provided module
    stream.
    """

    cwd = tmpdir.mkdir("workdir")
    rootdir = None
    mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
    external_repos = []

    builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    invalid_context_to_build = "invalid_context"

    with pytest.raises(Exception) as e:
        builder.build(module_stream, resume=False, context_to_build=invalid_context_to_build)

    err_msg = e.value.args[0]
    assert "does not exist" in err_msg
    assert "invalid_context" in err_msg
