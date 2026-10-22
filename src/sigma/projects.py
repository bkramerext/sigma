"""Compatibility exports for integrations that still import ``sigma.projects``.

New code should use :mod:`sigma.investigations`. This module retains the former
Python API while persisted data and external clients migrate.
"""

from sigma.investigations import (
    LEGACY_STATE,
    ROOT,
    SEED,
    STATE,
    Event,
    Provenance,
    ResearchMode,
    Stage,
    StageChange,
    Strategy,
    StrategyChange,
    _decode,
    _document,
    _next_timestamp,
    _research_mode,
    _settings,
    _stage,
    change_stage,
    create_strategy,
    edit_strategy,
    investigation_payload,
    list_events,
    list_strategies,
    remove_strategy,
    reorder_strategies,
)
from sigma.investigations import (
    Investigation as Project,
)
from sigma.investigations import (
    InvestigationChange as ProjectChange,
)
from sigma.investigations import (
    InvestigationDestination as ProjectDestination,
)
from sigma.investigations import (
    InvestigationError as ProjectError,
)
from sigma.investigations import (
    InvestigationSettings as ProjectSettings,
)
from sigma.investigations import (
    InvestigationView as ProjectView,
)
from sigma.investigations import (
    _investigation_name as _project_name,
)
from sigma.investigations import (
    _open_investigation as _open_project,
)
from sigma.investigations import (
    _update_investigation as _update_project,
)
from sigma.investigations import (
    close_investigation as close_project,
)
from sigma.investigations import (
    create_investigation as create_project,
)
from sigma.investigations import (
    initialize_investigation as initialize_project,
)
from sigma.investigations import (
    inspect_investigation as inspect_project,
)
from sigma.investigations import (
    investigation_destination as project_destination,
)
from sigma.investigations import (
    investigation_path as project_path,
)
from sigma.investigations import (
    investigation_settings as project_settings,
)
from sigma.investigations import (
    investigations_root as projects_root,
)
from sigma.investigations import (
    open_investigation as open_project,
)
from sigma.investigations import (
    update_investigation as update_project,
)

__all__ = [
    "LEGACY_STATE",
    "ROOT",
    "SEED",
    "STATE",
    "Event",
    "Project",
    "ProjectChange",
    "ProjectDestination",
    "ProjectError",
    "ProjectSettings",
    "ProjectView",
    "Provenance",
    "ResearchMode",
    "Stage",
    "StageChange",
    "Strategy",
    "StrategyChange",
    "_decode",
    "_document",
    "_next_timestamp",
    "_open_project",
    "_project_name",
    "_research_mode",
    "_settings",
    "_stage",
    "_update_project",
    "change_stage",
    "close_project",
    "create_project",
    "create_strategy",
    "edit_strategy",
    "initialize_project",
    "inspect_project",
    "investigation_payload",
    "list_events",
    "list_strategies",
    "open_project",
    "project_destination",
    "project_path",
    "project_settings",
    "projects_root",
    "remove_strategy",
    "reorder_strategies",
    "update_project",
]
