"""Test-only deterministic identity shim around the real SIGMA FastAPI app.

The X-Test-* headers are accepted only by this isolated test ASGI module. The
production application accepts principals solely from cloud-auth middleware.
"""

from types import SimpleNamespace

from fastapi import Request

from sigma import api

app = api.app


@app.middleware("http")
async def deterministic_test_principal(request: Request, call_next):
    subject = request.headers.get("x-test-subject")
    if subject and request.headers.get("x-test-revoked") != "true":
        request.state.cloud_principal = SimpleNamespace(
            subject=subject,
            email=request.headers.get("x-test-email", f"{subject}@example.test"),
            role=request.headers.get("x-test-role", "member"),
        )
    return await call_next(request)


async def deterministic_execution(source: str, runtime_name: str = "python"):
    from sigma.python_sandbox import ExecutionResult

    return ExecutionResult(
        "completed",
        0,
        "fixture-output\n",
        "",
        1,
        image_id="deterministic-test-image",
        runtime=runtime_name,
        artifacts=(("evidence.txt", "text/plain", b"persistent private artifact\n"),),
    )


api.python_sandbox.execute = deterministic_execution
