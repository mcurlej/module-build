from os import path

from setuptools import setup, find_packages


def read_requirements(filename):
    specifiers = []
    dep_links = []
    with open(filename, "r") as f:
        for line in f:
            if line.startswith("-r") or line.strip() == "":
                continue
            if line.startswith("git+"):
                dep_links.append(line.strip())
            else:
                specifiers.append(line.strip())
    return specifiers, dep_links


setup_py_path = path.dirname(path.realpath(__file__))
install_requires, deps_links = read_requirements(path.join(setup_py_path, "requirements.txt"))
tests_require, _ = read_requirements(path.join(setup_py_path, "test-requirements.txt"))

setup(
    name="module-build",
    description="A library and CLI tool for building module streams.",
    version="0.2.0",
    classifiers=[
        "Programming Language :: Python",
        "Topic :: Software Development :: Build Tools"
    ],
    keywords="module build fedora modularity koji mock rpm",
    author="Martin Curlej",
    author_email="martin.curlej@redhat.com",
    url="https://github.com/mcurlej/module-build",
    license="MIT",
    packages=find_packages(exclude=("tests",)),
    include_package_data=True,
    zip_safe=False,
    install_requires=install_requires,
    tests_require=tests_require,
    dependency_links=deps_links,
    entry_points={
        "console_scripts": [
            "module-build = module_build.cli:main",
        ],
    },
)
