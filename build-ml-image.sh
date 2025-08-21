#!/bin/bash
# Script to build the ML-enabled Docker image with memory optimizations
echo "Building ML-enabled Docker image with sentence-transformers..."
echo "This build may take some time and requires additional memory."

# Set Docker BuildKit memory options
export DOCKER_BUILDKIT=1

# Build the image with memory optimizations, targeting the ml-enabled stage
docker build --memory=4g --target ml-enabled -t email-librarian-ml:latest .

# Check if build was successful
if [ $? -eq 0 ]; then
    echo -e "\e[32mML-enabled Docker image built successfully!\e[0m"
    echo "You can run it with: docker run -p 8000:8000 email-librarian-ml:latest"
else
    echo -e "\e[31mBuild failed. You may need to increase available memory.\e[0m"
fi
