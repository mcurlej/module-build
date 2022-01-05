import os
from unittest.mock import patch

from module_build.metadata import load_modulemd_file_from_path, generate_module_stream_version


class TestException(Exception):
    pass


def get_full_data_path(path):
    dir_path = os.path.dirname(os.path.abspath(__file__))

    full_path = os.path.join(dir_path, "data", path)

    return full_path


def mock_mmdv3_and_version(modulemd_path="modulemd/perl-bootstrap.yaml",
                           timestamp=1632575809.6422336):

    modulemd_full_path = get_full_data_path(modulemd_path)
    mmd = load_modulemd_file_from_path(modulemd_full_path)

    with patch("module_build.metadata.time.time") as mock_time:
        mock_time.return_value = timestamp
        version = generate_module_stream_version()

    return mmd, version


def fake_buildroot_run(self):
    """ Fake function which creates dummy rpm file in the result directory of a component. The
    NEVRA of the RPM is fake. The only real parts are the name and the modular rpm suffix which
    in real life overrides the %{dist} macro. The function represents a succesfull build in the
    mock buildroot """

    rpm_filename = "/{name}-0:1.0-1{dist}.x86_64.rpm".format(name=self.component["name"],
                                                             dist=self.rpm_suffix)

    with open(self.result_dir_path + rpm_filename, "w") as f:
        f.write("dummy")

    self.finished = True

    return "", 0


def fake_get_artifacts(self, artifacts):
    """ A helper function to create valid NEVRA filenames for inserting in the artifacts section of
    a modulemd file """

    artifacts_nevra = []
    for a in artifacts:
        path, filename = a.rsplit("/", 1)
        filename = filename.rsplit(".", 1)[0]
        artifacts_nevra.append(filename)

    return artifacts_nevra


def assert_modular_dependencies(modular_deps, expected_modular_deps):
    """ A helper method for comparing result and expected modular dependecies of a module stream """

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
