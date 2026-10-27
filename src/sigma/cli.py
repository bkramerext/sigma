"""JSON project commands and streamed repository setup/verification commands."""

import argparse
import json
import sys
from dataclasses import asdict

from sigma.agentic_evidence import get_run, list_runs
from sigma.local_config import load_local_config
from sigma.projects import (
    ProjectError,
    change_stage,
    close_project,
    create_project,
    create_strategy,
    edit_strategy,
    initialize_project,
    inspect_project,
    list_events,
    list_strategies,
    open_project,
    remove_strategy,
    reorder_strategies,
    update_project,
)
from sigma.text_views import inspect_text, save_source
from sigma.tooling import run_tooling
from sigma.ui import run_shutdown, run_ui

COMMAND_DETAILS = {
    "init": (
        "Create and initialize a project at an explicit path.",
        "./sigma init projects/demo.sigma --title 'Demo' --problem 'What explains this result?'",
        "SIGMA_PROJECTS_ROOT is not used; the path is explicit. Use `create` to place a project under the configured projects root.",
    ),
    "create": (
        "Create a project in the configured projects root.",
        "./sigma create --title 'Demo' --problem 'What explains this result?'",
        "SIGMA_PROJECTS_ROOT selects the root; otherwise the repository projects directory is used. The root must exist and be writable.",
    ),
    "open": (
        "Open a project and report its current contents.",
        "./sigma open projects/demo.sigma",
        "The project path must identify a valid SIGMA project.",
    ),
    "inspect": (
        "Inspect project settings and saved strategies without changing them.",
        "./sigma inspect projects/demo.sigma",
        "The project path must identify a valid SIGMA project.",
    ),
    "events": (
        "List the recorded project history.",
        "./sigma events projects/demo.sigma",
        "The project path must identify a valid SIGMA project.",
    ),
    "strategies": (
        "List the project's persistent strategies.",
        "./sigma strategies projects/demo.sigma",
        "Removed strategies remain in research history.",
    ),
    "new-strategy": (
        "Save a human-authored strategy to a project.",
        "./sigma new-strategy projects/demo.sigma --title 'Compare cases' --approach 'Test small cases first.'",
        "The project path must identify a valid SIGMA project.",
    ),
    "remove-strategy": (
        "Remove a strategy from the active pool while retaining its research history.",
        "./sigma remove-strategy projects/demo.sigma STRATEGY_ID",
        "The strategy ID must belong to the project.",
    ),
    "edit-strategy": (
        "Update a strategy's title and approach while preserving earlier text in history.",
        "./sigma edit-strategy projects/demo.sigma STRATEGY_ID --title 'Revised' --approach 'Check boundary cases.'",
        "The strategy ID must belong to the project.",
    ),
    "stage-strategy": (
        "Set a strategy's manually tracked stage.",
        "./sigma stage-strategy projects/demo.sigma STRATEGY_ID ready",
        "Stage must be draft, ready, exploring, or hold.",
    ),
    "reorder-strategies": (
        "Reorder all active strategies with protection against stale ordering.",
        "./sigma reorder-strategies projects/demo.sigma --order ID_A ID_B --expected-order ID_B ID_A",
        "`--expected-order` must match the project's current active order.",
    ),
    "edit-project": (
        "Atomically update project settings using the previously inspected settings snapshot.",
        "./sigma edit-project projects/demo.sigma --title 'Demo' --problem 'Question?' --research-mode default --model gpt-6.1-sol --thinking high --expected '{...}'",
        "Use `inspect` to obtain the current settings snapshot for `--expected`; stale snapshots are rejected.",
    ),
    "text": (
        "Inspect authored and cached Plain/Markdown project or strategy text.",
        "./sigma text projects/demo.sigma --scope project",
        "Use `--strategy-id` with strategy scope.",
    ),
    "agentic-runs": (
        "List saved agentic generation evidence or export one complete run record.",
        "./sigma agentic-runs projects/demo.sigma [RUN_ID]",
        "A supplied run ID must exist in this project's saved evidence.",
    ),
    "save-text": (
        "Save authored Plain or Markdown source using a digest to prevent overwriting newer text.",
        "./sigma save-text projects/demo.sigma --scope project --format markdown --body '# Notes' --expected-digest DIGEST",
        "Obtain the current digest with `text`; stale digests are rejected. Strategy scope requires `--strategy-id`.",
    ),
    "close": (
        "Close the current local project context.",
        "./sigma close",
        "No project path is required.",
    ),
    "sandbox-build": (
        "Build an optional pinned isolated Python or SageMath research runtime.",
        "./sigma sandbox-build --runtime python",
        "Requires the configured container runtime and network access to fetch the pinned image.",
    ),
    "sandbox-execute": (
        "Execute a source file in an isolated research runtime for a project.",
        "./sigma sandbox-execute projects/demo.sigma --runtime python --source-file experiment.py",
        "Requires the matching sandbox image to be built. Execution failures are returned as structured JSON.",
    ),
    "sandbox-capabilities": (
        "Report locally available research execution runtimes.",
        "./sigma sandbox-capabilities",
        "A runtime is available only when its image and container runtime are ready.",
    ),
    "make_sample": (
        "Create a Samples catalog entry from an exported project JSON file.",
        "./sigma make_sample export.json --name demo",
        "The export must be valid; the sample name must satisfy catalog naming rules.",
    ),
    "setup": (
        "Install locked Python and frontend dependencies.",
        "./sigma setup",
        "Requires `uv` and `npm` on PATH; see the setup output for a missing-tool diagnostic.",
    ),
    "test": (
        "Run project scenarios, API/CLI checks, lint, types, and frontend build.",
        "./sigma test",
        "Requires the repository's locked development tools; this command makes no paid model calls.",
    ),
    "start": (
        "Start or safely restart this checkout's browser UI.",
        "./sigma start --navigate --signin",
        "Uses SIGMA local configuration and the configured UI ports; `--navigate` opens a browser tab.",
    ),
    "shutdown": (
        "Stop identifiable local SIGMA UI servers safely.",
        "./sigma shutdown",
        "Only processes identifiable as SIGMA instances are stopped; unrelated port owners are left alone.",
    ),
}


