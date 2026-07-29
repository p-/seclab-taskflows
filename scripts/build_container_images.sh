#!/bin/bash
# SPDX-FileCopyrightText: GitHub, Inc.
# SPDX-License-Identifier: MIT

# Build seclab container shell images.
# Must be run from the root of the seclab-taskflows repository.
# Images must be rebuilt whenever a Dockerfile changes.
#
# Usage: ./scripts/build_container_images.sh [base|malware|network|source-access|sast|all]
#   default: all

set -euo pipefail

__dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__root="$(cd "${__dir}/.." && pwd)"
CONTAINERS_DIR="${__root}/src/seclab_taskflows/containers"
IMAGE_PREFIX="ghcr.io/githubsecuritylab"

build_base() {
    echo "Building ${IMAGE_PREFIX}/seclab-shell-base..."
    docker build -t "${IMAGE_PREFIX}/seclab-shell-base:latest" "${CONTAINERS_DIR}/base/"
}

build_malware() {
    echo "Building ${IMAGE_PREFIX}/seclab-shell-malware-analysis..."
    docker build -t "${IMAGE_PREFIX}/seclab-shell-malware-analysis:latest" "${CONTAINERS_DIR}/malware_analysis/"
}

build_network() {
    echo "Building ${IMAGE_PREFIX}/seclab-shell-network-analysis..."
    docker build -t "${IMAGE_PREFIX}/seclab-shell-network-analysis:latest" "${CONTAINERS_DIR}/network_analysis/"
}

build_source_access() {
    echo "Building ${IMAGE_PREFIX}/seclab-shell-source-access..."
    docker build -t "${IMAGE_PREFIX}/seclab-shell-source-access:latest" "${CONTAINERS_DIR}/source_access/"
}

build_sast() {
    echo "Building ${IMAGE_PREFIX}/seclab-shell-sast..."
    docker build -t "${IMAGE_PREFIX}/seclab-shell-sast:latest" "${CONTAINERS_DIR}/sast/"
}

target="${1:-all}"

case "$target" in
    base)
        build_base
        ;;
    malware)
        build_base
        build_malware
        ;;
    network)
        build_base
        build_network
        ;;
    source-access)
        build_source_access
        ;;
    sast)
        build_base
        build_sast
        ;;
    all)
        build_base
        build_malware
        build_network
        build_source_access
        build_sast
        ;;
    *)
        echo "Unknown target: $target" >&2
        echo "Usage: $0 [base|malware|network|source-access|sast|all]" >&2
        exit 1
        ;;
esac

echo "Done."
