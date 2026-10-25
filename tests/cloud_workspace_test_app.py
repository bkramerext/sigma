"""Test-only deterministic identity shim around the real SIGMA FastAPI app.

The X-Test-* headers are accepted only by this isolated test ASGI module. The
production application accepts principals solely from cloud-auth middleware.
"""

from fastapi import Request

from sigma.storage import validate_startup

validate_startup()

from sigma import api, cloud_auth

app = api.app


@app.middleware("http")
async def deterministic_test_principal(request: Request, call_next):
    subject = request.headers.get("x-test-subject")
    if subject and request.headers.get("x-test-revoked") != "true":
        request.state.cloud_principal = cloud_auth.Principal(
            subject=subject,
            email=request.headers.get("x-test-email", f"{subject}@example.test"),
            role=request.headers.get("x-test-role", "member"),
        )
    return await call_next(request)


async def deterministic_auth_middleware(request: Request, call_next):
    """Replace only OIDC session resolution in the isolated integration server."""
    if request.url.path == "/api/ui-instance" or request.url.path.startswith("/api/cloud-auth/"):
        return await call_next(request)
    if not isinstance(getattr(request.state, "cloud_principal", None), cloud_auth.Principal):
        from fastapi.responses import JSONResponse

        return JSONResponse({"error": "Authentication required."}, status_code=401)
    return await call_next(request)


api.cloud_auth.middleware = deterministic_auth_middleware


async def deterministic_browser_origin(request: Request, call_next):
    """Permit only the explicitly configured local Vite origin in this test app."""
    from fastapi.responses import JSONResponse

    origin = request.headers.get("origin")
    allowed = {"http://127.0.0.1:5173", "http://localhost:5173"}
    fixture_origin = __import__("os").environ.get("SIGMA_TEST_BROWSER_ORIGIN", "")
    if fixture_origin:
        allowed.add(fixture_origin)
    if origin and origin not in allowed:
        return JSONResponse({"error": "Untrusted browser origin"}, status_code=403)
    return await api.cloud_auth.middleware(request, call_next)


# Replace only the origin filter in this test-only ASGI app. Production app
# keeps its fixed localhost and configured-host origin allowlist.
for middleware in api.app.user_middleware:
    if middleware.kwargs.get("dispatch") is api.local_browser_only:
        middleware.kwargs["dispatch"] = deterministic_browser_origin
api.app.middleware_stack = None


async def deterministic_execution(source: str, runtime_name: str = "python"):
    from sigma.python_sandbox import ExecutionResult

    failed = source == "# deterministic failure"
    return ExecutionResult(
        "failed" if failed else "completed",
        1 if failed else 0,
        "" if failed else "fixture-output\n",
        "fixture failure\n" if failed else "",
        1,
        image_id="deterministic-test-image",
        runtime=runtime_name,
        artifacts=()
        if failed
        else (("evidence.txt", "text/plain", b"persistent private artifact\n"),),
    )


api.python_sandbox.execute = deterministic_execution
