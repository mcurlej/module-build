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
