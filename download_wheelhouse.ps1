Param(
    [string]$requirements = "requirements.docker.txt",
    [string]$output = "wheelhouse"
)

if (-not (Test-Path $requirements)) {
    Write-Error "Requirements file not found: $requirements"
    exit 1
}

if (-not (Test-Path $output)) {
    New-Item -ItemType Directory -Path $output | Out-Null
}

Write-Host "Downloading wheels to $output ..."
python -m pip download -r $requirements -d $output
Write-Host "Done. Copy $output into your build context and run: docker compose build --build-arg WHEELHOUSE=1"
