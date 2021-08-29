from module_build.modulemd import Modulemd


def load_modulemd_file(file_path):
    mmd = Modulemd.read_packager_file()

    return mmd


def process_mmd_build_configuration(mmd):
    pass
