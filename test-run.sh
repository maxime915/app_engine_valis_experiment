#!/bin/bash

set -euo pipefail

IDIR="./test-inputs"
ODIR="./test-outputs"
TAG="app-engine-valis-exp"

if [ ! -d $IDIR ]; then
    mkdir $IDIR
    cp data/s1-36.tiff "${IDIR}/fixed_image"
    cp data/s1-37.tiff "${IDIR}/moving_image"
    cp data/geo.json "${IDIR}/geometry_moving"
    cp data/crop.txt "${IDIR}/crop"
    cp data/registration_type.txt "${IDIR}/registration_type"
    cp data/max_proc_size.txt "${IDIR}/max_proc_size"
    cp data/micro_max_proc_size.txt "${IDIR}/micro_max_proc_size"
fi

if [ ! -d $ODIR ]; then
    mkdir $ODIR
elif [ ! -z "$(ls -A ${ODIR})" ]; then
    echo "${ODIR} is not empty"
    exit 1
fi

docker build -t $TAG .
docker run -it \
    --mount type=bind,source=$IDIR,target=/inputs,readonly \
    --mount type=bind,source=$ODIR,target=/outputs \
    $TAG
