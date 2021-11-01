import time

from datetime import datetime

from module_build.modulemd import Modulemd


def load_modulemd_file_from_path(file_path):
    """Function for loading the modulemd yaml file.

    :param file_path: path to the modulemd yaml file.
    :type file_path: str,
    :return: Modulemd object
    :rtype: :class:`Modulemd.PackagerV3` instance
    """
    mmd = Modulemd.read_packager_file(file_path)

    # read_packager_file returns a tuple with the original GType definition and the instantiated
    # python object so we are returning only the python object
    if "_ResultTuple" in str(type(mmd)):
        return mmd[1]

    return mmd


def load_modulemd_file_from_scm(file_path):
    raise NotImplementedError()


def generate_module_stream_version(timestamp=False):
    """Generates a version of a module stream. The version of a module stream can be an arbitrary
    unix timestamp or a timestamp taken from the commit of a git branch.

    :param timestamp: unix timestamp
    :type timestamp: int, optional
    :return: Formated module stream version
    :rtype: str
    """

    if timestamp:
        dt = datetime.utcfromtimestamp(int(timestamp))
    else:
        dt = datetime.utcfromtimestamp(int(time.time()))

    # we need to format the timestamp so its human readable and becomes a module stream version
    version = int(dt.strftime("%Y%m%d%H%M%S"))

    return version


def generate_and_populate_output_mmd(name, stream, context, version, description, summary,
                                     mod_license, components, artifacts, dependencies):

    mmd = Modulemd.ModuleStreamV2.new(name, stream)
    mmd.set_context(context)
    mmd.set_static_context()
    mmd.set_version(version)
    mmd.set_description(description)
    mmd.set_summary(summary)
    mmd.add_module_license(mod_license)

    new_deps = Modulemd.Dependencies()
    for d in dependencies["buildtime"]:
        name, stream = d.split(":")
        new_deps.add_buildtime_stream(name, stream)

    for d in dependencies["runtime"]:
        name, stream = d.split(":")
        new_deps.add_runtime_stream(name, stream)

    mmd.add_dependencies(new_deps)

    for c in components:
        comp_mmd = Modulemd.ComponentRpm.new(c["name"])
        comp_mmd.set_ref(c["ref"])
        comp_mmd.set_buildorder(c["buildorder"])
        comp_mmd.set_buildonly(c["buildonly"])
        comp_mmd.set_buildroot(c["buildroot"])
        comp_mmd.set_rationale(c["rationale"])
        comp_mmd.set_repository(c["repository"])
        comp_mmd.set_srpm_buildroot(c["srpm_buildroot"])
        for arch in c["multilib_arches"]:
            comp_mmd.add_multilib_arch(arch)

    mmd.add_component(comp_mmd)

    for a in artifacts:
        mmd.add_rpm_artifact(a)

    return mmd


def mmd_to_str(mmd):

    index = Modulemd.ModuleIndex()
    index.add_module_stream(mmd)

    return index.dump_to_string()
