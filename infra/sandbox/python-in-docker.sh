#!/bin/sh
# Runs a model-written RUN script inside the pinned investigation image: no network, capped CPU, memory and processes.
# Invoked as `<this> -I -c <code>` from the candidate tree; that tree is the only mount.
exec docker run --rm -i --network none --memory 1g --pids-limit 128 --ulimit cpu=30 -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$PWD":/w -w /w --entrypoint python "${KAIROS_SANDBOX_IMAGE:-kairos-investigation-django:build003}" "$@"
