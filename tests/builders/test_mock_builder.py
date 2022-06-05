import os
from pathlib import Path
from unittest.mock import patch

import pytest
from module_build.builders.mock_builder import MockBuilder, MockBuildPool
from module_build.metadata import load_modulemd_file_from_path
from module_build.mock.info import MockBuildInfoSRPM
from module_build.stream import ModuleStream
from tests import (assert_modular_dependencies, fake_buildroot_run,
                   fake_call_createrepo_c_on_dir, fake_get_artifacts,
                   get_full_data_path, mock_mmdv3_and_version)


# We wrap testcase into classes to avoid duplication
# of parametrized arguments across multiple test functions
@pytest.mark.parametrize("workers", (1, 2, 5))
class TestMockBuilder:
    def test_create_mock_builder(self, tmpdir, workers):
        """ Test for an instance of MockBuilder. This serves as a sanity test. """
        cwd = tmpdir.mkdir("workdir").strpath
        srpm_dir = None
        rootdir = cwd + "/rootdir"
        mock_cfg_path = "/etc/mock/fedora-35-x86_64.cfg"
        external_repos = ["/repo1", "/repo2"]

        builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir, srpm_dir, workers)

        assert builder.workdir == str(cwd)
        assert builder.mock_cfg_path == mock_cfg_path
        assert builder.external_repos == external_repos
        assert builder.rootdir == rootdir

    def test_generate_buildbatches(self, tmpdir, workers):
        """ Test the generation of build batches for the build process of a module. This serves as a
        sanity test. """
        cwd = tmpdir.mkdir("workdir").strpath
        srpm_dir = None
        rootdir = None
        mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
        external_repos = []

        builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir, srpm_dir, workers)

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

    def test_generate_buildbatches_with_empty_buildorder_property(self, tmpdir, workers):
        """ Test the generation of build batches when some components are missing buildorders """
        cwd = tmpdir.mkdir("workdir").strpath
        srpm_dir = None
        rootdir = None
        mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
        external_repos = []

        builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir, srpm_dir, workers)

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

    def test_generate_buildbatches_with_no_buildorder(self, tmpdir, workers):
        """ Test the generation of build batches when there is no buildorder set """
        cwd = tmpdir.mkdir("workdir").strpath
        srpm_dir = None
        rootdir = None
        mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
        external_repos = []

        builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir, srpm_dir, workers)

        mmd, version = mock_mmdv3_and_version("modulemd/perl-bootstrap-no-buildorder.yaml")

        module_stream = ModuleStream(mmd, version)

        build_batches = builder.generate_build_batches(module_stream.components)

        assert len(build_batches) == 1

        expected_num_comps = 178

        assert expected_num_comps == len(build_batches[0]["components"])

    @patch("module_build.builders.mock_builder.mockbuild.config.load_config",
           return_value={"target_arch": "x86_64", "dist": "fc26"})
    def test_create_build_contexts(self, mock_config, tmpdir, workers):
        """ Test for creation and initialization of the metadata which will keep track and the state of
        build process for each context defined in a module stream. This serves as a sanity test.
        """
        cwd = tmpdir.mkdir("workdir").strpath
        srpm_dir = None
        rootdir = None
        mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
        external_repos = []

        builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir, srpm_dir, workers)

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
    def test_create_build_context_dir(self, mock_config, tmpdir, workers):
        """ Test for the creating a `context` dir inside our working directory """
        cwd = tmpdir.mkdir("workdir").strpath
        srpm_dir = None
        rootdir = None
        mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
        external_repos = []

        builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir, srpm_dir, workers)

        mmd, version = mock_mmdv3_and_version()

        module_stream = ModuleStream(mmd, version)

        context_names = [c.context_name for c in module_stream.contexts]

        builder.create_build_contexts(module_stream)

        expected_dir_names = [context.get_NSVCA() for context in module_stream.contexts]

        for name in context_names:
            builder.create_build_context_dir(name)

        for name in expected_dir_names:
            assert name in os.listdir(cwd)

    def test_create_build_context_dir_raises_no_build_context_metadata(self, tmpdir, workers):
        """ Test the builder to raise when creating a `context` directory when the builder was not
        initialized correctly.
        """
        cwd = tmpdir.mkdir("workdir").strpath
        srpm_dir = None
        rootdir = None
        mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
        external_repos = []

        builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir, srpm_dir, workers)

        mmd, version = mock_mmdv3_and_version()

        module_stream = ModuleStream(mmd, version)

        with pytest.raises(Exception):
            builder.create_build_context_dir(module_stream.contexts[0].name)

    @patch("module_build.builders.mock_builder.mockbuild.config.load_config",
           return_value={"target_arch": "x86_64", "dist": "fc35"})
    def test_create_build_batch_dir(self, mock_config, tmpdir, workers):
        """ Test for the creating a `build_batches` and `batch` directory """
        cwd = tmpdir.mkdir("workdir").strpath
        srpm_dir = None
        rootdir = None
        mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
        external_repos = []

        builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir, srpm_dir, workers)

        mmd, version = mock_mmdv3_and_version()

        module_stream = ModuleStream(mmd, version)

        context_names = [c.context_name for c in module_stream.contexts]

        builder.create_build_contexts(module_stream)

        builder.create_build_batch_dir(context_names[0], 0)

        build_batches_dir = os.listdir(cwd + "/" + os.listdir(cwd)[0] + "/build_batches")

        assert len(build_batches_dir) == 1
        assert "batch_0" == build_batches_dir[0]

    def test_create_build_batch_dir_raises_no_build_context_metadata(self, tmpdir, workers):
        """ Test the builder to raise when creating a `batch` directory when the builder was not
        initialized correctly.
        """
        cwd = tmpdir.mkdir("workdir")
        srpm_dir = None
        rootdir = None
        mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
        external_repos = []

        builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir, srpm_dir, workers)

        mmd, version = mock_mmdv3_and_version()

        module_stream = ModuleStream(mmd, version)

        with pytest.raises(Exception):
            builder.create_build_batch_dir(module_stream.contexts[0].name, 0)

    @patch("module_build.builders.mock_builder.MockBuilder.call_createrepo_c_on_dir", new=fake_call_createrepo_c_on_dir)
    @patch("module_build.builders.mock_builder.MockBuilder.get_artifacts_nevra", new=fake_get_artifacts)
    @patch("module_build.builders.mock_builder.mockbuild.config.load_config",
           return_value={"target_arch": "x86_64", "dist": "fc35"})
    def test_build_perl_bootstrap(self, mock_config, tmpdir, workers):
        """ This is a sanity test for the build process. We are testing here if everything is created
        as expected. We will use `fake_buildroot_run` to fake the actual build in a mock buildroot. """

        cwd = tmpdir.mkdir("workdir").strpath
        srpm_dir = None
        rootdir = None
        mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
        external_repos = []

        builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir, srpm_dir, workers)

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

    @patch("module_build.builders.mock_builder.MockBuilder.call_createrepo_c_on_dir", new=fake_call_createrepo_c_on_dir)
    @patch("module_build.builders.mock_builder.MockBuilder.get_artifacts_nevra", new=fake_get_artifacts)
    @patch("module_build.builders.mock_builder.mockbuild.config.load_config",
           return_value={"target_arch": "x86_64", "dist": "fc35"})
    def test_build_specific_context(self, mock_config, tmpdir, workers):

        cwd = tmpdir.mkdir("workdir").strpath
        srpm_dir = None
        rootdir = None
        mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
        external_repos = []

        builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir, srpm_dir, workers)

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
    def test_build_invalid_context(self, mock_config, tmpdir, workers):
        """
        We test to raise an exception when the choosen context does not exist in the provided module
        stream.
        """

        cwd = tmpdir.mkdir("workdir").strpath
        srpm_dir = None
        rootdir = None
        mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
        external_repos = []

        builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir, srpm_dir, workers)

        mmd, version = mock_mmdv3_and_version()

        module_stream = ModuleStream(mmd, version)

        invalid_context_to_build = "invalid_context"

        with pytest.raises(Exception) as e:
            builder.build(module_stream, resume=False, context_to_build=invalid_context_to_build)

        err_msg = e.value.args[0]
        assert "does not exist" in err_msg
        assert "invalid_context" in err_msg

    @pytest.mark.parametrize(
        "create_fake_srpm",
        [({"name": "unicorn"}, {"name": "rustc"}), ], indirect=True
    )
    @patch("module_build.mock.info.MockBuildInfo.srpms_enabled", return_value=True)
    @patch("module_build.builders.mock_builder.mockbuild.config.load_config",
           return_value={"target_arch": "x86_64", "dist": "fc35"})
    def test_srpm_build_with_missing_sources(self, mock_config, srpms, tmpdir, workers, create_fake_srpm):
        """
        Test build in SRPM mode with missing sources.
        """

        # Validate created Fake SRPMs
        fake_srpm_files = Path(create_fake_srpm).glob('*.rpm')
        fake_srpm_files = [x for x in fake_srpm_files if x.is_file()]
        assert 2 == len(fake_srpm_files)

        cwd = tmpdir.mkdir("workdir").strpath
        srpm_dir = str(Path(create_fake_srpm).resolve())
        rootdir = None
        mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
        external_repos = []

        builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir, srpm_dir, workers)

        mmd, version = mock_mmdv3_and_version(modulemd_path="modulemd/flatpak-runtime.yaml")
        mmd.set_module_name("flatpak-runtime")
        mmd.set_stream_name("devel")

        module_stream = ModuleStream(mmd, version)

        context_to_build = "1234"

        with pytest.raises(Exception) as e:
            builder.build(module_stream, resume=False, context_to_build=context_to_build)

        err_msg = e.value.args[0]
        assert "Missing SRPM for" in err_msg
        assert "flatpak" in err_msg

    @pytest.mark.parametrize("create_fake_srpm", [({"name": "nginx"}, {"name": "rustc"}, {"name": "php"}), ], indirect=True)
    def test_srpm_mapping_with_invalid_files(self, tmpdir, create_fake_srpm, workers):
        """
        Test SRPM mapping with invalid SRPM files.
        """

        # Add garbage files to SRPM directory
        garbage_file_names = ("struck.src.rpm", "nginx-1.33.src.rpm", "not_a_file", "magic.rpm")
        for idx, f in enumerate(garbage_file_names, start=1):
            with open(Path(create_fake_srpm) / f, "wb") as fd:
                fd.write(os.urandom(1024 * 10 * idx))

        # Validate created Fake SRPMs
        fake_srpm_files = Path(create_fake_srpm).glob('*.rpm')
        fake_srpm_files = [x for x in fake_srpm_files if x.is_file()]
        assert 6 == len(fake_srpm_files)

        cwd = tmpdir.mkdir("workdir").strpath
        srpm_dir = str(Path(create_fake_srpm).resolve())
        rootdir = None
        mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
        external_repos = []

        builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir, srpm_dir, workers)

        assert 3 == builder.mock_info.get_srpm_count()
        assert isinstance(builder.mock_info._if_srpm_present("nginx")[0], MockBuildInfoSRPM)


