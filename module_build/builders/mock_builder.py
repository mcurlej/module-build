import copy
import os
import shutil
import subprocess

from module_build.metadata import (generate_and_populate_output_mmd, mmd_to_str,
                                   generate_module_stream_version)

class MockBuilder:
    # TODO enable building only specific contexts
    # TODO enable multiprocess queues for component building.
    def __init__(self, mock_cfg_path, workdir):
        self.states = ["init", "building", "failed", "finished"]
        self.workdir = workdir
        self.mock_cfg_path = mock_cfg_path

    def build(self, module_stream):
        # first we must process the metadata provided by the module stream
        # components need to be organized to `build_batches`
        self.create_build_contexts(module_stream)

        # when the metadata processing is done, we can ge to the building of the defined `contexts`
        for context_name, build_context in self.build_contexts.items():
            # we create a dir for the contexts where we will store everything related to a `context`
            build_context["dir"] = self.create_build_context_dir(context_name)

            build_context["status"]["state"] = self.states[1]
            batch_repo_path = os.path.abspath(build_context["dir"] + "/build_batches")
            batch_repo = "file://{repo}".format(repo=batch_repo_path)

            # the keys in `build_context["build_batches"]` represent the `buildorder` of the context
            # we use `sorted` to get the `buildorder` into an ascending order
            for position in sorted(build_context["build_batches"]):

                batch = build_context["build_batches"][position]
                batch["dir"] = self.create_build_batch_dir(context_name, position)

                build_context["status"]["current_build_batch"] = position
                build_context["build_batches"][position]["batch_state"] = self.states[1]

                # create/update the repository in `build_batches` dir so we can use it as modular 
                # batch dependency repository for buildtime dependencies. Each finished batch will 
                # be used for the next one as modular dependency.
                self.call_createrepo_c_on_dir(batch_repo_path)

                for index, component in enumerate(batch["components"]):

                    build_context["build_batches"][position]["curr_comp"] = index
                    build_context["build_batches"][position]["curr_comp_state"] = self.states[1]

                    # we prepare a mock config for the mock buildroot.
                    mock_cfg_str = self.generate_and_process_mock_cfg(component, context_name,
                                                                      position)

                    buildroot = MockBuildroot(component, mock_cfg_str, batch["dir"], position,
                                              build_context["modularity_label"],
                                              build_context["rpm_suffix"],
                                              batch_repo)

                    buildroot.run()

                    batch["finished_builds"] += buildroot.get_artifacts()

                    build_context["build_batches"][position]["curr_comp_state"] = self.states[3]
                    build_context["status"]["num_finished_comps"] += 1

                # when the batch has finished building all its components, we will turn the batch 
                # dir into a module stream. `close_batch` will add a modules.yaml file so the dir 
                # and its build rpms can be used in the next batch as modular dependencies
                self.close_batch(position, context_name)

                build_context["build_batches"][position]["batch_state"] = self.states[3]

            build_context["status"]["state"] = self.states[3]
            self.finalize_build_context(context_name)


    def build_status(self):
        pass

    def generate_build_batches(self, components):
        """Method which organizes components of a module stream into build batches.

        :param components: list of components
        :type components: list
        :return build_batches: dict of build batches.
        :rtype build_batches: dict
        """
        # TODO maybe rewrite it as a class method?
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

        return build_batches

    def create_build_contexts(self, module_stream):
        """Method which creates metada which track the build process and state of a context of a 
        module stream.

        :param module_stream: a module stream object
        :type module_stream: :class:`module_build.stream.ModuleBuild` object
        """
        build_contexts = {}

        for context in module_stream.contexts:
            # TODO need to set arch in a more automatic way.
            context.set_arch("x86_64")
            build_context = {
                "name": context.context_name,
                "nsvca": context.get_NSVCA(),
                "modularity_label": context.get_modularity_label(),
                "metadata": context,
                "rpm_suffix": context.get_rpm_suffix(),
                "modular_deps": context.dependencies,
                "rpm_macros": context.rpm_macros,
                "status": {
                    "state": self.states[0],
                    "current_build_batch": 0,
                    "num_components": len(module_stream.components),
                    "num_finished_comps": 0,
                }
            }
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

        return batches_dir_path

    def create_and_populate_repo_dir(self):
        pass

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

    def close_batch(self, position, context_name):
        num_batches = len(self.build_contexts[context_name]["build_batches"])
        last_batch = sorted(self.build_contexts[context_name]["build_batches"])[-1]
        # we need to create a module stream out of a build_batch. This will happen only when there 
        # is more batches then 1. If there is only 1 batch (no set buildorder) nothing needs to 
        # be done. If the batch is the last in the buildorder it will be not used as a modular
        # dependency for any other batch so we also do nothing.
        if num_batches > 1 and last_batch != position:
            #
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
            build_batch = self.build_contexts[context_name]["build_batches"][position]
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

            batch_dir = self.build_contexts[context_name]["build_batches"][position]["dir"]
            mmd_file_name = "/{n}:{s}:{v}:{c}:{a}.modulemd.yaml".format(
                n=name,
                s=stream,
                v=version,
                c=context,
                a=self.build_contexts[context_name]["metadata"].arch,
            )

            with open(batch_dir + mmd_file_name, "w") as f:
                f.write(mmd_str)

    def call_createrepo_c_on_dir(self, dir):
        # TODO move out as a standalone function
        mock_cmd = ["createrepo_c", dir]
        proc = subprocess.Popen(mock_cmd)
        out, err = proc.communicate()

        if proc.returncode != 0:
            err_msg = "Command '%s' returned non-zero value %d%s" % (args, proc.returncode,
                                                                     out_log_msg)
            raise RuntimeError(err_msg)

        return out, err

    def finalize_build_context(self, context_name):
        # TODO copy all built rpms from all batch dirs to a single directory, create the final mmd file 
        # and call createrepo_c on it.
        context_dir = self.build_contexts[context_name]["dir"]
        final_repo_dir = context_dir + "/final_repo"
        os.makedirs(final_repo_dir)

        mmd = self.build_contexts[context_name]["metadata"].mmd

        for b in self.build_contexts[context_name]["build_batches"].values():
            for f in b["finished_builds"]:
                shutil.copy(f, final_repo_dir)
                # we get the filename from the file path and remove the .rpm extension
                mmd.add_rpm_artifact(f.split("/")[-1][:-4])

        mmd_str = mmd_to_str(mmd)

        mmd_file_name = "/{n}:{s}:{v}:{c}:{a}.modulemd.yaml".format(
            n=mmd.get_module_name(),
            s=mmd.get_stream_name(),
            v=mmd.get_version(),
            c=mmd.get_context(),
            a=self.build_contexts[context_name]["metadata"].arch,
        )

        mmd_yaml_file_path = final_repo_dir + "/" + mmd_file_name
        with open(mmd_yaml_file_path, "w") as f:
            f.write(mmd_str)

        self.build_contexts[context_name]["final_repo_path"] = final_repo_dir 
        self.build_contexts[context_name]["final_yaml_path"] = mmd_yaml_file_path
        self.call_createrepo_c_on_dir(final_repo_dir)

    def get_artifacts_nevra(self, artifacts):
        rpm_cmd = ["rpm", "--queryformat", "%{NAME} %{EPOCHNUM} %{VERSION} %{RELEASE} %{ARCH}\n",
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
                name, epoch, version, release, arch = nevra.split()
                artifacts_nevra.append("{}-{}:{}-{}.{}".format(name, epoch, version, release, arch))
        import pdb; pdb.set_trace()
        return artifacts_nevra


class MockBuildroot:
    def __init__(self, component, mock_cfg_str, batch_dir_path, batch_num, modularity_label,
                 rpm_suffix, batch_repo):

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

    def run(self):
        mock_cmd = ["mock", "-v", "-r", self.mock_cfg_path,
                    "--resultdir={result_dir_path}".format(result_dir_path=self.result_dir_path),
                    "--define=modularitylabel {label}".format(label=self.modularity_label),
                    "--define=dist {rpm_suffix}".format(
                        rpm_suffix=self.rpm_suffix),
                    "--addrepo={repo}".format(repo=self.batch_repo),
                    ]
        proc = subprocess.Popen(mock_cmd)
        out, err = proc.communicate()

        self.finished = True

        if proc.returncode != 0:
            err_msg = "Command '{cmd}' returned non-zero value {code}\n{err}".format(
                cmd=mock_cmd,
                code=proc.returncode,
                err=err,
            )
            raise RuntimeError(err_msg)

        return out, err

    def get_artifacts(self):
        if self.finished:
            artifacts = [os.path.join(self.result_dir_path, f) \
                            for f in os.listdir(self.result_dir_path) if f.endswith("rpm")]

            return artifacts
        else:
            # TODO add exception
            pass


    def _create_buildroot_result_dir(self):
        result_dir_path = os.path.join(self.batch_dir_path, self.component["name"])
        os.makedirs(result_dir_path)

        return result_dir_path

    def _create_mock_cfg_file(self):
        mock_cfg_file_path = "{result_dir_path}/{component_name}_mock.cfg".format(
            result_dir_path=self.result_dir_path,
            component_name=self.component["name"]
        )

        with open(mock_cfg_file_path, "w") as f:
            f.write(self.mock_cfg_str)

        return mock_cfg_file_path


class ModuleBuildRPM:
    def __init__(self):
        # TODO NVR should be something like perl-CGI-4.53-2.module_<platform_name>+<context_name>
        pass
