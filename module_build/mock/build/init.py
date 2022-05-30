import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

from module_build.log import logger
from module_build.metadata import mmd_to_str
from module_build.mock.build.pool import MockBuildPool
from module_build.mock.build.root import MockBuildroot
from module_build.mock.config import MockConfig
from module_build.mock.info.context import MockBuildInfoContext
from module_build.mock.info.helpers import MockBuildState
from module_build.mock.info.main import MockBuildInfo


class MockBuilder:
    def __init__(self, mock_cfg_path, workdir, external_repos, rootdir, srpm_dir, workers):
        # Variables init
        self.workdir = workdir
        self.mock_cfg_path = mock_cfg_path
        self.external_repos = external_repos
        self.rootdir = rootdir

        # Basic check for dependencies, binaries and folder
        self._precheck()
        # Create object containing all information
        self.mock_info = MockBuildInfo()
        # Create multiprocess build queue
        self.pool = self._create_workers_pool(workers) if workers > 1 else None
        # Create mapping for all SRPM packages
        if srpm_dir:
            self._map_srpm_files(srpm_dir)

    def build(self, module_stream, resume, context_to_build=None):
        # Parse external repo metadata for modules depedency needs.
        logger.info("Processing build profiles from external repositories.")
        self.mock_info.generate_build_profiles(self.external_repos)

        # Get dist and arch information from mock conf file.
        logger.info("Extracting arch and dist information from mock conf file.")
        self.mock_info.dist, self.mock_info.arch = MockConfig.get_dist_and_arch_info(self.mock_cfg_path, module_stream.version)

        # Process the metadata provided by the module stream.
        # Components need to be organized to `build_batches`
        logger.info("Processing buildorder of the module stream.")
        self._create_build_contexts(module_stream)

        # Check if context exists and is valid
        # TODO: Custom Exception
        if context_to_build and not self.mock_info.get_context(context_to_build):
            raise Exception(f"The '{context_to_build}' does not exists in this module stream!")

        if self.mock_info.srpms_enabled:
            logger.info("Checking that all components have their matching SRPM...")
            self.mock_info.check_all_srpms()

        # TODO. Resume needs rework.
        if resume:
            msg = "------------- Resuming Module Build --------------"
            logger.info(msg)
            self.find_and_set_resume_point()

        # When the metadata processing is done, we can ge to the building of the defined `contexts`
        for context in self.mock_info.get_context():
            # Check if there is a specified context to be build and if the current context is the
            # specified context to be build. If not skip.
            if context.not_needed_or_finished(resume, context_to_build):
                logger.info(f"Skipping building context '{context.name}' state: '{MockBuildState.FINISHED}'")
                continue

            logger.info(f"Building context '{context.name}' of module stream '{module_stream.name}:{module_stream.stream}'...")

            # Create a dir for the contexts where we will store everything related to a `context`
            context.create_directory(self.workdir)
            logger.info(f"Created dir for '{context.name}' context: {context.dir}")

            # Mark for start building context
            context.state = MockBuildState.BUILDING

            logger.info("Initializing batch repository...")
            context.init_batch_repo()

            # Batches are presorted
            for batch in context.get_batches():
                # Skip batch building if FINISHED and resume mode is ON.
                if batch.is_finished(resume):
                    logger.info(
                        f"The batch number '{batch.index}' from context '{context.name}' state is set to '{MockBuildState.FINISHED}'. Skipping..."
                    )
                    continue

                # Start batch building
                logger.info(f"Building batch number {batch.index}...")

                # Create batch directory
                logger.info(f"Creating batch directory if needed for batch number {batch.index}...")
                batch.create_directory(context.dir)

                logger.info("Updating batch information status")
                context.batch_position = batch.index
                batch.state = MockBuildState.BUILDING

                for index, component in enumerate(batch._components, start=1):
                    if batch.current_component > index and resume:
                        logger.info(
                            f"The component '{component['name']}' of batch: '{batch.index}', context: '{context.name}' is already built. Skipping."
                        )
                        continue

                    if self.mock_info.srpms_enabled:
                        if srpm_path := self.mock_info.get_srpm_path(component["name"], component["ref"]):
                            logger.info(f"Found SRPM for: {component['name']}")
                        else:
                            raise Exception(f"Missing SRPM for {component['name']}")
                    else:
                        srpm_path = ""

                    logger.info(f"Building component {index} out of {len(batch._components)}...")
                    logger.info(f"Building component '{component['name']}' out of batch '{batch.index}' from context '{context.name}'...")

                    # Update Batch status info
                    batch.current_component = index
                    batch.component_state = MockBuildState.BUILDING

                    # we prepare a mock config for the mock buildroot.
                    logger.info(f"Generating mock config for component '{component['name']}'...")
                    mock_cfg = self._generate_and_process_mock_cfg(component, context.name, batch.index)

                    logger.info(f"Initializing mock buildroot for component '{component['name']}'...")

                    if self.pool:
                        self.pool.add_job(
                            component,
                            mock_cfg,
                            batch._dir,
                            batch.index,
                            context.modularity_label,
                            context.rpm_suffix,
                            context.batch_repo_url,
                            self.external_repos,
                            self.rootdir,
                            srpm_path,
                        )
                    else:
                        buildroot = MockBuildroot(
                            component,
                            mock_cfg,
                            batch._dir,
                            batch.index,
                            context.modularity_label,
                            context.rpm_suffix,
                            context.batch_repo_url,
                            self.external_repos,
                            self.rootdir,
                            srpm_path,
                        )

                        buildroot.run()

                        # batch["finished_builds"] += buildroot.get_artifacts()
                        batch.artifacts = buildroot.get_artifacts()

                        # Update batch Stats
                        batch.component_state = MockBuildState.FINISHED
                        batch.finished_comopnents = component
                        # build_context["status"]["num_finished_comps"] += 1

                self.pool.wait()

                # when the batch has finished building all its components, we will turn the batch
                # dir into a module stream. `finalize_batch` will add a modules.yaml file so the dir
                # and its built rpms can be used in the /next batch as modular dependencies
                batch.finalize_batch(context.name, context.batches_num, context.dependencies)

                # create/update the repository in `build_batches` dir so we can use it as
                # modular batch dependency repository for buildtime dependencies. Each finished
                # batch will be used for the next one as modular dependency.
                logger.info("Updating build batch modular repository...")
                context.init_batch_repo()

                batch.state = MockBuildState.FINISHED

            context.state = MockBuildState.FINISHED
            # self.finalize_build_context(context_name)

    def _precheck(self):
        # Check if workdir directory exists
        if not Path(self.workdir).is_dir():
            logger.fatal("Workdir directory does not exists.")
            sys.exit(1)

        if not importlib.util.find_spec("mockbuild"):
            logger.fatal("Mock cannot be found, please install is to continue.")
            sys.exit(1)

    def final_report(self):
        pass

    def _create_workers_pool(self, processess):
        logger.info(f"Creating pool with {processess} mock workers...")

        return MockBuildPool(processess)

    def _create_build_contexts(self, module_stream):
        """
        Method which creates metadata which track the build process and state of a context of a
        module stream.

        :param module_stream: a module stream object
        :type module_stream: :class:`module_build.stream.ModuleBuild` object
        """

        for context in module_stream.contexts:
            logger.info(f"Processing '{context.context_name}' context...")

            # TODO: This needs be bo moved probably to MockInfo because it
            # duplicates itself in every Context....
            context.set_arch(self.mock_info.arch)

            # Generate MockBuildInfoContext object with default values
            logger.info("Generating Context object...")
            build_info_context = MockBuildInfoContext(context, self.mock_info.dist)

            logger.info("Checking for buildtime module dependencies...")
            build_info_context.check_buildroot_profiles(build_info_context.buildtime_dependencies)

            logger.info("Generating build batches from the components buildorder...")
            build_info_context.generate_build_batches(module_stream.components)

            logger.info(f"Finished generating build context: '{build_info_context.name}'")
            self.mock_info.add_context(build_info_context)

    def _generate_and_process_mock_cfg(self, component, context_name, batch_num):
        mock_config = MockConfig(self.mock_cfg_path)

        # building modules from SRPM don't require MBS plugin
        if not self.mock_info.srpms_enabled:
            mock_config.enable_mbs("distgit", component["name"], component["ref"])

        # we need to tell mock which modular build dependencies need to be enabled
        context = self.mock_info.get_context(context_name)
        # modular_deps represent modular buildtime dependency provided by the definition in the
        # modulemd yaml file
        modular_deps = context.buildtime_dependencies
        # when using `buildorder`, the previous batch will be provided as a build dependency for the
        # next in the `buildorder`. If the `buildorder` is not used then all components will be
        # grouped into batch_0 by default and the `modular_batch_deps` will be an empty list.
        # TODO there is no need to extect it .............................
        # batch = context.get_batches(batch_num)
        # modular_batch_deps = context["build_batches"][batch_num]["modular_batch_deps"]
        # modules_to_enable = modular_deps + modular_batch_deps
        modules_to_enable = modular_deps

        # buildroot_profiles = context["buildroot_profiles"]
        # srpm_buildroot_profiles = context["srpm_buildroot_profiles"]
        # profiles_to_install = buildroot_profiles + srpm_buildroot_profiles
        profiles_to_install = context.buildroot_profiles

        mock_config.enable_modules(modules_to_enable)
        mock_config.enable_modules(profiles_to_install, True)
        mock_config.add_macros(context.rpm_macros)

        return mock_config

    def call_createrepo_c_on_dir(self, dir):
        # TODO move out as a standalone function
        msg = "createrepo_c called on dir: {path}".format(
            path=dir,
        )
        logger.info(msg)

        mock_cmd = ["createrepo_c", dir]
        proc = subprocess.Popen(mock_cmd)
        out, err = proc.communicate()

        if proc.returncode != 0:
            err_msg = "Command '%s' returned non-zero value %d%s" % (mock_cmd, proc.returncode, out)
            raise RuntimeError(err_msg)

        return out, err

    def finalize_build_context(self, context_name):
        msg = "Context '{name}' finished building all its batches...".format(name=context_name)
        logger.info(msg)
        context_dir = self.build_contexts[context_name]["dir"]
        final_repo_dir = context_dir + "/final_repo"
        os.makedirs(final_repo_dir)

        mmd = self.build_contexts[context_name]["metadata"].mmd

        name = mmd.get_module_name()
        stream = mmd.get_stream_name()
        version = mmd.get_version()
        context = mmd.get_context()
        arch = self.build_contexts[context_name]["metadata"].arch

        msg = ("Copying build artifacts from batches directories to the final repo" " dir: {path}").format(path=final_repo_dir)
        logger.info(msg)

        for bb in self.build_contexts[context_name]["build_batches"].values():
            for file_path in bb["finished_builds"]:
                shutil.copy(file_path, final_repo_dir)
            artifacts = self.get_artifacts_nevra(bb["finished_builds"])

            for a in artifacts:
                mmd.add_rpm_artifact(a)

        mmd_str = mmd_to_str(mmd)

        mmd_file_name = "/{n}:{s}:{v}:{c}:{a}.modulemd.yaml".format(
            n=name,
            s=stream,
            v=version,
            c=context_name,
            a=arch,
        )

        mmd_yaml_file_path = final_repo_dir + "/" + mmd_file_name
        with open(mmd_yaml_file_path, "w") as f:
            f.write(mmd_str)

        msg = ("Modulemd yaml file for the '{name}:{stream}:{version}:{context}' module stream has " "been written to: {path}").format(
            name=name, stream=stream, version=version, context=context, path=mmd_yaml_file_path
        )

        self.build_contexts[context_name]["final_repo_path"] = final_repo_dir
        self.build_contexts[context_name]["final_yaml_path"] = mmd_yaml_file_path

        # if the module steam has configured rpm filters we filter out the rpms which should not
        # be present in the final repo
        filtered_rpms = self.build_contexts[context]["filtered_rpms"]

        if filtered_rpms:
            rpm_filenames = [f for f in os.listdir(final_repo_dir) if f.endswith("rpm")]
            for f in rpm_filenames:
                rpm_name = f.rsplit("-", 2)[0]
                if rpm_name in filtered_rpms:
                    file_path = final_repo_dir + "/" + f
                    msg = "Filtering out '{rpm}' from the final repo...".format(rpm=f)
                    logger.info(msg)
                    os.remove(file_path)

        self.call_createrepo_c_on_dir(final_repo_dir)

        # we create a dummy file which marks the whole repo as finished. This serves as a marker
        # for the --resume feature to mark the whole build as finished
        finished_file_path = context_dir + "/finished"
        with open(finished_file_path, "w") as f:
            f.write("finished")

    def get_artifacts_nevra(self, artifacts):
        """
        We need to format name of RPMs to the NEVRA format. We do this with calling
        `rpm --queryformat` on built rpms. The NEVRA format is necesary for the artifact portion
        of a modulemd yaml file.
        """
        rpm_cmd = ["rpm", "--queryformat", "%{NAME} %{EPOCHNUM} %{VERSION} %{RELEASE} %{ARCH} %{SOURCERPM}\n", "-qp"]

        # TODO the whole method is dirty needs to be rewritten.
        # TODO need to add component dir to the component metadata so this will be simpler
        metadata = {}
        for a in artifacts:
            cwd, filename = a.rsplit("/", 1)
            if cwd not in metadata:
                metadata[cwd] = []

            metadata[cwd].append(filename)

        artifacts_nevra = []
        for cwd, filenames in metadata.items():
            out = subprocess.check_output(rpm_cmd + filenames, cwd=cwd, universal_newlines=True)

            nevras = out.strip().split("\n")
            for nevra in nevras:
                name, epoch, version, release, arch, src = nevra.split()
                if "none" in src:
                    arch = "src"
                artifacts_nevra.append("{}-{}:{}-{}.{}".format(name, epoch, version, release, arch))

        return artifacts_nevra

    def find_and_set_resume_point(self):
        # TODO this is too big i need to rewrite it and put it into smaller chunks, rewrite this
        # using os.walk()
        resume_point = {}
        # we find out which context we need to resume.
        expected_dir_names = []
        for context in self.build_contexts.values():
            expected_dir_names.append(context["nsvca"])

        # check if the work directory contains any context directories
        context_dirs = [d for d in os.listdir(self.workdir) if d in expected_dir_names]

        if not context_dirs:
            raise Exception(
                (
                    "No expected context directories in the working directory: {dir}\n" "Are you sure you are in the correct working directory?\n"
                ).format(dir=self.workdir)
            )

        msg = "Found possible context directories: {dirs}".format(dirs=context_dirs)
        logger.info(msg)

        for context_name, context in self.build_contexts.items():
            build_batches = context["build_batches"]

            # if the context dir does not exists the build process did not start yet for that
            # context
            if context["nsvca"] not in context_dirs:
                continue

            cd_path = self.workdir + "/" + context["nsvca"]
            # we look for the finished filename in the context dir
            finished = [f for f in os.listdir(cd_path) if f == "finished"]
            context = self.build_contexts[context_name]
            # we set dir for the existing context
            context["dir"] = cd_path
            build_batches_dir = cd_path + "/build_batches"
            batch_dirs = [d for d in os.listdir(build_batches_dir) if d.startswith("batch")]

            if finished:
                # if the whole context is finished, then we populate the builder metadata with
                # the current state of the context in the working directory.
                msg = ("Context '{context}' is finished. Extracting and processing " "metadata...").format(context=context_name)
                logger.info(msg)

                context["status"]["state"] = self.states[3]

                for position in sorted(build_batches):
                    actual_batch_name = "batch_{position}".format(position=position)

                    if actual_batch_name in batch_dirs:
                        batch_dir = build_batches_dir + "/" + actual_batch_name
                        finished = [f for f in os.listdir(batch_dir) if f == "finished"]
                        msg = "Processing batch number '{num}' of context '{context}'...".format(num=position, context=context_name)
                        logger.info(msg)

                        # we set the dir for existing batch
                        build_batches[position]["dir"] = batch_dir
                        for comp in build_batches[position]["components"]:
                            comp_dir = batch_dir + "/" + comp["name"]

                            if not os.path.isdir(comp_dir):
                                msg = (
                                    "Component dir of component '{name}' from batch number" " '{num}' of context '{context}' does not exist!"
                                ).format(
                                    name=comp["name"],
                                    num=position,
                                    context=context_name,
                                )
                                raise Exception(msg)

                            # add finished RPMs to the builder metadata
                            rpm_files = [f for f in os.listdir(comp_dir) if f.endswith("rpm")]
                            for rpm in rpm_files:
                                file_path = comp_dir + "/" + rpm
                                build_batches[position]["finished_builds"].append(file_path)

                        last_comp = len(build_batches[position]["components"]) - 1
                        build_batches[position]["batch_state"] = self.states[3]
                        build_batches[position]["curr_comp_state"] = self.states[3]
                        build_batches[position]["curr_comp"] = last_comp
                        msg = "Batch number '{num}' of context '{context}' is finished.".format(
                            num=position,
                            context=context_name,
                        )
                        logger.info(msg)
                    else:
                        msg = "Context dir of context '{context}' is corrupted! The batch dir " "'{dir}' of batch number '{num}' does not exist!"
                        raise Exception(msg)

            else:
                # if the context is not finished we need to find at which batch and which
                # component has failed last time
                msg = (
                    "Found an unfinished context! Context '{context}' is NOT finished. "
                    "Extracting and processing metadata. Setting context '{context}' as "
                    "the resume point."
                ).format(context=context_name)
                logger.info(msg)

                # we set the context resume point and the state of the context to "building"
                resume_point["context"] = context_name
                context["status"]["state"] = self.states[1]

                msg = "Finding existing batch directories of context '{context}'...".format(context=context_name)
                logger.info(msg)

                for position in sorted(build_batches):
                    actual_batch_name = "batch_{position}".format(position=position)

                    # we search through the existing batch dirs in the context dir.
                    if actual_batch_name in batch_dirs:
                        batch_dir = build_batches_dir + "/" + actual_batch_name

                        finished = [f for f in os.listdir(batch_dir) if f == "finished"]
                        msg = "Processing batch number '{num}' of context '{context}'...".format(num=position, context=context_name)
                        logger.info(msg)

                        # if the batch dir exist we add it to the builder metadata
                        build_batches[position]["dir"] = batch_dir
                        if finished:
                            # if the batch is marked as finished we get the build rpms and add them
                            # to the builder metadata
                            for comp in build_batches[position]["components"]:
                                comp_dir = batch_dir + "/" + comp["name"]
                                rpm_files = [f for f in os.listdir(comp_dir) if f.endswith("rpm")]
                                for rpm in rpm_files:
                                    file_path = comp_dir + "/" + rpm
                                    build_batches[position]["finished_builds"].append(file_path)

                            last_comp = len(build_batches[position]["components"]) - 1
                            build_batches[position]["batch_state"] = self.states[3]
                            build_batches[position]["curr_comp_state"] = self.states[3]
                            build_batches[position]["curr_comp"] = last_comp
                            msg = "Batch number '{num}' of context '{context}' is finished.".format(
                                num=position,
                                context=context_name,
                            )
                            logger.info(msg)
                        else:
                            # if a batch is not finished we need to identify which component failed
                            msg = (
                                "Found an unfinished batch! Batch number '{num}' of context"
                                " '{context}' is NOT finished. Setting batch number '{num}' "
                                "of context '{context}' as the resume point."
                            ).format(num=position, context=context_name)
                            logger.info(msg)

                            # we set the batch resume point and the batch state to 'building'
                            resume_point["batch"] = position
                            context["status"]["current_build_batch"] = position
                            build_batches[position]["batch_state"] = self.states[1]

                            for index, comp in enumerate(build_batches[position]["components"]):
                                comp_dir = batch_dir + "/" + comp["name"]

                                # we check if the component dir exists
                                if os.path.isdir(comp_dir):
                                    msg = ("Processing component '{name}' of batch number '{num}' " "of context '{context}'...").format(
                                        num=position, context=context_name, name=comp["name"]
                                    )
                                    logger.info(msg)

                                    finished = [f for f in os.listdir(comp_dir) if f == "finished"]
                                    # we find out if the dir is marked as finished
                                    if finished:
                                        msg = ("Component '{name}' of batch number '{num}' of " "context '{context}' is finished.").format(
                                            num=position, context=context_name, name=comp["name"]
                                        )
                                        logger.info(msg)
                                        # if the component is finished we add the information
                                        # about the artifacts to the builder metadata
                                        filenames = os.listdir(comp_dir)
                                        rpm_files = [f for f in filenames if f.endswith("rpm")]
                                        for rpm in rpm_files:
                                            file_path = comp_dir + "/" + rpm
                                            build_batches[position]["finished_builds"].append(file_path)
                                    else:
                                        # if an unfinished component is found we update the batch
                                        # and set the component resume point
                                        msg = (
                                            "Found an unfinished component! Component '{name}'"
                                            " of batch number '{num}' of context '{context}' is "
                                            "NOT finished. Setting component '{name}' as the "
                                            "resume point."
                                        )
                                        build_batch = build_batches[position]
                                        build_batch["batch_state"] = self.states[1]
                                        build_batch["curr_comp_state"] = self.states[0]
                                        build_batch["curr_comp"] = index
                                        resume_point["component"] = comp["name"]
                                        shutil.rmtree(comp_dir)
                                        break
                                else:
                                    # if the directory of the current component does not exist and
                                    # we have not found any unfinished component until now, this
                                    # means that for some reason the directory of the unfinished
                                    # component does not exist anymore and we set the resume point
                                    # to that component
                                    if "component" not in resume_point:
                                        msg = (
                                            "Found an unfinished component! "
                                            "It seems that the component directory of component "
                                            "'{name}' does not exist. Component '{name}' is "
                                            "next in line for building. Setting component "
                                            "'{name}' as the resume point."
                                        ).format(name=comp["name"])
                                        logger.info(msg)

                                        build_batch = build_batches[position]
                                        build_batch["batch_state"] = self.states[1]
                                        build_batch["curr_comp_state"] = self.states[0]
                                        build_batch["curr_comp"] = index
                                        resume_point["component"] = comp["name"]
                                        break

                            # if for some reason all the components are finished but the resume
                            # point for the component has not been set, we asume that the batch
                            # is finished but was not set to the finished state.
                            if index + 1 == len(build_batches[position]["components"]):
                                if "component" not in resume_point:
                                    yaml_file = [f for f in os.listdir(batch_dir) if f.endswith("yaml")]

                                    if len(yaml_file):
                                        yaml_file_path = batch_dir + "/" + yaml_file[0]
                                        os.remove(yaml_file_path)

                                    build_batch = build_batches[position]
                                    last_comp = len(build_batch["components"]) - 1
                                    build_batch["batch_state"] = self.states[3]
                                    build_batch["curr_comp_state"] = self.states[3]
                                    build_batch["curr_comp"] = last_comp
                                    self.finalize_batch(position, context_name)
                                    msg = ("Batch number '{num}' of context '{context}'" " is finished.").format(
                                        num=position,
                                        context=context_name,
                                    )
                                    logger.info(msg)
                                    # after we finalize the current branch we set the resume point
                                    # to the first component of the next batch
                                    next_batch_position = position + 1

                                    # we need to find out if this is the last batch in the context
                                    if next_batch_position in build_batches:
                                        next_batch = build_batches[next_batch_position]
                                        next_comp = next_batch["components"][0]
                                    else:
                                        # if there is no other batch then we set the resume point
                                        # for the component to the last component of the current
                                        # batch
                                        next_batch_position = position
                                        next_comp = build_batch["components"][last_comp]

                                    resume_point["batch"] = next_batch_position
                                    resume_point["component"] = next_comp["name"]
                                    break
                    else:
                        if "batch" not in resume_point:
                            # if all of the existing batches are finished and the batch resume point
                            # was not found we set the resume point for the next batch in line and
                            # its first component
                            first_component = build_batches[position]["components"][0]
                            resume_point["batch"] = position
                            resume_point["component"] = first_component["name"]
                            break

            context["dir"] = cd_path

        if resume_point:
            # if there is something to resume, the resume point will be at least populated by the
            # context to resume. When we have a resume point we need to remove final repo because
            # the number of build RPMs can change.
            # TODO put the removing of final repo to its own method
            context_name = resume_point["context"]
            context_dir_path = self.build_contexts[context_name]["dir"]
            final_repo_path = context_dir_path + "/final_repo"

            if os.path.isdir(final_repo_path):
                logger.info("Removing old final repo...")

                shutil.rmtree(final_repo_path)

            if len(resume_point) and len(resume_point) == 1 and "context" in resume_point:
                msg = (
                    "The context '{name}' has finished building all its batches and components."
                    "It seems it was not finalized. Finalizing context..."
                ).format(name=context_name)

            else:
                msg = (
                    "According to the files and metadata provided from the working directory "
                    "'{dir}' the resume point of the module build has been identified.\nThe "
                    "build will resume building at component '{comp}' of build batch number "
                    "'{num}' of build context '{context}'"
                ).format(dir=self.workdir, comp=resume_point["component"], num=resume_point["batch"], context=resume_point["context"])
        else:
            msg = "No resume point found! It seems all batches and components of your module " "stream are built!"
        logger.info(msg)
