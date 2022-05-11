import copy
import os
import shutil
import subprocess
from collections import OrderedDict

import mockbuild.config

from module_build.log import logger
from module_build.metadata import (generate_and_populate_output_mmd, mmd_to_str,
                                   generate_module_stream_version)
from module_build.modulemd import Modulemd


class MockBuilder:
    # TODO enable building only specific contexts
    # TODO enable multiprocess queues for component building.
    def __init__(self, mock_cfg_path, workdir, external_repos, rootdir):
        self.states = ["init", "building", "failed", "finished"]
        self.workdir = workdir
        self.mock_cfg_path = mock_cfg_path
        self.external_repos = external_repos
        self.rootdir = rootdir

    def build(self, module_stream, resume, context_to_build=None):
        # first we must process the metadata provided by the module stream
        # components need to be organized to `build_batches`
        logger.info("Processing buildorder of the module stream.")
        self.create_build_contexts(module_stream)

        if context_to_build:
            if context_to_build not in self.build_contexts:
                raise Exception("The '{context}' does not exists in this module stream!".format(
                    context=context_to_build))

        if resume:
            msg = "------------- Resuming Module Build --------------"
            logger.info(msg)
            self.find_and_set_resume_point()

        # when the metadata processing is done, we can ge to the building of the defined `contexts`
        for context_name, build_context in self.build_contexts.items():
            # check if there is a specified context to be build and if the current context is the
            # specified context to be build. If not skip.
            if context_to_build and context_to_build != context_name:
                continue

            if build_context["status"]["state"] == self.states[3] and resume:
                msg = "The build context '{context}' state is set to '{state}'. Skipping...".format(
                    context=context_name,
                    state=self.states[3],
                )
                logger.info(msg)
                continue

            msg = "Building context '{context}' of module stream '{module}:{stream}'...".format(
                context=context_name,
                module=module_stream.name,
                stream=module_stream.stream)
            logger.info(msg)
            # we create a dir for the contexts where we will store everything related to a `context`
            if "dir" not in build_context:
                build_context["dir"] = self.create_build_context_dir(context_name)

            build_context["status"]["state"] = self.states[1]
            batch_repo_path = os.path.abspath(build_context["dir"] + "/build_batches")
            batch_repo = "file://{repo}".format(repo=batch_repo_path)

            if not os.path.isdir(batch_repo_path):
                os.makedirs(batch_repo_path)
                msg = "Initializing batch repo for the first time..."
                logger.info(msg)
                self.call_createrepo_c_on_dir(batch_repo_path)

            sorted_batches = sorted(build_context["build_batches"])
            # the keys in `build_context["build_batches"]` represent the `buildorder` of the context
            # we use `sorted` to get the `buildorder` into an ascending order
            for position in sorted_batches:
                batch = build_context["build_batches"][position]

                if batch["batch_state"] == self.states[3] and resume:
                    msg = ("The batch number '{num}' from context '{context}' state is set "
                           "to '{state}'. Skipping...").format(
                        context=context_name,
                        state=self.states[3],
                        num=position,
                    )
                    logger.info(msg)
                    continue

                msg = "Building batch number {num}...".format(num=position)
                logger.info(msg)

                if "dir" not in batch:
                    batch["dir"] = self.create_build_batch_dir(context_name, position)

                build_context["status"]["current_build_batch"] = position
                build_context["build_batches"][position]["batch_state"] = self.states[1]

                for index, component in enumerate(batch["components"]):

                    if batch["curr_comp"] > index and resume:
                        msg = ("The component '{name}' of batch number '{num}' of "
                               "context '{context}' is already built. Skipping...").format(
                                   name=component["name"],
                                   num=position,
                                   context=context_name)
                        logger.info(msg)
                        continue

                    msg = "Building component {index} out of {all}...".format(
                        index=index + 1,
                        all=len(batch["components"]))
                    logger.info(msg)

                    msg = ("Building component '{name}' out of batch '{batch}' from context"
                           " '{context}'...").format(name=component["name"],
                                                     batch=position,
                                                     context=context_name)
                    logger.info(msg)

                    build_context["build_batches"][position]["curr_comp"] = index
                    build_context["build_batches"][position]["curr_comp_state"] = self.states[1]

                    msg = "Generating mock config for component '{name}'...".format(
                        name=component["name"]
                    )
                    logger.info(msg)
                    # we prepare a mock config for the mock buildroot.
                    mock_cfg_str = self.generate_and_process_mock_cfg(component, context_name,
                                                                      position)

                    msg = "Initializing mock buildroot for component '{name}'...".format(
                        name=component["name"]
                    )
                    logger.info(msg)

                    buildroot = MockBuildroot(component, mock_cfg_str, batch["dir"], position,
                                              build_context["modularity_label"],
                                              build_context["rpm_suffix"],
                                              batch_repo, self.external_repos, self.rootdir)

                    buildroot.run()

                    batch["finished_builds"] += buildroot.get_artifacts()

                    build_context["build_batches"][position]["curr_comp_state"] = self.states[3]
                    build_context["status"]["num_finished_comps"] += 1

                # when the batch has finished building all its components, we will turn the batch
                # dir into a module stream. `finalize_batch` will add a modules.yaml file so the dir
                # and its built rpms can be used in the /next batch as modular dependencies
                self.finalize_batch(position, context_name)

                build_context["build_batches"][position]["batch_state"] = self.states[3]

            build_context["status"]["state"] = self.states[3]
            self.finalize_build_context(context_name)

    def final_report(self):
        pass

    def generate_build_batches(self, components):
        """Method which organizes components of a module stream into build batches.

        :param components: list of components
        :type components: list
        :return build_batches: dict of build batches.
        :rtype build_batches: dict
        """
        build_batches = {}

        for component in components:
            position = component["buildorder"]

            if position not in build_batches:
                build_batches[position] = {
                    "components": [],
                    "curr_comp": 0,
                    "curr_comp_state": self.states[0],
                    "batch_state": self.states[0],
                    "finished_builds": [],
                    "modular_batch_deps": [],
                }

            build_batches[position]["components"].append(component)

        # after we have the build batches populated we need to generate list of module streams,
        # which will be used in the batches as modular dependencies. Each batch will serve as a
        # module stream dependency for the next batch.
        sorted_build_batches = sorted(build_batches)

        for order in sorted_build_batches:
            index = sorted_build_batches.index(order)
            # every batch will have the previous batch as a modular stream dependency excluding the
            # first batch. The first batch does not have any previous batch so there will be no
            # no modular batch dependency.
            if index != 0:
                # we need to find out how many batches are there previously
                prev_batches = [b for b in sorted_build_batches[:index]]
                # for each previous batch we add a batch modular stream dependency
                for b in prev_batches:
                    build_batches[order]["modular_batch_deps"].append("batch{b}:{b}".format(
                        b=b
                    ))

        msg = "The following build batches where identified according to the buildorder:"
        logger.info(msg)

        msg_batch = ""
        for order in sorted_build_batches:
            comp_names = []

            for comp in build_batches[order]["components"]:
                comp_names.append(comp["name"])

            msg_batch += """
            batch number (buildorder): {order}
            component count: {count}
            modular batch dependencies:
            {deps}
            components:
            {comp_names}
            ---------------------""".format(order=order, count=len(comp_names),
                                            comp_names=comp_names,
                                            deps=build_batches[order]["modular_batch_deps"])
        logger.info(msg_batch)

        msg = "Total build batch count: {num}".format(num=len(sorted_build_batches))
        logger.info(msg)

        return build_batches

    def create_build_contexts(self, module_stream):
        """Method which creates metada which track the build process and state of a context of a
        module stream.

        :param module_stream: a module stream object
        :type module_stream: :class:`module_build.stream.ModuleBuild` object
        """
        mock_path, mock_filename = self.mock_cfg_path.rsplit("/", 1)

        # Support for mock2 and mock3
        # mockbuild is missing __version__ attribute so we are handling Exception
        try:
            mock_cfg = mockbuild.config.load_config(mock_path, self.mock_cfg_path, None,
                                                    module_stream.version, mock_path)
        except TypeError:
            mock_cfg = mockbuild.config.load_config(mock_path, self.mock_cfg_path, None)

        dist = None
        if "dist" in mock_cfg:
            dist = mock_cfg["dist"]

        if "target_arch" in mock_cfg:
            self.arch = mock_cfg["target_arch"]
        else:
            raise Exception(("Your mock configuration file does not provide the information about "
                             "the architecture for which the module stream should be build. Please"
                             " inlcude the `target_arch` config option in your initial mock cfg!"))

        buildroot_profiles = {}
        srpm_buildroot_profiles = {}
        if self.external_repos:
            for repo in self.external_repos:
                mi = Modulemd.ModuleIndex.new()
                repodata_path = repo + "/repodata"
                yaml_file = [f for f in os.listdir(repodata_path) if f.endswith(
                    "modules.yaml.gz")]

                if yaml_file:
                    yaml_file_path = repodata_path + "/" + yaml_file[0]
                    mi.update_from_file(yaml_file_path, True)
                    streams = mi.search_streams()

                    for s in streams:
                        profiles = s.get_profile_names()
                        name = s.get_module_name()
                        stream = s.get_stream_name()
                        module_stream_str = "{name}:{stream}".format(name=name, stream=stream)

                        if "buildroot" in profiles:
                            stream_profile = "{stream}/buildroot".format(stream=module_stream_str)
                            buildroot_profiles[module_stream_str] = stream_profile

                        if "srpm-buildroot" in profiles:
                            stream_profile = "{stream}/srpm-buildroot".format(
                                stream=module_stream_str)
                            srpm_buildroot_profiles[module_stream_str] = stream_profile

        build_contexts = OrderedDict()

        for context in module_stream.contexts:
            msg = "Processing '{context}' context...".format(context=context.context_name)
            logger.info(msg)
            context.set_arch(self.arch)
            build_context = {
                "name": context.context_name,
                "nsvca": context.get_NSVCA(),
                "modularity_label": context.get_modularity_label(),
                "metadata": context,
                "rpm_suffix": context.get_rpm_suffix(dist),
                "modular_deps": context.dependencies,
                "rpm_macros": context.rpm_macros,
                "filtered_rpms": module_stream.filtered_rpms,
                "buildroot_profiles": [],
                "srpm_buildroot_profiles": [],
                "status": {
                    "state": self.states[0],
                    "current_build_batch": 0,
                    "num_components": len(module_stream.components),
                    "num_finished_comps": 0,
                }
            }

            if buildroot_profiles:
                for ms in build_context["modular_deps"]["buildtime"]:
                    if ms in buildroot_profiles:
                        stream_profile = buildroot_profiles[ms]
                        build_context["buildroot_profiles"].append(stream_profile)

            if srpm_buildroot_profiles:
                for ms in build_context["modular_deps"]["buildtime"]:
                    if ms in srpm_buildroot_profiles:
                        stream_profile = srpm_buildroot_profiles[ms]
                        build_context["srpm_buildroot_profiles"].append(stream_profile)

            logger.info("Generating build batches from the components buildorder...")
            build_context["build_batches"] = self.generate_build_batches(module_stream.components)
            build_contexts[context.context_name] = build_context

        self.build_contexts = build_contexts

    def create_build_context_dir(self, context_name):
        if not self.build_contexts:
            # TODO make this to a custom exception
            raise Exception(("No `build_contexts` metadata found! Please run the `create_build_"
                             "contexts` method before creating directories for contexts."))

        context_dir_path = os.path.join(self.workdir,
                                        self.build_contexts[context_name]["nsvca"])
        os.makedirs(context_dir_path)

        msg = "Created dir for '{context}' context: {path}".format(context=context_name,
                                                                   path=context_dir_path)
        logger.info(msg)

        return context_dir_path

    def create_build_batch_dir(self, context_name, batch_num):
        if not self.build_contexts:
            # TODO make this to a custom exception
            raise Exception(("No `build_contexts` metadata found! Please run the `create_build_"
                             "contexts` method before creating directories for contexts."))

        batches_dir_path = os.path.join(self.workdir,
                                        self.build_contexts[context_name]["nsvca"],
                                        "build_batches",
                                        "batch_{batch_num}".format(batch_num=batch_num))
        os.makedirs(batches_dir_path)

        msg = "Created dir for batch number {num} from '{context}' context: {path}".format(
            num=batch_num,
            context=context_name,
            path=batches_dir_path,
        )
        logger.info(msg)

        return batches_dir_path

    def generate_and_process_mock_cfg(self, component, context_name, batch_num):
        # TODO consider to remove from this class and make a standalone function
        mock_cfg_str = ""
        mock_cfg_str += "config_opts['scm'] = True\n"
        mock_cfg_str += "config_opts['scm_opts']['method'] = 'distgit'\n"
        mock_cfg_str += "config_opts['scm_opts']['package'] = '{component_name}'\n".format(
            component_name=component["name"]
        )
        mock_cfg_str += "config_opts['scm_opts']['branch'] = '{component_ref}'\n".format(
            component_ref=component["ref"]
        )

        # we need to tell mock which modular build dependencies need to be enabled
        context = self.build_contexts[context_name]
        # modular_deps represent modular buildtime dependency provided by the definition in the
        # modulemd yaml file
        modular_deps = context["modular_deps"]["buildtime"]
        # when using `buildorder`, the previous batch will be provided as a build dependency for the
        # next in the `buildorder`. If the `buildorder` is not used then all components will be
        # grouped into batch_0 by default and the `modular_batch_deps` will be an empty list.
        modular_batch_deps = context["build_batches"][batch_num]["modular_batch_deps"]
        modules_to_enable = modular_deps + modular_batch_deps
        mock_cfg_str += "# we enable necesary build module dependencies.\n"
        mock_cfg_str += "config_opts['module_enable'] = {modules}\n".format(
            modules=modules_to_enable)

        buildroot_profiles = context["buildroot_profiles"]
        srpm_buildroot_profiles = context["srpm_buildroot_profiles"]
        profiles_to_install = buildroot_profiles + srpm_buildroot_profiles

        mock_cfg_str += "config_opts['module_install'] = {profiles}\n".format(
            profiles=profiles_to_install)

        mock_cfg_str += "# we set the necessary macros provided by the `build_opts` option.\n"
        for m in context["rpm_macros"]:
            if m:
                macro, value = m.split(" ")
                mock_cfg_str += "config_opts['macros']['{macro}'] = {value}\n".format(
                    macro=macro,
                    value=value,
                )

        mock_cfg_str += "include('{mock_cfg_path}')\n".format(mock_cfg_path=self.mock_cfg_path)

        return mock_cfg_str

    def finalize_batch(self, position, context_name):
        msg = "Batch number {num} finished building all its components.".format(num=position)
        logger.info(msg)

        build_batch = self.build_contexts[context_name]["build_batches"][position]

        msg = "Artifact count: {count}".format(count=len(build_batch["finished_builds"]))
        logger.info(msg)

        msg = "\nList of artifacts:\n"
        for fb in build_batch["finished_builds"]:
            msg += "- {file_path}\n".format(file_path=fb)
        logger.info(msg)

        num_batches = len(self.build_contexts[context_name]["build_batches"])
        last_batch = sorted(self.build_contexts[context_name]["build_batches"])[-1]
        batch_dir = self.build_contexts[context_name]["build_batches"][position]["dir"]
        # we need to create a module stream out of a build_batch. This will happen only when there
        # is more batches then 1. If there is only 1 batch (no set buildorder) nothing needs to
        # be done. If the batch is the last in the buildorder it will be not used as a modular
        # dependency for any other batch so we also do nothing.
        if num_batches > 1 and last_batch != position:
            name = "batch{num}".format(num=position)
            stream = "{num}".format(num=position)
            context = "b{num}".format(num=position)
            version = generate_module_stream_version()
            if position + 1 == num_batches:
                description = ("This module stream is a buildorder modular dependency for "
                               "batch_{last_batch}.").format(last_batch=num_batches)
            else:
                description = ("This module stream is a buildorder modular dependency for "
                               "batch_{num}-{last_batch}.").format(num=position + 1,
                                                                   last_batch=num_batches)
            summary = description
            mod_license = "MIT"
            # for each new batch mmd we want a copy of the modular dependencies which are
            # provided from the initial mmd file
            modular_deps = copy.deepcopy(self.build_contexts[context_name]["modular_deps"])
            modular_batch_deps = build_batch["modular_batch_deps"]

            for d in modular_batch_deps:
                modular_deps["buildtime"].append(d)
                modular_deps["runtime"].append(d)

            components = build_batch["components"]

            artifacts = self.get_artifacts_nevra(build_batch["finished_builds"])

            mmd = generate_and_populate_output_mmd(name, stream, context, version, description,
                                                   summary, mod_license, components,
                                                   artifacts, modular_deps)

            mmd_str = mmd_to_str(mmd)

            mmd_file_name = "/{n}:{s}:{v}:{c}:{a}.modulemd.yaml".format(
                n=name,
                s=stream,
                v=version,
                c=context,
                a=self.build_contexts[context_name]["metadata"].arch,
            )
            file_path = batch_dir + mmd_file_name

            with open(file_path, "w") as f:
                f.write(mmd_str)

            msg = ("Batch number {position} is defined as modular batch dependency for batches "
                   "{num}-{last_batch}").format(position=position, num=position + 1,
                                                last_batch=last_batch)
            logger.info(msg)
            msg = "Modular metadata written to: {path}".format(path=file_path)

            # create/update the repository in `build_batches` dir so we can use it as
            # modular batch dependency repository for buildtime dependencies. Each finished
            # batch will be used for the next one as modular dependency.
            msg = "Updating build batch modular repository..."
            logger.info(msg)
            build_batches_dir = self.build_contexts[context_name]["dir"] + "/build_batches"
            self.call_createrepo_c_on_dir(build_batches_dir)
        # we create a dummy file which marks the whole batch as finished. This serves as a marker
        # for the --resume feature to mark the whole build as finished
        finished_file_path = batch_dir + "/finished"
        with open(finished_file_path, "w") as f:
            f.write("finished")

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
            err_msg = "Command '%s' returned non-zero value %d%s" % (mock_cmd, proc.returncode,
                                                                     out)
            raise RuntimeError(err_msg)

        return out, err

    def finalize_build_context(self, context_name):
        msg = "Context '{name}' finished building all its batches...".format(
            name=context_name)
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

        msg = ("Copying build artifacts from batches directories to the final repo"
               " dir: {path}").format(path=final_repo_dir)
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

        msg = ("Modulemd yaml file for the '{name}:{stream}:{version}:{context}' module stream has "
               "been written to: {path}").format(name=name, stream=stream, version=version,
                                                 context=context, path=mmd_yaml_file_path)

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
        rpm_cmd = ["rpm", "--queryformat",
                   "%{NAME} %{EPOCHNUM} %{VERSION} %{RELEASE} %{ARCH} %{SOURCERPM}\n",
                   "-qp"]

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
            out = subprocess.check_output(rpm_cmd + filenames, cwd=cwd,
                                          universal_newlines=True)

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
            raise Exception(("No expected context directories in the working directory: {dir}\n"
                             "Are you sure you are in the correct working directory?\n").format(
                dir=self.workdir))

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
                msg = ("Context '{context}' is finished. Extracting and processing "
                       "metadata...").format(context=context_name)
                logger.info(msg)

                context["status"]["state"] = self.states[3]

                for position in sorted(build_batches):
                    actual_batch_name = "batch_{position}".format(position=position)

                    if actual_batch_name in batch_dirs:
                        batch_dir = build_batches_dir + "/" + actual_batch_name
                        finished = [f for f in os.listdir(batch_dir) if f == "finished"]
                        msg = "Processing batch number '{num}' of context '{context}'...".format(
                            num=position, context=context_name)
                        logger.info(msg)

                        # we set the dir for existing batch
                        build_batches[position]["dir"] = batch_dir
                        for comp in build_batches[position]["components"]:
                            comp_dir = batch_dir + "/" + comp["name"]

                            if not os.path.isdir(comp_dir):
                                msg = ("Component dir of component '{name}' from batch number"
                                       " '{num}' of context '{context}' does not exist!").format(
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
                        msg = ("Context dir of context '{context}' is corrupted! The batch dir "
                               "'{dir}' of batch number '{num}' does not exist!")
                        raise Exception(msg)

            else:
                # if the context is not finished we need to find at which batch and which
                # component has failed last time
                msg = ("Found an unfinished context! Context '{context}' is NOT finished. "
                       "Extracting and processing metadata. Setting context '{context}' as "
                       "the resume point.").format(context=context_name)
                logger.info(msg)

                # we set the context resume point and the state of the context to "building"
                resume_point["context"] = context_name
                context["status"]["state"] = self.states[1]

                msg = "Finding existing batch directories of context '{context}'...".format(
                    context=context_name)
                logger.info(msg)

                for position in sorted(build_batches):
                    actual_batch_name = "batch_{position}".format(position=position)

                    # we search through the existing batch dirs in the context dir.
                    if actual_batch_name in batch_dirs:
                        batch_dir = build_batches_dir + "/" + actual_batch_name

                        finished = [f for f in os.listdir(batch_dir) if f == "finished"]
                        msg = "Processing batch number '{num}' of context '{context}'...".format(
                            num=position, context=context_name)
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
                            msg = ("Found an unfinished batch! Batch number '{num}' of context"
                                   " '{context}' is NOT finished. Setting batch number '{num}' "
                                   "of context '{context}' as the resume point.").format(
                                num=position, context=context_name)
                            logger.info(msg)

                            # we set the batch resume point and the batch state to 'building'
                            resume_point["batch"] = position
                            context["status"]["current_build_batch"] = position
                            build_batches[position]["batch_state"] = self.states[1]

                            for index, comp in enumerate(build_batches[position]["components"]):
                                comp_dir = batch_dir + "/" + comp["name"]

                                # we check if the component dir exists
                                if os.path.isdir(comp_dir):
                                    msg = ("Processing component '{name}' of batch number '{num}' "
                                           "of context '{context}'...").format(
                                        num=position, context=context_name, name=comp["name"])
                                    logger.info(msg)

                                    finished = [f for f in os.listdir(comp_dir) if f == "finished"]
                                    # we find out if the dir is marked as finished
                                    if finished:
                                        msg = ("Component '{name}' of batch number '{num}' of "
                                               "context '{context}' is finished.").format(
                                            num=position,
                                            context=context_name,
                                            name=comp["name"])
                                        logger.info(msg)
                                        # if the component is finished we add the information
                                        # about the artifacts to the builder metadata
                                        filenames = os.listdir(comp_dir)
                                        rpm_files = [f for f in filenames if f.endswith("rpm")]
                                        for rpm in rpm_files:
                                            file_path = comp_dir + "/" + rpm
                                            build_batches[position]["finished_builds"].append(
                                                file_path)
                                    else:
                                        # if an unfinished component is found we update the batch
                                        # and set the component resume point
                                        msg = ("Found an unfinished component! Component '{name}'"
                                               " of batch number '{num}' of context '{context}' is "
                                               "NOT finished. Setting component '{name}' as the "
                                               "resume point.")
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
                                        msg = ("Found an unfinished component! "
                                               "It seems that the component directory of component "
                                               "'{name}' does not exist. Component '{name}' is "
                                               "next in line for building. Setting component "
                                               "'{name}' as the resume point.").format(
                                                   name=comp["name"])
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
                                    yaml_file = [f for f in os.listdir(batch_dir) if f.endswith(
                                        "yaml")]

                                    if len(yaml_file):
                                        yaml_file_path = batch_dir + "/" + yaml_file[0]
                                        os.remove(yaml_file_path)

                                    build_batch = build_batches[position]
                                    last_comp = len(build_batch["components"]) - 1
                                    build_batch["batch_state"] = self.states[3]
                                    build_batch["curr_comp_state"] = self.states[3]
                                    build_batch["curr_comp"] = last_comp
                                    self.finalize_batch(position, context_name)
                                    msg = ("Batch number '{num}' of context '{context}'"
                                           " is finished.").format(
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
                msg = ("The context '{name}' has finished building all its batches and components."
                       "It seems it was not finalized. Finalizing context...").format(
                           name=context_name)

            else:
                msg = ("According to the files and metadata provided from the working directory "
                       "'{dir}' the resume point of the module build has been identified.\nThe "
                       "build will resume building at component '{comp}' of build batch number "
                       "'{num}' of build context '{context}'").format(
                           dir=self.workdir,
                    comp=resume_point["component"],
                    num=resume_point["batch"],
                    context=resume_point["context"])
        else:
            msg = ("No resume point found! It seems all batches and components of your module "
                   "stream are built!")
        logger.info(msg)


class MockBuildroot:
    def __init__(self, component, mock_cfg_str, batch_dir_path, batch_num, modularity_label,
                 rpm_suffix, batch_repo, external_repos, rootdir):

        self.finished = False
        self.component = component
        self.mock_cfg_str = mock_cfg_str
        self.batch_dir_path = batch_dir_path
        self.batch_num = batch_num
        self.modularity_label = modularity_label
        self.rpm_suffix = rpm_suffix
        self.result_dir_path = self._create_buildroot_result_dir()
        self.mock_cfg_path = self._create_mock_cfg_file()
        self.batch_repo = batch_repo
        self.external_repos = external_repos
        self.rootdir = rootdir

    def run(self):
        mock_cmd = ["mock", "-v", "-r", self.mock_cfg_path,
                    "--resultdir={result_dir_path}".format(result_dir_path=self.result_dir_path),
                    "--define=modularitylabel {label}".format(label=self.modularity_label),
                    "--define=dist {rpm_suffix}".format(
                        rpm_suffix=self.rpm_suffix),
                    "--addrepo={repo}".format(repo=self.batch_repo),
                    ]

        if self.external_repos:
            for repo in self.external_repos:
                mock_cmd.append("--addrepo=file://{repo}".format(repo=repo))

        if self.rootdir:
            mock_cmd.append("--rootdir={rootdir}".format(rootdir=self.rootdir))

        msg = "Running mock buildroot for component '{name}' with command:\n{cmd}".format(
            name=self.component["name"],
            cmd=mock_cmd,
        )
        logger.info(msg)
        stdout_log_file_path = self.result_dir_path + "/mock_stdout.log"

        msg = "The 'stdout' of the mock buildroot process is written to: {path}".format(
            path=stdout_log_file_path)
        logger.info(msg)

        with open(stdout_log_file_path, "w") as f:
            proc = subprocess.Popen(mock_cmd, stdout=f, stderr=f,
                                    universal_newlines=True)
        out, err = proc.communicate()

        if proc.returncode != 0:
            err_msg = "Command '{cmd}' returned non-zero value {code}\n{err}".format(
                cmd=mock_cmd,
                code=proc.returncode,
                err=err,
            )
            raise RuntimeError(err_msg)

        msg = "Mock buildroot finished build of component '{name}' successfully!".format(
            name=self.component["name"]
        )
        logger.info(msg)
        logger.info("---------------------------------")

        self.finished = True
        self._finalize_component()

        return out, err

    def get_artifacts(self):
        if self.finished:
            artifacts = [os.path.join(self.result_dir_path, f)
                         for f in os.listdir(self.result_dir_path) if f.endswith("rpm")]

            return artifacts
        else:
            # TODO add exception
            pass

    def _finalize_component(self):
        if self.finished:
            finished_file_path = self.result_dir_path + "/finished"
            with open(finished_file_path, "w") as f:
                f.write("finished")
        else:
            # TODO add exception
            pass

    def _create_buildroot_result_dir(self):
        result_dir_path = os.path.join(self.batch_dir_path, self.component["name"])
        os.makedirs(result_dir_path)

        msg = "Created result dir for '{name}' mock build: {path}".format(
            name=self.component["name"],
            path=result_dir_path,
        )
        logger.info(msg)

        return result_dir_path

    def _create_mock_cfg_file(self):
        mock_cfg_file_path = "{result_dir_path}/{component_name}_mock.cfg".format(
            result_dir_path=self.result_dir_path,
            component_name=self.component["name"]
        )

        with open(mock_cfg_file_path, "w") as f:
            f.write(self.mock_cfg_str)

        msg = "Mock config for '{name}' component written to: {path}".format(
            name=self.component["name"],
            path=mock_cfg_file_path,
        )
        logger.info(msg)

        return mock_cfg_file_path
