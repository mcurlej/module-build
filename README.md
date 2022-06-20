# module-build

A library and a cli tool for building module streams.
<br />
The `module-build` tool only accepts [version 3](https://github.com/fedora-modularity/libmodulemd/blob/main/yaml_specs/modulemd_packager_v3.yaml) of the modulemd-packager yaml file format.

# Installation

## Development
After cloning the project we have to setup the required dependencies.

First we need to fullfill dependencies which are required on system level. This can be done on Fedora 34 and up.

```
$ sudo dnf install libmodulemd mock createrepo_c
```
<br />


For development we recommend to create a python virtualenv with the `--system-site-packages` argument.

```
$ mkvirtualenv -p python3 --system-site-packages module-build
```
<br />


After the virtualenv is created, install the rest of the dependencies with pip.

```
$ pip install -r requirements.txt
```

and

```
$ pip install -r test-requirements.txt
```
<br />


After the dependencies are installed you can run unittests with:

```
$ tox
```
<br />


To run only `flake8` on your code run:

```
$ tox -e flake8
```
<br />


To enable the `module-build` commmand in the command line run:
<br />


---
**NOTE**

We recommend that you run the command below inside a virtualenv.

---
<br />


```
$ python setup.py develop
```
<br />


# CLI usage

## Building a module stream

For now `module-build` only works with [Fedora dist-git](https://src.fedoraproject.org/browse/projects/). We assume that every ref of a component in your modulemd yaml file refers to a dist-git branch and every name of the component refers to a dist-git repository name.
<br />
<br />
There are 3 required parameters for `module-build`:
<br />
<br />
`--mock-cfg` - mock configuration file
<br />
`--modulemd` - the path to your modulemd yaml file
<br />
`<working directory>` - directory where the log files and built rpms will be stored
<br />
<br />
```
$ module-build -f flatpak-runtime.yaml -c /etc/mock/fedora-35-x86_64.cfg ./workdir
```
<br />

If your modulemd yaml file does not provide module name or module stream it can be added by `--module-name` or `--module-stream` respectively.
<br />
<br />
```
$ module-build -f flatpak-runtime.yaml -c /etc/mock/fedora-35-x86_64.cfg --module-name=flatpak-runtime --module-stream=devel ./workdir
```
<br />
<br />

If you want to build a specific `context` out your module stream you can define it by `--module-context` 
parameter: 
<br />
<br />
```
$ module-build -f flatpak-runtime.yaml -c /etc/mock/fedora-35-x86_64.cfg --module-name=flatpak-runtime --module-stream=devel --module-context=mycontext ./workdir
```
<br />
<br />

## Resume building a component from a module stream
If a build of a component fails you can resume the build from that component. For this you need to spefify the `--resume` flag and the `--module-version=<version_timestapm>` option which can identify which build context you want to resume.
<br />
<br />
```
$ module-build -f flatpak-runtime.yaml -c /etc/mock/fedora-35-x86_64.cfg --resume --module-version=20211112140429 ./workdir
```
<br />
<br />

## Building a module stream with modular dependencies
When your module stream has modular dependencies you have to provide those dependencies to `module-build` in a form of a repo created by `createrepo_c`.
<br />
<br />
For example the `flatpak-runtime` module is a modular dependency for module `flatpak-common`. To provide `flatpak-runtime` you will need to use the `--add-repo` option to your build.
<br />
<br />
```
$ module-build -f flatpak-common.yaml -c /etc/mock/fedora-35-x86_64.cfg --add-repo=/path/to/repository/containin/flatpak-runtime/module ./workdir
```
<br />
<br />

## Building a module stream components in a custom chroot dir
Sometimes a build of a component can consume a lot of disk space. By default `mock` stores all its chroots in `/var/lib/mock` which can cause problems if you are low on disk space. You can change the location of the chroot dir to custom one with option `--rootdir`.
<br />
<br />
```
$ module-build -f flatpak-runtime.yaml -c /etc/mock/fedora-35-x86_64.cfg --rootdir=/path/to/custom/dir/ ./workdir
```

## Building a module stream components from SRPMs
This option allows to build all components directly from SRPM instead of utilizing SCM. You acn turn in on by specifiing directory path with source RPMs in `--srpm-dir`.
<br />
<br />
```
$ module-build -f flatpak-runtime.yaml -c /etc/mock/fedora-35-x86_64.cfg --srpm-dir /path/to/srpms  ./workdir
```

## Building a module in multiprocess mode.
This option allows to build components simultaneously. To utilize this mode, please specify amount of `--workers` higher than `1`.
This mode requires to turn off logger stdout by `--no-stdout` argument.
<br />
<br />
```
$ module-build -f perl-bootstrap-new.yaml -c /etc/mock/fedora-35-x86_64.cfg --module-name=perl-bootstrap -w 2 --no-stdout /workdir
```
