from pathlib import Path

from module_build.log import logger
from module_build.metadata import generate_module_stream_version
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

    def create_directory(self, context_workdir):
        path = Path(context_workdir) / "build_batches" / f"batch_{self.index}"
        path.mkdir(parents=True, exist_ok=True)
        self._dir = path

    def add_component(self, component):
        self._components.append(component)

    # def finalize_batch(self, position, context_name, num_of_batches_in_context):
    #     logger.info(f"Batch number '{self.index}' finished building all its components.")

    #     # Get Context & Batch Objects
    #     context = self.mock_info.get_context(context_name)
    #     build_batch = context.get_batch(position)

    #     logger.info(f"Artifact count: {self.finished_builds_num}")

    #     msg = "\nList of artifacts:\n"
    #     for fb in self.finished_builds:
    #         msg += "- {file_path}\n".format(file_path=fb)
    #     logger.info(msg)

    #     # num_batches = len(context.get_batchs())
    #     last_batch = sorted(self.build_contexts[context_name]["build_batches"])[-1]
    #     batch_dir = self.build_contexts[context_name]["build_batches"][position]["dir"]
    #     # we need to create a module stream out of a build_batch. This will happen only when there
    #     # is more batches then 1. If there is only 1 batch (no set buildorder) nothing needs to
    #     # be done. If the batch is the last in the buildorder it will be not used as a modular
    #     # dependency for any other batch so we also do nothing.

    #     if num_of_batches_in_context > 1 and num_of_batches_in_context != self.index:
    #         name = f"batch{self.index}"
    #         stream = f"{self.index}"
    #         context = f"b{self.index}"
    #         version = generate_module_stream_version()

    #         if self.index + 1 == num_of_batches_in_context:
    #             description = f"This module stream is a buildorder modular dependency for batch_{num_of_batches_in_context}."
    #         else:
    #             description = f"This module stream is a buildorder modular dependency for batch_{self.index}-{num_of_batches_in_context}."

    #         summary = description
    #         mod_license = "MIT"
    #         # for each new batch mmd we want a copy of the modular dependencies which are
    #         # provided from the initial mmd file
    #         modular_deps = copy.deepcopy(self.build_contexts[context_name]["modular_deps"])
    #         modular_batch_deps = build_batch["modular_batch_deps"]

    #         for d in modular_batch_deps:
    #             modular_deps["buildtime"].append(d)
    #             modular_deps["runtime"].append(d)

    #         components = build_batch["components"]

    #         artifacts = self.get_artifacts_nevra(build_batch["finished_builds"])

    #         mmd = generate_and_populate_output_mmd(
    #             name, stream, context, version, description, summary, mod_license, components, artifacts, modular_deps
    #         )

    #         mmd_str = mmd_to_str(mmd)

    #         mmd_file_name = "/{n}:{s}:{v}:{c}:{a}.modulemd.yaml".format(
    #             n=name,
    #             s=stream,
    #             v=version,
    #             c=context,
    #             a=self.build_contexts[context_name]["metadata"].arch,
    #         )
    #         file_path = batch_dir + mmd_file_name

    #         with open(file_path, "w") as f:
    #             f.write(mmd_str)

    #         msg = ("Batch number {position} is defined as modular batch dependency for batches " "{num}-{last_batch}").format(
    #             position=position, num=position + 1, last_batch=last_batch
    #         )
    #         logger.info(msg)
    #         msg = "Modular metadata written to: {path}".format(path=file_path)

    #         # create/update the repository in `build_batches` dir so we can use it as
    #         # modular batch dependency repository for buildtime dependencies. Each finished
    #         # batch will be used for the next one as modular dependency.
    #         msg = "Updating build batch modular repository..."
    #         logger.info(msg)
    #         build_batches_dir = self.build_contexts[context_name]["dir"] + "/build_batches"
    #         self.call_createrepo_c_on_dir(build_batches_dir)
    #     # we create a dummy file which marks the whole batch as finished. This serves as a marker
    #     # for the --resume feature to mark the whole build as finished
    #     finished_file_path = batch_dir + "/finished"
    #     with open(finished_file_path, "w") as f:
    #         f.write("finished")
