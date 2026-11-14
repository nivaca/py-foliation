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
Version:        0.6.4
Release:        1%{?dist}
Summary:        Change the page labels (the numbering a viewer shows) of PDF documents

License:        GPL-3.0-or-later
URL:            https://github.com/nivaca/py-foliation
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  desktop-file-utils
BuildRequires:  appstream
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
# The AppStream metadata, for software centres (launched by this package's menu entry)
install -d %{buildroot}%{_metainfodir}
sed 's|<launchable type="desktop-id">.*</launchable>|<launchable type="desktop-id">py-foliation.desktop</launchable>|; s|<icon type="stock">.*</icon>|<icon type="stock">py-foliation</icon>|' \
    packaging/io.github.nivaca.py-foliation.metainfo.xml > %{buildroot}%{_metainfodir}/io.github.nivaca.py-foliation.metainfo.xml
install -Dpm 0644 packaging/man/py-foliation.1 %{buildroot}%{_mandir}/man1/py-foliation.1
install -Dpm 0644 packaging/man/es/py-foliation.1 %{buildroot}%{_mandir}/es/man1/py-foliation.1
# Completion of the command line, in each shell
install -d %{buildroot}%{bash_completions_dir} %{buildroot}%{fish_completions_dir} %{buildroot}%{zsh_completions_dir}
export PYTHONPATH=%{buildroot}%{python3_sitelib}
%{python3} -m py_foliation completion bash > %{buildroot}%{bash_completions_dir}/py-foliation
%{python3} -m py_foliation completion fish > %{buildroot}%{fish_completions_dir}/py-foliation.fish
%{python3} -m py_foliation completion zsh > %{buildroot}%{zsh_completions_dir}/_py-foliation
unset PYTHONPATH

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/py-foliation.desktop
appstreamcli validate --no-net %{buildroot}%{_metainfodir}/io.github.nivaca.py-foliation.metainfo.xml
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
%{_metainfodir}/io.github.nivaca.py-foliation.metainfo.xml
%{_mandir}/man1/py-foliation.1*
%lang(es) %{_mandir}/es/man1/py-foliation.1*
%{bash_completions_dir}/py-foliation
%{fish_completions_dir}/py-foliation.fish
%{zsh_completions_dir}/_py-foliation

%changelog
* Sat Nov 14 2026 Nicolas Vaughan <nivaca@fastmail.com> - 0.6.4-1
- Python 3.15 or later is needed; no longer built for Fedora 44

* Sat Nov 14 2026 Nicolas Vaughan <nivaca@fastmail.com> - 0.6.3-1
- Python 3.13 or later is needed

* Sat Nov 14 2026 Nicolas Vaughan <nivaca@fastmail.com> - 0.6.2-1
- No Flatpak any more; plainer documentation and comments

* Fri Nov 13 2026 Nicolas Vaughan <nivaca@fastmail.com> - 0.6.1-1
- The window no longer stops answering at some sizes (the preview's scroll
  bars showed and hid without end)

* Fri Nov 13 2026 Nicolas Vaughan <nivaca@fastmail.com> - 0.6-1
- Page layout and page view as Xodo names them, from the menu of the pages;
  Settings > Language

* Fri Nov 13 2026 Nicolas Vaughan <nivaca@fastmail.com> - 0.5-1
- The view when the file is opened: layout, zoom, panel and first page
  (py-foliation view, and File > View when opened... in the window)

* Fri Nov 13 2026 Nicolas Vaughan <nivaca@fastmail.com> - 0.4-1
- Internal clean-up: shared helpers and smaller modules; no change in what
  the commands and the window do

* Thu Nov 12 2026 Nicolas Vaughan <nivaca@fastmail.com> - 0.3-1
- Actions on several pages at once, from a right-click menu in the list of
  pages: number them, continue the numbering, one label, labels one by one

* Thu Nov 12 2026 Nicolas Vaughan <nivaca@fastmail.com> - 0.2-1
- Folios (1r, 1v, 2r) and suffixes; labels from a list; copy; several files,
  --dry-run, --password; saving keeps a PDF's encryption; thumbnails and go to a
  label in the window; completions and man pages

* Thu Nov 12 2026 Nicolas Vaughan <nivaca@fastmail.com> - 0.1-1
- First package: the command line and the window, in English or Spanish,
  with a menu entry that also opens PDF files
