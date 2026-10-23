#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 2 || "$1" != /* || "$2" != /* ]]; then
  echo "usage: $0 /absolute/path/to/sigma-data /absolute/path/to/backup.tar.gz" >&2
  exit 2
fi
root=$1
archive=$2
was_running=0
if docker inspect -f '{{.State.Running}}' sigma-api 2>/dev/null | grep -q true; then
  was_running=1
  docker stop --time 30 sigma-api >/dev/null
fi
restart() { if [[ $was_running -eq 1 ]]; then docker start sigma-api >/dev/null; fi; }
trap restart EXIT
python3 ops/data_archive.py backup "$root" "$archive"
echo "Created private data backup at $archive. Encrypt before copying off-host."
