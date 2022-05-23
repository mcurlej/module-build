from pathlib import Path


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
