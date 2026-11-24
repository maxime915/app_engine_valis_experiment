#!/bin/bash

set -euo pipefail

IDIR="$(realpath -m ./test-inputs)"
ODIR="$(realpath -m ./test-outputs)"
TAG="$1"

# input names must match the keys of descriptor.yaml (prefixed to force order)
if [ ! -d "$IDIR" ]; then
    mkdir "$IDIR"
    cp data/s1-36.tiff "${IDIR}/a_fixed_image"
    cp data/s1-37.tiff "${IDIR}/b_moving_image"
    cp data/geo.json "${IDIR}/c_geometry_moving"
    cp data/crop.txt "${IDIR}/d_crop"
    cp data/registration_type.txt "${IDIR}/e_registration_type"
    cp data/max_proc_size.txt "${IDIR}/f_max_proc_size"
    cp data/micro_max_proc_size.txt "${IDIR}/g_micro_max_proc_size"
elif [ ! -f "${IDIR}/a_fixed_image" ]; then
    echo "${IDIR} uses outdated input names (expected a_fixed_image, ...): remove it to regenerate" >&2
    exit 1
fi

if [ ! -d "$ODIR" ]; then
    mkdir "$ODIR"
elif [ -n "$(ls -A "$ODIR")" ]; then
    echo "${ODIR} is not empty" >&2
    exit 1
fi

# mimic the App Engine pod: non-root user and the resources of descriptor.yaml
docker build -t "$TAG" .
docker run -it --rm \
    --user "$(id -u):$(id -g)" \
    --memory 8g \
    --cpus 2 \
    --mount type=bind,source="$IDIR",target=/inputs,readonly \
    --mount type=bind,source="$ODIR",target=/outputs \
    "$TAG"
