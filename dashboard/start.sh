#!/bin/sh
set -eu
cd "$(dirname "$0")"
command -v node >/dev/null 2>&1 || { echo 'Install Node.js 12 or newer.'; exit 1; }
node -e "if(parseInt(process.versions.node,10)<12){console.error('Install Node.js 12 or newer.');process.exit(1)}"
exec node start.mjs "${1:-3000}" --open
