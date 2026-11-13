# py-foliation, which changes the page labels of PDF documents.
# Copyright (C) 2026 Nicolas Vaughan <nivaca@fastmail.com>
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. This program is distributed WITHOUT ANY
# WARRANTY; see the LICENSE file, or <https://www.gnu.org/licenses/>.
#
# Build with packaging/build-rpm.sh, which makes the source tarball.

Name:           py-foliation
Version:        0.1
Release:        1%{?dist}
Summary:        Change the page labels (the numbering a viewer shows) of PDF documents

License:        GPL-3.0-or-later
URL:            https://github.com/nivaca/py-foliation
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  desktop-file-utils
# For %%check: the tests run the commands and the window (headless).
BuildRequires:  python3-pytest
BuildRequires:  python3-pyside6

# pikepdf comes from the package's metadata (pyproject.toml).
# The window: Fedora's PySide6 (the "gui" extra names the PyPI wheels).
Requires:       python3-pyside6
Requires:       hicolor-icon-theme

%description
py-foliation changes the page labels of PDF documents: the numbering a PDF
viewer shows for their pages (i, ii, iii ... 1, 2, 3 ... App-A, App-B ...),
range by range, without touching the pages themselves.

It comes as a command line (py-foliation) and a window (py-foliation-gui)
that shows every page with its label, in English or Spanish.

%prep
%autosetup -n %{name}-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l py_foliation
# The package has its own menu entry; py-foliation-install (for pip/uv
# installations) would add a second one.
rm %{buildroot}%{_bindir}/py-foliation-install
desktop-file-install --dir=%{buildroot}%{_datadir}/applications packaging/py-foliation.desktop
install -d %{buildroot}%{_datadir}/icons
cp -pr src/py_foliation/icons/linux/hicolor %{buildroot}%{_datadir}/icons/

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/py-foliation.desktop
%pyproject_check_import -e 'py_foliation.gui*'
# The whole test suite, on the installed package, with no settings of the
# builder's and the window drawn offscreen.
export HOME="$PWD/check-home" PY_FOLIATION_CONFIG="$PWD/check-home/config" QT_QPA_PLATFORM=offscreen
%pytest -q tests
%{py3_test_envvars} %{buildroot}%{_bindir}/py-foliation --version | grep -q '%{version}'

%files -f %{pyproject_files}
%doc README.md README_es.md
%{_bindir}/py-foliation
%{_bindir}/py-foliation-gui
%{_datadir}/applications/py-foliation.desktop
%{_datadir}/icons/hicolor/*/apps/py-foliation.*

%changelog
* Thu Nov 12 2026 Nicolas Vaughan <nivaca@fastmail.com> - 0.1-1
- First package: the command line and the window, in English or Spanish,
  with a menu entry that also opens PDF files
