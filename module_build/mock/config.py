from module_build.constants import KEY_MODULE_ENABLE, KEY_MODULE_INSTALL
from module_build.log import logger


class MockConfig:
    def __init__(self, mock_cfg_path):
        self.content = {}
        self.base_mock_cfg_path = mock_cfg_path

    def enable_modules(self, modules, to_install=False):
        key = KEY_MODULE_INSTALL if to_install else KEY_MODULE_ENABLE

        if key in self.content:
            self.content[key].append(modules)
        else:
            self.content[key] = modules

    def enable_mbs(self, method, package, branch):
        self.content = {
            "config_opts['scm']": "True",
            "config_opts['scm_opts']['method']": f"'{method}'",
            "config_opts['scm_opts']['package']": f"'{package}'",
            "config_opts['scm_opts']['branch']": f"'{branch}'",
        }

    def disable_mbs(self):
        for k in list(self.content.keys()):
            if k.startswith("config_opts['scm'"):
                del self.content[k]

    def add_macros(self, macros):
        for m in macros:
            if m:
                macro, value = m.split(" ")
                self.content[f"config_opts['macros']['{macro}']"] = {value}

    def write_config(self, result_dir, component_name):
        path = f"{result_dir}/{component_name}_mock.cfg"

        with open(path, "w") as f:
            for key, value in self.content.items():
                f.write(f"{key} = {value}\n")

            f.write(f"include('{self.base_mock_cfg_path}')")

        logger.info("Mock config for '{component_name}' component written to: {path}")

        return path
