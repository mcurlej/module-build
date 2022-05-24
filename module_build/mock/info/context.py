from pathlib import Path

from module_build.mock.info.batch import MockBuildInfoBatch
from module_build.mock.info.helpers import MockBuildState, MockBuildStatusContext
from module_build.mock.info.utils import call_createrepo_c_on_dir


class MockBuildInfoContext:
    def __init__(self, context, dist=""):
        self._dir = ""
        self._build_batches = []
        self._metadata = context
        self._current_build_batch = 0
        self._buildroot_profiles = {}
        self._status = MockBuildStatusContext(state=MockBuildState.INIT, current_build_batch=0, num_finished_comps=[])

        self._dist = dist  # TODO This needs to be gone.

    @property
    def name(self):
        return self._metadata.context_name

    @property
    def nsvca(self):
        return self._metadata.get_NSVCA()

    @property
    def rpm_macros(self):
        return self._metadata.rpm_macros

    @property
    def modularity_label(self):
        return self._metadata.get_modularity_label()

    @property
    def dependencies(self):
        return self._metadata.dependencies

    @property
    def state(self):
        return self._status["state"]

    @property
    def batches_num(self):
        return len(self._build_batches)

    @property
    def rpm_suffix(self):
        return self._metadata.get_rpm_suffix(self._dist)  # Ehhhh distttt

    @property
    def batch_repo_url(self):
        return f"file://{self.batch_repo_path}"

    @property
    def buildtime_dependencies(self):
        return self.dependencies.get("buildtime", None)

    @property
    def finished_components(self):
        return len(self._status["num_finished_comps"])

    @property
    def buildroot_profiles(self):
        return self._buildroot_profiles

    @property
    def dir(self):
        """
        Path to directory containing given batch.

        Returns:
            str: Relative path to batch directory/
        """
        return str(self._dir.resolve())

    @finished_components.setter
    def finished_components(self, component):
        self._status["num_finished_comps"].append(component)

    @state.setter
    def state(self, state):
        """
        Sets state for current context.

        Args:
            state (MockBuildState): State.

        Raises:
            Exception: TODO
        """
        if not isinstance(state, MockBuildState):
            raise Exception("Wrong instance type")
        self._status["state"] = state

    @state.setter
    def batch_position(self, position):
        """
        Sets current batch build position.

        Args:
            position (int): Batch index.
        """
        self._status["current_build_batch"] = position

    def _batch_present(self, index):
        """
        Check for batch with given index and return it.

        Args:
            index (int): Batch index.

        Returns:
            list: List of MatchBuildInfoBatch
        """
        return [batch for batch in self._build_batches if batch.index == index]

    def _add_to_build_batch(self, buildorder, component):
        """Adds component object to given batch.

        Args:
            buildorder (int): Index of buildorder.
            component (str): Component name.
        """
        if batch := self._batch_present(buildorder):
            batch[0].add_component(component)
        else:
            self._build_batches.append(MockBuildInfoBatch(buildorder, component))

    def _generate_modular_batch_dependencies(self):
        # This is not needed
        pass
        # # We start iterating from 2nd element becouse first batch 0 won't have any deps
        # for batch in self._build_batches[1:]:
        #     index = sorted_build_batches.index(order)
        #     # every batch will have the previous batch as a modular stream dependency excluding the
        #     # first batch. The first batch does not have any previous batch so there will be no
        #     # no modular batch dependency.
        #         # we need to find out how many batches are there previously
        #         prev_batches = [b for b in sorted_build_batches[:index]]
        #         # for each previous batch we add a batch modular stream dependency
        #         for b in prev_batches:
        #             build_batches[order]["modular_batch_deps"].append("batch{b}:{b}".format(
        #                 b=b
        #             ))

    def _sort_batches(self):
        """
        Sorts batches based on index property.
        """
        self._build_batches.sort(key=lambda x: x.index)

    def create_directory(self, workdir):
        """
        Creates main directory for given context.

        Args:
            workdir (str): Path to main working directory.
        """
        path = Path(workdir) / self.nsvca
        path.mkdir(parents=True, exist_ok=True)
        self._dir = path

    def generate_build_batches(self, components):
        """
        Method which organizes components of a module stream into build batches.

        :param components: list of components
        :type components: list
        :return build_batches: dict of build batches.
        :rtype build_batches: dict
        """

        for component in components:
            self._add_to_build_batch(component["buildorder"], component)

        # Index (which is really Buildorder) is not guaranted to be sorted. or to be in clean
        # scheme like 0, 1, 2, 3. So let's sort it.
        self._sort_batches()

        # after we have the build batches populated we need to generate list of module streams,
        # which will be used in the batches as modular dependencies. Each batch will serve as a
        # module stream dependency for the next batch.
        # self.generate_modular_batch_dependencies()

    def get_modular_batch_deps(self, batch_id):
        # after we have the build batches populated we need to generate list of module streams,
        # which will be used in the batches as modular dependencies. Each batch will serve as a
        # module stream dependency for the next batch.
        for batch in self._build_batches:
            if batch.index < batch_id:
                yield f"batch{batch.index}:{batch.index}"

    def get_batches(self, index=None):
        if index:
            return next(filter(lambda x: x.index == index, self._build_batches))
        else:
            return self._build_batches

    def check_buildroot_profiles(self, buildroot_profiles):
        for ms in self._metadata.dependencies.get("buildtime", []):
            for bp in buildroot_profiles:  # srpm & rpm
                if ms in bp:
                    self._buildroot_profiles.append(bp[ms])

    def init_batch_repo(self):
        self.batch_repo_path = Path(self._dir) / "build_batches"

        if not self.batch_repo_path.is_dir():
            self.batch_repo_path.mkdir(parents=True, exist_ok=True)
            call_createrepo_c_on_dir(self.batch_repo_path)

    def not_needed_or_finished(self, resume, context_to_build=None):
        return (context_to_build and context_to_build != self.name) or (self.state == MockBuildState.FINISHED and resume)
