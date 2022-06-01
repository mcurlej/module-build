import argparse
import os
import pdb
import sys
import traceback

from module_build.builders.mock_builder import MockBuilder
from module_build.log import init_logging, logger
from module_build.metadata import (generate_module_stream_version,
                                   load_modulemd_file_from_path)
from module_build.stream import ModuleStream


class FullPathAction(argparse.Action):
    """A custom argparse action which converts all relative paths to absolute."""

    def __call__(self, parser, args, values, option_string=None):
        full_path = self._get_full_path(values)
        # `add_repo` should be an `append` action
        if self.dest == "add_repo":
            add_repo = getattr(args, "add_repo")
            add_repo.append(full_path)
            setattr(args, self.dest, add_repo)
        else:
            setattr(args, self.dest, full_path)

    def _get_full_path(self, path):
        full_path = path

        if not path.startswith("/"):
            dir_path = os.getcwd()
            full_path = os.path.abspath(os.path.join(dir_path, path))

        return full_path


def get_arg_parser():
    description = """
        module-build is a command line utility which enables you to build modules locally.
        """
    parser = argparse.ArgumentParser("module-build", description=description, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("workdir", type=str, action=FullPathAction, help=("The working directory where the build of a module stream will" " happen."))

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument("-f", "--modulemd", type=str, action=FullPathAction, help="Path to the modulemd yaml file")

    # group.add_argument("-g", "--git-branch", type=str,
    #                   help=("URL to the git branch where the modulemd yaml file resides."))

    parser.add_argument("-c", "--mock-cfg", help="Path to the mock config.", default=".", type=str, required=True, action=FullPathAction)
    parser.add_argument("-o", "--no-stdout", action="store_true", help="If set logger output in stdout will not be displayed.")
    parser.add_argument("-w", "--workers", type=int, default=1, help="When set to value higher than 1, will use multiprocess mode.")
    parser.add_argument("-r", "--resume", action="store_true", help="If set it will try to continue the build where it failed last time.")

    parser.add_argument(
        "-n",
        "--module-name",
        type=str,
        help=("You can define the module name with this option if it is not set in the provided modulemd yaml file."),
    )

    parser.add_argument(
        "-s",
        "--module-stream",
        type=str,
        help=("You can define the module stream name with this option if it is not set in the provided modulemd yaml file."),
    )

    parser.add_argument(
        "-l",
        "--module-version",
        type=int,
        help=(
            "You can define the module stream name with this option. If it is not"
            " set the current unix timestamp will be used instead. This option is"
            " also required when using the resume feature. You can specify which "
            "module stream version you want to resume."
        ),
    )

    parser.add_argument(
        "-m",
        "--srpm-dir",
        type=str,
        help=("Path to directory with SRPMs. When set, all module components will be build from given sources."),
        action=FullPathAction,
    )

    parser.add_argument("-g", "--module-context", type=str, help=("When set it will only build the selected context from the modules stream."))
    # TODO verbose is not implemented
    # parser.add_argument("-v", "--verbose", action="store_true",
    #                     help="Will display all output to stdout.")

    parser.add_argument("-d", "--debug", action="store_true", help="When the module build fails it will start the python `pdb` debugger.")
    parser.set_defaults(add_repo=[])
    parser.add_argument(
        "-p",
        "--add-repo",
        type=str,
        action=FullPathAction,
        help=("With this option you can provide external RPM repositories to the buildroots of the module build. Can be used multiple times."),
    )

    parser.add_argument("-t", "--rootdir", type=str, help=("Provides a new location for you buildroots."))

    return parser


def main():
    parser = get_arg_parser()
    args = parser.parse_args()

    if args.resume and args.module_version is None:
        parser.error("when using -r/--resume you need also set -l/--module-version so we can can identify which contexts build need to be resumed.")

    if args.workers > 1 and not args.no_stdout:
        parser.error("Multiprocess mode requires disabling stdout output -o/--no-stdout.")

    # TODO this needs to be updated when scm checkout will be added
    yaml_filename = args.modulemd.split("/")[-1].rsplit(".", 1)[0]
    init_logging(args.workdir, yaml_filename, logger, args.no_stdout)

    # PHASE1: Load metadata and configuration provided by the user
    logger.info("Processing provided module stream metadata...")
    if args.modulemd:
        mmd = load_modulemd_file_from_path(args.modulemd)
        version = generate_module_stream_version()

    # if args.git_branch:
    # TODO the git branch checkout is not implemented
    #    mmd = load_modulemd_file_from_scm(args.git_branch)
    #   version = generate_module_stream_version(args.git_branch)

    if args.module_name:
        mmd.set_module_name(args.module_name)

    if args.module_stream:
        mmd.set_stream_name(args.module_stream)

    if args.module_version:
        version = args.module_version

    logger.info("Initializing the module build process...")
    module_stream = ModuleStream(mmd, version)

    # TODO move the whole validation in the argparse
    if not mmd:
        raise Exception("no input")

        # PHASE2: init the builder
    if args.module_context:
        log_msg = "Starting to build the '{name}:{stream}:{context}' of the module stream.".format(
            name=module_stream.name, stream=module_stream.stream, context=args.module_context
        )
    else:
        log_msg = "Starting to build the '{name}:{stream}' module stream.".format(
            name=module_stream.name,
            stream=module_stream.stream,
        )

    logger.info(log_msg)

    # TODO add exceptions
    mock_builder = MockBuilder(args.mock_cfg, args.workdir, args.add_repo, args.rootdir, args.srpm_dir, args.workers)

    # PHASE3: try to build the module stream
    try:
        mock_builder.build(module_stream, args.resume, context_to_build=args.module_context)
    except Exception:
        formated_tb = traceback.format_exc()
        exc_info = sys.exc_info()

        if args.debug:
            print(formated_tb)
            msg = (
                "The program is now in debug mode after encountering an exception."
                " When encountering an error the `pdb` python debugger is"
                " started. See the following variables to check the state of the build:\n\n"
                "`formated_tb` - formated traceback of the exception\n"
                "`exc_info` - tuple with the exception information\n"
                "`module_stream` - object of module stream metadata loaded from your "
                "modulemd file\n"
                "`mock_builder` - object which holds the state of your module build\n\n"
            )
            logger.info(msg)

            pdb.set_trace()
        else:
            print(formated_tb)
            raise exc_info[1]

    # PHASE4: Make a final report on the module stream build
    # TODO implement final_report
    mock_builder.final_report()


if __name__ == "__main__":
    main()
