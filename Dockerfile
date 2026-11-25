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
#
# Python dependencies are installed from uv.lock (frozen), so the image runs
# exactly the same package versions as the local `uv sync` environment,
# including the CPU-only torch/torchvision wheels pinned there.

FROM python:3.11-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.8.13 /uv /usr/local/bin/uv

ARG BF_VERSION=7.0.0

# UV_PYTHON: build the venv on the base image's interpreter, which also exists
#   at the same path in the runtime image (venvs are not relocatable).
# UV_PROJECT_ENVIRONMENT: create the venv at its final path.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/root \
    TORCH_HOME=/opt/torch \
    JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    UV_PYTHON=/usr/local/bin/python3.11 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_LINK_MODE=copy \
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

# Third-party dependencies only (cached layer, unaffected by source changes).
# --frozen: fail instead of re-resolving if uv.lock is out of date.
COPY pyproject.toml uv.lock /build/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Application code, installed non-editable since /build is not kept.
COPY LICENSE README.md /build/
COPY src /build/src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

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
