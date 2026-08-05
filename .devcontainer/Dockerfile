FROM mcr.microsoft.com/devcontainers/python:3-3.14-trixie

ARG UV_VERSION=0.11.26

RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    git=1:2.47.3-0+deb13u1 \
    pipx=1.7.1-1 \
    just=1.40.0-1+b1 \
    gnupg2=2.4.7-21+deb13u1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pipx install uv==${UV_VERSION}

RUN mkdir -p /opt/venv && chown vscode:vscode /opt/venv
RUN mkdir -p /claude && chown vscode:vscode /claude
