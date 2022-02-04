Name: module-build
Version: 0.1.0
Release: 1%{?dist}
Summary: Tool/library for building module streams locally
License: MIT
BuildArch: noarch

URL: https://github.com/mcurlej/module-build
Source0: %{url}/archive/%{version}/%{name}-%{version}.tar.gz

BuildRequires: python3-devel
BuildRequires: python3-pytest
BuildRequires: python3-setuptools
BuildRequires: libmodulemd >= 2.13.0
BuildRequires: python3-gobject
BuildRequires: mock

Requires: createrepo_c
Requires: libmodulemd >= 2.13.0
Requires: mock


%description
A library and a cli tool for building module streams. 


%prep
%autosetup -p1


%build
%py3_build


%install
%py3_install


%check
%pytest


%files
%doc README.md
%license LICENSE
%{python3_sitelib}/module_build/
%{python3_sitelib}/module_build-*.egg-info/
%{_bindir}/module-build


%changelog
* Tue Feb 01 2022 Martin Čurlej <mcurlej@redhat.com> - 0.1.0-1
- Added the ability to build stand-alone module streams (mcurlej@redhat.com)
- Uses modular dependencies when building module streams (mcurlej@redhat.com)
- Resuming of a failed module stream build on the component level (mcurlej@redhat.com)
