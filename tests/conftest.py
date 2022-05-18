from subprocess import DEVNULL, run
from tempfile import NamedTemporaryFile

import pytest


def create_fake_spec(tmp_srpm_dir, name, version=None, release=None):
    with NamedTemporaryFile(mode="w", suffix=".spec", dir=tmp_srpm_dir, delete=False) as tmp_spec:
        tmp_spec.write(
            f"Name: {name}\nVersion: {version or '1.22.4'}\nRelease: {release or '2'}\nSummary: Simplicity\nLicense: MIT\n%description")
        return tmp_spec.name


@pytest.fixture
def create_fake_srpm(request, tmp_path):
    tmp_dir = str(tmp_path.resolve())
    for data in request.param:
        spec_path = create_fake_spec(**data, tmp_srpm_dir=tmp_dir)
        result = run(["rpmbuild", "-bs", "-D", f"_srcrpmdir {tmp_dir}", "-D", f"_topdir {tmp_dir}", f"{spec_path}"], stdout=DEVNULL)

        if result.returncode != 0:
            raise Exception(f"Error creating fake srpm: {result.returncode}")

    return tmp_dir