class TestMockBuilderAsync:
    @patch("module_build.builders.mock_builder.MockBuildPool.add_job")
    @patch("module_build.builders.mock_builder.MockBuilder.call_createrepo_c_on_dir", new=fake_call_createrepo_c_on_dir)
    @patch("module_build.builders.mock_builder.MockBuilder.get_artifacts_nevra", new=fake_get_artifacts)
    @patch("module_build.builders.mock_builder.mockbuild.config.load_config",
           return_value={"target_arch": "x86_64", "dist": "fc35"})
    def test_poll_async_add_to_queue(self, mock_config, add_job, tmpdir):
        """
            Tests adding jobs to queue
        """
        cwd = tmpdir.mkdir("workdir").strpath
        srpm_dir = None
        rootdir = None
        workers = 2
        mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
        external_repos = []

        builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir, srpm_dir, workers)

        mmd, version = mock_mmdv3_and_version()

        module_stream = ModuleStream(mmd, version)

        context_to_build = "f26devel"

        builder.build(module_stream, resume=False, context_to_build=context_to_build)

        assert add_job.call_count == 178

    @patch("module_build.builders.mock_builder.MockBuildPool.add_job", return_value=True)
    @patch("module_build.builders.mock_builder.MockBuilder.call_createrepo_c_on_dir", new=fake_call_createrepo_c_on_dir)
    @patch("module_build.builders.mock_builder.MockBuilder.get_artifacts_nevra", new=fake_get_artifacts)
    @patch("module_build.builders.mock_builder.mockbuild.config.load_config",
           return_value={"target_arch": "x86_64", "dist": "fc35"})
    def test_multiprocess_failure(self, mock_config, addjob, tmpdir):
        """
            Tests multiprocess component failure
        """
        cwd = tmpdir.mkdir("workdir").strpath
        srpm_dir = None
        rootdir = None
        workers = 2
        mock_cfg_path = get_full_data_path("mock_cfg/fedora-35-x86_64.cfg")
        external_repos = []

        builder = MockBuilder(mock_cfg_path, cwd, external_repos, rootdir, srpm_dir, workers)

        mmd, version = mock_mmdv3_and_version(modulemd_path="modulemd/flatpak-runtime.yaml")
        mmd.set_module_name("flatpak-runtime")
        mmd.set_stream_name("devel")

        module_stream = ModuleStream(mmd, version)

        context_to_build = "1234"

        # Simulate failure by overriding class attribute
        with patch.object(MockBuildPool, "failed", 1):
            with pytest.raises(Exception) as e:
                builder.build(module_stream, resume=False, context_to_build=context_to_build)

                err_msg = e.value.args[0]
                assert "Some components failed" in err_msg
