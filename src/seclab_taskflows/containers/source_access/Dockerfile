# SPDX-FileCopyrightText: GitHub, Inc.
# SPDX-License-Identifier: MIT

FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash coreutils git ca-certificates file binutils xxd \
    universal-ctags global cscope ripgrep fd-find tree \
    && ln -s /usr/bin/fdfind /usr/local/bin/fd \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace