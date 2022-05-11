from pathlib import Path


class MockBuildInfo():
    def __init__(self):
        self.srpms = []

    def _if_srpm_present(self, name):
        return [srpm for srpm in self.srpms if srpm.name == name]

    def add_srpm(self, name, path):
        """Add MockBuildInfoSRPM object to current instance.

        Args:
            name (str): Name of module.
            path (str, Path): Path to the srpm.
        """
        if srpms := self._if_srpm_present(name):
            srpms[0].add_path(path)
        else:
            self.srpms.append(MockBuildInfoSRPM(name, path))

    def get_srpm_path(self, name, match=""):
        """Wrapped for getting path from MockBuildInfoSRPM based on module name.

        Args:
            name (str): Module name.
            match (str, optional): Module ref. Defaults to "".

        Returns:
            str: Relative path to srpm.
        """
        for srpm in self.srpms:
            if srpm.name == name:
                return srpm.get_path(match)

        return None

    def get_srpm_count(self):
        """Returns number of MockBuildInfoSRPM stored in object.

        Returns:
            int: Number of srpms objects.
        """
        return len(self.srpms)

    def srpms_enabled(self):
        """Check if srpm mode is enabled based on number MockBuildInfoSRPM
        objects stored in class.

        Returns:
            bool: Check if srpms are enabled
        """
        return self.srpms != []


class MockBuildInfoSRPM():
    """
    Object which stores single SRPM information.
    Part of MockBuildInfo.
    """

    def __init__(self, name, path):
        self.name = name
        self.paths = [self._make_path_obj(path)]

    def _make_path_obj(self, path):
        """Helper method for parsing srpm path.

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
        """Method for adding additional srpm paths for modules.

        Args:
            path (Path, str): Path for SRPM.
        """
        path = self._make_path_obj(path)
        self.paths.append(path)

    def get_path(self, match=""):
        """Method that returns path to srpm.

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
