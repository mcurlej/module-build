import argparse
import os


def get_arg_parser():
    description = (
        """
        module-build is a command line utility which enables you to build modules locally.
        """
    )
    parser = argparse.ArgumentParser("module-build", description=description,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-f", "--modulemd", required=True, type=str,
                        help="Path to the modulemd yaml file")

    parser.add_argument("-c", "--mock-cfg", help="Path to the mock config.",
                        default=".", type=str)

    return parser


def main():
    parser = get_arg_parser()
    args = parser.parse_args()

    print("This is a placeholder!")



if __name__ == "__main__":
    main()
