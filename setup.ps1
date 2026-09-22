$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
Set-Location -LiteralPath $taskRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -m venv .venv
    } else {
        throw 'Python 3.12 is required. Install it from python.org, then run setup.ps1 again.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python 3.12 environment.' }
}
if (Test-Path -LiteralPath 'requirements-tested.txt') {
    & '.venv/Scripts/python.exe' -m pip install -r requirements-tested.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & '.venv/Scripts/python.exe' -m pip install --no-deps -e .
} else {
    & '.venv/Scripts/python.exe' -m pip install -e '.[dev]'
}
if ($LASTEXITCODE -ne 0) { throw 'Project installation failed.' }
if (-not (Test-Path -LiteralPath 'config.local.json')) {
    Copy-Item -LiteralPath 'config.example.json' -Destination 'config.local.json'
}
Write-Output 'Dependencies installed. Open main.py in VS Code and press Run Python File. See QUICK_START.md for the guide and TROUBLESHOOTING.md if Windows blocks OpenCV.'
