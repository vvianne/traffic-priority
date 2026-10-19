#!/usr/bin/env bash

set -euo pipefail

IMAGE_NAME="traffic-priority"
PROJECT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIRECTORY="${PROJECT_DIRECTORY}/results"

echo "Building Docker image ${IMAGE_NAME}..."
docker build -t "${IMAGE_NAME}" .

if [[ "${1:-}" == "experiment" ]]; then
    mkdir -p "${RESULTS_DIRECTORY}/raw"
    echo "Running the privileged paired experiment..."
    docker run --privileged --rm \
        --mount "type=bind,source=${RESULTS_DIRECTORY},target=/app/results" \
        "${IMAGE_NAME}" "$@"
elif [[ "${1:-}" == "analyze" ]]; then
    mkdir -p "${RESULTS_DIRECTORY}"
    echo "Analyzing saved experiment data..."
    docker run --rm \
        --mount "type=bind,source=${RESULTS_DIRECTORY},target=/app/results" \
        "${IMAGE_NAME}" "$@"
else
    echo "Running the privileged interactive Mininet container..."
    docker run --privileged --rm -it "${IMAGE_NAME}" "$@"
fi
