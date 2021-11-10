import os
from unittest.mock import patch

import pytest

from module_build.builders.mock_builder import MockBuilder
from module_build.stream import ModuleStream
from module_build.metadata import load_modulemd_file_from_path
from tests import mock_mmdv3_and_version


def test_create_mock_builder(tmpdir):
    """ Test for an instance of MockBuilder. This serves as a sanity test. """
    cwd = tmpdir.mkdir("workdir")
    builder = MockBuilder("", cwd)

    expected_states = ["init", "building", "failed", "finished"]

    assert builder.workdir == str(cwd)
    assert builder.states == expected_states
    assert not builder.mock_cfg_path


def test_generate_buildbatches(tmpdir):
    """ Test the generation of build batches for the build process of a module. This serves as a 
    sanity test. """
    cwd = tmpdir.mkdir("workdir")
    builder = MockBuilder("", cwd)

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
    builder = MockBuilder("", cwd)

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
    builder = MockBuilder("", cwd)

    mmd, version = mock_mmdv3_and_version("modulemd/perl-bootstrap-no-buildorder.yaml")

    module_stream = ModuleStream(mmd, version)

    build_batches = builder.generate_build_batches(module_stream.components)

    assert len(build_batches) == 1

    expected_num_comps = 178

    assert expected_num_comps == len(build_batches[0]["components"])


def test_create_build_contexts(tmpdir):
    """ Test for creation and initialization of the metadata which will keep track and the state of 
    build process for each context defined in a module stream. This serves as a sanity test.
    """
    cwd = tmpdir.mkdir("workdir")
    builder = MockBuilder("", cwd)

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
        ".module_f26+f26devel",
        ".module_f27+f27devel",
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
        assert "rpm_macros" in bc
        assert "modular_deps" in bc
        assert "rpm_suffix" in bc
        assert bc["rpm_suffix"] in expected_rpm_suffixes


def test_create_build_context_dir(tmpdir):
    """ Test for the creating a `context` dir inside our working directory """
    cwd = tmpdir.mkdir("workdir")
    builder = MockBuilder("", cwd)

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
    builder = MockBuilder("", cwd)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    with pytest.raises(Exception):
        builder.create_build_context_dir(module_stream.contexts[0].name)


def test_create_build_batch_dir(tmpdir):
    """ Test for the creating a `build_batches` and `batch` directory """
    cwd = tmpdir.mkdir("workdir")
    builder = MockBuilder("", cwd)

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
    builder = MockBuilder("", cwd)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    with pytest.raises(Exception):
        builder.create_build_batch_dir(module_stream.contexts[0].name, 0)


def fake_buildroot_run(self):
    """ Fake function which creates dummy rpm file in the result directory of a component. The 
    NEVRA of the RPM is fake. The only real parts are the name and the modular rpm suffix which 
    in real life overrides the %{dist} macro. The function represents a succesfull build in the
    mock buildroot """

    # TODO move to __init__.py
    rpm_filename = "/{name}-0:1.0-1{dist}.x86_64.rpm".format(name=self.component["name"],
                                                    dist=self.rpm_suffix)

    with open(self.result_dir_path + rpm_filename, "w") as f:
        f.write("dummy")

    self.finished = True

    return "", 0


def assert_modular_dependencies(modular_deps, expected_modular_deps):
    # TODO move to __init__.py
    runtime_modules = modular_deps.get_runtime_modules()

    for module in runtime_modules:
        streams = modular_deps.get_runtime_streams(module)
        
        for stream in streams:
            module_stream = "{module}:{stream}".format(module=module, stream=stream)
            assert module_stream in expected_modular_deps

    buildtime_modules = modular_deps.get_buildtime_modules()
        
    for module in buildtime_modules:
        streams = modular_deps.get_buildtime_streams(module)
        
        for stream in streams:
            module_stream = "{module}:{stream}".format(module=module, stream=stream)
            assert module_stream in expected_modular_deps


def test_build_perl_bootstrap(tmpdir):
    """ This is a sanity test for the build process. We are testing here if everything is created
    as expected. We will use `fake_buildroot_run` to fake the actual build in a mock buildroot. """

    cwd = tmpdir.mkdir("workdir")
    builder = MockBuilder("/etc/mock/fedora-34-x86_64.cfg", cwd)

    mmd, version = mock_mmdv3_and_version()

    module_stream = ModuleStream(mmd, version)

    with patch("module_build.builders.mock_builder.MockBuildroot.run", new=fake_buildroot_run):
        builder.build(module_stream)

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
                batch_yaml_name_stream = "batch:{num}".format(num=i)
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
        # RPM file for the sake of the test, in reallity one component can produce multiple RPMs.
        final_rpm_count = len([f for f in os.listdir(c["final_repo_path"]) if f.endswith("rpm")])
        assert finished_builds_count == final_rpm_count

        # we check the final_repo

        mmd = load_modulemd_file_from_path(c["final_yaml_path"])
        modular_deps = mmd.get_dependencies()[0]
        expected_modular_deps = c["modular_deps"]["buildtime"]
        expected_modular_deps.append(expected_platform[n])
        assert_modular_dependencies(modular_deps, expected_modular_deps)


def test_resume_module_build_failed_first_component():
    pass


def test_resume_module_build_failed_not_first_component():
    pass


def test_resume_module_build_failed_to_create_batch_yaml_file():
    pass


def test_resume_module_build_failed_to_create_final_yaml_file():
    pass
