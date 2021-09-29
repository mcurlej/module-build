import argparse

from module_build.metadata import (load_modulemd_file_from_path, load_modulemd_file_from_scm,
                                   generate_module_stream_version)
from module_build.stream import ModuleStream


def get_arg_parser():
    description = (
        """
        module-build is a command line utility which enables you to build modules locally.
        """
    )
    parser = argparse.ArgumentParser("module-build", description=description,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("WORKDIR", type=str,
                        help=("The working directory where the build of a module stream will"
                              " happen."))

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument("-f", "--modulemd", type=str,
                       help="Path to the modulemd yaml file")
    group.add_argument("-g", "--git-branch", type=str,
                       help=("URL to the git branch where the modulemd yaml file resides."))

    parser.add_argument("-c", "--mock-cfg", help="Path to the mock config.",
                        default=".", required=True, type=str)
    parser.add_argument("-a", "--arch", required=True, type=str,
                        help="Architecture for which the module is build.")

    return parser


def main():
    parser = get_arg_parser()
    args = parser.parse_args()

# PHASE1: Load metadata and configuration provided by the user
    if args.modulemd:
        mmd = load_modulemd_file_from_path(args.modulemd)
        version = generate_module_stream_version()
        module_stream = ModuleStream(mmd, version)

    if args.git_branch:
        mmd = load_modulemd_file_from_scm(args.git_branch)
        version = generate_module_stream_version(args.git_branch)
        module_stream = ModuleStream(mmd, version)

    # TODO move the whole validation in the argparse
    if not mmd:
        raise Exception("no input")

# PHASE2: create working dirs and necessary files

# PHASE3: init the builder and attempt to build the module stream

# PHASE4: Make a final report on the module stream build


if __name__ == "__main__":
    main()
