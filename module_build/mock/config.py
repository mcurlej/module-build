import mockbuild.config
from module_build.constants import (
    KEY_MACROS_PREFIX,
    KEY_MODULE_ENABLE,
    KEY_MODULE_INSTALL,
    KEY_SCM_BRANCH,
    KEY_SCM_ENABLE,
    KEY_SCM_METHOD,
    KEY_SCM_PACKAGE,
    KEY_SCM_PREFIX_ALL,
)
from module_build.log import logger


class MockConfig:
    def __init__(self, mock_cfg_path):
        self.arch = None
        self.dist = None
        self.content = {}
        self.base_mock_cfg_path = mock_cfg_path

    def enable_modules(self, modules, to_install=False):
        """
        Enables options to install/enable module dependencies while constructing
        the buildroot.

        Args:
            modules (list): Names of modules.
            to_install (bool, optional): Switch to install module mode. Defaults to False.
        """
        key = KEY_MODULE_INSTALL if to_install else KEY_MODULE_ENABLE

        if key in self.content:
            self.content[key].append(modules)
        else:
            self.content[key] = modules

    def enable_mbs(self, method, package, branch):
        """
            Adds all neccessary options to mock config to enable MBS functionality.

        Args:
            method (str): Method name
            package (str): Package name
            branch (str): Name of repository branch
        """
        self.content.update(
            {
                KEY_SCM_ENABLE: "True",
                KEY_SCM_METHOD: f"'{method}'",
                KEY_SCM_PACKAGE: f"'{package}'",
                KEY_SCM_BRANCH: f"'{branch}'",
            }
        )

    def disable_mbs(self):
        """
        Removes all MBS keys from mock config.
        """
        for k in list(self.content.keys()):
            if k.startswith(KEY_SCM_PREFIX_ALL):
                del self.content[k]

    def add_macros(self, macros):
        """
        Add specified macros to mock config.

        Args:
            macros (list): List of macros in format: MACRO<space>VALUE
        """
        for m in macros:
            if m:
                macro, value = m.split(" ")
                self.content[f"{KEY_MACROS_PREFIX}['{macro}']"] = value

    def write_config(self, result_dir, component_name):
        """
        Writes mock config to provided directory.

        Args:
            result_dir (str): Output directory for mock config file
            component_name (str): Suffix for mock config filename

        Returns:
            str: Path to newly create mock config file.
        """
        path = f"{result_dir}/{component_name}_mock.cfg"

        with open(path, "w") as f:
            for key, value in self.content.items():
                f.write(f"{key} = {value}\n")

            f.write(f"include('{self.base_mock_cfg_path}')")

        logger.info(f"Mock config for '{component_name}' component written to: {path}")

        return path

    @staticmethod
    def get_dist_and_arch_info(mock_cfg_path, msv):
        mock_path, mock_filename = mock_cfg_path.rsplit("/", 1)

        try:
            mock_cfg = mockbuild.config.load_config(mock_path, mock_cfg_path, None, msv, mock_path)
        except TypeError:
            mock_cfg = mockbuild.config.load_config(mock_path, mock_cfg_path, None)

        dist = mock_cfg["dist"] if "dist" in mock_cfg else None

        if "target_arch" in mock_cfg:
            arch = mock_cfg["target_arch"]
        else:
            raise Exception(
                (
                    "Your mock configuration file does not provide the information about "
                    "the architecture for which the module stream should be build. Please"
                    " inlcude the `target_arch` config option in your initial mock cfg!"
                )
            )

        return dist, arch
