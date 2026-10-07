#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec node start.mjs "${1:-3000}" --open
