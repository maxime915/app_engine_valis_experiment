# syntax=docker/dockerfile:1.8
#
# The upstream cdgatenbee/valis-wsi image is ~9.6GB, mostly because it ships:
#  - a GPU/CUDA build of pytorch (multiple GB of bundled CUDA libraries), and
#  - the full build toolchain (compilers, libvips build deps, uv cache, ...)
#    left in the final image (it isn't actually a multi-stage build).
#
# This Dockerfile builds valis-wsi from scratch on top of a slim Python base,
# using the CPU-only pytorch wheels (GPU support is dropped, per project
# decision) and a proper multi-stage build so build tools never reach the
# final image. libvips/openslide/openjdk are pulled as prebuilt Debian
# packages instead of being compiled from source.

FROM python:3.11-slim-bookworm AS builder

ARG TORCH_VERSION=2.7.1
ARG TORCHVISION_VERSION=0.22.1
ARG BF_VERSION=7.0.0

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/root \
    TORCH_HOME=/opt/torch \
    JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    VIRTUAL_ENV=/app/.venv \
    PATH=/app/.venv/bin:$PATH

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        wget \
        libvips42 \
        openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# venvs are not relocatable: create it at its final path in the runtime image.
RUN python3 -m venv /app/.venv

# CPU-only pytorch/torchvision wheels first, so installing valis-wsi
# afterwards is satisfied by them instead of pulling GPU builds from PyPI.
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu \
    "torch==${TORCH_VERSION}+cpu" \
    "torchvision==${TORCHVISION_VERSION}+cpu"

# Application code, installed together with valis-wsi (see pyproject.toml).
COPY pyproject.toml LICENSE README.md /build/
COPY src /build/src
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu .

# Bio-Formats jar is expected next to the valis package itself.
RUN wget -q "https://downloads.openmicroscopy.org/bio-formats/${BF_VERSION}/artifacts/bioformats_package.jar" \
    -O /app/.venv/lib/python3.11/site-packages/valis/bioformats_package.jar

# valis rewrites valis/data/bf_formats.txt every time the JVM starts, and the
# pod runs as an unknown non-root user.
RUN chmod -R a+rwx /app/.venv/lib/python3.11/site-packages/valis/data

# Pre-download pytorch model weights so the runtime image works offline.
COPY docker/download_weights.py /build/download_weights.py
RUN python3 /build/download_weights.py

FROM python:3.11-slim-bookworm

# Runtime-only native dependencies: libvips (pyvips loads it via cffi, no
# headers needed), openslide (whole-slide image formats) and a headless JRE
# for Bio-Formats/scyjava (no GPU/CUDA runtime, no compilers).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libvips42 \
        libopenslide0 \
        openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# The cluster runs the container as an arbitrary non-root user that cannot
# write outside /app and /tmp: weights live in a world-readable location and
# every runtime cache/config (matplotlib, fontconfig, jgo, ...) goes to /tmp.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache \
    XDG_CONFIG_HOME=/tmp/.config \
    MPLCONFIGDIR=/tmp/matplotlib \
    TORCH_HOME=/opt/torch \
    JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    VIRTUAL_ENV=/app/.venv \
    PATH=/app/.venv/bin:$PATH

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder --chmod=a+rX /opt/torch /opt/torch

WORKDIR /app
COPY script.py /app/script.py

CMD [ "python3", "script.py" ]
