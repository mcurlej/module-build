import subprocess

from module_build.log import logger


def call_createrepo_c_on_dir(dir):
    # TODO move out as a standalone function
    msg = "createrepo_c called on dir: {path}".format(
        path=dir,
    )
    logger.info(msg)

    mock_cmd = ["createrepo_c", dir]
    proc = subprocess.Popen(mock_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()

    if proc.returncode != 0:
        err_msg = "Command '%s' returned non-zero value %d%s" % (mock_cmd, proc.returncode, out)
        raise RuntimeError(err_msg)

    return out, err
