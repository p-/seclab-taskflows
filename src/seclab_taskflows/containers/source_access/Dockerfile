# SPDX-FileCopyrightText: GitHub, Inc.
# SPDX-License-Identifier: MIT

FROM seclab-shell-base:latest
RUN apt-get update && apt-get install -y --no-install-recommends \
    universal-ctags global cscope ripgrep fd-find tree \
    && ln -s /usr/bin/fdfind /usr/local/bin/fd \
    && rm -rf /var/lib/apt/lists/*