def add_command(subparsers: argparse._SubParsersAction, name: str, **kwargs):
    """Create command help with a consistent purpose, examples, and diagnostics."""
    purpose, example, notes = COMMAND_DETAILS[name]
    return subparsers.add_parser(
        name,
        description=purpose,
        epilog=f"Example:\n  {example}\n\nNotes: {notes}",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        **kwargs,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SIGMA projects and repository maintenance",
        epilog="Use `sigma -h COMMAND` or `sigma COMMAND --help` for detailed command help.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    init = add_command(commands, "init")
    init.add_argument("path")
    init.add_argument("--title", required=True)
    init.add_argument("--problem", required=True)
    init.add_argument("--research-mode", default="default")
    init.add_argument("--model", default="gpt-6.1-sol")
    init.add_argument("--thinking", default="high")
    init.add_argument("--difficulty", choices=["easy", "medium", "hard"], default="medium")
    create = add_command(
        commands, "create", help="Create a project in the configured projects root"
    )
    create.add_argument("--title", required=True)
    create.add_argument("--problem", required=True)
    create.add_argument("--research-mode", default="default")
    create.add_argument("--model", default="gpt-6.1-sol")
    create.add_argument("--thinking", default="high")
    create.add_argument("--difficulty", choices=["easy", "medium", "hard"], default="medium")
    for name in ("open", "inspect", "events"):
        add_command(commands, name).add_argument("path")
    strategies = add_command(commands, "strategies", help="List persistent strategies")
    strategies.add_argument("path")
    strategy = add_command(commands, "new-strategy", help="Save a human-authored strategy")
    strategy.add_argument("path")
    strategy.add_argument("--title", required=True)
    strategy.add_argument("--approach", required=True)
    remove = add_command(
        commands, "remove-strategy", help="Remove from pool, retaining research history"
    )
    remove.add_argument("path")
    remove.add_argument("strategy_id")
    edit = add_command(
        commands, "edit-strategy", help="Edit name/description, retaining earlier text"
    )
    edit.add_argument("path")
    edit.add_argument("strategy_id")
    edit.add_argument("--title", required=True)
    edit.add_argument("--approach", required=True)
    stage = add_command(commands, "stage-strategy", help="Change a manually tracked stage")
    stage.add_argument("path")
    stage.add_argument("strategy_id")
    stage.add_argument("stage", choices=["draft", "ready", "exploring", "hold"])
    reorder = add_command(
        commands, "reorder-strategies", help="Reorder all active IDs with stale-order protection"
    )
    reorder.add_argument("path")
    reorder.add_argument("--order", nargs="+", required=True)
    reorder.add_argument("--expected-order", nargs="+", required=True)
    edit_project = add_command(
        commands,
        "edit-project",
        help="Atomically update project settings with a prior settings JSON snapshot",
    )
    edit_project.add_argument("path")
    for field in ("title", "problem", "research-mode", "model", "thinking", "expected"):
        edit_project.add_argument("--" + field, required=True)
    edit_project.add_argument("--difficulty", choices=["easy", "medium", "hard"])
    text = add_command(commands, "text", help="Inspect current and cached Plain/Markdown text")
    text.add_argument("path")
    text.add_argument("--scope", choices=["project", "strategy"], required=True)
    text.add_argument("--strategy-id")
    runs = add_command(
        commands,
        "agentic-runs",
        help="List saved agentic generation evidence or export one run as JSON",
    )
    runs.add_argument("path")
    runs.add_argument("run_id", nargs="?", help="Run ID to export as a complete JSON record")
    save_text = add_command(commands, "save-text", help="Save an authored Plain or Markdown source")
    save_text.add_argument("path")
    save_text.add_argument("--scope", choices=["project", "strategy"], required=True)
    save_text.add_argument("--strategy-id")
    save_text.add_argument("--format", choices=["plain", "markdown"], required=True)
    save_text.add_argument("--body", required=True)
    save_text.add_argument("--expected-digest", required=True)
    add_command(commands, "close")
    build = add_command(commands, "sandbox-build", help="Build an optional pinned research runtime")
    build.add_argument("--runtime", choices=["python", "sagemath"], required=True)
    execute = add_command(
        commands, "sandbox-execute", help="Execute a source file in an isolated research runtime"
    )
    execute.add_argument("path")
    execute.add_argument("--runtime", choices=["python", "sagemath"], default="python")
    execute.add_argument("--source-file", required=True)
    add_command(
        commands, "sandbox-capabilities", help="Inspect locally available research runtimes"
    )
    sample = add_command(
        commands,
        "make_sample",
        help="Create a Samples catalog entry from a project export JSON file",
    )
    sample.add_argument("exported_project")
    sample.add_argument("--name", required=True)
    add_command(commands, "setup", help="Install locked Python and frontend dependencies")
    add_command(commands, "test", help="Run tests, API/CLI checks, lint, types and build")
    ui_command = add_command(
        commands, "start", help="Start or safely restart this checkout's browser UI"
    )
    ui_command.add_argument(
        "--mock-auth",
        action="store_true",
        help="Run local-only mock identity switching for the hosted sign-in walkthrough",
    )
    ui_command.add_argument(
        "--signin",
        action="store_true",
        help="Start with a local admin identity from SIGMA_CLOUD_ADMIN_CONTACT_EMAIL",
    )
    ui_command.add_argument(
        "--navigate",
        "--nav",
        dest="navigate",
        action="store_true",
        help="Open SIGMA in a browser tab after startup",
    )
    add_command(commands, "shutdown", help="Stop identifiable local SIGMA UI servers safely")
    for command_parser in commands.choices.values():
        for action in command_parser._actions:
            if action.help is None:
                label = action.dest.replace("_", " ")
                action.help = f"Set {label}" if action.option_strings else label.capitalize()
            if action.required:
                action.help += " (required)"
    argv = sys.argv[1:]
    if len(argv) == 2 and argv[0] in {"-h", "--help"} and argv[1] in COMMAND_DETAILS:
        argv = [argv[1], "--help"]
    args = parser.parse_args(argv)
    if args.command == "make_sample":
        from sigma.samples import make_sample

        try:
            destination = make_sample(args.exported_project, args.name)
            print(json.dumps({"sample": args.name, "path": str(destination)}, indent=2))
        except ProjectError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(2)
        sys.exit(0)
    if args.command == "sandbox-build":
        from sigma.tooling import build_sandbox

        sys.exit(build_sandbox(args.runtime))
    if args.command in {"sandbox-execute", "sandbox-capabilities"}:
        import asyncio
        from pathlib import Path

        from sigma.python_sandbox import execute_research_code
        from sigma.research_tools import execution_capabilities

        try:
            result = (
                execution_capabilities()
                if args.command == "sandbox-capabilities"
                else asyncio.run(
                    execute_research_code(
                        args.path,
                        Path(args.source_file).read_text(encoding="utf-8"),
                        runtime_name=args.runtime,
                    )
                )
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if (
                args.command == "sandbox-execute"
                and isinstance(result, dict)
                and result["status"] != "completed"
            ):
                sys.exit(1)
        except (ProjectError, OSError, UnicodeError) as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(2)
        sys.exit(0)
    if args.command == "start":
        sys.exit(run_ui(navigate=args.navigate, signin=args.signin, mock_auth=args.mock_auth))
    if args.command == "shutdown":
        sys.exit(run_shutdown())
    if args.command in {"setup", "test"}:
        sys.exit(run_tooling(args.command))
    try:
        load_local_config()
        if args.command == "init":
            result = asdict(
                initialize_project(
                    args.path,
                    args.title,
                    args.problem,
                    args.research_mode,
                    args.model,
                    args.thinking,
                    args.difficulty,
                )
            )
        elif args.command == "create":
            result = asdict(
                create_project(
                    args.title,
                    args.problem,
                    args.research_mode,
                    args.model,
                    args.thinking,
                    args.difficulty,
                )
            )
        elif args.command == "edit-project":
            try:
                expected = json.loads(args.expected)
            except ValueError as exc:
                raise ProjectError("--expected must be a JSON settings snapshot") from exc
            result = asdict(
                update_project(
                    args.path,
                    args.title,
                    args.problem,
                    args.research_mode,
                    args.model,
                    args.thinking,
                    expected,
                    difficulty=args.difficulty,
                )
            )
        elif args.command == "open":
            result = asdict(open_project(args.path))
        elif args.command == "inspect":
            result = asdict(inspect_project(args.path))
        elif args.command == "new-strategy":
            result = asdict(create_strategy(args.path, args.title, args.approach))
        elif args.command == "edit-strategy":
            result = asdict(edit_strategy(args.path, args.strategy_id, args.title, args.approach))
        elif args.command == "remove-strategy":
            result = asdict(remove_strategy(args.path, args.strategy_id))
        elif args.command == "stage-strategy":
            result = asdict(change_stage(args.path, args.strategy_id, args.stage))
        elif args.command == "reorder-strategies":
            result = asdict(reorder_strategies(args.path, args.order, args.expected_order))
        elif args.command == "strategies":
            result = {"strategies": [asdict(s) for s in list_strategies(args.path)]}
        elif args.command == "text":
            result = inspect_text(args.path, args.scope, args.strategy_id)
        elif args.command == "agentic-runs":
            result = (
                get_run(args.path, args.run_id) if args.run_id else {"runs": list_runs(args.path)}
            )
        elif args.command == "save-text":
            result = asdict(
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
            close_project()
            result = {"closed": True}
        if args.command == "init":
            from sigma.recents import record_access

            record_access(inspect_project(args.path))
        print(json.dumps(result))
    except (ProjectError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
