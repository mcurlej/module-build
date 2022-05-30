import os
import subprocess

from module_build.log import logger


class MockBuildroot:
    def __init__(
        self,
        component,
        mock_cfg,
        batch_dir_path,
        batch_num,
        modularity_label,
        rpm_suffix,
        batch_repo,
        external_repos,
        rootdir,
        srpm_path,
        callback=None,
    ):

        self.finished = False
        self.component = component
        self.batch_dir_path = batch_dir_path
        self.batch_num = batch_num
        self.modularity_label = modularity_label
        self.rpm_suffix = rpm_suffix
        self.result_dir_path = self._create_buildroot_result_dir()
        self.mock_cfg_path = mock_cfg.write_config(self.result_dir_path, self.component["name"])
        self.batch_repo = batch_repo
        self.external_repos = external_repos
        self.rootdir = rootdir
        self.srpm_path = srpm_path

        if callback is not None:
            callback.append(component["name"])

    def run(self):
        mock_cmd = [
            "mock",
            "-v",
            "-r",
            self.mock_cfg_path,
            "--resultdir={result_dir_path}".format(result_dir_path=self.result_dir_path),
            "--define=modularitylabel {label}".format(label=self.modularity_label),
            "--define=dist {rpm_suffix}".format(rpm_suffix=self.rpm_suffix),
            "--addrepo={repo}".format(repo=self.batch_repo),
            f"--uniqueext={self.component['name']}",
        ]

        if self.external_repos:
            for repo in self.external_repos:
                mock_cmd.append("--addrepo=file://{repo}".format(repo=repo))

        if self.rootdir:
            mock_cmd.append("--rootdir={rootdir}".format(rootdir=self.rootdir))

        if self.srpm_path:
            mock_cmd.append(self.srpm_path)

        msg = "Running mock buildroot for component '{name}' with command:\n{cmd}".format(
            name=self.component["name"],
            cmd=mock_cmd,
        )
        logger.info(msg)
        stdout_log_file_path = self.result_dir_path + "/mock_stdout.log"

        msg = "The 'stdout' of the mock buildroot process is written to: {path}".format(path=stdout_log_file_path)
        logger.info(msg)

        with open(stdout_log_file_path, "w") as f:
            proc = subprocess.Popen(mock_cmd, stdout=f, stderr=f, universal_newlines=True)
        out, err = proc.communicate()

        if proc.returncode != 0:
            err_msg = "Command '{cmd}' returned non-zero value {code}\n{err}".format(
                cmd=mock_cmd,
                code=proc.returncode,
                err=err,
            )
            raise RuntimeError(err_msg)

        msg = "Mock buildroot finished build of component '{name}' successfully!".format(name=self.component["name"])
        logger.info(msg)
        logger.info("---------------------------------")

        self.finished = True
        self._finalize_component()
        return self.component["name"]

        # return out, err

    def get_artifacts(self):
        if self.finished:
            artifacts = [os.path.join(self.result_dir_path, f) for f in os.listdir(self.result_dir_path) if f.endswith("rpm")]

            return artifacts
        else:
            # TODO add exception
            pass

    def _finalize_component(self):
        if self.finished:
            finished_file_path = self.result_dir_path + "/finished"
            with open(finished_file_path, "w") as f:
                f.write("finished")
        else:
            # TODO add exception
            pass

    def _create_buildroot_result_dir(self):
        result_dir_path = os.path.join(self.batch_dir_path, self.component["name"])
        os.makedirs(result_dir_path)

        msg = "Created result dir for '{name}' mock build: {path}".format(
            name=self.component["name"],
            path=result_dir_path,
        )
        logger.info(msg)

        return result_dir_path
