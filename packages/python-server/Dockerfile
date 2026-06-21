# SPDX-License-Identifier: MIT
# biltiq-privacy-server — container scaffold (BILTIQ-013).
#
# SCAFFOLD ONLY: this image is offered, not led with. The default deployment is
# native pip + systemd (see the README server quickstart). CI does NOT build or
# publish this Dockerfile (spec § Out of Scope); it is a starting point an
# operator adapts. Pin the base digest and add a non-root user before any
# production use.
#
# Build context is the repo root so both workspace packages are visible:
#   docker build -f packages/python-server/Dockerfile -t biltiq/privacy-server:0.1.0 .

FROM python:3.12-slim

# uvicorn[standard] pulls C-extension wheels; slim has no compiler, but the
# pinned deps ship manylinux wheels so no build toolchain is required here.
WORKDIR /app

# Install the engine first, then the sidecar, from the workspace checkout — the
# server depends on biltiq-privacy by name, so the sibling must resolve locally
# rather than from PyPI (mirrors the README pip path).
COPY packages/python-core /app/packages/python-core
COPY packages/python-server /app/packages/python-server
RUN pip install --no-cache-dir \
        /app/packages/python-core \
        /app/packages/python-server

# NER model is a dev/runtime-path install, never a wheel dependency (ADR-0006):
# the published dist ships without it, so the image downloads it explicitly.
RUN python -m spacy download en_core_web_sm

# The two secrets are injected at run time (-e / --env-file), never baked in:
#   docker run --rm -p 8088:8088 \
#     -e BILTIQ_JWT_SECRET=... -e BILTIQ_HMAC_KEY=... biltiq/privacy-server:0.1.0
EXPOSE 8088

# Console script from [project.scripts]; serve binds 0.0.0.0:8088 by default.
ENTRYPOINT ["biltiq-privacy-server", "serve"]
