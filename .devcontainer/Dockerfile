FROM mcr.microsoft.com/devcontainers/python:3-3.14-trixie

ARG UV_VERSION=0.11.26

RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install git pipx just

RUN pipx install uv==${UV_VERSION}

RUN mkdir -p /opt/venv && chown vscode:vscode /opt/venv

RUN mkdir -p /claude && chown vscode:vscode /claude

RUN curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
