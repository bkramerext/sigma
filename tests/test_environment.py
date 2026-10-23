"""Give every standalone scenario private app, project and auth directories."""

import atexit
import os
from pathlib import Path
from tempfile import TemporaryDirectory

_temporary = TemporaryDirectory(prefix="sigma-scenario-")
_root = Path(_temporary.name)
for _name in ("state", "projects", "auth"):
    (_root / _name).mkdir(mode=0o700)
os.environ["SIGMA_STATE_DIR"] = str(_root / "state")
os.environ["SIGMA_PROJECTS_ROOT"] = str(_root / "projects")
os.environ["SIGMA_AUTH_HOME"] = str(_root / "auth")
atexit.register(_temporary.cleanup)
