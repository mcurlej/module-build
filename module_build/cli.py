import argparse
import logging

from module_build.builders.mock_builder import MockBuilder
from module_build.log import init_logging
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
    parser.add_argument("workdir", type=str,
                        help=("The working directory where the build of a module stream will"
                              " happen."))

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument("-f", "--modulemd", type=str,
                       help="Path to the modulemd yaml file")
    group.add_argument("-g", "--git-branch", type=str,
                       help=("URL to the git branch where the modulemd yaml file resides."))

    parser.add_argument("-c", "--mock-cfg", help="Path to the mock config.",
                        default=".", type=str, required=True)
    parser.add_argument("-a", "--arch", required=True, type=str,
                        help="Architecture for which the module is build.")
    # TODO revive does not work
    parser.add_argument("-r", "--resume", action="store_true",
                        help="If set it will try to continue the build where it failed last time.")

    parser.add_argument("-n", "--module-name", type=str,
                        help=("You can define the module name with this option if it is not"
                              " set in the provided modulemd yaml file."))

    parser.add_argument("-s", "--module-stream", type=str,
                        help=("You can define the module stream name with this option if it is not"
                              " set in the provided modulemd yaml file."))

    parser.add_argument("-l", "--module-version", type=int,
                        help=("You can define the module stream name with this option if it is not "
                              " set unix timestamp will be used instead. This option is also used "
                              "when using the resume feature. You can specify which module stream "
                              "version you want to resume."))
    # TODO verbose is not implemented
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Will display all output to stdout.")

    parser.add_argument("-d", "--debug", action="store_true",
                        help="When the module build fails it will start the pdb debugger.")

    parser.add_argument("-p", "--add-repo", type=str, action="append",
                        help=("With this option you can provide external RPM repositories to the"
                              " buildroots of the module build. Can be used multiple times."))

    parser.add_argument("-t", "--rootdir", type=str,
                        help=("Provides a new location for you buildroots."))

    return parser


def main():
    parser = get_arg_parser()
    args = parser.parse_args()

    if args.resume and args.module_version is None:
        parser.error("when using -r/--resume you need also set -l/--module-version so we can "
                     "can identify which contexts build need to be resumed.")

    # TODO this needs to be updated when scm checkout will be added
    yaml_filename = args.modulemd.split("/")[-1].rsplit(".", 1)[0]
    init_logging(args.workdir, yaml_filename)

# PHASE1: Load metadata and configuration provided by the user
    logging.info("Processing provided module stream metadata...")
    if args.modulemd:
        mmd = load_modulemd_file_from_path(args.modulemd)
        version = generate_module_stream_version()

    if args.git_branch:
        # TODO the git branch checkout does not work
        mmd = load_modulemd_file_from_scm(args.git_branch)
        version = generate_module_stream_version(args.git_branch)

    if args.module_name:
        mmd.set_module_name(args.module_name)

    if args.module_stream:
        mmd.set_stream_name(args.module_stream)
    
    if args.module_version:
        version = args.module_version

    logging.info("Initializing the module build process...")
    module_stream = ModuleStream(mmd, version)

    # TODO move the whole validation in the argparse
    if not mmd:
        raise Exception("no input")

# PHASE2: init the builder
    log_msg = "Starting to build the '{name}:{stream}' module stream.".format(
        name=module_stream.name,
        stream=module_stream.stream,
    )
    logging.info(log_msg)

    # TODO convert all relative paths to absolute 
    # TODO add exceptions
    mock_builder = MockBuilder(args.mock_cfg, args.workdir, args.arch, args.add_repo, args.rootdir)

# PHASE3: try to build the module stream
    #try:
    mock_builder.build(module_stream, args.resume)
    #except Exception as e:
        # TODO enable this with the --debug option
    #    if args.debug:
    #        import pdb; pdb.set_trace()
    #    else:
    #        # TODO reraise and display the original exception
    #        pass

# PHASE4: Make a final report on the module stream build
    mock_builder.final_report()

if __name__ == "__main__":
    main()
