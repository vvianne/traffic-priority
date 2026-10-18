#!/usr/bin/env bash

set -euo pipefail

IMAGE_NAME="traffic-priority"

echo "Building Docker image ${IMAGE_NAME}..."
docker build -t "${IMAGE_NAME}" .

echo "Running the privileged Mininet container..."
docker run --privileged --rm -it "${IMAGE_NAME}"
