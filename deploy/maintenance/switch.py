"""Toggle the host Caddy maintenance snippet; requires root and installed host config."""

import os
import pathlib
import subprocess
import sys

DIRECTORY = pathlib.Path("/etc/caddy/sigma-maintenance")
SNIPPET = DIRECTORY / "active.caddy"
CONFIG = pathlib.Path("/etc/caddy/Caddyfile")
CONTENT = """@maintenance_image path /__sigma_maintenance/maintainance-page.png
handle @maintenance_image {
    root * /var/www/sigma-maintenance
    header Cache-Control "no-store, max-age=0"
    rewrite * /maintainance-page.png
    file_server
}
handle {
    error 503
}
"""


def run(*args):
    subprocess.run(args, check=True)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("on", "off"):
        raise SystemExit("usage: switch.py on|off")
    if os.geteuid() != 0:
        raise SystemExit("must run as root")
    if not CONFIG.is_file() or not DIRECTORY.is_dir() or DIRECTORY.is_symlink():
        raise SystemExit("host maintenance directory not installed")
    before = SNIPPET.read_bytes() if SNIPPET.exists() else None
    if sys.argv[1] == "on":
        if not all(
            pathlib.Path("/var/www/sigma-maintenance", name).is_file()
            for name in ("index.html", "maintainance-page.png")
        ):
            raise SystemExit("maintenance page not installed")
        SNIPPET.write_text(CONTENT)
    else:
        SNIPPET.unlink(missing_ok=True)
    try:
        run("caddy", "validate", "--config", str(CONFIG))
        run("systemctl", "reload", "caddy")
    except (OSError, subprocess.CalledProcessError):
        if before is None:
            SNIPPET.unlink(missing_ok=True)
        else:
            SNIPPET.write_bytes(before)
        run("caddy", "validate", "--config", str(CONFIG))
        run("systemctl", "reload", "caddy")
        raise
    print("SIGMA maintenance:", sys.argv[1])


if __name__ == "__main__":
    main()
