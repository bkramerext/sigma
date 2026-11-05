"""Hosted authentication scenarios, part 1 of 2."""

from cloud_auth_fixture import *


class CloudAuthTests(CloudAuthFixture):
    def test_e003_local_readonly_build_preflight_without_workspace(self):
        """Local operator can check a stale process without granting workspace access."""
        environment = {
            "SIGMA_CLOUD_AUTH_LOCAL": "true",
            "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
            "SIGMA_UI_INSTANCE_ID": "test-managed-instance",
        }
        with patch.dict(os.environ, environment):
            with (
                patch("sigma.build_info.build_commit", return_value="a" * 40),
                patch("sigma.build_info.checkout_commit", return_value="a" * 40),
            ):
                response = self.client.get("/api/local-runtime/build")
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(
                    response.json(),
                    {
                        "backend_build_commit": "a" * 40,
                        "backend_checkout_commit": "a" * 40,
                        "backend_update_required": False,
                        "build_verified": True,
                    },
                )
                self.assertEqual(response.headers["cache-control"], "no-store")
                # A build-only preflight is not an admin authorization grant.
                self.assertNotEqual(
                    self.client.get("/api/cloud-research/readiness").status_code, 200
                )
                with TestClient(
                    app,
                    base_url="http://127.0.0.1",
                    client=("192.0.2.10", 23456),
                ) as remote:
                    self.assertEqual(remote.get("/api/local-runtime/build").status_code, 404)
            with (
                patch("sigma.build_info.build_commit", return_value="a" * 40),
                patch("sigma.build_info.checkout_commit", return_value="b" * 40),
            ):
                result = self.client.get("/api/local-runtime/build")
                self.assertEqual(result.status_code, 200)
                self.assertTrue(result.json()["backend_update_required"])
                self.assertFalse(result.json()["build_verified"])
            with (
                patch("sigma.build_info.build_commit", return_value="unknown"),
                patch("sigma.build_info.checkout_commit", return_value=None),
            ):
                result = self.client.get("/api/local-runtime/build")
                self.assertEqual(result.status_code, 200)
                self.assertFalse(result.json()["build_verified"])
        # The diagnostic is unavailable in hosted mode even with a managed marker.
        with patch.dict(os.environ, {"SIGMA_UI_INSTANCE_ID": "test-managed-instance"}):
            self.assertNotEqual(self.client.get("/api/local-runtime/build").status_code, 200)

    def test_public_sample_paper_without_signin(self):
        """Only immutable catalog PDFs bypass hosted auth, never working papers."""
        pdf = (
            Path(__file__).resolve().parent / "fixtures/sigma-valid-sample-paper.pdf"
        ).read_bytes()
        with patch("sigma.samples.top_sample_pdf", return_value=pdf) as fetch:
            response = self.client.get("/api/projects/samples/test-sample/top-paper/pdf")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.content, pdf)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertIn("inline", response.headers["content-disposition"])
        fetch.assert_called_once_with("test-sample")
        self.assertIsNone(self.client.cookies.get(cloud_auth.GUEST_COOKIE))
        self.assertEqual(self.client.get("/api/projects/papers/private/pdf").status_code, 401)
        self.assertEqual(
            self.client.get("/api/projects/samples/test-sample/top-paper/tex").status_code, 401
        )
        for path in (
            "/api/projects/samples/-bad/top-paper/pdf",
            "/api/projects/samples/a%2Fb/top-paper/pdf",
        ):
            self.assertFalse(cloud_auth.public_sample_paper_path("GET", path))
        self.assertFalse(
            cloud_auth.public_sample_paper_path(
                "POST", "/api/projects/samples/test-sample/top-paper/pdf"
            )
        )

    def test_mock_queue_recovery_never_contacts_hosted_research(self):
        import asyncio

        from sigma import cloud_research, cloud_workspaces, research_sessions

        with (
            patch.object(cloud_workspaces, "enabled", return_value=True),
            patch.object(
                research_sessions,
                "_all",
                return_value=[{"id": "mock-1", "status": "queued", "simulated": True}],
            ),
            patch.object(
                cloud_research,
                "reconcile_orphaned_jobs",
                side_effect=AssertionError("Mock queue contacted hosted jobs"),
            ),
            patch.object(
                research_sessions,
                "_worker",
                side_effect=AssertionError("Mock queue dispatched a provider worker"),
            ),
        ):
            asyncio.run(research_sessions.ensure_queued_workers("/mock/private-a"))

    def test_mock_save_skips_cloud_job_sync(self):
        from sigma import cloud_research, cloud_workspaces, research_sessions

        with (
            patch.object(cloud_workspaces, "enabled", return_value=True),
            patch.object(research_sessions, "_directory", return_value=Path(self.temp.name)),
            patch.object(
                cloud_research,
                "sync_job",
                side_effect=AssertionError("Mock session synced a hosted job"),
            ),
        ):
            research_sessions._save(
                "/mock/private-a",
                {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "status": "queued",
                    "simulated": True,
                },
            )

    def test_mock_session_lifecycle_is_deterministic_and_provider_free(self):
        from sigma import research_sessions

        record = {
            "id": "11111111-1111-4111-8111-111111111111",
            "project_path": "/mock/private-a",
            "project_id": "project-a",
            "strategy_id": "strategy-a",
            "strategy_title": "Test strategy",
            "strategy_runs": [
                {"strategy_id": "strategy-a", "artifacts": [], "status": "queued", "calls_used": 0}
            ],
            "status": "queued",
            "mock_stage": 0,
            "mock_scenario": "completed",
            "simulated": True,
            "artifacts": [],
            "events": [],
        }
        with (
            patch.object(research_sessions, "_save") as saved,
            patch.object(research_sessions, "_outcome", return_value={"assessment": "mixed"}),
            patch.object(
                research_sessions,
                "_worker",
                side_effect=AssertionError("No provider worker may run"),
            ),
        ):
            for expected in ("running", "running", "ended"):
                research_sessions._advance_mock(record)
                self.assertEqual(record["status"], expected)
            self.assertEqual(len(record["artifacts"]), 1)
            self.assertTrue(record["artifacts"][0]["simulated"])
            self.assertEqual(
                record["strategy_runs"][0]["artifacts"], [record["artifacts"][0]["id"]]
            )
            self.assertEqual(record["strategy_runs"][0]["calls_used"], 0)
            self.assertEqual([e["sequence"] for e in record["events"]], [1, 2, 3])
            research_sessions._advance_mock(record)
            self.assertEqual(saved.call_count, 3)
            self.assertEqual(len(record["artifacts"]), 1)

    def test_mock_session_resume_continues_simulation_without_provider_calls(self):
        from sigma import research_sessions

        session_id = "11111111-1111-4111-8111-111111111111"
        record = {
            "id": session_id,
            "project_path": "/mock/private-a",
            "project_id": "project-a",
            "strategy_id": "strategy-a",
            "strategy_title": "Test strategy",
            "strategy_runs": [
                {
                    "strategy_id": "strategy-a",
                    "status": "stopped",
                    "current_action": "Stopped",
                    "artifacts": [],
                    "calls_used": 0,
                }
            ],
            "status": "stopped",
            "mode": "mock",
            "simulated": True,
            "mock_stage": 1,
            "mock_scenario": "completed",
            "events": [],
            "artifacts": [],
        }
        with (
            patch.object(research_sessions, "_read", return_value=record),
            patch.object(research_sessions, "_all", return_value=[record]),
            patch.object(research_sessions, "_save") as save,
            patch.object(
                research_sessions, "get_limits", return_value=research_sessions.DEFAULT_LIMITS
            ),
        ):
            resumed = research_sessions.control_mock_session(
                "/mock/private-a", session_id, "resume"
            )
            assert resumed is not None
            self.assertEqual(resumed["status"], "queued")
            self.assertEqual(resumed["mock_stage"], 1)
            self.assertTrue(resumed["simulated"])
            self.assertIn("No provider was called", resumed["message"])
            self.assertEqual(resumed["events"][-1]["kind"], "simulation.resumed")
            self.assertEqual(record["strategy_runs"][0]["status"], "queued")
            save.assert_called_once()

    def test_mock_failure_scenarios_never_create_fake_evidence(self):
        from sigma import research_sessions

        for scenario in ("failed", "provider-error", "exhausted"):
            record = {
                "project_path": "/mock/private-a",
                "project_id": "project-a",
                "strategy_id": "strategy-a",
                "strategy_title": "Test strategy",
                "strategy_runs": [{"artifacts": [], "status": "queued", "calls_used": 0}],
                "status": "queued",
                "mock_stage": 2,
                "mock_scenario": scenario,
                "simulated": True,
                "artifacts": [],
                "events": [],
            }
            with (
                self.subTest(scenario=scenario),
                patch.object(research_sessions, "_save"),
                patch.object(research_sessions, "_outcome", return_value={}),
            ):
                research_sessions._advance_mock(record)
                self.assertEqual(record["status"], "failed")
                self.assertEqual(record["artifacts"], [])
                self.assertIn("No provider was called", record["message"])

    def test_local_sponsored_test_flag_selects_mock_and_rejects_personal_switch(self):
        origin = {"Origin": "http://127.0.0.1:5173"}
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_LOCAL_SPONSORED_TEST_MODE": "1",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root),
            },
        ):
            status = self.client.get("/api/cloud-auth/status").json()
            self.assertTrue(status["sponsored_test_mode"])
            self.assertEqual(
                self.client.post(
                    "/api/cloud-auth/mock/select?identity=member-a", headers=origin
                ).status_code,
                204,
            )
            status = self.client.get("/api/cloud-auth/status").json()
            self.assertTrue(status["account"]["sponsorship"]["eligible"])
            self.assertEqual(status["account"]["model_access"]["mode"], "sponsored")
            denied = self.client.post(
                "/api/cloud-auth/mock/model-access?mode=personal", headers=origin
            )
            self.assertEqual(denied.status_code, 403)
            direct_provider_mode = self.client.post(
                "/api/ai/mode", json={"mode": "personal"}, headers=origin
            )
            self.assertEqual(direct_provider_mode.status_code, 403)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )
            funding = self.client.get("/api/cloud-auth/mock/funding")
            self.assertEqual(funding.status_code, 200, funding.text)
            self.assertTrue(funding.json()["allowance"]["simulated"])
            self.assertEqual(funding.json()["provider"], "connected")
            disconnected = self.client.post(
                "/api/cloud-auth/mock/provider?scenario=unavailable", headers=origin
            )
            self.assertEqual(disconnected.status_code, 200, disconnected.text)
            self.assertEqual(
                self.client.get("/api/cloud-auth/mock/funding").json()["provider"], "unavailable"
            )
            # The next launch's automatic identity selection rediscovers the sponsored state.
            self.assertEqual(
                self.client.post(
                    "/api/cloud-auth/mock/select?identity=member-a", headers=origin
                ).status_code,
                204,
            )
            funding = self.client.get("/api/cloud-auth/mock/funding").json()
            self.assertEqual(funding["mode"], "sponsored")
            self.assertEqual(funding["provider"], "connected")

    def test_mock_research_route_never_invokes_live_start(self):
        from sigma import research_sessions

        origin = {"Origin": "http://127.0.0.1:5173"}
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root),
            },
        ):
            self.assertEqual(
                self.client.post(
                    "/api/cloud-auth/mock/select",
                    params={"identity": "member-a"},
                    headers=origin,
                ).status_code,
                204,
            )
            created = self.client.post(
                "/api/projects/create",
                json={"title": "Research fixture", "problem": "Test mock research."},
                headers=origin,
            )
            self.assertEqual(created.status_code, 201, created.text)
            project = created.json()
            with (
                patch.object(
                    research_sessions,
                    "start_session",
                    side_effect=AssertionError("Real research start must never run in mock mode"),
                ),
                patch.object(
                    research_sessions,
                    "mock_session",
                    return_value={
                        "id": "mock-session",
                        "status": "queued",
                        "simulated": True,
                    },
                ) as fake,
            ):
                response = self.client.post(
                    "/api/projects/research-sessions/mock",
                    json={
                        "path": project["path"],
                        "strategy_id": "fixture-strategy",
                        "expected_project_id": project["project"]["id"],
                        "idempotency_key": "11111111-1111-4111-8111-111111111111",
                    },
                    headers=origin,
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertTrue(response.json()["simulated"])
                fake.assert_called_once()
            with (
                patch.object(
                    research_sessions,
                    "control_mock_session",
                    return_value={"id": "mock-session", "status": "queued", "simulated": True},
                ) as mock_control,
                patch.object(
                    research_sessions,
                    "control_session",
                    side_effect=AssertionError("Mock resume must not enter provider resume checks"),
                ),
            ):
                resumed = self.client.post(
                    "/api/projects/research-sessions/mock-session/control",
                    json={"path": project["path"], "action": "resume"},
                    headers=origin,
                )
                self.assertEqual(resumed.status_code, 200, resumed.text)
                self.assertTrue(resumed.json()["simulated"])
                mock_control.assert_called_once_with(project["path"], "mock-session", "resume")
            with (
                patch.object(research_sessions, "control_mock_session", return_value=None),
                patch.object(
                    research_sessions,
                    "control_session",
                    side_effect=AssertionError("Mock identities must not resume real sessions"),
                ),
            ):
                denied_resume = self.client.post(
                    "/api/projects/research-sessions/real-session/control",
                    json={"path": project["path"], "action": "resume"},
                    headers=origin,
                )
                self.assertEqual(denied_resume.status_code, 404, denied_resume.text)
            blocked = self.client.post(
                "/api/projects/research-sessions/start",
                json={},
                headers=origin,
            )
            self.assertEqual(blocked.status_code, 403)

    def test_mock_members_cannot_read_each_others_session_records(self):
        from sigma import research_sessions

        origin = {"Origin": "http://127.0.0.1:5173"}
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root),
            },
        ):
            self.assertEqual(
                self.client.post(
                    "/api/cloud-auth/mock/select",
                    params={"identity": "member-a"},
                    headers=origin,
                ).status_code,
                204,
            )
            created = self.client.post(
                "/api/projects/create",
                json={"title": "Private mock session", "problem": "Test isolation"},
                headers=origin,
            )
            self.assertEqual(created.status_code, 201, created.text)
            path = created.json()["path"]
            session_id = "11111111-1111-4111-8111-111111111111"
            # The session file belongs to Member A's project workspace.
            with patch.object(research_sessions, "_snapshot") as snapshot:
                # A project-scoped read must resolve through the active workspace,
                # never through a supplied path belonging to another member.
                self.assertEqual(
                    self.client.get(
                        "/api/projects/research-sessions",
                        params={"path": path},
                    ).status_code,
                    200,
                )
                self.assertFalse(snapshot.called)
            self.assertEqual(
                self.client.post(
                    "/api/cloud-auth/mock/select",
                    params={"identity": "member-b"},
                    headers=origin,
                ).status_code,
                204,
            )
            for endpoint in (
                "/api/projects/research-sessions",
                f"/api/projects/research-sessions/{session_id}",
            ):
                denied = self.client.get(endpoint, params={"path": path})
                self.assertIn(denied.status_code, {400, 403, 404}, denied.text)
            artifact = self.client.get(
                "/api/projects/research-executions/11111111-1111-4111-8111-111111111111/"
                "artifacts/evidence.txt",
                params={"path": path},
            )
            self.assertIn(artifact.status_code, {400, 403, 404}, artifact.text)
            self.assertEqual(
                self.client.post(
                    "/api/cloud-auth/mock/select",
                    params={"identity": "member-a"},
                    headers=origin,
                ).status_code,
                204,
            )
            self.assertEqual(
                self.client.get(
                    "/api/projects/research-sessions",
                    params={"path": path},
                ).status_code,
                200,
            )

    def test_mock_member_projects_are_not_visible_to_other_members(self):
        origin = {"Origin": "http://127.0.0.1:5173"}
        member_a_path = ""
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root),
            },
        ):
            for identity in ("member-a", "member-b"):
                selected = self.client.post(
                    "/api/cloud-auth/mock/select",
                    params={"identity": identity},
                    headers=origin,
                )
                self.assertEqual(selected.status_code, 204)
                created = self.client.post(
                    "/api/projects/create",
                    json={
                        "title": "Mock isolation " + identity,
                        "problem": "Verify member project isolation.",
                    },
                    headers=origin,
                )
                self.assertEqual(created.status_code, 201, created.text)
                project = created.json()
                self.assertIn("path", project)
                if identity == "member-a":
                    member_a_path = project["path"]
                    self.assertEqual(
                        self.client.get(
                            "/api/projects/inspect", params={"path": member_a_path}
                        ).status_code,
                        200,
                    )
                else:
                    denied = self.client.get(
                        "/api/projects/inspect",
                        params={"path": member_a_path},
                    )
                    self.assertIn(denied.status_code, {400, 403, 404})
                    denied_open = self.client.post(
                        "/api/projects/open",
                        json={"path": member_a_path},
                        headers=origin,
                    )
                    self.assertIn(denied_open.status_code, {400, 403, 404})
            switched = self.client.post(
                "/api/cloud-auth/mock/select",
                params={"identity": "member-a"},
                headers=origin,
            )
            self.assertEqual(switched.status_code, 204)
            self.assertEqual(
                self.client.get(
                    "/api/projects/inspect", params={"path": member_a_path}
                ).status_code,
                200,
            )

    def test_mock_member_switches_bind_separate_project_workspaces(self):
        from sigma import cloud_workspaces

        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root),
            },
        ):
            self.assertTrue(cloud_workspaces.enabled())
            seen = []
            for identity in ("member-a", "member-b", "member-a"):
                response = self.client.post(
                    "/api/cloud-auth/mock/select",
                    params={"identity": identity},
                    headers={"Origin": "http://127.0.0.1:5173"},
                )
                self.assertEqual(response.status_code, 204)
                status = self.client.get("/api/cloud-auth/status")
                self.assertEqual(status.status_code, 200)
                self.assertTrue(status.json()["authenticated"])
                seen.append(status.json()["account"]["workspace"]["id"])
                # The project endpoint executes through the same workspace
                # dependency used by all project operations.
                projects = self.client.get("/api/projects/recent")
                self.assertEqual(projects.status_code, 200)
            self.assertNotEqual(seen[0], seen[1])
            self.assertEqual(seen[0], seen[2])

    def test_mock_project_mutations_are_not_blanket_blocked(self):
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root),
            },
        ):
            selected = self.client.post(
                "/api/cloud-auth/mock/select?identity=member-a",
                headers={"Origin": "http://127.0.0.1:5173"},
            )
            self.assertEqual(selected.status_code, 204)
            # A normal project mutation may fail validation, but must not be
            # rejected by the mock execution guard.
            project = self.client.post(
                "/api/projects/close",
                json={"path": "/nonexistent/mock-project"},
                headers={"Origin": "http://127.0.0.1:5173"},
            )
            self.assertNotIn("research execution is disabled", project.text)
            execution = self.client.post(
                "/api/projects/research-sessions",
                json={},
                headers={"Origin": "http://127.0.0.1:5173"},
            )
            self.assertEqual(execution.status_code, 403)
            self.assertTrue(execution.json()["simulated"])
            provider = self.client.get("/api/ai/connection")
            self.assertEqual(provider.status_code, 403)

    def test_mock_members_receive_distinct_stable_workspaces(self):
        from sigma.cloud_workspaces import workspace_for_subject

        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root),
            },
        ):
            cfg = cloud_auth.config()
            self.assertIsNone(cfg.error)
            first = cloud_auth._persist_user_state(
                cfg,
                cloud_auth.Principal("mock:member-a", "mock-member-a@localhost.invalid", "member"),
            )
            second = cloud_auth._persist_user_state(
                cfg,
                cloud_auth.Principal("mock:member-b", "mock-member-b@localhost.invalid", "member"),
            )
            first_again = cloud_auth._persist_user_state(
                cfg,
                cloud_auth.Principal("mock:member-a", "mock-member-a@localhost.invalid", "member"),
            )
        self.assertTrue(first["workspace"]["available"])
        self.assertTrue(second["workspace"]["available"])
        self.assertNotEqual(first["workspace"]["id"], second["workspace"]["id"])
        self.assertEqual(first["workspace"]["id"], first_again["workspace"]["id"])
        self.assertEqual(
            workspace_for_subject("mock:member-a").workspace_id,
            first["workspace"]["id"],
        )

    def test_mock_auth_requires_explicit_loopback_local_configuration(self):
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "SIGMA_CLOUD_AUTH_HOME": str(self.root),
                "GOOGLE_OIDC_CLIENT_ID": "",
                "GOOGLE_OIDC_CLIENT_SECRET": "",
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "",
            },
        ):
            cfg = cloud_auth.config()
            self.assertIsNone(cfg.error)
            self.assertTrue(cfg.local)
            self.assertTrue(cloud_auth._mock_enabled(cfg))
            with patch.dict(os.environ, {"SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5182"}):
                self.assertTrue(cloud_auth._mock_enabled(cloud_auth.config()))
            with patch.dict(os.environ, {"SIGMA_CLOUD_PUBLIC_ORIGIN": "https://sigma.example.org"}):
                self.assertFalse(cloud_auth._mock_enabled(cloud_auth.config()))
            for invalid_origin in (
                "http://example.org:5182",
                "http://127.0.0.1:5182/path",
                "https://127.0.0.1:5182",
                "http://user@127.0.0.1:5182",
            ):
                with (
                    self.subTest(origin=invalid_origin),
                    patch.dict(os.environ, {"SIGMA_CLOUD_PUBLIC_ORIGIN": invalid_origin}),
                ):
                    self.assertFalse(cloud_auth._mock_enabled(cloud_auth.config()))

    def test_mock_auth_disabled_for_hosted_and_nonlocal_configurations(self):
        with patch.dict(os.environ, {"SIGMA_MOCK_AUTH": "1"}):
            self.assertFalse(cloud_auth._mock_enabled(cloud_auth.config()))
            response = self.client.post(
                "/api/cloud-auth/mock/select?identity=admin",
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(
                response.status_code, 401
            )  # Protected by auth middleware when mock mode is off.
        with patch.dict(
            os.environ,
            {
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": ORIGIN,
            },
        ):
            self.assertFalse(cloud_auth._mock_enabled(cloud_auth.config()))

    def test_mock_auth_rejects_cross_origin_and_remote_clients(self):
        with patch.dict(
            os.environ,
            {
                "SIGMA_MOCK_AUTH": "1",
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
            },
        ):
            self.assertTrue(cloud_auth._mock_enabled(cloud_auth.config()))
            self.assertEqual(
                self.client.post(
                    "/api/cloud-auth/mock/select?identity=admin",
                    headers={"Origin": "http://evil.example"},
                ).status_code,
                403,
            )
            # A remote ASGI peer must be rejected even with an allowed Origin.
            from fastapi.testclient import TestClient

            with TestClient(
                app, base_url="http://127.0.0.1", client=("198.51.100.8", 12345)
            ) as remote:
                self.assertEqual(
                    remote.post(
                        "/api/cloud-auth/mock/select?identity=admin",
                        headers={"Origin": "http://127.0.0.1:5173"},
                    ).status_code,
                    403,
                )

    def test_google_login_reports_missing_local_oauth_settings_before_redirect(self):
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
                "GOOGLE_OIDC_CLIENT_ID": "",
                "GOOGLE_OIDC_CLIENT_SECRET": "",
            },
        ):
            response = self.client.get("/api/cloud-auth/login", follow_redirects=False)
        self.assertEqual(response.status_code, 503)
        self.assertIn("GOOGLE_OIDC_CLIENT_ID", response.json()["detail"])
        self.assertIn("GOOGLE_OIDC_CLIENT_SECRET", response.json()["detail"])

    def test_guest_cookie_is_bound_to_one_verified_subject(self):
        from sigma import cloud_workspaces

        token_value = uuid4().hex * 2
        owner = cloud_workspaces.guest_workspace(
            token_value, create=True, subject="verified-google-subject-a"
        )
        self.assertIsNotNone(owner)
        assert owner is not None
        same_owner = cloud_workspaces.guest_workspace(
            token_value, subject="verified-google-subject-a"
        )
        self.assertEqual(same_owner, owner)
        self.assertIsNone(
            cloud_workspaces.guest_workspace(token_value, subject="verified-google-subject-b")
        )
        # A signed-out browser can continue its temporary guest page; signing
        # in as another Google identity will be checked against the binding.
        self.assertEqual(cloud_workspaces.guest_workspace(token_value), owner)

    def test_guest_sample_projects_use_temporary_workspace_without_recents(self):
        from sigma import cloud_workspaces

        with TestClient(app, base_url="https://testserver") as guest:
            catalog = guest.get("/api/projects/samples")
            self.assertEqual(catalog.status_code, 200, catalog.text)
            raw_guest = guest.cookies.get(cloud_auth.GUEST_COOKIE)
            self.assertIsNotNone(raw_guest)
            workspace = cloud_workspaces.guest_workspace(raw_guest)
            self.assertIsNotNone(workspace)
            assert workspace is not None
            self.assertTrue(workspace.guest)
            sample_id = "qubit-non-markovian-decoherence"
            listed_sample = next(
                item for item in catalog.json()["projects"] if item["id"] == sample_id
            )
            source = json.loads(
                (
                    Path(__file__).resolve().parents[1] / "samples" / sample_id / "project.json"
                ).read_bytes()
            )
            self.assertEqual(listed_sample["investigation_type"], "physics")
            self.assertEqual(listed_sample["problem"], source["problem"])
            self.assertEqual(source["schema_version"], 8)
            opened = guest.post(
                "/api/projects/samples/open",
                json={"sample_id": sample_id},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(opened.status_code, 200, opened.text)
            project_path = Path(opened.json()["path"])
            self.assertTrue(project_path.is_relative_to(workspace.path))
            self.assertTrue((project_path / "project.json").is_file())
            copied = opened.json()["project"]
            self.assertEqual(copied["investigation_type"], "physics")
            self.assertEqual(copied["schema_version"], 8)
            self.assertEqual(copied["problem"], source["problem"])
            self.assertEqual(copied["project_type_snapshot"]["name"], "Physics")
            self.assertEqual(copied["project_type_snapshot"]["icon"]["key"], "physics")
            self.assertEqual(guest.get("/api/projects/recent").json(), {"projects": []})
            inspected = guest.get("/api/projects/inspect", params={"path": str(project_path)})
            self.assertEqual(inspected.status_code, 200, inspected.text)
            self.assertEqual(
                guest.post(
                    "/api/projects/research-sessions/start",
                    json={"path": str(project_path)},
                    headers={"Origin": ORIGIN},
                ).status_code,
                403,
            )
            self.assertEqual(
                guest.post(
                    "/api/projects/text/convert",
                    json={"path": str(project_path)},
                    headers={"Origin": ORIGIN},
                ).status_code,
                403,
            )
        self.assertTrue(project_path.exists(), "Guest files remain until expiry, not as projects")
        with TestClient(app, base_url="https://testserver") as another_guest:
            self.assertEqual(another_guest.get("/api/projects/recent").status_code, 401)

    def test_guest_play_signin_and_project_signout_keep_the_project_page(self):
        from sigma import cloud_workspaces

        with TestClient(app, base_url="https://testserver") as browser:
            catalog = browser.get("/api/projects/samples")
            self.assertEqual(catalog.status_code, 200, catalog.text)
            opened = browser.post(
                "/api/projects/samples/open",
                json={"sample_id": catalog.json()["projects"][0]["id"]},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(opened.status_code, 200, opened.text)
            guest_path = opened.json()["path"]
            guest_id = opened.json()["project"]["id"]
            source_guest = cloud_workspaces.guest_workspace(
                browser.cookies.get(cloud_auth.GUEST_COOKIE)
            )
            self.assertIsNotNone(source_guest)

            completed = self.finish(
                client=browser,
                return_to=f"/project?path={guest_path}&resume_play=1",
            )
            self.assertEqual(completed.status_code, 303)
            return_query = parse_qs(urlsplit(completed.headers["location"]).query)
            member_path = return_query["path"][0]
            self.assertEqual(return_query["resume_play"], ["1"])
            self.assertNotEqual(member_path, guest_path)
            member_project = browser.post(
                "/api/projects/open", json={"path": member_path}, headers={"Origin": ORIGIN}
            )
            self.assertEqual(member_project.status_code, 200, member_project.text)
            self.assertEqual(member_project.json()["project"]["id"], guest_id)

            copied = browser.post(
                "/api/projects/guest-copy",
                json={"path": member_path},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(copied.status_code, 201, copied.text)
            guest_copy_path = copied.json()["path"]
            self.assertNotEqual(guest_copy_path, member_path)
            self.assertTrue(Path(member_path).exists(), "Signing out must retain the account copy")
            signed_out = browser.post("/api/cloud-auth/logout", headers={"Origin": ORIGIN})
            self.assertEqual(signed_out.status_code, 204)
            guest_copy = browser.post(
                "/api/projects/open", json={"path": guest_copy_path}, headers={"Origin": ORIGIN}
            )
            self.assertEqual(guest_copy.status_code, 200, guest_copy.text)
            self.assertEqual(guest_copy.json()["project"]["id"], guest_id)

    def test_separate_guest_workspaces_can_open_same_sample_with_saved_sessions(self):
        from sigma import research_sessions

        paths: list[str] = []
        session_ids: list[set[str]] = []
        for _ in range(2):
            with TestClient(app, base_url="https://testserver") as guest:
                opened = guest.post(
                    "/api/projects/samples/open",
                    json={"sample_id": "nonconsecutive-subset-sums"},
                    headers={"Origin": ORIGIN},
                )
                self.assertEqual(opened.status_code, 200, opened.text)
                path = opened.json()["path"]
                paths.append(path)
                session_ids.append({record["id"] for record in research_sessions._all(path)})

        self.assertTrue(session_ids[0])
        self.assertTrue(session_ids[1])
        self.assertFalse(session_ids[0] & session_ids[1])
        self.assertNotEqual(paths[0], paths[1])

    def test_guest_projects_stay_temporary_when_local_google_auth_is_unready(self):
        from dataclasses import replace

        from sigma import cloud_workspaces

        unavailable = replace(cloud_auth.config(), error="Google sign-in is not configured")
        with (
            patch.dict(os.environ, {"SIGMA_CLOUD_AUTH_LOCAL": "true"}),
            patch.object(cloud_auth, "config", return_value=unavailable),
            TestClient(app, base_url="https://testserver") as guest,
        ):
            catalog = guest.get("/api/projects/samples")
            self.assertEqual(catalog.status_code, 200, catalog.text)
            opened = guest.post(
                "/api/projects/samples/open",
                json={"sample_id": catalog.json()["projects"][0]["id"]},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(opened.status_code, 200, opened.text)
            workspace = cloud_workspaces.guest_workspace(
                guest.cookies.get(cloud_auth._cookie_name(cloud_auth.GUEST_COOKIE, unavailable))
            )
            self.assertIsNotNone(workspace)
            assert workspace is not None
            self.assertTrue(Path(opened.json()["path"]).is_relative_to(workspace.path))

    def test_signin_returns_to_safe_project_continuation(self):
        project_return = "/project?path=%2Ftmp%2Fguest-project&resume_play=1"
        completed = self.finish(return_to=project_return)
        self.assertEqual(completed.status_code, 303)
        self.assertEqual(completed.headers["location"], project_return)

        unsupported_intent, _ = self.start_flow(
            return_to="/project?path=%2Ftmp%2Fguest-project&resume_play=2"
        )
        with cloud_auth._db(cloud_auth.config()) as db:
            flow = db.execute(
                "SELECT return_to FROM flows WHERE state_hash=?",
                (cloud_auth._hash(unsupported_intent),),
            ).fetchone()
        self.assertEqual(flow["return_to"], "/project?path=%2Ftmp%2Fguest-project")

        state, _ = self.start_flow(return_to="https://evil.example/steal")
        with cloud_auth._db(cloud_auth.config()) as db:
            flow = db.execute(
                "SELECT return_to FROM flows WHERE state_hash=?", (cloud_auth._hash(state),)
            ).fetchone()
        self.assertIsNone(flow["return_to"])

    def test_successful_signin_admin_invite_and_revocation(self):
        self.assertEqual(
            self.client.get(
                "/api/projects/research-sessions", params={"path": str(self.project_path)}
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.get(
                "/api/projects/research-sessions", headers={"X-User-Email": "admin@example.org"}
            ).status_code,
            401,
        )
        signed_in = self.finish()
        self.assertEqual(signed_in.status_code, 303)
        self.assertTrue((self.root / "workspaces" / "workspaces.sqlite3").is_file())
        session = signed_in.cookies[cloud_auth.SESSION_COOKIE]
        self.assertIn("Secure", signed_in.headers["set-cookie"])
        self.assertIn("HttpOnly", signed_in.headers["set-cookie"])
        self.assertIn("Max-Age=28800", signed_in.headers["set-cookie"])
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, session)
        status = self.client.get("/api/cloud-auth/status").json()
        self.assertEqual(
            status["user"],
            {"email": "admin@example.org", "role": "admin"},
        )
        self.assertEqual(
            status["account"]["identity"], {"email": "admin@example.org", "verified": True}
        )
        self.assertEqual(status["account"]["access"], {"status": "invited", "role": "admin"})
        self.assertTrue(status["account"]["workspace"]["available"])
        self.assertEqual(
            status["account"]["model_access"],
            {"mode": "sponsored", "connection": "checking"},
        )
        self.assertTrue(status["account"]["sponsorship"]["eligible"])
        self.assertEqual(status["admin_contact_email"], "admin@example.org")
        self.assertNotIn("grants", status)
        self.assertNotIn("denied_email", status)
        # Exercise the real verified Principal -> workspace dependency path,
        # not only the test-only deterministic identity adapter.
        workspace_response = self.client.get(
            "/api/projects/recent",
            headers={
                "X-Test-Subject": "forged-browser-subject",
                "X-User-Email": "victim@example.org",
                "X-Workspace-ID": "forged-workspace",
            },
        )
        self.assertEqual(workspace_response.status_code, 200, workspace_response.text)
        self.assertEqual(workspace_response.json()["projects"], [])
        workspace_database = self.root / "workspaces" / "workspaces.sqlite3"
        self.assertTrue(workspace_database.is_file())
        import sqlite3

        with sqlite3.connect(workspace_database) as db:
            entries = db.execute("SELECT subject_hash,workspace_id FROM workspaces").fetchall()
        self.assertEqual(len(entries), 1)
        with sqlite3.connect(self.root / "access.sqlite3") as db:
            persisted = db.execute(
                "SELECT email,role,access_active,workspace_id,sponsorship_eligible,model_access,model_connection_status FROM user_state WHERE subject=?",
                ("google-sub-1",),
            ).fetchone()
        self.assertEqual(
            persisted,
            (
                "admin@example.org",
                "admin",
                1,
                status["account"]["workspace"]["id"],
                1,
                "sponsored",
                "checking",
            ),
        )
        self.assertNotIn(b"forged-browser-subject", workspace_database.read_bytes())
        self.assertNotIn(b"victim@example.org", workspace_database.read_bytes())
        invite = self.client.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "email", "value": " Person@Example.org ", "role": "member"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(invite.status_code, 200)
        self.assertEqual(invite.json()["value"], "person@example.org")
        member_context = TestClient(app)
        member = member_context.__enter__()
        self.addCleanup(member_context.__exit__, None, None, None)
        member_login = self.finish(
            email="person@example.org", subject="google-sub-member", client=member
        )
        self.assertEqual(member_login.status_code, 303)
        revoked = self.client.delete(
            "/api/cloud-auth/admin/grants/email/person%40example.org", headers={"Origin": ORIGIN}
        )
        self.assertEqual(revoked.status_code, 200)
        with sqlite3.connect(self.root / "access.sqlite3") as db:
            member_state = db.execute(
                "SELECT access_active,sponsorship_eligible FROM user_state WHERE subject=?",
                ("google-sub-member",),
            ).fetchone()
        self.assertEqual(member_state, (0, 0))
        self.assertEqual(member.get("/api/projects/recent").status_code, 401)
        self.assertEqual(self.client.get("/api/cloud-auth/admin/grants").json()["grants"], [])
        self.assertEqual(
            self.client.post("/api/ai/disconnect", headers={"Origin": ORIGIN}).status_code, 403
        )

    def test_hosted_read_only_model_checks_keep_auth_mutations_blocked(self):
        signed_in = self.finish()
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_in.cookies[cloud_auth.SESSION_COOKIE]
        )
        with patch("sigma.api.models", return_value={"connection": {"status": "unconfigured"}}):
            response = self.client.get("/api/ai/models")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["connection"]["status"], "unconfigured")
            self.assertEqual(response.headers["cache-control"], "no-store")
        with patch("sigma.api.connection", return_value={"status": "unconfigured"}):
            self.assertEqual(self.client.get("/api/ai/connection").status_code, 200)
        for path in ("/api/ai/auth/begin", "/api/ai/disconnect"):
            self.assertEqual(
                self.client.post(path, headers={"Origin": ORIGIN}, json={}).status_code, 403
            )
        self.assertEqual(
            self.client.post(
                "/api/ai/mode", headers={"Origin": ORIGIN}, json={"mode": "api_key"}
            ).status_code,
            422,
        )
        # The admin-only sponsor handoff route accepts this URL shape, but an
        # unknown identifier cannot resolve to an OAuth authorization URL.
        self.assertEqual(self.client.get("/api/ai/auth/open/guessed").status_code, 400)
        self.assertEqual(TestClient(app).get("/api/ai/models").status_code, 401)

    def test_session_persists_across_client_restart_and_logout_revokes_it(self):
        signed_in = self.finish()
        raw = signed_in.cookies[cloud_auth.SESSION_COOKIE]

        # A new desktop browser process keeps its secure cookie while the
        # server-side session remains in the persistent auth database.
        restarted_context = TestClient(app)
        restarted = restarted_context.__enter__()
        self.addCleanup(restarted_context.__exit__, None, None, None)
        restarted.cookies.set(cloud_auth.SESSION_COOKIE, raw)
        self.assertEqual(
            restarted.get("/api/cloud-auth/status").json()["user"]["email"], "admin@example.org"
        )
        self.assertEqual(restarted.get("/api/projects/recent").status_code, 200)

        signed_out = restarted.post("/api/cloud-auth/logout", headers={"Origin": ORIGIN})
        self.assertEqual(signed_out.status_code, 204)
        self.assertIn('__Host-sigma_session="";', signed_out.headers["set-cookie"])
        self.assertIn("Max-Age=0", signed_out.headers["set-cookie"])
        self.assertIsNone(cloud_auth.resolve_session(raw))
        self.assertEqual(restarted.get("/api/projects/recent").status_code, 401)

        # A copied/stale cookie cannot restore access from another client.
        stale_context = TestClient(app)
        stale = stale_context.__enter__()
        self.addCleanup(stale_context.__exit__, None, None, None)
        stale.cookies.set(cloud_auth.SESSION_COOKIE, raw)
        self.assertEqual(stale.get("/api/projects/recent").status_code, 401)

    def test_admin_contact_is_designated_admin_and_subject_binding_is_enforced(self):
        response = self.finish(email="admin@example.org", subject="first-admin-subject")
        self.assertEqual(response.status_code, 303)
        self.assertIn(cloud_auth.SESSION_COOKIE, response.cookies)

        second_context = TestClient(app)
        second_client = second_context.__enter__()
        self.addCleanup(second_context.__exit__, None, None, None)
        denied = self.finish(
            email="admin@example.org", subject="different-google-subject", client=second_client
        )
        self.assertEqual(denied.status_code, 303)
        self.assertEqual(denied.headers["location"], "/?access=denied")
        self.assertNotIn(cloud_auth.SESSION_COOKIE, denied.cookies)

    def test_invitation_request_uses_verified_identity_and_is_admin_only(self):
        admin_login = self.finish(email="admin@example.org", subject="request-admin")
        self.assertEqual(admin_login.status_code, 303)
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, admin_login.cookies[cloud_auth.SESSION_COOKIE]
        )
        visitor_context = TestClient(app)
        visitor = visitor_context.__enter__()
        self.addCleanup(visitor_context.__exit__, None, None, None)
        denied = self.finish(email="visitor@example.org", subject="request-visitor", client=visitor)
        self.assertEqual(denied.headers["location"], "/?access=denied")
        visitor.cookies.set(cloud_auth.DENIED_COOKIE, denied.cookies[cloud_auth.DENIED_COOKIE])
        with patch.object(cloud_auth, "_deliver_invitation") as deliver:
            result = visitor.post(
                "/api/cloud-auth/invitation-request",
                json={"email": "forged@example.org"},
                headers={"Origin": ORIGIN},
            )
        self.assertEqual(result.status_code, 200)
        deliver.assert_called_once()
        self.assertEqual(deliver.call_args.args[0], "visitor@example.org")
        self.assertGreater(deliver.call_args.args[1], 0)
        self.assertEqual(visitor.get("/api/cloud-auth/admin/invitation-requests").status_code, 401)
        requests = self.client.get("/api/cloud-auth/admin/invitation-requests")
        self.assertEqual(requests.status_code, 200)
        row = requests.json()["requests"][0]
        self.assertEqual(row["email"], "visitor@example.org")
        self.assertEqual(row["status"], "notified")
        authorized = self.client.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "email", "value": "Visitor@Example.org", "role": "member"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(authorized.status_code, 200)
        self.assertEqual(
            self.client.get("/api/cloud-auth/admin/invitation-requests").json()["requests"], []
        )
        revoked = self.client.delete(
            "/api/cloud-auth/admin/grants/email/visitor%40example.org",
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(revoked.status_code, 200)
        row = self.client.get("/api/cloud-auth/admin/invitation-requests").json()["requests"][0]
        updated = self.client.put(
            f"/api/cloud-auth/admin/invitation-requests/{row['subject']}",
            json={"status": "reviewed"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["status"], "reviewed")
        self.assertEqual(
            self.client.get("/api/cloud-auth/admin/invitation-requests").json()["requests"], []
        )
        # A reviewed request is closed. Since the grant was subsequently
        # revoked, this uninvited identity can submit a fresh request; that
        # fresh request is then deduplicated while it is open.
        with patch.object(cloud_auth, "_deliver_invitation") as redeliver:
            resubmitted = visitor.post(
                "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
            )
            self.assertEqual(resubmitted.status_code, 200, resubmitted.text)
            self.assertEqual(resubmitted.json(), {"status": "notified", "duplicate": False})
            requests = self.client.get("/api/cloud-auth/admin/invitation-requests").json()[
                "requests"
            ]
            self.assertEqual(len(requests), 1)
            self.assertEqual(requests[0]["email"], "visitor@example.org")
            self.assertEqual(requests[0]["status"], "notified")
            self.assertTrue(
                visitor.post(
                    "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
                ).json()["duplicate"]
            )
            redeliver.assert_called_once()
        self.assertEqual(deliver.call_count, 1)

    def test_invited_user_welcome_is_persisted_once_and_scoped_to_identity(self):
        admin_login = self.finish(email="admin@example.org", subject="welcome-admin")
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, admin_login.cookies[cloud_auth.SESSION_COOKIE]
        )
        initial_admin = self.client.get("/api/cloud-auth/status").json()
        self.assertFalse(initial_admin["account"]["invitation_welcome_pending"])
        grant = self.client.post(
            "/api/cloud-auth/admin/grants",
            headers={"Origin": ORIGIN},
            json={
                "kind": "email",
                "value": "welcome-member@example.org",
                "role": "member",
                "allowance_usd": 0.75,
            },
        )
        self.assertEqual(grant.status_code, 200, grant.text)

        member_login = self.finish(email="welcome-member@example.org", subject="welcome-member")
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, member_login.cookies[cloud_auth.SESSION_COOKIE]
        )
        invited = self.client.get("/api/cloud-auth/status").json()
        self.assertTrue(invited["account"]["invitation_welcome_pending"])

        cross_origin = self.client.post(
            "/api/cloud-auth/welcome", headers={"Origin": "https://other.test"}
        )
        self.assertEqual(cross_origin.status_code, 403)
        dismissed = self.client.post("/api/cloud-auth/welcome", headers={"Origin": ORIGIN})
        self.assertEqual(dismissed.status_code, 200, dismissed.text)
        self.assertEqual(dismissed.json(), {"dismissed": True})
        self.assertFalse(
            self.client.get("/api/cloud-auth/status").json()["account"][
                "invitation_welcome_pending"
            ]
        )

        # A new verified callback and subsequent reload do not repeat a dismissed welcome.
        repeated_login = self.finish(email="welcome-member@example.org", subject="welcome-member")
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, repeated_login.cookies[cloud_auth.SESSION_COOKIE]
        )
        self.assertFalse(
            self.client.get("/api/cloud-auth/status").json()["account"][
                "invitation_welcome_pending"
            ]
        )

        self.client.cookies.clear()
        guest_attempt = self.client.post("/api/cloud-auth/welcome", headers={"Origin": ORIGIN})
        self.assertEqual(guest_attempt.status_code, 401)

    def test_invitation_welcome_schema_migrates_existing_user_state(self):
        path = self.root / "legacy-auth.sqlite3"
        db = sqlite3.connect(path)
        try:
            db.execute(
                """CREATE TABLE user_state (
                    subject TEXT PRIMARY KEY, email TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('member','admin')),
                    access_active INTEGER NOT NULL CHECK(access_active IN (0,1)),
                    workspace_id TEXT,
                    sponsorship_eligible INTEGER NOT NULL CHECK(sponsorship_eligible IN (0,1)),
                    model_access TEXT NOT NULL CHECK(model_access IN ('personal','sponsored')),
                    model_connection_status TEXT NOT NULL DEFAULT 'checking',
                    updated_at INTEGER NOT NULL
                )"""
            )
            db.execute(
                "INSERT INTO user_state VALUES('legacy-subject','legacy@example.org','member',1,NULL,0,'personal','checking',123)"
            )
            db.commit()
        finally:
            db.close()
        path.chmod(0o600)
        cloud_auth._initialize(path)
        db = sqlite3.connect(path)
        try:
            columns = {row[1] for row in db.execute("PRAGMA table_info(user_state)")}
            self.assertIn("invitation_welcome_pending", columns)
            self.assertIn("model_access_explicit", columns)
            pending = db.execute(
                "SELECT invitation_welcome_pending FROM user_state WHERE subject='legacy-subject'"
            ).fetchone()[0]
            explicit = db.execute(
                "SELECT model_access_explicit FROM user_state WHERE subject='legacy-subject'"
            ).fetchone()[0]
        finally:
            db.close()
        self.assertEqual(pending, 0)
        self.assertEqual(explicit, 0)

    def test_invitation_request_succeeds_when_notification_delivery_fails(self):
        denied = self.finish(email="visitor@example.org", subject="request-retry")
        self.client.cookies.set(cloud_auth.DENIED_COOKIE, denied.cookies[cloud_auth.DENIED_COOKIE])
        with patch.object(
            cloud_auth, "_deliver_invitation", side_effect=RuntimeError("not configured")
        ):
            accepted = self.client.post(
                "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
            )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json(), {"status": "pending", "duplicate": False})
        with cloud_auth._db(cloud_auth.config()) as db:
            saved = db.execute(
                "SELECT status,notification_error FROM invitation_requests WHERE subject='request-retry'"
            ).fetchone()
        self.assertEqual(saved["status"], "pending")
        self.assertEqual(saved["notification_error"], "delivery failed")
        self.assertEqual(denied.headers["location"], "/?access=denied")

    def test_invitation_notification_uses_verified_admins_not_fixed_recipient(self):
        self.finish(email="admin@example.org", subject="verified-notification-admin")
        with (
            patch.dict(
                os.environ,
                {
                    "SIGMA_INVITATION_SMTP_USERNAME": "sigma-notify@example.org",
                    "SIGMA_INVITATION_SMTP_PASSWORD": "fixture-app-password",
                },
            ),
            patch.object(cloud_auth.smtplib, "SMTP") as smtp_factory,
        ):
            client = smtp_factory.return_value.__enter__.return_value
            cloud_auth._deliver_invitation("verified@example.org", 123)
        smtp_factory.assert_called_once_with("smtp.gmail.com", 587, timeout=10)
        client.starttls.assert_called_once()
        client.login.assert_called_once_with("sigma-notify@example.org", "fixture-app-password")
        message = client.send_message.call_args.args[0]
        self.assertEqual(message["From"], "sigma-notify@example.org")
        self.assertEqual(message["To"], "sigma-notify@example.org")
        self.assertEqual(message["Bcc"], "admin@example.org")
        self.assertEqual(client.send_message.call_args.kwargs["to_addrs"], ["admin@example.org"])

    def test_notification_recipient_set_tracks_verified_admin_grants_and_revocation(self):
        self.finish(email="admin@example.org", subject="notice-bootstrap")
        with cloud_auth._db(cloud_auth.config()) as db:
            db.execute(
                "INSERT INTO grants(kind,value,role,active,updated_at) VALUES('email',?,'admin',1,?)",
                ("second@example.org", cloud_auth._now()),
            )
        self.finish(email="second@example.org", subject="notice-second")
        with cloud_auth._db(cloud_auth.config()) as db:
            db.execute(
                "INSERT INTO grants(kind,value,role,active,updated_at) VALUES('email',?,'admin',1,?)",
                ("not-verified@example.org", cloud_auth._now()),
            )
        cfg = cloud_auth.config()
        self.assertEqual(
            cloud_auth._notification_admin_recipients(cfg),
            ["admin@example.org", "not-verified@example.org", "second@example.org"],
        )
        with (
            patch.dict(
                os.environ,
                {
                    "SIGMA_INVITATION_SMTP_USERNAME": "sigma-notify@example.org",
                    "SIGMA_INVITATION_SMTP_PASSWORD": "fixture-app-password",
                },
            ),
            patch.object(cloud_auth.smtplib, "SMTP") as smtp_factory,
        ):
            cloud_auth._deliver_invitation("applicant@example.org", 123)
        client = smtp_factory.return_value.__enter__.return_value
        sent = client.send_message.call_args
        self.assertEqual(sent.args[0]["To"], "sigma-notify@example.org")
        self.assertEqual(
            sent.args[0]["Bcc"],
            "admin@example.org, not-verified@example.org, second@example.org",
        )
        self.assertEqual(
            sent.kwargs["to_addrs"],
            ["admin@example.org", "not-verified@example.org", "second@example.org"],
        )
        with cloud_auth._db(cfg) as db:
            db.execute(
                "UPDATE grants SET active=0 WHERE kind='email' AND value=?",
                ("second@example.org",),
            )
        self.assertEqual(
            cloud_auth._notification_admin_recipients(cfg),
            ["admin@example.org", "not-verified@example.org"],
        )

    def test_feedback_delivery_failure_does_not_lose_saved_submission(self):
        self.finish(email="admin@example.org", subject="notice-feedback-admin")
        with patch.object(
            cloud_auth, "_deliver_feedback", side_effect=RuntimeError("mail unavailable")
        ) as send:
            received = self.client.post(
                "/api/cloud-auth/feedback",
                json={"message": "Please make the Session controls more visible."},
                headers={"Origin": ORIGIN},
            )
        self.assertEqual(received.status_code, 200, received.text)
        self.assertEqual(received.json()["status"], "received")
        send.assert_called_once()
        with cloud_auth._db(cloud_auth.config()) as db:
            row = db.execute(
                "SELECT message,notification_error,status FROM feedback_requests WHERE id=?",
                (received.json()["id"],),
            ).fetchone()
        self.assertIn("Session controls", row["message"])
        self.assertEqual(row["notification_error"], "delivery failed")
        self.assertEqual(row["status"], "new")

    def test_invitation_requests_are_rate_limited_per_verified_email(self):
        with patch.object(cloud_auth, "_deliver_invitation"):
            for index in range(4):
                denied = self.finish(email="visitor@example.org", subject=f"request-limit-{index}")
                self.client.cookies.set(
                    cloud_auth.DENIED_COOKIE, denied.cookies[cloud_auth.DENIED_COOKIE]
                )
                response = self.client.post(
                    "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
                )
                self.assertEqual(response.status_code, 429 if index == 3 else 200)

    def test_simultaneous_invitation_submission_does_not_send_duplicate_mail(self):
        denied = self.finish(email="visitor@example.org", subject="request-concurrent")
        raw_cookie = denied.cookies[cloud_auth.DENIED_COOKIE]
        self.client.cookies.set(cloud_auth.DENIED_COOKIE, raw_cookie)
        with cloud_auth._db(cloud_auth.config()) as db:
            subject = db.execute(
                "SELECT subject FROM denied_access WHERE token_hash=?",
                (cloud_auth._hash(raw_cookie),),
            ).fetchone()["subject"]
            db.execute(
                "INSERT INTO invitation_requests(subject,email,requested_at,status,notification_started_at) VALUES(?,?,?,'sending',?)",
                (subject, "visitor@example.org", int(time.time()), int(time.time())),
            )
        with patch.object(cloud_auth, "_deliver_invitation") as deliver:
            response = self.client.post(
                "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
            )
        self.assertEqual(response.status_code, 409)
        deliver.assert_not_called()

    def test_feedback_persists_optional_contact_and_verified_account_for_admin_review(self):
        response = self.finish(email="admin@example.org", subject="feedback-admin")
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, response.cookies[cloud_auth.SESSION_COOKIE]
        )
        visitor_context = TestClient(app)
        visitor = visitor_context.__enter__()
        self.addCleanup(visitor_context.__exit__, None, None, None)
        submitted = visitor.post(
            "/api/cloud-auth/feedback",
            json={
                "message": "Please make the saved session list easier to scan.",
                "contact_email": " Visitor@Example.org ",
                "subject": "forged-subject",
                "account_email": "forged@example.org",
            },
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(submitted.status_code, 422)
        accepted = visitor.post(
            "/api/cloud-auth/feedback",
            json={
                "message": "Please make the saved session list easier to scan.",
                "contact_email": " Visitor@Example.org ",
            },
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["status"], "received")
        cookie = accepted.cookies[cloud_auth.FEEDBACK_RATE_COOKIE]
        self.assertIn("HttpOnly", accepted.headers["set-cookie"])
        self.assertIn("Secure", accepted.headers["set-cookie"])
        self.assertIn("SameSite=lax", accepted.headers["set-cookie"])
        with cloud_auth._db(cloud_auth.config()) as db:
            stored = db.execute(
                "SELECT * FROM feedback_requests WHERE id=?", (accepted.json()["id"],)
            ).fetchone()
            rate_row = db.execute("SELECT key_hash FROM feedback_rate_limits").fetchone()
        self.assertEqual(stored["contact_email"], "visitor@example.org")
        self.assertIsNone(stored["subject"])
        self.assertIsNone(stored["account_email"])
        self.assertNotEqual(rate_row["key_hash"], cookie)
        self.assertEqual(visitor.get("/api/cloud-auth/admin/feedback").status_code, 401)
        inbox = self.client.get("/api/cloud-auth/admin/feedback")
        self.assertEqual(inbox.status_code, 200)
        row = inbox.json()["feedback"][0]
        self.assertEqual(row["id"], accepted.json()["id"])
        self.assertEqual(row["contact_email"], "visitor@example.org")
        self.assertIsNone(row["account_email"])
        updated = self.client.put(
            f"/api/cloud-auth/admin/feedback/{row['id']}",
            json={"status": "reviewed"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(updated.status_code, 200)
        removed = self.client.delete(
            f"/api/cloud-auth/admin/feedback/{row['id']}", headers={"Origin": ORIGIN}
        )
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(removed.json(), {"removed": True})
        self.assertEqual(self.client.get("/api/cloud-auth/admin/feedback").json()["feedback"], [])
        with cloud_auth._db(cloud_auth.config()) as db:
            audit = db.execute(
                "SELECT actor,action,kind,value FROM audit WHERE action='feedback_removed'"
            ).fetchone()
        self.assertEqual(
            tuple(audit),
            ("admin@example.org", "feedback_removed", "feedback", row["id"]),
        )
        self.assertEqual(
            visitor.put(
                f"/api/cloud-auth/admin/feedback/{row['id']}",
                json={"status": "closed"},
                headers={"Origin": ORIGIN},
            ).status_code,
            401,
        )
        self.assertEqual(
            visitor.delete(
                f"/api/cloud-auth/admin/feedback/{row['id']}", headers={"Origin": ORIGIN}
            ).status_code,
            401,
        )

    def test_signed_in_feedback_uses_google_identity_as_contact(self):
        response = self.finish(email="admin@example.org", subject="feedback-contact")
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, response.cookies[cloud_auth.SESSION_COOKIE]
        )
        with patch.object(cloud_auth, "_deliver_feedback") as delivered:
            sent = self.client.post(
                "/api/cloud-auth/feedback",
                json={
                    "message": "Please update the project guide.",
                    "contact_email": "different@example.org",
                },
                headers={"Origin": ORIGIN},
            )
        self.assertEqual(sent.status_code, 200)
        with cloud_auth._db(cloud_auth.config()) as db:
            stored = db.execute(
                "SELECT subject,account_email,contact_email FROM feedback_requests WHERE id=?",
                (sent.json()["id"],),
            ).fetchone()
        self.assertEqual(stored["subject"], "feedback-contact")
        self.assertEqual(stored["account_email"], "admin@example.org")
        self.assertEqual(stored["contact_email"], "admin@example.org")
        self.assertEqual(delivered.call_args.kwargs["contact_email"], "admin@example.org")

    def test_feedback_records_only_verified_session_identity_and_rate_limits(self):
        signed_in = self.finish(email="admin@example.org", subject="feedback-member")
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_in.cookies[cloud_auth.SESSION_COOKIE]
        )
        for index in range(6):
            response = self.client.post(
                "/api/cloud-auth/feedback",
                json={"message": f"Feedback message {index} with enough characters."},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(response.status_code, 429 if index == 5 else 200)
        with cloud_auth._db(cloud_auth.config()) as db:
            rows = db.execute("SELECT subject,account_email FROM feedback_requests").fetchall()
            buckets = db.execute("SELECT COUNT(*) AS n FROM feedback_rate_limits").fetchone()["n"]
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row["subject"] == "feedback-member" for row in rows))
        self.assertTrue(all(row["account_email"] == "admin@example.org" for row in rows))
        self.assertEqual(buckets, 1)

    def test_feedback_validates_fields_and_requires_same_origin(self):
        for payload in (
            {"message": "short"},
            {"message": "A message with enough characters.", "contact_email": "bad-email"},
            {"message": "A message with enough characters.", "identity": "admin@example.org"},
        ):
            response = self.client.post(
                "/api/cloud-auth/feedback", json=payload, headers={"Origin": ORIGIN}
            )
            self.assertEqual(response.status_code, 422)
        self.assertEqual(
            self.client.post(
                "/api/cloud-auth/feedback",
                json={"message": "A message with enough characters."},
                headers={"Origin": "https://attacker.example"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/cloud-auth/feedback", json={"message": "A message with enough characters."}
            ).status_code,
            403,
        )
        self.assertEqual(self.client.get("/api/cloud-auth/admin/feedback").status_code, 401)

    def test_non_admin_cannot_review_or_read_feedback(self):
        signed_in = self.finish(email="admin@example.org", subject="feedback-review-admin")
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_in.cookies[cloud_auth.SESSION_COOKIE]
        )
        grant = self.client.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "email", "value": "member@example.org", "role": "member"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(grant.status_code, 200)
        member_context = TestClient(app)
        member = member_context.__enter__()
        self.addCleanup(member_context.__exit__, None, None, None)
        member_login = self.finish(
            email="member@example.org", subject="feedback-review-member", client=member
        )
        member.cookies.set(
            cloud_auth.SESSION_COOKIE, member_login.cookies[cloud_auth.SESSION_COOKIE]
        )
        submitted = member.post(
            "/api/cloud-auth/feedback",
            json={"message": "Please clarify the recent projects panel."},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(submitted.status_code, 200)
        self.assertEqual(member.get("/api/cloud-auth/admin/feedback").status_code, 403)
        self.assertEqual(
            member.put(
                f"/api/cloud-auth/admin/feedback/{submitted.json()['id']}",
                json={"status": "closed"},
                headers={"Origin": ORIGIN},
            ).status_code,
            403,
        )
        self.assertEqual(
            member.delete(
                f"/api/cloud-auth/admin/feedback/{submitted.json()['id']}",
                headers={"Origin": ORIGIN},
            ).status_code,
            403,
        )

    def test_changing_contact_preserves_bound_admin_and_authorizes_new_contact(self):
        response = self.finish(email="admin@example.org", subject="preserved-admin-subject")
        self.assertIn(cloud_auth.SESSION_COOKIE, response.cookies)
        os.environ["SIGMA_CLOUD_ADMIN_CONTACT_EMAIL"] = "sponsor@example.test"

        admin_client_context = TestClient(app)
        admin_client = admin_client_context.__enter__()
        self.addCleanup(admin_client_context.__exit__, None, None, None)
        admin_client.cookies.set(
            cloud_auth.SESSION_COOKIE, response.cookies[cloud_auth.SESSION_COOKIE]
        )
        status = admin_client.get("/api/cloud-auth/status").json()
        self.assertEqual(status["admin_contact_email"], "sponsor@example.test")
        self.assertEqual(status["user"], {"email": "admin@example.org", "role": "admin"})
        self.assertEqual(
            admin_client.get("/api/cloud-auth/admin/grants").json()["bootstrap_admin"],
            "admin@example.org",
        )

        denied_context = TestClient(app)
        denied_client = denied_context.__enter__()
        self.addCleanup(denied_context.__exit__, None, None, None)
        denied = self.finish(
            email="sponsor@example.test", subject="new-contact-subject", client=denied_client
        )
        self.assertNotEqual(denied.headers["location"], "/?access=denied")
        self.assertIn(cloud_auth.SESSION_COOKIE, denied.cookies)
        denied_client.cookies.set(
            cloud_auth.SESSION_COOKIE, denied.cookies[cloud_auth.SESSION_COOKIE]
        )
        status = denied_client.get("/api/cloud-auth/status").json()
        self.assertEqual(status["user"]["role"], "admin")
        self.assertFalse(status["account"]["invitation_welcome_pending"])
        # The contact email remains pinned to its verified Google subject.
        other_context = TestClient(app)
        other = other_context.__enter__()
        self.addCleanup(other_context.__exit__, None, None, None)
        mismatched = self.finish(
            email="sponsor@example.test", subject="different-google-subject", client=other
        )
        self.assertEqual(mismatched.headers["location"], "/?access=denied")

    def test_local_google_chosen_configured_admin_is_signed_in_without_invitation(self):
        # Reproduce a local development instance whose first bootstrap admin was
        # previously bound to a different Google account. Selecting the now
        # configured admin in Google's standard chooser must grant access.
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://127.0.0.1:5173",
            },
        ):
            first = self.finish(email="admin@example.org", subject="initial-google-subject")
            self.assertIn("sigma_session", first.cookies)
            self.client.cookies.clear()
            initially_uninvited = self.finish(
                email="sponsor@example.test", subject="configured-google-subject"
            )
            self.assertEqual(initially_uninvited.headers["location"], "/")
            self.assertIn("sigma_session", initially_uninvited.cookies)
            self.client.cookies.set("sigma_session", initially_uninvited.cookies["sigma_session"])
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["user"]["role"], "guest"
            )
            os.environ["SIGMA_CLOUD_ADMIN_CONTACT_EMAIL"] = "sponsor@example.test"
            # The verified identity becomes an administrator as soon as the
            # configured contact changes; guest status does not pin its role.
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["user"]["role"], "admin"
            )
            self.assertEqual(
                self.client.post(
                    "/api/cloud-auth/invitation-request",
                    json={},
                    headers={"Origin": "http://127.0.0.1:5173"},
                ).status_code,
                401,
            )
            # A fresh chooser flow continues to complete normally.
            allowed = self.finish(email="sponsor@example.test", subject="configured-google-subject")
            self.assertEqual(allowed.status_code, 303)
            self.assertEqual(allowed.headers["location"], "/")
            self.assertIn("sigma_session", allowed.cookies)
            self.assertIn('sigma_denied="";', allowed.headers["set-cookie"])
            self.client.cookies.set("sigma_session", allowed.cookies["sigma_session"])
            account = self.client.get("/api/cloud-auth/status").json()
            self.assertTrue(account["authenticated"])
            self.assertEqual(account["user"], {"email": "sponsor@example.test", "role": "admin"})
            self.assertFalse(account["account"]["invitation_welcome_pending"])
            self.assertEqual(account["admin_contact_email"], "sponsor@example.test")
            self.assertEqual(self.client.get("/api/cloud-auth/admin/grants").status_code, 200)

    def test_local_uninvited_google_user_requests_invitation_and_becomes_member(self):
        local_origin = "http://127.0.0.1:5173"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.org",
            },
        ):
            admin_login = self.finish(email="admin@example.org", subject="onboard-admin")
            self.client.cookies.set("sigma_session", admin_login.cookies["sigma_session"])
            guest_context = TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 12346)
            )
            guest = guest_context.__enter__()
            self.addCleanup(guest_context.__exit__, None, None, None)
            signed_in = self.finish(
                email="new-member@example.org", subject="onboard-member", client=guest
            )
            self.assertEqual(signed_in.status_code, 303)
            self.assertEqual(signed_in.headers["location"], "/")
            guest.cookies.set("sigma_session", signed_in.cookies["sigma_session"])
            status = guest.get("/api/cloud-auth/status").json()
            self.assertTrue(status["authenticated"])
            self.assertEqual(status["user"], {"email": "new-member@example.org", "role": "guest"})
            self.assertEqual(status["account"]["access"]["status"], "uninvited")
            self.assertFalse(status["account"]["sponsorship"]["eligible"])
            self.assertEqual(guest.get("/api/projects/recent").status_code, 200)
            self.assertEqual(
                guest.post(
                    "/api/projects/research-sessions/start",
                    headers={"Origin": local_origin},
                    json={},
                ).status_code,
                403,
            )
            with patch.object(cloud_auth, "_deliver_invitation") as deliver:
                requested = guest.post(
                    "/api/cloud-auth/invitation-request", headers={"Origin": local_origin}
                )
                self.assertEqual(requested.status_code, 200, requested.text)
                self.assertEqual(requested.json()["status"], "notified")
                self.assertTrue(
                    guest.post(
                        "/api/cloud-auth/invitation-request", headers={"Origin": local_origin}
                    ).json()["duplicate"]
                )
                deliver.assert_called_once()
            admin_restart = TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 12347)
            )
            self.addCleanup(admin_restart.close)
            admin_restart.cookies.set("sigma_session", admin_login.cookies["sigma_session"])
            queue = admin_restart.get("/api/cloud-auth/admin/invitation-requests").json()[
                "requests"
            ]
            self.assertEqual(queue[0]["email"], "new-member@example.org")
            approved = admin_restart.post(
                "/api/cloud-auth/admin/grants",
                json={
                    "kind": "email",
                    "value": "new-member@example.org",
                    "role": "member",
                    "allowance_usd": 0.75,
                },
                headers={"Origin": local_origin},
            )
            self.assertEqual(approved.status_code, 200, approved.text)
            # The existing guest session becomes an authorized member without
            # another OAuth callback. Its first member status read must still
            # queue the one-time welcome dialog.
            promoted = guest.get("/api/cloud-auth/status").json()
            self.assertEqual(
                promoted["user"], {"email": "new-member@example.org", "role": "member"}
            )
            self.assertTrue(promoted["account"]["invitation_welcome_pending"])
            dismissed = guest.post("/api/cloud-auth/welcome", headers={"Origin": local_origin})
            self.assertEqual(dismissed.status_code, 200, dismissed.text)
            signed_in_again = self.finish(
                email="new-member@example.org", subject="onboard-member", client=guest
            )
            self.assertEqual(signed_in_again.status_code, 303)
            guest.cookies.set("sigma_session", signed_in_again.cookies["sigma_session"])
            member = guest.get("/api/cloud-auth/status").json()
            self.assertEqual(member["user"]["role"], "member")
            self.assertFalse(member["account"]["invitation_welcome_pending"])
            self.assertTrue(member["account"]["sponsorship"]["eligible"])
            self.assertIsNone(member["account"].get("invitation_status"))
            allowance = guest.get("/api/cloud-auth/local-sponsored-allowance")
            self.assertEqual(allowance.status_code, 200, allowance.text)
            self.assertEqual(allowance.json()["allowance_usd"], 0.75)

    def test_guest_project_api_allowlist_denies_every_other_registered_operation(self):
        local_origin = "http://127.0.0.1:5173"
        projects_root = Path(self.temp.name) / "projects"
        workspaces_root = Path(self.temp.name) / "workspaces"
        projects_root.mkdir()
        workspaces_root.mkdir()
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.org",
                "SIGMA_PROJECTS_ROOT": str(projects_root),
                "SIGMA_CLOUD_WORKSPACES_ROOT": str(workspaces_root),
            },
        ):
            admin_login = self.finish(email="admin@example.org", subject="route-admin")
            self.client.cookies.set("sigma_session", admin_login.cookies["sigma_session"])
            member_project = self.client.post(
                "/api/projects/create",
                json={
                    "title": f"Private route audit project {time.time_ns()}",
                    "problem": "A private member project used to check guest scoping.",
                    "research_mode": "default",
                },
                headers={"Origin": local_origin},
            )
            self.assertEqual(member_project.status_code, 201, member_project.text)
            member_path = member_project.json()["path"]
            member_project_before = self.client.get(
                "/api/projects/inspect", params={"path": member_path}
            ).json()

            guest_context = TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 12348)
            )
            guest = guest_context.__enter__()
            self.addCleanup(guest_context.__exit__, None, None, None)
            guest_login = self.finish(
                email="route-guest@example.org", subject="route-guest", client=guest
            )
            guest.cookies.set("sigma_session", guest_login.cookies["sigma_session"])
            catalog = guest.get("/api/projects/samples")
            self.assertEqual(catalog.status_code, 200, catalog.text)
            sample_id = catalog.json()["projects"][0]["id"]
            copied = guest.post(
                "/api/projects/samples/open",
                json={"sample_id": sample_id},
                headers={"Origin": local_origin},
            )
            self.assertEqual(copied.status_code, 200, copied.text)
            guest_path = copied.json()["path"]
            self.assertEqual(
                guest.get("/api/projects/inspect", params={"path": guest_path}).status_code, 200
            )
            from sigma import cloud_workspaces, project_bundle

            guest_workspace = cloud_workspaces.guest_workspace(
                guest.cookies.get(
                    cloud_auth._cookie_name(cloud_auth.GUEST_COOKIE, cloud_auth.config())
                ),
                subject="route-guest",
            )
            self.assertIsNotNone(guest_workspace)
            assert guest_workspace is not None
            self.assertTrue(Path(guest_path).is_relative_to(guest_workspace.path))

            def write_project_member(relative: str, contents: bytes) -> None:
                project = Path(guest_path)
                if project.is_dir():
                    target = project / relative
                    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    target.write_bytes(contents)
                else:
                    project_bundle.write_file(guest_path, relative, contents)

            # Populate valid owner-scoped session/execution artifacts in the
            # guest's own project bundle so the allowlisted read handlers are
            # exercised successfully, not just inferred from the middleware.
            project_id = copied.json()["project"]["id"]
            session_id = str(uuid4())
            session = {
                "id": session_id,
                "project_path": str(Path(guest_path).resolve()),
                "project_id": project_id,
                "session_number": 1,
                "status": "ended",
                "message": "isolated fixture session",
                "steps": [],
            }
            write_project_member(
                f"research-sessions/{session_id}.json", json.dumps(session).encode()
            )
            execution_id = str(uuid4())
            artifact_bytes = b"guest-owned artifact"
            execution = {
                "id": execution_id,
                "project_id": project_id,
                "status": "completed",
                "created_at": cloud_auth._now(),
                "artifacts": [
                    {
                        "filename": "owned.txt",
                        "media_type": "text/plain",
                        "size_bytes": len(artifact_bytes),
                        "sha256": hashlib.sha256(artifact_bytes).hexdigest(),
                    }
                ],
            }
            write_project_member(
                f"research-executions/{execution_id}.json", json.dumps(execution).encode()
            )
            write_project_member(
                f"research-executions/{execution_id}.artifacts/owned.txt", artifact_bytes
            )
            project_read = guest.get("/api/projects/inspect", params={"path": guest_path})
            self.assertEqual(project_read.status_code, 200, project_read.text)
            session_read = guest.get(
                f"/api/projects/research-sessions/{session_id}", params={"path": guest_path}
            )
            self.assertEqual(session_read.status_code, 200, session_read.text)
            artifact_read = guest.get(
                f"/api/projects/research-executions/{execution_id}/artifacts/owned.txt",
                params={"path": guest_path},
            )
            self.assertEqual(artifact_read.status_code, 200, artifact_read.text)
            self.assertEqual(artifact_read.content, artifact_bytes)
            for response in (project_read, session_read, artifact_read):
                self.assertEqual(response.headers.get("cache-control"), "no-store")
                self.assertEqual(response.headers.get("referrer-policy"), "no-referrer")
                self.assertEqual(response.headers.get("x-content-type-options"), "nosniff")
                self.assertEqual(
                    response.headers.get("content-security-policy"), "frame-ancestors 'none'"
                )
            for route in (
                "events",
                "research-limits",
                "current-understanding",
                "research-sessions",
                "research-executions",
                "papers",
                "papers/preflight",
                "papers/progress",
                "proposals/config",
                "text",
                "recent",
            ):
                response = guest.get(
                    f"/api/projects/{route}",
                    params={"path": guest_path, "scope": "project"},
                )
                self.assertEqual(response.status_code, 200, (route, response.text))

            paper_id = uuid4().hex
            pdf_bytes = b"%PDF-1.4 guest fixture"
            paper_record = {
                "paper_id": paper_id,
                "project_id": project_id,
                "created_at": cloud_auth._now(),
                "snapshot_sha256": "0" * 64,
                "validation_warnings": [],
                "generation": {},
                "draft": {
                    "title": "Guest-owned paper",
                    "abstract": "Fixture abstract.",
                    "problem_framing": [],
                    "methods": [],
                    "sections": [],
                    "claims": [],
                    "limitations": [],
                    "open_obligations": [],
                    "conclusions": [],
                },
                "tex_source": r"\documentclass{article}",
                "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
                "pdf_size_bytes": len(pdf_bytes),
            }
            paper_prefix = "papers" if Path(guest_path).is_dir() else "artifacts/papers"
            write_project_member(
                f"{paper_prefix}/{paper_id}.json", json.dumps(paper_record).encode()
            )
            write_project_member(f"{paper_prefix}/{paper_id}.pdf", pdf_bytes)
            paper_reads = (
                guest.get("/api/projects/papers", params={"path": guest_path}),
                guest.get(f"/api/projects/papers/{paper_id}", params={"path": guest_path}),
                guest.get(f"/api/projects/papers/{paper_id}/pdf", params={"path": guest_path}),
                guest.get(f"/api/projects/papers/{paper_id}/txt", params={"path": guest_path}),
                guest.get(f"/api/projects/papers/{paper_id}/tex", params={"path": guest_path}),
            )
            self.assertTrue(
                all(response.status_code == 200 for response in paper_reads),
                [(response.status_code, response.text[:160]) for response in paper_reads],
            )
            self.assertEqual(paper_reads[2].content, pdf_bytes)
            self.assertIn("Guest-owned paper", paper_reads[3].text)
            self.assertIn(r"\documentclass{article}", paper_reads[4].text)
            self.assertTrue(
                all(response.headers.get("cache-control") == "no-store" for response in paper_reads)
            )
            self.assertEqual(
                guest.get("/api/projects/strategies", params={"path": guest_path}).status_code,
                200,
            )
            from sigma import research_sessions

            with patch.object(
                research_sessions,
                "ensure_queued_workers",
                side_effect=AssertionError("guest read attempted queued provider work"),
            ):
                sessions = guest.get("/api/projects/research-sessions", params={"path": guest_path})
            self.assertEqual(sessions.status_code, 200, sessions.text)
            with patch(
                "sigma.proposals.models",
                side_effect=AssertionError("guest config attempted provider discovery"),
            ):
                config = guest.get("/api/projects/proposals/config", params={"path": guest_path})
            self.assertEqual(config.status_code, 200, config.text)
            self.assertFalse(config.json()["available"])

            # Direct API requests to member-owned paths are scoped to the
            # guest workspace and return the same not-found response as absent
            # guest data. This avoids leaking whether member data exists.
            for route in (
                "inspect",
                "strategies",
                "events",
                "research-limits",
                "research-sessions",
                "current-understanding",
                "research-executions",
                "papers",
                "papers/preflight",
                "papers/progress",
            ):
                response = guest.get(f"/api/projects/{route}", params={"path": member_path})
                self.assertEqual(response.status_code, 404, (route, response.text))
            text_response = guest.get(
                "/api/projects/text", params={"path": member_path, "scope": "conclusions"}
            )
            self.assertEqual(text_response.status_code, 404, text_response.text)
            for route in (
                "research-sessions/audit-probe",
                "research-executions/audit-probe",
                "research-executions/audit-probe/artifacts/audit-probe",
                "papers/audit-probe",
                "papers/audit-probe/pdf",
                "papers/audit-probe/txt",
                "papers/audit-probe/tex",
            ):
                response = guest.get(f"/api/projects/{route}", params={"path": member_path})
                self.assertIn(response.status_code, {400, 404}, (route, response.text))
            self.assertEqual(
                guest.post(
                    "/api/projects/open",
                    json={"path": member_path},
                    headers={"Origin": local_origin},
                ).status_code,
                404,
            )
            self.assertEqual(
                guest.post(
                    "/api/projects/update",
                    json={"path": member_path, "title": "Overwritten"},
                    headers={"Origin": local_origin},
                ).status_code,
                403,
            )
            for route in (
                "/api/projects/audit",
                "/api/projects/export",
                "/api/projects/download",
                "/api/projects/export/report",
            ):
                self.assertEqual(
                    guest.get(route, params={"path": guest_path}).status_code,
                    403,
                    route,
                )
            member_project_after = self.client.get(
                "/api/projects/inspect", params={"path": member_path}
            ).json()
            self.assertEqual(member_project_after, member_project_before)

            # The route inventory is an enforcement test: future project
            # endpoints are denied unless their exact method/path is added to
            # the reviewed guest-safe allowlist.
            protected_count = 0
            allowed_routes = set()
            public_sample_routes = set()
            for route in app.routes:
                route_path = getattr(route, "path", "")
                if not route_path.startswith("/api/projects/"):
                    continue
                for method in getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}:
                    concrete_path = re.sub(r"\{[^}]+\}", "audit-probe", route_path)
                    if cloud_auth.public_sample_paper_path(method, concrete_path):
                        public_sample_routes.add((method, route_path))
                        continue
                    if cloud_auth._guest_project_route_allowed(method, concrete_path):
                        allowed_routes.add((method, route_path))
                        continue
                    response = guest.request(
                        method,
                        concrete_path,
                        params={"path": member_path},
                        json={} if method in {"POST", "PUT", "PATCH", "DELETE"} else None,
                        headers={"Origin": local_origin},
                    )
                    self.assertEqual(
                        response.status_code,
                        403,
                        (method, route_path, response.status_code, response.text),
                    )
                    protected_count += 1
            self.assertGreater(protected_count, 30)
            self.assertEqual(
                public_sample_routes,
                {("GET", "/api/projects/samples/{sample_id}/top-paper/pdf")},
            )
            expected_guest_routes = {
                ("GET", path)
                for path in cloud_auth._GUEST_PROJECT_READ_PATHS | {"/api/projects/samples"}
            } | {
                ("GET", "/api/projects/research-sessions/{session_id}"),
                ("GET", "/api/projects/research-executions/{execution_id}"),
                (
                    "GET",
                    "/api/projects/research-executions/{execution_id}/artifacts/{filename}",
                ),
                ("GET", "/api/projects/papers/{paper_id}"),
                ("GET", "/api/projects/papers/{paper_id}/pdf"),
                ("GET", "/api/projects/papers/{paper_id}/txt"),
                ("GET", "/api/projects/papers/{paper_id}/tex"),
                ("POST", "/api/projects/samples/open"),
                ("POST", "/api/projects/open"),
                ("POST", "/api/projects/close"),
            }
            self.assertEqual(allowed_routes, expected_guest_routes)
            self.assertEqual(
                guest.get("/api/cloud-auth/local-sponsored-allowance").status_code, 403
            )
            self.assertEqual(guest.get("/api/ai/connection").status_code, 403)
            for admin_route in (
                "/api/cloud-auth/admin/invitation-requests",
                "/api/cloud-auth/admin/grants",
                "/api/cloud-auth/admin/feedback",
            ):
                self.assertEqual(guest.get(admin_route).status_code, 403, admin_route)

    def test_local_admin_pill_request_routes_selected_sponsor_to_sponsor_oauth(self):
        from sigma import ai_store

        local_origin = "http://127.0.0.1:5173"
        sponsor_home = Path(self.temp.name) / "sponsor-auth"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "sponsor@example.test",
                "SIGMA_AUTH_HOME": str(sponsor_home),
            },
        ):
            os.environ["SIGMA_CLOUD_SPONSOR_EMAIL"] = "sponsor@example.test"
            login = self.finish(email="sponsor@example.test", subject="configured-google-admin")
            self.assertEqual(login.status_code, 303)
            self.client.cookies.update(login.cookies)
            status = self.client.get("/api/cloud-auth/status").json()
            self.assertEqual(status["user"]["role"], "admin")
            self.assertEqual(status["user"]["email"], "sponsor@example.test")
            self.assertEqual(status["account"]["model_access"]["mode"], "sponsored")

            # A pre-existing cookie whose legacy personal value was never
            # deliberately selected must still resolve to default sponsorship.
            with cloud_auth._db(cloud_auth.config()) as db:
                db.execute(
                    "UPDATE user_state SET model_access='personal',model_access_selected=0 "
                    "WHERE subject='configured-google-admin'"
                )
            status = self.client.get("/api/cloud-auth/status").json()
            self.assertEqual(status["account"]["model_access"]["mode"], "sponsored")

            self.seed_personal_plan_authorization("configured-google-admin")
            cloud_auth.set_model_access("configured-google-admin", "personal")
            status = self.client.get("/api/cloud-auth/status").json()
            self.assertEqual(status["account"]["model_access"]["mode"], "personal")

            async def add_selected_sponsor():
                async with ai_store.sponsor_transaction() as state:
                    state["accounts"]["selected-sponsor"] = {
                        "email": "sponsor@example.test",
                        "access_token": "existing-sponsor-token",
                    }
                    state["active"] = "selected-sponsor"

            import asyncio

            asyncio.run(add_selected_sponsor())
            with patch(
                "sigma.api.chatgpt_auth.begin",
                new=AsyncMock(return_value={"id": "sponsor-attempt"}),
            ) as begin:
                response = self.client.post(
                    "/api/ai/sponsor-auth/begin", json={}, headers={"Origin": local_origin}
                )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["id"], "sponsor-attempt")
            begin.assert_awaited_once_with(account_id="selected-sponsor", sponsor=True)

            grant = self.client.post(
                "/api/cloud-auth/admin/grants",
                json={
                    "kind": "email",
                    "value": "member@example.test",
                    "role": "member",
                    "allowance_usd": 1,
                },
                headers={"Origin": local_origin},
            )
            self.assertEqual(grant.status_code, 200, grant.text)
            member_context = TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 23457)
            )
            member = member_context.__enter__()
            self.addCleanup(member_context.__exit__, None, None, None)
            member_login = self.finish(
                email="member@example.test",
                subject="sponsor-change-denied-member",
                client=member,
            )
            self.assertEqual(member_login.status_code, 303)
            member.cookies.update(member_login.cookies)
            with patch(
                "sigma.api.chatgpt_auth.begin",
                new=AsyncMock(return_value={"id": "member-personal-attempt"}),
            ) as member_begin:
                personal = member.post(
                    "/api/ai/auth/begin", json={}, headers={"Origin": local_origin}
                )
                sponsor_route_denied = member.post(
                    "/api/ai/sponsor-auth/begin", json={}, headers={"Origin": local_origin}
                )
            self.assertEqual(personal.status_code, 200, personal.text)
            member_begin.assert_awaited_once_with(None, False, None)
            self.assertEqual(sponsor_route_denied.status_code, 403, sponsor_route_denied.text)

            async def saved_sponsor_token():
                async with ai_store.sponsor_transaction() as state:
                    return state["accounts"]["selected-sponsor"]["access_token"]

            self.assertEqual(asyncio.run(saved_sponsor_token()), "existing-sponsor-token")

    def test_local_admin_sponsored_mode_transition_uses_bounded_global_pilot(self):
        from sigma import ai_store, chatgpt_auth

        local_origin = "http://127.0.0.1:5173"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "sponsor@example.test",
                "SIGMA_AUTH_HOME": str(Path(self.temp.name) / "sponsor-auth"),
            },
        ):
            os.environ["SIGMA_CLOUD_SPONSOR_EMAIL"] = "sponsor@example.test"
            os.environ.pop("SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD", None)
            login = self.finish(email="sponsor@example.test", subject="mode-transition-admin")
            self.client.cookies.update(login.cookies)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )
            with patch(
                "sigma.api.chatgpt_auth.discovery",
                AsyncMock(
                    return_value={"authorization_endpoint": "https://auth.openai.com/authorize"}
                ),
            ):
                started = self.client.post(
                    "/api/ai/auth/begin", json={}, headers={"Origin": local_origin}
                )
                self.assertEqual(started.status_code, 200, started.text)
                cancelled = self.client.post(
                    f"/api/ai/auth/cancel/{started.json()['id']}",
                    json={},
                    headers={"Origin": local_origin},
                )
            self.assertEqual(cancelled.status_code, 200, cancelled.text)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )
            headers = {"Origin": local_origin}
            fabricated = self.client.post(
                "/api/ai/mode", json={"mode": "personal"}, headers=headers
            )
            self.assertEqual(fabricated.status_code, 403, fabricated.text)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )
            with cloud_auth._db(cloud_auth.config()) as db:
                db.execute(
                    "UPDATE user_state SET model_access='personal',model_access_selected=1 "
                    "WHERE subject='mode-transition-admin'"
                )
            legacy_selected = self.client.post(
                "/api/ai/mode", json={"mode": "personal"}, headers=headers
            )
            self.assertEqual(legacy_selected.status_code, 403, legacy_selected.text)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "personal",
                "legacy preference remains truthful without becoming authorization proof",
            )
            with cloud_auth._db(cloud_auth.config()) as db:
                db.execute(
                    "UPDATE user_state SET model_access='sponsored',model_access_selected=0 "
                    "WHERE subject='mode-transition-admin'"
                )
            self.seed_personal_plan_authorization(
                "mode-transition-admin", record_authorization=False
            )
            credential_path = (
                ai_store.personal_directory_for_subject("mode-transition-admin")
                / "credentials.json"
            )
            credential_state = ai_store.read(credential_path)
            credential = credential_state["accounts"]["fixture-personal"]
            credential["scopes"] = ["resource.invoke"]
            credential["plan_authorized"] = False
            ai_store.write(credential_path, credential_state)
            missing_plan_scope = self.client.post(
                "/api/ai/mode", json={"mode": "personal"}, headers=headers
            )
            self.assertEqual(missing_plan_scope.status_code, 403, missing_plan_scope.text)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )
            credential["scopes"] = list(chatgpt_auth.PLAN_SCOPES)
            credential["plan_authorized"] = True
            ai_store.write(credential_path, credential_state)
            cloud_auth.record_personal_authorization("mode-transition-admin")
            switched_personal = self.client.post(
                "/api/ai/mode", json={"mode": "personal"}, headers=headers
            )
            self.assertEqual(switched_personal.status_code, 200, switched_personal.text)

            from sigma import cloud_research

            # Funding mode selection remains possible even when allowance
            # inspection is unavailable; Play admission checks the ledger.
            with patch.object(
                cloud_research,
                "snapshot",
                side_effect=cloud_research.CloudResearchUnavailable("fixture ledger unavailable"),
            ) as snapshot:
                selected = self.client.post(
                    "/api/ai/mode",
                    json={"mode": "sponsored"},
                    headers={"Origin": local_origin},
                )
            self.assertEqual(selected.status_code, 200, selected.text)
            snapshot.assert_not_called()
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )

            selected = self.client.post(
                "/api/ai/mode",
                json={"mode": "sponsored"},
                headers={"Origin": local_origin},
            )
            self.assertEqual(selected.status_code, 200, selected.text)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )
            budget = self.client.get("/api/cloud-auth/local-sponsored-allowance")
            self.assertEqual(budget.status_code, 200, budget.text)
            self.assertEqual(budget.json()["global_ceiling_usd"], 50.0)
            self.assertEqual(budget.json()["global_spend_period"], "calendar_month")

    def test_local_admin_connection_reports_validated_sponsor_identity(self):
        import asyncio
        import time

        from sigma import ai_store, chatgpt_auth, openai_connection

        local_origin = "http://127.0.0.1:5173"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "sponsor@example.test",
                "SIGMA_AUTH_HOME": str(Path(self.temp.name) / "sponsor-auth"),
            },
        ):
            os.environ["SIGMA_CLOUD_SPONSOR_EMAIL"] = "sponsor@example.test"
            login = self.finish(email="sponsor@example.test", subject="connection-identity-admin")
            self.client.cookies.update(login.cookies)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )

            async def persist_oauth_credentials():
                async with ai_store.sponsor_transaction() as state:
                    state["accounts"]["completed-oauth"] = {
                        "client_id": "fixture-oauth-client",
                        "email": "sponsor@example.test",
                        "access_token": "validated-sponsor-access-token",
                        "refresh_token": "validated-sponsor-refresh-token",
                        "expires_at": time.time() + 3600,
                        "scopes": list(chatgpt_auth.PLAN_SCOPES),
                    }
                    state["active"] = "completed-oauth"

            asyncio.run(persist_oauth_credentials())

            async def validated_catalog(*_args, **_kwargs):
                result = {
                    "status": "connected",
                    "checked_at": "2026-10-28T00:00:00Z",
                    "ttl_seconds": 60,
                }
                return result

            with patch.object(
                openai_connection, "_check", AsyncMock(side_effect=validated_catalog)
            ):
                response = self.client.get("/api/ai/connection?refresh=true")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["status"], "connected")
            self.assertEqual(response.json()["account_label"], "sponsor@example.test")
            self.assertNotIn("validated-sponsor-access-token", response.text)
            self.assertNotIn("validated-sponsor-refresh-token", response.text)

            grant = self.client.post(
                "/api/cloud-auth/admin/grants",
                json={
                    "kind": "email",
                    "value": "member@example.test",
                    "role": "member",
                    "allowance_usd": 1,
                },
                headers={"Origin": local_origin},
            )
            self.assertEqual(grant.status_code, 200, grant.text)
            member_context = TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 23458)
            )
            member = member_context.__enter__()
            self.addCleanup(member_context.__exit__, None, None, None)
            member_login = self.finish(
                email="member@example.test",
                subject="sponsor-identity-hidden-member",
                client=member,
            )
            self.assertEqual(member_login.status_code, 303)
            member.cookies.update(member_login.cookies)
            self.assertEqual(
                member.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )
            with patch.object(
                openai_connection, "_check", AsyncMock(side_effect=validated_catalog)
            ):
                member_response = member.get("/api/ai/connection?refresh=true")
                mode_response = member.post(
                    "/api/ai/mode",
                    json={"mode": "sponsored"},
                    headers={"Origin": local_origin},
                )
            self.assertEqual(member_response.status_code, 200, member_response.text)
            self.assertEqual(member_response.json()["status"], "connected")
            self.assertNotIn("account_label", member_response.json())
            self.assertNotIn("sponsor@example.test", member_response.text)
            self.assertEqual(mode_response.status_code, 200, mode_response.text)
            self.assertNotIn("sponsor@example.test", mode_response.text)

    def test_personal_disconnect_cannot_cancel_other_users_or_sponsor_oauth_attempts(self):
        from sigma import chatgpt_auth

        local_origin = "http://127.0.0.1:5173"
        b_client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 23461))
        self.addCleanup(b_client.close)
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "sponsor@example.test",
                "SIGMA_CLOUD_AUTH_HOME": str(Path(self.temp.name) / "auth-db"),
                "SIGMA_AUTH_HOME": str(Path(self.temp.name) / "auth-home"),
            },
        ):
            os.environ["SIGMA_CLOUD_SPONSOR_EMAIL"] = "sponsor@example.test"
            with cloud_auth._db(cloud_auth.config()) as db:
                db.execute(
                    "INSERT INTO grants(kind,value,role,active,updated_at) VALUES('email',?,'admin',1,?)",
                    ("personal@example.test", cloud_auth._now()),
                )
            z_login = self.finish(email="sponsor@example.test", subject="attempt-owner-z")
            b_login = self.finish(
                email="personal@example.test",
                subject="attempt-owner-b",
                client=b_client,
            )
            self.assertEqual(z_login.status_code, 303)
            self.assertEqual(b_login.status_code, 303)
            self.client.cookies.update(z_login.cookies)
            b_client.cookies.update(b_login.cookies)
            headers = {"Origin": local_origin}
            endpoint = "https://auth.openai.com/authorize"
            with patch.object(
                chatgpt_auth,
                "discovery",
                AsyncMock(return_value={"authorization_endpoint": endpoint}),
            ):
                z_personal = self.client.post("/api/ai/auth/begin", json={}, headers=headers)
                self.assertEqual(z_personal.status_code, 200, z_personal.text)
                z_sponsor = self.client.post("/api/ai/sponsor-auth/begin", json={}, headers=headers)
                self.assertEqual(z_sponsor.status_code, 200, z_sponsor.text)
                personal_id = z_personal.json()["id"]
                sponsor_id = z_sponsor.json()["id"]

                # B disconnects B's own personal store while both Z flows are
                # pending. Neither pending flow may be cancelled as a side effect.
                disconnected = b_client.post("/api/ai/disconnect", json={}, headers=headers)
                self.assertEqual(disconnected.status_code, 200, disconnected.text)
                for attempt_id in (personal_id, sponsor_id):
                    self.assertEqual(
                        self.client.get(f"/api/ai/auth/attempt/{attempt_id}").json()["status"],
                        "connecting",
                    )
                    self.assertEqual(
                        b_client.get(f"/api/ai/auth/attempt/{attempt_id}").status_code, 400
                    )
                    self.assertEqual(
                        b_client.post(
                            f"/api/ai/auth/cancel/{attempt_id}", json={}, headers=headers
                        ).status_code,
                        400,
                    )

                # A failed attempt can be retried only by its owner, against
                # the same personal/sponsor store in which it began.
                for attempt_id in (personal_id, sponsor_id):
                    attempt = chatgpt_auth._attempts[attempt_id]
                    chatgpt_auth.finish(attempt, "failed", "Fixture failure.")
                    attempt.retry_client_id = "fixture-client"
                    self.assertEqual(
                        b_client.post(
                            "/api/ai/auth/begin",
                            json={"retry_attempt_id": attempt_id},
                            headers=headers,
                        ).status_code,
                        400,
                    )
                self.assertEqual(
                    self.client.post(
                        "/api/ai/auth/begin",
                        json={"retry_attempt_id": sponsor_id},
                        headers=headers,
                    ).status_code,
                    400,
                    "a personal OAuth retry must not consume a sponsor-store attempt ID",
                )


if __name__ == "__main__":
    main()
