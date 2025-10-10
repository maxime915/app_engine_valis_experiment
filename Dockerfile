# syntax=docker/dockerfile:1.8

FROM openjdk:26-slim-bookworm@sha256:c500738236e84ee2b043e2c50ab41b95a69e70926720a3ae1b1655c57ff1de08

ARG MAVEN_VERSION=3.9.11
ARG BASE_URL=https://dlcdn.apache.org/maven/maven-3/${MAVEN_VERSION}/binaries

WORKDIR /app

# install distro dependencies (libvips, gcc)
RUN apt -y update && \
    apt -y install --no-install-recommends libvips42=8.14.1-3+deb12u2 g++=4:12.2.0-3 curl=7.88.1-10+deb12u14 && \
    apt -y clean && \
    rm -rf /var/lib/apt/lists/*

RUN echo "url: ${BASE_URL}/apache-maven-${MAVEN_VERSION}-bin.tar.gz"

# install maven
RUN mkdir -p /usr/share/maven /usr/share/maven/ref \
    && curl -fsSL -o /tmp/apache-maven.tar.gz ${BASE_URL}/apache-maven-${MAVEN_VERSION}-bin.tar.gz \
    && tar -xzf /tmp/apache-maven.tar.gz -C /usr/share/maven --strip-components=1 \
    && rm -f /tmp/apache-maven.tar.gz \
    && ln -s /usr/share/maven/bin/mvn /usr/bin/mvn

# install uv
COPY --from=ghcr.io/astral-sh/uv:0.8.9@sha256:325891cb48ac399d419db01908520edd222bfba9f03df12cbba61a5da02fb83b /uv /uvx /bin/

# install python dependencies
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-install-project

# add library code (and install module)
COPY LICENSE README.md src ./
RUN uv sync --frozen

# add script
COPY script.py ./

CMD [ "uv", "run", "script.py" ]

