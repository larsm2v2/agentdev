# PowerShell script to build the ML-enabled Docker image with memory optimizations
Write-Host "Building ML-enabled Docker image with sentence-transformers..."
Write-Host "This build may take some time and requires additional memory."

# Set Docker BuildKit memory options
$env:DOCKER_BUILDKIT = 1

# Build the image with memory optimizations, targeting the ml-enabled stage
docker build --memory=4g --target ml-enabled -t email-librarian-ml:latest .

# Check if build was successful
if ($LASTEXITCODE -eq 0) {
    Write-Host "ML-enabled Docker image built successfully!" -ForegroundColor Green
    Write-Host "You can run it with: docker run -p 8000:8000 email-librarian-ml:latest"
} else {
    Write-Host "Build failed. You may need to increase available memory." -ForegroundColor Red
}
