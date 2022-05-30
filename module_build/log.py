import logging
import sys
import time

logger = logging.getLogger("module-build")


def init_logging(cwd, yaml_filename, no_stdout, logger):
    main_log_file_path = cwd + "/{yaml}-module-build-{timestamp}.log".format(yaml=yaml_filename, timestamp=int(time.time()))
    log_format = "%(asctime)s | %(levelname)s | %(message)s"

    logger.setLevel("INFO")

    log_formatter = logging.Formatter(log_format)
    # we want to write to a log file
    main_log_handle = logging.FileHandler(main_log_file_path)
    main_log_handle.setFormatter(log_formatter)

    logger.addHandler(main_log_handle)

    if not no_stdout:
        # at the same time we want to write to stdout
        cli_handler = logging.StreamHandler(sys.stdout)
        cli_handler.setFormatter(log_formatter)

        logger.addHandler(cli_handler)
