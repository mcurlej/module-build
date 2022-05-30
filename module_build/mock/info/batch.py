import copy
from pathlib import Path

from module_build.constants import DEFAULT_LICENSE_TYPE
from module_build.log import logger
from module_build.metadata import generate_and_populate_output_mmd, generate_module_stream_version, mmd_to_str
from module_build.mock.info.helpers import MockBuildState, MockBuildStatusBatch


class MockBuildInfoBatch:
    def __init__(self, buildorder, component=None):
        self.index = buildorder

        self._artifacts = []
        self._components = [component]
        self._status = MockBuildStatusBatch(
            state=MockBuildState.INIT, component_state=MockBuildState.INIT, current_component=0, finished_components=[]
        )

    @property
    def state(self):
        return self._status["state"]

    @property
    def artifacts(self):
        return self._artifacts

    @property
    def finished_builds(self):
        return self._status["finished_components"]

    @property
    def finished_builds_num(self):
        return len(self._status["finished_components"])

    @property
    def current_component(self):
        return self._status["current_component"]

    @property
    def component_state(self):
        return self._status["component_state"]

    @property
    def finished_components(self):
        return self._status["finished_components"]

    @property
    def dir(self):
        return self._dir

    @state.setter
    def state(self, state):
        self._status["state"] = state

    @artifacts.setter
    def artifacts(self, artifacts):
        self._artifacts.extend(artifacts)

    @finished_components.setter
    def finished_components(self, finished_components):
        self._status["finished_components"].append(finished_components)

    @component_state.setter
    def component_state(self, component_state):
        self._status["component_state"] = component_state

    @current_component.setter
    def current_component(self, current_component):
        self._status["current_component"] = current_component

    def _mark_as_finished(self):
        finished_file_path = self.dir / "finished"
        finished_file_path.touch(exist_ok=True)

    def create_directory(self, context_workdir):
        path = Path(context_workdir) / "build_batches" / f"batch_{self.index}"
        path.mkdir(parents=True, exist_ok=True)
        self._dir = path

    def add_component(self, component):
        self._components.append(component)

    def is_finished(self, resume):
        return self.state == MockBuildState.FINISHED

    def get_components_names(self):
        for component in self._components:
            yield component["name"]

    def get_components(self, names=[]):
        if not names:
            return self._components

    def finalize_batch(self, context_name, num_of_batches_in_context, dependencies):
        logger.info(f"Batch number '{self.index}' finished building all its components.")
        logger.info(f"Artifact count: {self.finished_builds_num}")

        msg = "\nList of artifacts:\n"
        for fb in self._artifacts:
            msg += "- {file_path}\n".format(file_path=fb)
        logger.info(msg)

        # we need to create a module stream out of a build_batch. This will happen only when there
        # is more batches then 1. If there is only 1 batch (no set buildorder) nothing needs to
        # be done. If the batch is the last in the buildorder it will be not used as a modular
        # dependency for any other batch so we also do nothing.

        if num_of_batches_in_context > 1 and num_of_batches_in_context != self.index:
            name = f"batch{self.index}"
            stream = f"{self.index}"
            context = f"b{self.index}"
            version = generate_module_stream_version()

            description = "This module stream is a buildorder modular dependency for batch_"
            if self.index + 1 == num_of_batches_in_context:
                description += f"{num_of_batches_in_context}"
            else:
                description += f"{self.index}-{num_of_batches_in_context}"

            summary = description

            # for each new batch mmd we want a copy of the modular dependencies which are
            # provided from the initial mmd file
            modular_deps = copy.deepcopy(dependencies)

            # First batch is excluded ofc
            if not self.index:
                # batch numeration is static so no need to store it anywhere.
                for i in range(0, self.index):
                    for key in ("buildtime", "runtime"):
                        modular_deps[key].append(f"batch{i}:{i}")

            components = self.get_components()
            artifacts = self.get_artifacts_nevra(self.artifacts)

            mmd = generate_and_populate_output_mmd(
                name, stream, context, version, description, summary, DEFAULT_LICENSE_TYPE, components, artifacts, modular_deps
            )

            mmd_str = mmd_to_str(mmd)

            mmd_file_name = "/{n}:{s}:{v}:{c}:{a}.modulemd.yaml".format(
                n=name,
                s=stream,
                v=version,
                c=context,
                a=self.build_contexts[context_name]["metadata"].arch,
            )
            file_path = self.dir + mmd_file_name

            with open(file_path, "w") as f:
                f.write(mmd_str)

            logger.info(
                f"Batch number {self.index} is defined as modular batch dependency for batches {self.index + 1}-{num_of_batches_in_context - 1}"
            )
            logger.info(f"Modular metadata written to: {file_path}")

        # we create a dummy file which marks the whole batch as finished. This serves as a marker
        # for the --resume feature to mark the whole build as finished
        self._mark_as_finished()
