#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || "$1" != /* ]]; then
  echo "usage: $0 /absolute/path/to/sigma-data" >&2
  exit 2
fi
root=$1
marker="$root/.sigma-deployment-volume-v1"
if [[ -L "$marker" ]]; then
  echo "volume marker must not be a symlink" >&2
  exit 2
fi
if [[ -L "$root" ]]; then
  echo "data path must not be a symlink" >&2
  exit 2
elif [[ -e "$root" ]]; then
  if [[ ! -d "$root" ]]; then echo "data path exists and is not a directory" >&2; exit 2; fi
  if [[ -e "$marker" ]]; then
    python3 - "$root" "$marker" <<'PY'
import os, stat, sys
root, marker = sys.argv[1:]
for path in (root, marker):
    info = os.lstat(path)
    expected = stat.S_ISDIR(info.st_mode) if path == root else stat.S_ISREG(info.st_mode)
    if not expected or stat.S_ISLNK(info.st_mode) or info.st_uid != 10001 or info.st_mode & 0o077:
        raise SystemExit(f"unsafe existing data volume: {path}")
if open(marker, "rb").read() != b"SIGMA durable cloud data volume v1\n":
    raise SystemExit("existing volume marker is invalid")
PY
    echo "Persistent SIGMA volume already initialized at $root."
    exit 0
  fi
  if [[ -n "$(ls -A "$root")" ]]; then
    echo "refusing to initialize a nonempty unmarked data directory" >&2
    exit 2
  fi
else
  install -d -o 10001 -g 10001 -m 0700 "$root"
fi
if [[ ! -e "$marker" ]]; then
  python3 - "$marker" <<'PY'
import os, sys
fd = os.open(sys.argv[1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
with os.fdopen(fd, "wb") as marker:
    marker.write(b"SIGMA durable cloud data volume v1\n")
    marker.flush()
    os.fsync(marker.fileno())
PY
  chown 10001:10001 "$marker"
  chmod 0600 "$marker"
fi
python3 - "$root" "$marker" <<'PY'
import os, stat, sys
for path in sys.argv[1:]:
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode) or info.st_uid != 10001 or info.st_mode & 0o077:
        raise SystemExit(f"unsafe data-volume permissions: {path}")
PY
echo "Persistent SIGMA volume initialized at $root (uid 10001, mode 0700)."
