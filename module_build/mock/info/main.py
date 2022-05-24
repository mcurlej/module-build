from pathlib import Path

from module_build import modulemd
from module_build.constants import RPM_BUILDROOT_PROFILE, SRPM_BUILDROOT_PROFILE
from module_build.mock.info.srpm import MockBuildInfoSRPM


class MockBuildInfo:
    def __init__(self):
        self.srpms = []
        self.contexts = []
        self._buildroot_profiles = {}

    @property
    def arch(self):
        return self._arch

    @property
    def dist(self):
        return self._dist

    @property
    def buildroot_profiles(self):
        """
        Available RPM buildroot profiles.

        Returns:
            list: TODO
        """
        return self._buildroot_profiles.get(RPM_BUILDROOT_PROFILE, None)

    @property
    def srpm_buildroot_profiles(self):
        """
        Available SRPM buildroot profiles.

        Returns:
            list: TODO
        """
        return self._buildroot_profiles.get(SRPM_BUILDROOT_PROFILE, None)

    @property
    def srpm_count(self):
        """
        Returns number of MockBuildInfoSRPM stored in object.

        Returns:
            int: Number of srpms objects.
        """
        return len(self.srpms)

    @property
    def srpms_enabled(self):
        """
        Check if srpm mode is enabled based on number MockBuildInfoSRPM
        objects stored in the class.

        Returns:
            bool: Check if srpms are enabled.
        """
        return self.srpms != []

    @arch.setter
    def arch(self, arch):
        self._arch = arch

    @dist.setter
    def dist(self, dist):
        self._dist = dist

    def _srpm_present(self, name):
        """
        Checks for SRPM existance with given name.

        Args:
            name (str): Component name.

        Returns:
            list: MockBuildInfoSRPM objects
        """
        return [srpm for srpm in self.srpms if srpm.name == name]

    def _get_all_components_names(self):
        for context in self.contexts:
            for batch in context.get_batches():
                yield batch.get_components_names()

    def add_srpm(self, name, path):
        """
        Add MockBuildInfoSRPM object to current instance.

        Args:
            name (str): Name of module.
            path (str, Path): Path to the srpm.
        """
        if srpms := self._srpms_present(name):
            srpms[0].add_path(path)
        else:
            self.srpms.append(MockBuildInfoSRPM(name, path))

    def get_srpm_path(self, name, match=""):
        """
        Wrapped for getting path from MockBuildInfoSRPM based on module name.

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

    def add_context(self, context):
        """
        Add context object to MockInfo.

        Args:
            context (MockBuildInfoContext): MockBuildInfoContext instance.
        """
        self.contexts.append(context)

    def get_context(self, name=None):
        """
        Get context object with given name.

        Args:
            index (int): Index of given Context object.

        Returns:
            MockBuildIndoContext: Context object
        """
        if name:
            return next(filter(lambda x: x.name == name, self.contexts))
        else:
            return self.contexts

    def check_all_srpms(self):
        for component_name in self._get_all_components_names():
            if not self._srpm_present(component_name):
                raise Exception(f"Missing SRPM for component {component_name}")

    def generate_build_profiles(self, external_repos):
        """
        Generates available buildroot profiles from external repository.

        Args:
            external_repos (str): Path to external repository directory.
        """
        for repo in external_repos:
            mi = modulemd.ModuleIndex.new()
            if (yaml_file_path := next((Path(repo) / "repodata").glob("*modules.yaml.gz"), None)) is None:
                mi.update_from_file(str(yaml_file_path.resolve()), True)
                streams = mi.search_streams()

                for s in streams:
                    profiles = s.get_profile_names()
                    module_stream_str = f"{s.get_module_name()}:{s.get_stream_name()}"
                    if SRPM_BUILDROOT_PROFILE in profiles:
                        self._buildroot_profiles[SRPM_BUILDROOT_PROFILE][module_stream_str] = f"{s.get_stream_name()}/{SRPM_BUILDROOT_PROFILE}"
                    if RPM_BUILDROOT_PROFILE in profiles:
                        self._buildroot_profiles[RPM_BUILDROOT_PROFILE][module_stream_str] = f"{s.get_stream_name()}/{RPM_BUILDROOT_PROFILE}"
