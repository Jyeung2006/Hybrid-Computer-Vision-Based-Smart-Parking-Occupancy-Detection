$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot '.venv/Scripts/python.exe') -m parking_probe @args
exit $LASTEXITCODE

