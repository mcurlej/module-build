import tempfile
from pathlib import Path

import libarchive
from module_build.constants import SPEC_EXTENSION, SRPM_EXTENSION
from module_build.log import logger


class MockBuildInfoSRPM:
    """
    Object which stores single SRPM information.
    Part of MockBuildInfo.
    """

    def __init__(self, name, path):
        self.name = name
        self.paths = [self._make_path_obj(path)]

    def _make_path_obj(self, path):
        """
        Helper method for parsing srpm path.

        Args:
            path (Path, str): Path to srpm

        Raises:
            Exception: Default/

        Returns:
            Path: Path object to srpm.
        """
        if isinstance(path, Path):
            return path
        elif isinstance(path, str):
            return Path(path)
        else:
            raise Exception("Wrong path object")

    def add_path(self, path):
        """
        Method for adding additional srpm paths for modules.

        Args:
            path (Path, str): Path for SRPM.
        """
        path = self._make_path_obj(path)
        self.paths.append(path)

    def get_path(self, match=""):
        """
        Method that returns path to srpm.

        Args:
            match (str, optional): String that should be part of src name. Defaults to "".

        Returns:
            str: Relative srpm path
        """
        # By default return first object
        if len(self.paths) == 1:
            return str(self.paths[0].resolve())

        # In case of multiple SRPM with the same name, try to match one using 'ref'
        for path in self.paths:
            if match in path.name:
                return str(path.resolve())

        # Should never happend but just in case
        return None

    def map_srpm_files(self, srpm_dir):
        """
            Function responsible for mapping srpm names to modules names.
            It extracts .spec file from the rpm and looks for 'Name:'
            line with an actual name. All results are stored in mock_info
            variable inside class object.

        Args:
            srpm_dir (str, Path): Path to directory with SRPM files
        """
        logger.info(f"Mapping SRPMs in directory: {srpm_dir}")

        srpm_dir = srpm_dir if isinstance(srpm_dir, Path) else Path(srpm_dir)

        for file in srpm_dir.glob(f"*.{SRPM_EXTENSION}"):
            logger.info(f"SRPM: Mapping component for '{file.name}' file")

            with libarchive.file_reader(str(file.resolve())) as archive:
                for entry in archive:
                    # check for spec file
                    if not all((entry.isfile, entry.pathname.endswith(SPEC_EXTENSION))):
                        continue

                    logger.info(f"SRPM: Located .spec file: '{entry.pathname}'")

                    # read content of spec file and look for "Name:"
                    with tempfile.NamedTemporaryFile() as tmp:
                        for block in entry.get_blocks():
                            tmp.write(block)

                        # Reset fd
                        tmp.flush()
                        tmp.seek(0)

                        for line in tmp:
                            # we are still in bytes
                            line_str = line.decode("utf-8")

                            if line_str.startswith("Name:"):
                                component_name = line_str.split(":", 1)[1].strip()
                                logger.info(f"SRPM: Found SRPM: '{file.name}' for component: '{component_name}'")
                                self.mock_info.add_srpm(component_name, srpm_dir / file.name)
                                break
                    break
