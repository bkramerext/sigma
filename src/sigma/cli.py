"""JSON project commands and streamed repository setup/verification commands."""

import argparse
import json
import sys
from dataclasses import asdict

from sigma.projects import (
    ProjectError,
    close_project,
    create_strategy,
    initialize_project,
    inspect_project,
    list_events,
    list_strategies,
    open_project,
)
from sigma.tooling import run_tooling
from sigma.ui import run_ui


def main() -> None:
    parser = argparse.ArgumentParser(description="SIGMA projects and repository maintenance")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("path")
    init.add_argument("--title", required=True)
    init.add_argument("--problem", required=True)
    for name in ("open", "inspect", "events"):
        commands.add_parser(name).add_argument("path")
    strategies = commands.add_parser("strategies", help="List persistent strategies")
    strategies.add_argument("path")
    strategy = commands.add_parser("new-strategy", help="Save a human-authored strategy")
    strategy.add_argument("path")
    strategy.add_argument("--title", required=True)
    strategy.add_argument("--approach", required=True)
    commands.add_parser("close")
    commands.add_parser("setup", help="Install locked Python and frontend dependencies")
    commands.add_parser("test", help="Run scenarios, API/CLI checks, lint, types and build")
    commands.add_parser("ui", help="Launch the local browser UI and API; Ctrl+C stops both")
    args = parser.parse_args()
    if args.command == "ui":
        sys.exit(run_ui())
    if args.command in {"setup", "test"}:
        sys.exit(run_tooling(args.command))
    try:
        if args.command == "init":
            result = asdict(initialize_project(args.path, args.title, args.problem))
        elif args.command == "open":
            result = asdict(open_project(args.path))
        elif args.command == "inspect":
            result = asdict(inspect_project(args.path))
        elif args.command == "new-strategy":
            result = asdict(create_strategy(args.path, args.title, args.approach))
        elif args.command == "strategies":
            result = {"strategies": [asdict(s) for s in list_strategies(args.path)]}
        elif args.command == "events":
            result = {"events": [asdict(e) for e in list_events(args.path)]}
        else:
            close_project()
            result = {"closed": True}
        print(json.dumps(result))
    except ProjectError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
