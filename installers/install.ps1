# py-foliation, which changes the page labels of PDF documents.
# Copyright (C) 2026 Nicolas Vaughan <nicolasvaughan@proton.me>
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. This program is distributed WITHOUT ANY
# WARRANTY; see the LICENSE file, or <https://www.gnu.org/licenses/>.
#
# Installs py-foliation to run with Python, on Windows (PowerShell):
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/nivaca/py-foliation/main/installers/install.ps1 | iex"
#   powershell -ExecutionPolicy ByPass -File install.ps1 [--version X] [--no-gui] [--no-menu] [--uninstall]
#
# It finds Python 3.14 or later (the py launcher, or python on the PATH) and
# runs install.py with it (the one next to this script, or else the one in
# the repository): see install.py for what is installed, and where.
$ErrorActionPreference = "Stop"
$Url = "https://raw.githubusercontent.com/nivaca/py-foliation/main/installers/install.py"

$Python = $null
$Candidates = @(@("py", "-3.17"), @("py", "-3.16"), @("py", "-3.15"), @("py", "-3.14"), @("python"), @("python3"))
foreach ($Candidate in $Candidates) {
    $Exe = $Candidate[0]
    if (-not (Get-Command $Exe -ErrorAction SilentlyContinue)) { continue }
    $Rest = @($Candidate | Select-Object -Skip 1)
    # (the py launcher says "No suitable Python runtime found" on stderr for a
    # version it lacks, which Windows PowerShell turns into an error: next)
    try {
        & $Exe @Rest -c "import sys; sys.exit(sys.version_info < (3, 14))" 2>$null | Out-Null
    } catch { continue }
    if ($LASTEXITCODE -eq 0) { $Python = $Candidate; break }
}
if (-not $Python) {
    Write-Host "install.ps1: py-foliation needs Python 3.14 or later, and none was found."
    Write-Host "Install it from https://www.python.org/downloads/windows/ (or: winget install Python.Python.3.14)."
    exit 1
}

$Script = $null
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "install.py"))) {
    $Script = Join-Path $PSScriptRoot "install.py"
} else {
    $Script = Join-Path ([System.IO.Path]::GetTempPath()) "py-foliation-install.py"
    Invoke-WebRequest -Uri $Url -OutFile $Script -UseBasicParsing
}
$Exe = $Python[0]
$Rest = @($Python | Select-Object -Skip 1)
& $Exe @Rest $Script @args
exit $LASTEXITCODE
