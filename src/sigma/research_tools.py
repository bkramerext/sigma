"""Local computation capabilities shared by every research role request."""

from datetime import UTC, datetime
from typing import Any

from sigma import python_sandbox


def execution_capabilities() -> list[dict[str, Any]]:
    """Observe only local images; never pull, build, or run research code."""
    tools = []
    for runtime, name, field, facilities in (
        (
            "python",
            "Scientific Python",
            "python_code",
            "NumPy, SciPy, pandas, SymPy and Matplotlib",
        ),
        (
            "sagemath",
            "SageMath",
            "sage_code",
            "native Sage syntax, exact algebra, number theory and symbolic computation",
        ),
    ):
        settings = python_sandbox.runtime_settings(runtime)
        identity = python_sandbox._image_identity(runtime)
        tools.append(
            {
                **settings,
                "name": name,
                "available": identity is not None,
                "image_id": identity,
                "observed_at": datetime.now(UTC).isoformat(),
                "request_field": field,
                "result_field": "sage_execution" if runtime == "sagemath" else "python_execution",
                "capabilities": facilities,
                "network": "none",
                "project_files": False,
                "source_characters": 4000,
                "source_bytes": 16000,
                "output_bytes": 32000,
                "cpu_limit": 1,
                "process_limit": 64,
                "artifact_count": 8,
                "artifact_bytes": 4000000,
                "setup": f"./sigma sandbox-build --runtime {runtime}",
            }
        )
    return tools


def capability_guidance(tools: list[dict[str, Any]]) -> str:
    availability = " ".join(
        f"{tool['name']} is {'available' if tool['available'] else 'unavailable'}; "
        f"request field {tool['request_field']}, result field {tool['result_field']}."
        for tool in tools
    )
    return (
        "Execution tools: " + availability + " Consult execution_tools for the observed runtime, "
        "capabilities, exact limits and setup guidance. Only the Investigator dispatches a computation: "
        "set exactly one of python_code or sage_code to a self-contained program, and set the other "
        "to null; use null for both when computation is not useful or the runtime is unavailable. "
        "Sage code uses native .sage preparsing (R.<x> declarations and ^ exponentiation). "
        "The Skeptic inspects the source and returned execution record and requests follow-up "
        "experiments through the next Investigator cycle; it cannot dispatch code directly. "
        "Each run is fresh, offline, without project files. Write flat files under /artifacts and "
        "print concise summaries; reviewers receive metadata, not plot pixels or full captured files. "
        "Use the selected runtime's limits, not another tool's limits. A previously available image "
        "may become unavailable before dispatch; inspect actual result status and never invent output. "
        "Queued cancellation prevents dispatch; stopping research during a dispatched computation "
        "allows bounded completion and saves its actual result without starting another role call. "
        "Failed, interrupted and timed-out computations are not successful evidence. Exact Sage "
        "arithmetic is computation evidence, not independent formal proof verification."
    )
