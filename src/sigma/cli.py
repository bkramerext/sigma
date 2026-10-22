"""JSON investigation commands and streamed repository setup/verification commands."""

import argparse
import json
import sys
from dataclasses import asdict

from sigma.investigations import (
    InvestigationError,
    change_stage,
    close_investigation,
    create_investigation,
    create_strategy,
    edit_strategy,
    initialize_investigation,
    inspect_investigation,
    investigation_payload,
    list_events,
    list_strategies,
    open_investigation,
    remove_strategy,
    reorder_strategies,
    update_investigation,
)
from sigma.local_config import load_local_config
from sigma.text_views import inspect_text, save_source
from sigma.tooling import run_tooling
from sigma.ui import run_shutdown, run_ui


def main() -> None:
    parser = argparse.ArgumentParser(description="SIGMA investigations and repository maintenance")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("path")
    init.add_argument("--title", required=True)
    init.add_argument("--problem", required=True)
    init.add_argument(
        "--investigation-type", "--research-mode", dest="investigation_type", default="default"
    )
    init.add_argument("--model", default="gpt-6.1-sol")
    init.add_argument("--thinking", default="high")
    create = commands.add_parser(
        "create", help="Create an investigation in its configured location"
    )
    create.add_argument("--title", required=True)
    create.add_argument("--problem", required=True)
    create.add_argument(
        "--investigation-type", "--research-mode", dest="investigation_type", default="default"
    )
    create.add_argument("--model", default="gpt-6.1-sol")
    create.add_argument("--thinking", default="high")
    for name in ("open", "inspect", "events"):
        commands.add_parser(name).add_argument("path")
    strategies = commands.add_parser("strategies", help="List persistent strategies")
    strategies.add_argument("path")
    strategy = commands.add_parser("new-strategy", help="Save a human-authored strategy")
    strategy.add_argument("path")
    strategy.add_argument("--title", required=True)
    strategy.add_argument("--approach", required=True)
    remove = commands.add_parser(
        "remove-strategy", help="Remove from pool, retaining research history"
    )
    remove.add_argument("path")
    remove.add_argument("strategy_id")
    edit = commands.add_parser(
        "edit-strategy", help="Edit name/description, retaining earlier text"
    )
    edit.add_argument("path")
    edit.add_argument("strategy_id")
    edit.add_argument("--title", required=True)
    edit.add_argument("--approach", required=True)
    stage = commands.add_parser("stage-strategy", help="Change a manually tracked stage")
    stage.add_argument("path")
    stage.add_argument("strategy_id")
    stage.add_argument("stage", choices=["draft", "ready", "exploring", "hold"])
    reorder = commands.add_parser(
        "reorder-strategies", help="Reorder all active IDs with stale-order protection"
    )
    reorder.add_argument("path")
    reorder.add_argument("--order", nargs="+", required=True)
    reorder.add_argument("--expected-order", nargs="+", required=True)
    edit_investigation = commands.add_parser(
        "edit-investigation",
        help="Atomically update investigation settings with a prior settings JSON snapshot",
        aliases=["edit-project"],
    )
    edit_investigation.add_argument("path")
    for field in ("title", "problem", "model", "thinking", "expected"):
        edit_investigation.add_argument("--" + field, required=True)
    edit_investigation.add_argument(
        "--investigation-type", "--research-mode", dest="investigation_type", required=True
    )
    text = commands.add_parser("text", help="Inspect current and cached Plain/Markdown text")
    text.add_argument("path")
    text.add_argument("--scope", choices=["investigation", "strategy"], required=True)
    text.add_argument("--strategy-id")
    save_text = commands.add_parser("save-text", help="Save an authored Plain or Markdown source")
    save_text.add_argument("path")
    save_text.add_argument("--scope", choices=["investigation", "strategy"], required=True)
    save_text.add_argument("--strategy-id")
    save_text.add_argument("--format", choices=["plain", "markdown"], required=True)
    save_text.add_argument("--body", required=True)
    save_text.add_argument("--expected-digest", required=True)
    commands.add_parser("close")
    commands.add_parser("setup", help="Install locked Python and frontend dependencies")
    commands.add_parser("test", help="Run tests, API/CLI checks, lint, types and build")
    commands.add_parser("ui", help="Start or safely restart this checkout's browser UI")
    commands.add_parser("shutdown", help="Stop this checkout's running UI servers safely")
    args = parser.parse_args()
    if args.command == "ui":
        sys.exit(run_ui())
    if args.command == "shutdown":
        sys.exit(run_shutdown())
    if args.command in {"setup", "test"}:
        sys.exit(run_tooling(args.command))
    try:
        load_local_config()
        if args.command == "init":
            result = investigation_payload(
                initialize_investigation(
                    args.path,
                    args.title,
                    args.problem,
                    args.investigation_type,
                    args.model,
                    args.thinking,
                )
            )
        elif args.command == "create":
            result = investigation_payload(
                create_investigation(
                    args.title, args.problem, args.investigation_type, args.model, args.thinking
                )
            )
        elif args.command in {"edit-investigation", "edit-project"}:
            try:
                expected = json.loads(args.expected)
            except ValueError as exc:
                raise InvestigationError("--expected must be a JSON settings snapshot") from exc
            result = investigation_payload(
                update_investigation(
                    args.path,
                    args.title,
                    args.problem,
                    args.investigation_type,
                    args.model,
                    args.thinking,
                    expected,
                )
            )
        elif args.command == "open":
            result = investigation_payload(open_investigation(args.path))
        elif args.command == "inspect":
            result = investigation_payload(inspect_investigation(args.path))
        elif args.command == "new-strategy":
            result = investigation_payload(create_strategy(args.path, args.title, args.approach))
        elif args.command == "edit-strategy":
            result = investigation_payload(
                edit_strategy(args.path, args.strategy_id, args.title, args.approach)
            )
        elif args.command == "remove-strategy":
            result = investigation_payload(remove_strategy(args.path, args.strategy_id))
        elif args.command == "stage-strategy":
            result = investigation_payload(change_stage(args.path, args.strategy_id, args.stage))
        elif args.command == "reorder-strategies":
            result = investigation_payload(
                reorder_strategies(args.path, args.order, args.expected_order)
            )
        elif args.command == "strategies":
            result = {"strategies": [asdict(s) for s in list_strategies(args.path)]}
        elif args.command == "text":
            result = inspect_text(args.path, args.scope, args.strategy_id)
        elif args.command == "save-text":
            result = investigation_payload(
                save_source(
                    args.path,
                    args.scope,
                    args.body,
                    args.format,
                    args.expected_digest,
                    args.strategy_id,
                )
            )
        elif args.command == "events":
            result = {"events": [asdict(e) for e in list_events(args.path)]}
        else:
            close_investigation()
            result = {"closed": True}
        if args.command == "init":
            from sigma.recents import record_access

            record_access(inspect_investigation(args.path))
        print(json.dumps(result))
    except (InvestigationError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
