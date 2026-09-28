param([int]$Port = 8765, [switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not $SkipBuild) {
        & flutter build web --no-web-resources-cdn
        if ($LASTEXITCODE -ne 0) { throw 'Flutter build failed.' }
    }
    if (-not (Test-Path 'build/web/index.html')) { throw 'Build the Flutter app first.' }
    Set-Location (Join-Path $PSScriptRoot '../..')
    Write-Host "Open http://127.0.0.1:$Port when the parking server is ready."
    & ./.venv/Scripts/python.exe -m parking_probe.web_server --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Parking server exited with an error.' }
}
finally { Pop-Location }
