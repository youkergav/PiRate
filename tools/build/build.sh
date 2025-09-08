#!/usr/bin/env bash
set -euo pipefail

SELF_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
PIRATE_REPO="$(cd "${PIRATE_REPO:-$SELF_DIR/../../}" && pwd)"

export PIRATE_REPO

exec docker compose -f "$SELF_DIR/docker-compose.yml" --project-directory "$SELF_DIR" run --rm pirate-image-gen
