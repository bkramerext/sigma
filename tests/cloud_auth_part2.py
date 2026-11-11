"""Hosted authentication scenarios, part 2 of 2."""

from cloud_auth_fixture import *


class CloudAuthTests(CloudAuthFixture):
    def test_local_existing_cookie_keeps_same_email_personal_and_sponsor_credentials_separate(self):
        import asyncio
        import time
        from urllib.parse import parse_qs, urlencode, urlsplit

        from sigma import ai_store, chatgpt_auth, openai_connection

        local_origin = "http://127.0.0.1:5173"
        sponsor_token = "shared-sponsor-access"
        personal_token = "z-personal-access"
        observed_tokens: list[str] = []

        async def checked_catalog(access_token, mode="chatgpt"):
            observed_tokens.append(access_token)
            return {
                "status": "connected",
                "checked_at": "2026-10-28T00:00:00Z",
                "ttl_seconds": 60,
            }

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
            login = self.finish(email="sponsor@example.test", subject="same-email-personal-owner")
            self.assertEqual(login.status_code, 303)
            self.client.cookies.update(login.cookies)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )

            async def seed_shared_sponsor():
                async with ai_store.sponsor_transaction() as state:
                    state["accounts"]["shared-sponsor"] = {
                        "client_id": "oaiapp_fixture",
                        "subject": "same-chatgpt-subject",
                        "email": "sponsor@example.test",
                        "access_token": sponsor_token,
                        "refresh_token": "shared-sponsor-refresh",
                        "expires_at": time.time() + 3600,
                        "scopes": list(chatgpt_auth.PLAN_SCOPES),
                    }
                    state["active"] = "shared-sponsor"

            asyncio.run(seed_shared_sponsor())
            rejected_before_oauth = self.client.post(
                "/api/ai/mode",
                json={"mode": "personal"},
                headers={"Origin": local_origin},
            )
            self.assertEqual(rejected_before_oauth.status_code, 403, rejected_before_oauth.text)
            cookie_name = cloud_auth._cookie_name(cloud_auth.SESSION_COOKIE, cloud_auth.config())
            cookie = self.client.cookies.get(cookie_name)

            # Reopen a fresh client using the existing cookie and durable auth
            # home; sponsored default survives before OAuth succeeds.
            restart_context = TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 23459)
            )
            restarted = restart_context.__enter__()
            self.addCleanup(restart_context.__exit__, None, None, None)
            restarted.cookies.set(cookie_name, cookie)
            status = restarted.get("/api/cloud-auth/status")
            self.assertEqual(status.status_code, 200, status.text)
            self.assertEqual(status.json()["account"]["model_access"]["mode"], "sponsored")
            with patch.object(
                openai_connection,
                "_check",
                AsyncMock(side_effect=checked_catalog),
            ):
                initial_connection = restarted.get("/api/ai/connection")
            self.assertEqual(initial_connection.status_code, 200, initial_connection.text)
            self.assertEqual(initial_connection.json()["status"], "connected")
            self.assertEqual(initial_connection.json().get("account_label"), "sponsor@example.test")
            self.assertIn(sponsor_token, observed_tokens)

            token_record = {
                "client_id": "oaiapp_fixture",
                "subject": "same-chatgpt-subject",
                "email": "sponsor@example.test",
                "name": "Z Personal",
                "access_token": personal_token,
                "refresh_token": "z-personal-refresh",
                "expires_at": time.time() + 3600,
                "scopes": list(chatgpt_auth.PLAN_SCOPES),
            }
            with (
                patch.object(
                    chatgpt_auth,
                    "discovery",
                    AsyncMock(
                        return_value={"authorization_endpoint": "https://auth.openai.com/authorize"}
                    ),
                ),
                patch.object(
                    chatgpt_auth,
                    "http",
                    AsyncMock(return_value=(200, {"access_token": "exchanged-code"})),
                ) as exchange,
                patch.object(
                    chatgpt_auth, "validate_tokens", AsyncMock(return_value=token_record)
                ) as validate,
            ):
                started = restarted.post(
                    "/api/ai/auth/begin", json={}, headers={"Origin": local_origin}
                )
                self.assertEqual(started.status_code, 200, started.text)
                attempt_id = started.json()["id"]
                open_url = restarted.get(f"/api/ai/auth/open/{attempt_id}", follow_redirects=False)
                self.assertEqual(open_url.status_code, 307, open_url.text)
                authorization_url = urlsplit(open_url.headers["location"])
                self.assertEqual(authorization_url.hostname, "auth.openai.com")
                authorization = parse_qs(authorization_url.query)
                redirect_uri = urlsplit(authorization["redirect_uri"][0])
                callback_query = urlencode(
                    {
                        "state": authorization["state"][0],
                        "code": "fixture-oauth-code",
                        "client_id": "oaiapp_fixture",
                    }
                )

                async def complete_loopback_oauth():
                    port = redirect_uri.port
                    assert port is not None
                    reader, writer = await asyncio.open_connection("127.0.0.1", port)
                    writer.write(
                        (
                            f"GET {redirect_uri.path}?{callback_query} HTTP/1.1\r\n"
                            f"Host: {redirect_uri.netloc}\r\n\r\n"
                        ).encode()
                    )
                    await writer.drain()
                    response = await reader.read(4096)
                    writer.close()
                    await writer.wait_closed()
                    return response

                callback_response = asyncio.run(complete_loopback_oauth())
                self.assertIn(b"HTTP/1.1 200 OK", callback_response)
                exchange.assert_awaited_once()
                validate.assert_awaited_once()
            oauth_status = restarted.get(f"/api/ai/auth/attempt/{attempt_id}")
            for _ in range(100):
                oauth_status = restarted.get(f"/api/ai/auth/attempt/{attempt_id}")
                if oauth_status.json()["status"] != "connecting":
                    break
                time.sleep(0.01)
            self.assertEqual(oauth_status.json()["status"], "connected")
            self.assertEqual(
                restarted.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
                "successful OAuth alone must not switch funding mode",
            )

            with patch.object(openai_connection, "_check", AsyncMock(side_effect=checked_catalog)):
                personal_mode = restarted.post(
                    "/api/ai/mode", json={"mode": "personal"}, headers={"Origin": local_origin}
                )
            self.assertEqual(personal_mode.status_code, 200, personal_mode.text)
            self.assertEqual(
                restarted.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "personal",
            )
            with patch.object(openai_connection, "_check", AsyncMock(side_effect=checked_catalog)):
                personal = restarted.get("/api/ai/connection?refresh=true")
            self.assertEqual(personal.status_code, 200, personal.text)
            self.assertEqual(personal.json()["status"], "connected")
            self.assertEqual(personal.json()["account_label"], "sponsor@example.test")
            self.assertEqual(observed_tokens[-1], personal_token)
            personal_account_id = personal.json()["active_account"]
            reauthorize = restarted.post(
                "/api/ai/auth/begin",
                json={"account_id": personal_account_id},
                headers={"Origin": local_origin},
            )
            self.assertEqual(reauthorize.status_code, 200, reauthorize.text)
            restarted.post(
                f"/api/ai/auth/cancel/{reauthorize.json()['id']}",
                json={},
                headers={"Origin": local_origin},
            )

            with patch.object(openai_connection, "_check", AsyncMock(side_effect=checked_catalog)):
                sponsored_mode = restarted.post(
                    "/api/ai/mode",
                    json={"mode": "sponsored"},
                    headers={"Origin": local_origin},
                )
            self.assertEqual(sponsored_mode.status_code, 200, sponsored_mode.text)
            self.assertEqual(
                restarted.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
                "sponsored",
            )
            with patch.object(openai_connection, "_check", AsyncMock(side_effect=checked_catalog)):
                sponsor_connection = restarted.get("/api/ai/connection?refresh=true")
            self.assertEqual(sponsor_connection.status_code, 200, sponsor_connection.text)
            self.assertEqual(sponsor_connection.json()["status"], "connected")
            self.assertEqual(sponsor_connection.json()["account_label"], "sponsor@example.test")
            self.assertIn(sponsor_token, observed_tokens)

            with patch.object(openai_connection, "_check", AsyncMock(side_effect=checked_catalog)):
                personal_mode = restarted.post(
                    "/api/ai/mode", json={"mode": "personal"}, headers={"Origin": local_origin}
                )
            self.assertEqual(personal_mode.status_code, 200, personal_mode.text)
            with (
                patch.object(
                    chatgpt_auth,
                    "discovery",
                    AsyncMock(
                        return_value={"revocation_endpoint": "https://auth.openai.com/revoke"}
                    ),
                ),
                patch.object(chatgpt_auth, "http", AsyncMock(return_value=(200, {}))) as revoke,
            ):
                disconnected = restarted.post(
                    "/api/ai/disconnect", json={}, headers={"Origin": local_origin}
                )
            self.assertEqual(disconnected.status_code, 200, disconnected.text)
            self.assertTrue(revoke.await_count <= 1)
            disconnected_personal = restarted.get("/api/ai/connection?refresh=true")
            self.assertIn(
                disconnected_personal.json()["status"], {"reauth_required", "disconnected"}
            )
            with patch.object(openai_connection, "_check", AsyncMock(side_effect=checked_catalog)):
                returned_to_sponsor = restarted.post(
                    "/api/ai/mode",
                    json={"mode": "sponsored"},
                    headers={"Origin": local_origin},
                )
            self.assertEqual(returned_to_sponsor.status_code, 200, returned_to_sponsor.text)
            with patch.object(openai_connection, "_check", AsyncMock(side_effect=checked_catalog)):
                sponsor_after_personal_disconnect = restarted.get("/api/ai/connection?refresh=true")
            self.assertEqual(sponsor_after_personal_disconnect.json()["status"], "connected")
            self.assertIn(sponsor_token, observed_tokens)

            async def sponsor_store_token():
                async with ai_store.sponsor_transaction() as state:
                    return state["accounts"]["shared-sponsor"]["access_token"]

            self.assertEqual(asyncio.run(sponsor_store_token()), sponsor_token)

    def test_local_z_and_b_admins_have_unlimited_and_n_has_metered_sponsorship(self):
        local_origin = "http://127.0.0.1:5173"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "sponsor@example.test",
                "SIGMA_AUTH_HOME": str(Path(self.temp.name) / "allowance-sponsor-auth"),
            },
        ):
            z_login = self.finish(email="sponsor@example.test", subject="allowance-z-admin")
            self.client.cookies.update(z_login.cookies)
            for email, role, allowance in (
                ("personal@example.test", "admin", None),
                ("member@example.test", "member", 0.05),
            ):
                response = self.client.post(
                    "/api/cloud-auth/admin/grants",
                    json={
                        "kind": "email",
                        "value": email,
                        "role": role,
                        "allowance_usd": allowance,
                    },
                    headers={"Origin": local_origin},
                )
                self.assertEqual(response.status_code, 200, response.text)

            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["user"]["role"], "admin"
            )
            z_budget = self.client.get("/api/cloud-auth/local-sponsored-allowance")
            self.assertEqual(z_budget.status_code, 200, z_budget.text)
            self.assertEqual(z_budget.json()["allowance_usd"], 15.0)

            for email, subject, expected_role, expected_allowance in (
                ("personal@example.test", "allowance-b-admin", "admin", 15.0),
                ("member@example.test", "allowance-n-member", "member", 0.05),
            ):
                context = TestClient(
                    app,
                    base_url="http://127.0.0.1",
                    client=("127.0.0.1", 23460 if expected_role == "admin" else 23461),
                )
                client = context.__enter__()
                self.addCleanup(context.__exit__, None, None, None)
                login = self.finish(email=email, subject=subject, client=client)
                self.assertEqual(login.status_code, 303)
                client.cookies.update(login.cookies)
                status = client.get("/api/cloud-auth/status")
                self.assertEqual(status.json()["user"]["role"], expected_role)
                self.assertEqual(status.json()["account"]["model_access"]["mode"], "sponsored")
                budget = client.get("/api/cloud-auth/local-sponsored-allowance")
                self.assertEqual(budget.status_code, 200, budget.text)
                self.assertEqual(budget.json()["allowance_usd"], expected_allowance)

                if expected_role == "admin":
                    # A new Google identity can only select personal after its
                    # own isolated registration has plan permission.
                    unconnected = client.post(
                        "/api/ai/mode",
                        json={"mode": "personal"},
                        headers={"Origin": local_origin},
                    )
                    self.assertEqual(unconnected.status_code, 403, unconnected.text)
                    self.assertEqual(
                        client.get("/api/cloud-auth/status").json()["account"]["model_access"][
                            "mode"
                        ],
                        "sponsored",
                    )
                    self.seed_personal_plan_authorization(subject, "sponsor@example.test")
                    with patch(
                        "sigma.openai_connection._check",
                        new=AsyncMock(
                            return_value={
                                "status": "connected",
                                "checked_at": "fixture",
                                "ttl_seconds": 60,
                            }
                        ),
                    ):
                        personal = client.post(
                            "/api/ai/mode",
                            json={"mode": "personal"},
                            headers={"Origin": local_origin},
                        )
                        self.assertEqual(personal.status_code, 200, personal.text)
                        connection = client.get("/api/ai/connection")
                    self.assertEqual(connection.json()["status"], "connected")
                    self.assertEqual(connection.json().get("account_label"), "sponsor@example.test")

    def test_denied_identity_is_retained_only_for_request_and_other_account_resets_it(self):
        denied = self.finish(email="visitor@example.org")
        self.assertEqual(denied.status_code, 303)
        self.assertEqual(denied.headers["location"], "/?access=denied")
        self.assertNotIn(cloud_auth.SESSION_COOKIE, denied.cookies)
        self.assertFalse((self.root / "workspaces").exists())
        denied_token = denied.cookies[cloud_auth.DENIED_COOKIE]
        self.assertIn("HttpOnly", denied.headers["set-cookie"])
        self.assertIn("Secure", denied.headers["set-cookie"])
        self.client.cookies.set(cloud_auth.DENIED_COOKIE, denied_token)
        self.assertEqual(
            self.client.get("/api/cloud-auth/denied").json(),
            {"identity_available": True, "invitation_status": None},
        )
        self.assertEqual(self.client.get("/api/cloud-auth/status").json()["authenticated"], False)
        with patch.object(cloud_auth, "_deliver_invitation"):
            requested = self.client.post(
                "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
            )
        self.assertEqual(requested.status_code, 200)
        self.assertEqual(
            self.client.get("/api/cloud-auth/denied").json()["invitation_status"], "notified"
        )
        public_demo = self.client.get("/api/cloud-demo/")
        self.assertEqual(public_demo.status_code, 200)
        self.assertEqual(public_demo.json()["project"]["title"], "Counting Pairwise Handshakes")
        self.assertEqual(
            self.client.get(
                "/api/projects/research-sessions", params={"path": str(self.project_path)}
            ).status_code,
            401,
        )
        restart = self.client.get("/api/cloud-auth/login", follow_redirects=False)
        self.assertEqual(
            parse_qs(urlsplit(restart.headers["location"]).query)["prompt"], ["select_account"]
        )
        self.assertIn('__Host-sigma_denied="";', restart.headers["set-cookie"])
        self.assertEqual(self.client.get("/api/cloud-auth/denied").status_code, 404)
        self.assertEqual(self.client.get("/api/projects/recent").json(), {"projects": []})
        self.assertNotIn(cloud_auth.SESSION_COOKIE, restart.cookies)
        with cloud_auth._db(cloud_auth.config()) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)

    def test_account_switch_authorized_to_unauthorized_invalidates_session(self):
        first = self.finish()
        first_raw = first.cookies[cloud_auth.SESSION_COOKIE]
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, first_raw)
        self.assertEqual(self.client.get("/api/cloud-auth/admin/grants").status_code, 200)

        begin = self.client.get("/api/cloud-auth/login", follow_redirects=False)
        self.assertIn('__Host-sigma_session="";', begin.headers["set-cookie"])
        self.assertIn("Max-Age=0", begin.headers["set-cookie"])
        self.assertIsNone(cloud_auth.resolve_session(first_raw))
        with cloud_auth._db(cloud_auth.config()) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)
        self.assertEqual(self.client.get("/api/cloud-auth/admin/grants").status_code, 401)
        self.assertEqual(self.client.get("/api/projects/recent").json(), {"projects": []})

        denied = self.finish("visitor@example.org", "visitor-sub")
        self.assertEqual(denied.status_code, 303)
        self.assertNotIn(cloud_auth.SESSION_COOKIE, denied.cookies)
        self.assertIn('__Host-sigma_session="";', denied.headers["set-cookie"])
        self.assertIsNone(cloud_auth.resolve_session(first_raw))
        self.assertEqual(self.client.get("/api/projects/recent").json(), {"projects": []})
        self.assertEqual(self.client.get("/api/cloud-auth/admin/grants").status_code, 401)

    def test_account_switch_authorized_to_authorized_replaces_session(self):
        first = self.finish()
        first_raw = first.cookies[cloud_auth.SESSION_COOKIE]
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, first_raw)
        self.assertEqual(
            self.client.post(
                "/api/cloud-auth/admin/grants",
                json={"kind": "email", "value": "member@example.org", "role": "member"},
                headers={"Origin": ORIGIN},
            ).status_code,
            200,
        )
        begin = self.client.get("/api/cloud-auth/login", follow_redirects=False)
        self.assertIn('__Host-sigma_session="";', begin.headers["set-cookie"])
        self.assertIsNone(cloud_auth.resolve_session(first_raw))
        self.assertEqual(self.client.get("/api/projects/recent").json(), {"projects": []})

        second = self.finish("member@example.org", "member-sub")
        second_raw = second.cookies[cloud_auth.SESSION_COOKIE]
        principal = cloud_auth.resolve_session(second_raw)
        assert principal is not None
        self.assertEqual(principal.email, "member@example.org")
        self.assertIsNone(cloud_auth.resolve_session(first_raw))
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, second_raw)
        self.assertEqual(
            self.client.get("/api/cloud-auth/status").json()["user"]["email"], "member@example.org"
        )
        self.assertNotEqual(self.client.get("/api/projects/recent").status_code, 401)
        with cloud_auth._db(cloud_auth.config()) as db:
            rows = db.execute("SELECT email FROM sessions").fetchall()
            self.assertEqual([row["email"] for row in rows], ["member@example.org"])

    def test_local_mode_keeps_project_and_provider_apis_unauthenticated(self):
        local_project = self.root / "local-project.sigma"
        initialize_project(
            local_project, "Local test", "Test local API access", research_mode="mathematical"
        )
        with patch.dict(os.environ, {"SIGMA_CLOUD_AUTH_ENABLED": "false"}):
            self.assertEqual(self.client.get("/api/cloud-auth/status").json()["enabled"], False)
            self.assertNotEqual(
                self.client.get(
                    "/api/projects/research-sessions", params={"path": str(local_project)}
                ).status_code,
                401,
            )
            self.assertNotEqual(self.client.get("/api/ai/connection").status_code, 401)

    def test_hosted_google_auth_still_blocks_personal_chatgpt_auth(self):
        signed_in = self.finish()
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_in.cookies[cloud_auth.SESSION_COOKIE]
        )
        response = self.client.post("/api/ai/auth/begin", headers={"Origin": ORIGIN}, json={})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["error"],
            "AI provider authorization is unavailable in cloud mode.",
        )

    def test_hosted_default_and_explicit_sponsored_selection_match_provider_routing(self):
        import asyncio

        from sigma import ai_store, chatgpt_auth, openai_connection

        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "false",
                "SIGMA_CLOUD_SPONSOR_EMAIL": "admin@example.org",
                "SIGMA_CLOUD_CHATGPT_AUTH_HOME": str(Path(self.temp.name) / "hosted-sponsor"),
            },
        ):
            signed_in = self.finish()
            self.client.cookies.set(
                cloud_auth.SESSION_COOKIE, signed_in.cookies[cloud_auth.SESSION_COOKIE]
            )
            initial = self.client.get("/api/cloud-auth/status")
            self.assertEqual(initial.status_code, 200, initial.text)
            self.assertEqual(initial.json()["account"]["model_access"]["mode"], "sponsored")

            account = {
                "client_id": "fixture-chatgpt-client",
                "subject": "hosted-sponsor-subject",
                "email": "admin@example.org",
                "issuer": chatgpt_auth.ISSUER,
                "access_token": "hosted-sponsor-token",
                "refresh_token": "hosted-sponsor-refresh",
                "id_token": "hosted-sponsor-id",
                "token_type": "Bearer",
                "scopes": list(chatgpt_auth.PLAN_SCOPES),
                "expires_at": time.time() + 3600,
            }

            async def save_sponsor():
                async with ai_store.sponsor_transaction() as state:
                    state["accounts"] = {"hosted-sponsor": account}
                    state["active"] = "hosted-sponsor"

            asyncio.run(save_sponsor())
            provider_keys = []

            async def validated_provider(key, mode):
                provider_keys.append((key, mode))
                return openai_connection._CatalogResult(
                    {"status": "connected", "checked_at": "fixture", "ttl_seconds": 60},
                    set(),
                    {},
                    [],
                )

            with patch.object(openai_connection, "_check", side_effect=validated_provider):
                first = self.client.get("/api/ai/connection?refresh=true")
                self.assertEqual(first.status_code, 200, first.text)
                self.assertEqual(first.json()["status"], "connected")
                self.assertEqual(provider_keys[-1], ("hosted-sponsor-token", "chatgpt"))

                personal = self.client.post(
                    "/api/ai/mode", json={"mode": "personal"}, headers={"Origin": ORIGIN}
                )
                self.assertEqual(personal.status_code, 403, personal.text)
                self.assertEqual(
                    self.client.get("/api/cloud-auth/status").json()["account"]["model_access"][
                        "mode"
                    ],
                    "sponsored",
                )
                self.assertEqual(
                    len(provider_keys), 1, "personal mode must not borrow sponsor credentials"
                )

                sponsored = self.client.post(
                    "/api/ai/mode", json={"mode": "sponsored"}, headers={"Origin": ORIGIN}
                )
                self.assertEqual(sponsored.status_code, 200, sponsored.text)
                self.assertEqual(sponsored.json()["status"], "connected")
                self.assertEqual(provider_keys[-1], ("hosted-sponsor-token", "chatgpt"))
                self.assertEqual(
                    self.client.get("/api/cloud-auth/status").json()["account"]["model_access"][
                        "mode"
                    ],
                    "sponsored",
                )

    def test_pending_guest_invitation_is_auto_approved_on_next_google_signin(self):
        """A prior pending request must not block a newly authorized domain."""
        admin_context = TestClient(app)
        admin = admin_context.__enter__()
        self.addCleanup(admin_context.__exit__, None, None, None)
        signed_admin = self.finish(
            email="admin@example.org", subject="pending-domain-admin", client=admin
        )
        admin.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_admin.cookies[cloud_auth.SESSION_COOKIE]
        )
        applicant_email = "applicant@example.test"
        applicant_subject = "pending-domain-applicant"
        denied = self.finish(applicant_email, applicant_subject)
        self.assertIn(cloud_auth.DENIED_COOKIE, denied.cookies)
        self.client.cookies.set(cloud_auth.DENIED_COOKIE, denied.cookies[cloud_auth.DENIED_COOKIE])
        with patch.object(cloud_auth, "_deliver_invitation"):
            requested = self.client.post(
                "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
            )
        self.assertEqual(requested.status_code, 200, requested.text)
        with cloud_auth._db(cloud_auth.config()) as db:
            pending = db.execute(
                "SELECT status FROM invitation_requests WHERE subject=?", (applicant_subject,)
            ).fetchone()
        self.assertIn(pending["status"], {"notified", "pending"})
        granted = admin.post(
            "/api/cloud-auth/admin/grants",
            json={
                "kind": "domain",
                "value": "example.test",
                "role": "member",
                "allowance_usd": 10,
            },
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(granted.status_code, 200, granted.text)
        with patch.object(cloud_auth, "_deliver_invitation") as notice:
            signed = self.finish(applicant_email, applicant_subject)
        self.assertIn(cloud_auth.SESSION_COOKIE, signed.cookies)
        principal = cloud_auth.resolve_session(signed.cookies[cloud_auth.SESSION_COOKIE])
        self.assertIsNotNone(principal)
        assert principal is not None
        self.assertEqual(principal.role, "member")
        notice.assert_called_once()
        self.assertEqual(notice.call_args.kwargs["request_type"], "auto_approved")
        with cloud_auth._db(cloud_auth.config()) as db:
            grant = db.execute(
                "SELECT role,active,allowance_usd FROM grants WHERE kind='email' AND value=?",
                (applicant_email,),
            ).fetchone()
            request = db.execute(
                "SELECT status FROM invitation_requests WHERE subject=?", (applicant_subject,)
            ).fetchone()
        self.assertEqual(
            (grant["role"], grant["active"], grant["allowance_usd"]), ("member", 1, 10)
        )
        self.assertEqual(request["status"], "reviewed")
        listed = admin.get("/api/cloud-auth/admin/grants").json()
        self.assertTrue(
            any(
                account["email"] == applicant_email and account["authorized"]
                for account in listed["sessions"]
            )
        )
        self.assertFalse(
            any(
                req["email"] == applicant_email
                for req in admin.get("/api/cloud-auth/admin/invitation-requests").json()["requests"]
            )
        )

    def test_local_pending_guest_domain_promotion_materializes_member(self):
        local_origin = "http://127.0.0.1:5173"
        email = "applicant@example.test"
        subject = "local-domain-applicant"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
            },
        ):
            signed = self.finish(email=email, subject=subject)
            self.client.cookies.set("sigma_session", signed.cookies["sigma_session"])
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["user"]["role"], "guest"
            )
            with patch.object(cloud_auth, "_deliver_invitation"):
                requested = self.client.post(
                    "/api/cloud-auth/invitation-request", headers={"Origin": local_origin}
                )
            self.assertEqual(requested.status_code, 200, requested.text)
            with cloud_auth._db(cloud_auth.config()) as db:
                db.execute(
                    "INSERT INTO grants(kind,value,role,active,updated_at,allowance_usd) "
                    "VALUES('domain','example.test','member',1,?,10)",
                    (cloud_auth._now(),),
                )
            status = self.client.get("/api/cloud-auth/status").json()
            self.assertEqual(status["user"]["role"], "member")
            with cloud_auth._db(cloud_auth.config()) as db:
                grant = db.execute(
                    "SELECT role,active,allowance_usd FROM grants WHERE kind='email' AND value=?",
                    (email,),
                ).fetchone()
                pending = db.execute(
                    "SELECT status FROM invitation_requests WHERE subject=?", (subject,)
                ).fetchone()
                approvals = db.execute(
                    "SELECT count(*) FROM audit WHERE action='domain_auto_member' AND value=?",
                    (email,),
                ).fetchone()[0]
            self.assertIsNotNone(grant)
            self.assertEqual(tuple(grant), ("member", 1, 10))
            self.assertEqual(pending["status"], "reviewed")
            self.assertEqual(approvals, 1)
            self.client.get("/api/cloud-auth/status")
            # Membership persists independently of the original domain rule.
            with cloud_auth._db(cloud_auth.config()) as db:
                db.execute("UPDATE grants SET active=0 WHERE kind='domain'")
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["user"]["role"], "member"
            )

    def test_local_fresh_google_signin_after_admin_domain_grant(self):
        """Exercise local admin-save -> fresh Google callback, not just session refresh."""
        local_origin = "http://127.0.0.1:5173"
        applicant_email = "applicant@example.test"
        applicant_subject = "local-fresh-domain-applicant"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
            },
        ):
            admin_context = TestClient(app)
            admin = admin_context.__enter__()
            self.addCleanup(admin_context.__exit__, None, None, None)
            signed_admin = self.finish(
                email="admin@example.org", subject="local-domain-admin", client=admin
            )
            admin.cookies.set("sigma_session", signed_admin.cookies["sigma_session"])

            # Create a pending invitation before domain approval, as in the
            # failing manual scenario. The subsequent callback is a NEW login.
            guest = self.finish(applicant_email, applicant_subject)
            self.assertEqual(guest.status_code, 303)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["user"]["role"], "guest"
            )
            with patch.object(cloud_auth, "_deliver_invitation"):
                requested = self.client.post(
                    "/api/cloud-auth/invitation-request", headers={"Origin": local_origin}
                )
            self.assertEqual(requested.status_code, 200, requested.text)
            self.client.cookies.clear()

            granted = admin.post(
                "/api/cloud-auth/admin/grants",
                json={
                    "kind": "domain",
                    "value": "example.test",
                    "role": "member",
                    "allowance_usd": 10,
                },
                headers={"Origin": local_origin},
            )
            self.assertEqual(granted.status_code, 200, granted.text)
            with cloud_auth._db(cloud_auth.config()) as db:
                policy = db.execute(
                    "SELECT role,active,allowance_usd FROM grants "
                    "WHERE kind='domain' AND value='example.test'"
                ).fetchone()
            self.assertEqual(tuple(policy), ("member", 1, 10))

            with patch.object(cloud_auth, "_deliver_invitation") as notice:
                signed = self.finish(applicant_email, applicant_subject)
            self.assertEqual(signed.status_code, 303, signed.text)
            self.assertIn("sigma_session", signed.cookies)
            notice.assert_called_once()
            self.assertEqual(notice.call_args.kwargs["request_type"], "auto_approved")
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["user"]["role"], "member"
            )
            with cloud_auth._db(cloud_auth.config()) as db:
                individual = db.execute(
                    "SELECT role,active,allowance_usd FROM grants WHERE kind='email' AND value=?",
                    (applicant_email,),
                ).fetchone()
                invitation = db.execute(
                    "SELECT status FROM invitation_requests WHERE subject=?",
                    (applicant_subject,),
                ).fetchone()
                audit_count = db.execute(
                    "SELECT count(*) FROM audit WHERE action='domain_auto_member' AND value=?",
                    (applicant_email,),
                ).fetchone()[0]
            self.assertEqual(tuple(individual), ("member", 1, 10))
            self.assertEqual(invitation["status"], "reviewed")
            self.assertEqual(audit_count, 1)
            listed = admin.get("/api/cloud-auth/admin/grants").json()
            self.assertTrue(
                any(
                    item["email"] == applicant_email and item["authorized"]
                    for item in listed["sessions"]
                )
            )

    def test_domain_approved_google_login_materializes_individual_member(self):
        admin_context = TestClient(app)
        admin = admin_context.__enter__()
        self.addCleanup(admin_context.__exit__, None, None, None)
        signed_admin = self.finish(
            email="admin@example.org", subject="auto-login-admin", client=admin
        )
        admin.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_admin.cookies[cloud_auth.SESSION_COOKIE]
        )
        grant = admin.post(
            "/api/cloud-auth/admin/grants",
            json={
                "kind": "domain",
                "value": "example.org",
                "role": "member",
                "allowance_usd": 1.25,
            },
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(grant.status_code, 200, grant.text)
        with patch.object(cloud_auth, "_deliver_invitation") as notify:
            member = self.finish("member@example.org", "auto-login-member")
        self.assertEqual(member.status_code, 303)
        self.assertIn(cloud_auth.SESSION_COOKIE, member.cookies)
        notify.assert_called_once()
        self.assertEqual(notify.call_args.kwargs["request_type"], "auto_approved")
        self.assertEqual(notify.call_args.args[0], "member@example.org")
        with cloud_auth._db(cloud_auth.config()) as db:
            row = db.execute(
                "SELECT role,active,allowance_usd FROM grants WHERE kind='email' AND value=?",
                ("member@example.org",),
            ).fetchone()
            notice = db.execute(
                "SELECT status FROM invitation_requests WHERE subject='auto-login-member'"
            ).fetchone()
        self.assertEqual((row["role"], row["active"], row["allowance_usd"]), ("member", 1, 1.25))
        self.assertEqual(notice["status"], "reviewed")
        listed = admin.get("/api/cloud-auth/admin/grants").json()
        self.assertTrue(
            any(
                account["email"] == "member@example.org" and account["authorized"]
                for account in listed["sessions"]
            )
        )
        self.assertFalse(
            any(
                req["email"] == "member@example.org"
                for req in admin.get("/api/cloud-auth/admin/invitation-requests").json()["requests"]
            )
        )
        revoked = admin.delete(
            "/api/cloud-auth/admin/grants/domain/example.org", headers={"Origin": ORIGIN}
        )
        self.assertEqual(revoked.status_code, 200)
        # Revoking the domain policy blocks future automatic invites, but
        # already-materialized individual members remain independently active.
        current_member = cloud_auth.resolve_session(member.cookies[cloud_auth.SESSION_COOKIE])
        assert current_member is not None
        self.assertEqual(current_member.role, "member")

    def test_domain_granted_after_denied_signin_approves_invite_me_immediately(self):
        admin_context = TestClient(app)
        admin = admin_context.__enter__()
        self.addCleanup(admin_context.__exit__, None, None, None)
        signed_admin = self.finish(
            email="admin@example.org", subject="auto-request-admin", client=admin
        )
        admin.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_admin.cookies[cloud_auth.SESSION_COOKIE]
        )
        denied = self.finish("later@example.org", "auto-request-member")
        self.assertIn(cloud_auth.DENIED_COOKIE, denied.cookies)
        self.client.cookies.set(cloud_auth.DENIED_COOKIE, denied.cookies[cloud_auth.DENIED_COOKIE])
        rule = admin.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "domain", "value": "example.org", "role": "member"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(rule.status_code, 200)
        with patch.object(cloud_auth, "_deliver_invitation") as notify:
            approved = self.client.post(
                "/api/cloud-auth/invitation-request",
                json={"email": "forged@elsewhere.org"},
                headers={"Origin": ORIGIN},
            )
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json(), {"status": "approved", "duplicate": False})
        notify.assert_called_once()
        self.assertEqual(notify.call_args.kwargs["request_type"], "auto_approved")
        token = approved.cookies[cloud_auth.SESSION_COOKIE]
        active_member = cloud_auth.resolve_session(token)
        assert active_member is not None
        self.assertEqual(active_member.email, "later@example.org")
        with cloud_auth._db(cloud_auth.config()) as db:
            saved = db.execute(
                "SELECT role,active FROM grants WHERE kind='email' AND value='later@example.org'"
            ).fetchone()
            notice = db.execute(
                "SELECT status FROM invitation_requests WHERE subject='auto-request-member'"
            ).fetchone()
        self.assertEqual((saved["role"], saved["active"]), ("member", 1))
        self.assertEqual(notice["status"], "reviewed")
        # A parallel tab that still carries the original denied identity
        # receives the existing approval; it must not re-open the request.
        second_context = TestClient(app)
        second = second_context.__enter__()
        self.addCleanup(second_context.__exit__, None, None, None)
        second.cookies.set(cloud_auth.DENIED_COOKIE, denied.cookies[cloud_auth.DENIED_COOKIE])
        with patch.object(cloud_auth, "_deliver_invitation") as race_mail:
            race_result = second.post(
                "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
            )
        self.assertEqual(race_result.status_code, 200, race_result.text)
        self.assertEqual(race_result.json(), {"status": "approved", "duplicate": True})
        race_mail.assert_not_called()
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, token)
        with patch.object(cloud_auth, "_deliver_invitation") as duplicate_mail:
            repeated = self.client.post(
                "/api/cloud-auth/invitation-request", headers={"Origin": ORIGIN}
            )
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.json(), {"status": "approved", "duplicate": True})
        duplicate_mail.assert_not_called()

    def test_domain_auto_member_survives_email_failure_but_revoked_domain_blocks_new_users(self):
        admin_context = TestClient(app)
        admin = admin_context.__enter__()
        self.addCleanup(admin_context.__exit__, None, None, None)
        signed_admin = self.finish(
            email="admin@example.org", subject="auto-failure-admin", client=admin
        )
        admin.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_admin.cookies[cloud_auth.SESSION_COOKIE]
        )
        added = admin.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "domain", "value": "example.org", "role": "member"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(added.status_code, 200)
        with patch.object(
            cloud_auth, "_deliver_invitation", side_effect=RuntimeError("mail offline")
        ):
            signed = self.finish("new@example.org", "auto-failure-member")
        self.assertIn(cloud_auth.SESSION_COOKIE, signed.cookies)
        with cloud_auth._db(cloud_auth.config()) as db:
            row = db.execute(
                "SELECT status,notification_error FROM invitation_requests "
                "WHERE subject='auto-failure-member'"
            ).fetchone()
            grant = db.execute(
                "SELECT role,active FROM grants WHERE kind='email' AND value='new@example.org'"
            ).fetchone()
        self.assertEqual(
            (row["status"], row["notification_error"]), ("reviewed", "delivery failed")
        )
        self.assertEqual((grant["role"], grant["active"]), ("member", 1))
        revoked = admin.delete(
            "/api/cloud-auth/admin/grants/domain/example.org",
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(revoked.status_code, 200)
        later = self.finish("later@example.org", "auto-failure-new")
        self.assertIn(cloud_auth.DENIED_COOKIE, later.cookies)
        self.assertNotIn(cloud_auth.SESSION_COOKIE, later.cookies)
        existing = cloud_auth.resolve_session(signed.cookies[cloud_auth.SESSION_COOKIE])
        assert existing is not None
        self.assertEqual(existing.role, "member")

    def test_new_domain_grant_supersedes_older_revocation_but_not_later_revoke(self):
        """The newest explicit admin admission decision wins in local Google auth."""
        local_origin = "http://127.0.0.1:5173"
        email = "applicant@example.test"
        subject = "previously-revoked-domain-user"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
            },
        ):
            admin_context = TestClient(app)
            admin = admin_context.__enter__()
            self.addCleanup(admin_context.__exit__, None, None, None)
            signed_admin = self.finish(
                email="admin@example.org", subject="domain-policy-admin", client=admin
            )
            admin.cookies.set("sigma_session", signed_admin.cookies["sigma_session"])
            old_grant = admin.post(
                "/api/cloud-auth/admin/grants",
                json={"kind": "email", "value": email, "role": "member"},
                headers={"Origin": local_origin},
            )
            self.assertEqual(old_grant.status_code, 200, old_grant.text)
            revoked = admin.delete(
                "/api/cloud-auth/admin/grants/email/" + email,
                headers={"Origin": local_origin},
            )
            self.assertEqual(revoked.status_code, 200, revoked.text)
            guest = self.finish(email, subject)
            self.assertEqual(guest.status_code, 303)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["user"]["role"], "guest"
            )
            # Opening admin settings must not delete this legitimate Guest
            # session just because an explicit email grant was revoked.
            self.assertEqual(admin.get("/api/cloud-auth/admin/grants").status_code, 200)
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["user"]["role"], "guest"
            )
            # An explicit NEW domain grant supersedes the old revocation.
            granted = admin.post(
                "/api/cloud-auth/admin/grants",
                json={
                    "kind": "domain",
                    "value": "example.test",
                    "role": "member",
                    "allowance_usd": 10,
                },
                headers={"Origin": local_origin},
            )
            self.assertEqual(granted.status_code, 200, granted.text)
            # The admin UI automatically reloads grants after saving. That
            # must not terminate the previously signed-in Guest session.
            self.assertEqual(admin.get("/api/cloud-auth/admin/grants").status_code, 200)
            status = self.client.get("/api/cloud-auth/status").json()
            self.assertEqual(status["user"]["role"], "member")
            with cloud_auth._db(cloud_auth.config()) as db:
                restored = db.execute(
                    "SELECT role,active,allowance_usd FROM grants WHERE kind='email' AND value=?",
                    (email,),
                ).fetchone()
                approvals = db.execute(
                    "SELECT count(*) FROM audit WHERE action='domain_auto_member' AND value=?",
                    (email,),
                ).fetchone()[0]
            self.assertEqual(tuple(restored), ("member", 1, 10))
            self.assertEqual(approvals, 1)

            # Removing the individual grant is not a ban. Active example.test
            # grants authorize the SAME Google account again on the next pass.
            removed = admin.delete(
                "/api/cloud-auth/admin/grants/email/" + email,
                headers={"Origin": local_origin},
            )
            self.assertEqual(removed.status_code, 200, removed.text)
            with cloud_auth._db(cloud_auth.config()) as db:
                self.assertIsNone(
                    db.execute(
                        "SELECT 1 FROM grants WHERE kind='email' AND value=?", (email,)
                    ).fetchone()
                )
            for cycle in range(2):
                with patch.object(cloud_auth, "_deliver_invitation") as notice:
                    signed = self.finish(email, subject)
                self.assertEqual(signed.status_code, 303, signed.text)
                self.assertEqual(
                    self.client.get("/api/cloud-auth/status").json()["user"]["role"],
                    "member",
                    f"repeat sign-in cycle {cycle}",
                )
                notice.assert_called_once()
                if cycle == 0:
                    removed = admin.delete(
                        "/api/cloud-auth/admin/grants/email/" + email,
                        headers={"Origin": local_origin},
                    )
                    self.assertEqual(removed.status_code, 200, removed.text)
            with cloud_auth._db(cloud_auth.config()) as db:
                final_grant = db.execute(
                    "SELECT active,allowance_usd FROM grants WHERE kind='email' AND value=?",
                    (email,),
                ).fetchone()
            self.assertEqual(tuple(final_grant), (1, 10))

    def test_three_domain_authorization_cycles_reusing_same_google_account(self):
        """Remove/reauthorize must not poison later logins for the same subject."""
        local_origin = "http://127.0.0.1:5173"
        email = "applicant@example.test"
        subject = "repeat-domain-member-subject"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
            },
        ):
            admin_context = TestClient(app)
            admin = admin_context.__enter__()
            self.addCleanup(admin_context.__exit__, None, None, None)
            admin_login = self.finish(
                email="admin@example.org", subject="repeat-domain-admin", client=admin
            )
            admin.cookies.set("sigma_session", admin_login.cookies["sigma_session"])
            for cycle in range(3):
                granted = admin.post(
                    "/api/cloud-auth/admin/grants",
                    json={
                        "kind": "domain",
                        "value": "example.test",
                        "role": "member",
                        "allowance_usd": 10,
                    },
                    headers={"Origin": local_origin},
                )
                self.assertEqual(granted.status_code, 200, (cycle, granted.text))
                visible = admin.get("/api/cloud-auth/admin/grants")
                self.assertEqual(visible.status_code, 200, visible.text)
                domain = next(
                    grant
                    for grant in visible.json()["grants"]
                    if grant["kind"] == "domain" and grant["value"] == "example.test"
                )
                self.assertEqual((domain["role"], domain["active"]), ("member", 1))
                with patch.object(cloud_auth, "_deliver_invitation"):
                    login = self.finish(email, subject)
                self.assertEqual(login.status_code, 303, (cycle, login.text))
                role = self.client.get("/api/cloud-auth/status").json()["user"]["role"]
                self.assertEqual(role, "member", f"member login cycle {cycle}")
                with cloud_auth._db(cloud_auth.config()) as db:
                    grant = db.execute(
                        "SELECT role,active,allowance_usd FROM grants "
                        "WHERE kind='email' AND value=?",
                        (email,),
                    ).fetchone()
                self.assertEqual(tuple(grant), ("member", 1, 10))
                # Remove both derived email authorization and its domain.
                # No permanent deny or stale session may survive this reset.
                for kind, value in (("email", email), ("domain", "example.test")):
                    removed = admin.delete(
                        f"/api/cloud-auth/admin/grants/{kind}/{value}",
                        headers={"Origin": local_origin},
                    )
                    self.assertEqual(removed.status_code, 200, (cycle, removed.text))
                self.client.cookies.clear()
                self.assertEqual(admin.get("/api/cloud-auth/admin/grants").json()["grants"], [])
                with patch.object(cloud_auth, "_deliver_invitation"):
                    guest = self.finish(email, subject)
                self.assertEqual(guest.status_code, 303, (cycle, guest.text))
                guest_status = self.client.get("/api/cloud-auth/status").json()
                self.assertEqual(
                    guest_status["user"]["role"],
                    "guest",
                    f"guest between cycles {cycle}",
                )
                self.client.cookies.clear()

    def test_fresh_local_google_login_after_old_revoke_and_new_domain_grant(self):
        """A new domain admission supersedes old revocation and pending request."""
        local_origin = "http://127.0.0.1:5173"
        email = "previous-invite@example.test"
        subject = "fresh-previous-invite-sub"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
            },
        ):
            admin_context = TestClient(app)
            admin = admin_context.__enter__()
            self.addCleanup(admin_context.__exit__, None, None, None)
            admin_login = self.finish(
                email="admin@example.org", subject="fresh-policy-admin", client=admin
            )
            admin.cookies.set("sigma_session", admin_login.cookies["sigma_session"])
            old_grant = admin.post(
                "/api/cloud-auth/admin/grants",
                json={"kind": "email", "value": email, "role": "member"},
                headers={"Origin": local_origin},
            )
            self.assertEqual(old_grant.status_code, 200, old_grant.text)
            revoke = admin.delete(
                "/api/cloud-auth/admin/grants/email/" + email,
                headers={"Origin": local_origin},
            )
            self.assertEqual(revoke.status_code, 200, revoke.text)
            guest = self.finish(email, subject)
            self.assertEqual(guest.status_code, 303, guest.text)
            with patch.object(cloud_auth, "_deliver_invitation"):
                request = self.client.post(
                    "/api/cloud-auth/invitation-request",
                    headers={"Origin": local_origin},
                )
            self.assertEqual(request.status_code, 200, request.text)
            self.client.cookies.clear()

            domain = admin.post(
                "/api/cloud-auth/admin/grants",
                json={
                    "kind": "domain",
                    "value": "example.test",
                    "role": "member",
                    "allowance_usd": 10,
                },
                headers={"Origin": local_origin},
            )
            self.assertEqual(domain.status_code, 200, domain.text)
            with patch.object(cloud_auth, "_deliver_invitation") as notice:
                signed = self.finish(email, subject)
            self.assertEqual(signed.status_code, 303, signed.text)
            notice.assert_called_once()
            self.assertEqual(notice.call_args.kwargs["request_type"], "auto_approved")
            self.assertEqual(
                self.client.get("/api/cloud-auth/status").json()["user"]["role"], "member"
            )
            with cloud_auth._db(cloud_auth.config()) as db:
                grant = db.execute(
                    "SELECT active,allowance_usd FROM grants WHERE kind='email' AND value=?",
                    (email,),
                ).fetchone()
                invitation = db.execute(
                    "SELECT status FROM invitation_requests WHERE subject=?",
                    (subject,),
                ).fetchone()
                audit = db.execute(
                    "SELECT count(*) FROM audit WHERE action='domain_auto_member' AND value=?",
                    (email,),
                ).fetchone()[0]
            self.assertEqual(tuple(grant), (1, 10))
            self.assertEqual(invitation["status"], "reviewed")
            self.assertEqual(audit, 1)

    def test_legacy_inactive_email_does_not_block_active_domain(self):
        """Pre-migration revocation tombstones cannot disable later domain grants."""
        admin_context = TestClient(app)
        admin = admin_context.__enter__()
        self.addCleanup(admin_context.__exit__, None, None, None)
        signed_admin = self.finish(
            email="admin@example.org", subject="legacy-tombstone-admin", client=admin
        )
        admin.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_admin.cookies[cloud_auth.SESSION_COOKIE]
        )
        domain = admin.post(
            "/api/cloud-auth/admin/grants",
            json={
                "kind": "domain",
                "value": "example.org",
                "role": "member",
                "allowance_usd": 10,
            },
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(domain.status_code, 200, domain.text)
        with cloud_auth._db(cloud_auth.config()) as db:
            db.execute(
                "INSERT INTO grants(kind,value,role,active,updated_at) "
                "VALUES('email','blocked@example.org','member',0,?)",
                (cloud_auth._now(),),
            )
        with patch.object(cloud_auth, "_deliver_invitation") as notice:
            signed = self.finish("blocked@example.org", "legacy-blocked-subject")
        self.assertIn(cloud_auth.SESSION_COOKIE, signed.cookies)
        principal = cloud_auth.resolve_session(signed.cookies[cloud_auth.SESSION_COOKIE])
        self.assertIsNotNone(principal)
        assert principal is not None
        self.assertEqual(principal.role, "member")
        notice.assert_called_once()
        with cloud_auth._db(cloud_auth.config()) as db:
            grant = db.execute(
                "SELECT active,role,allowance_usd FROM grants WHERE kind='email' "
                "AND value='blocked@example.org'"
            ).fetchone()
        self.assertEqual(tuple(grant), (1, "member", 10))

    def test_exact_domain_and_revocation_of_existing_session(self):
        admin_context = TestClient(app)
        admin_client = admin_context.__enter__()
        self.addCleanup(admin_context.__exit__, None, None, None)
        admin = self.finish(client=admin_client)
        admin_client.cookies.set(
            cloud_auth.SESSION_COOKIE, admin.cookies[cloud_auth.SESSION_COOKIE]
        )
        invited = admin_client.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "email", "value": "person@outside.org", "role": "member"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(invited.status_code, 200)
        person = self.finish("person@outside.org", "person-sub")
        self.assertEqual(person.status_code, 303)
        person_cookie = person.cookies[cloud_auth.SESSION_COOKIE]
        person_principal = cloud_auth.resolve_session(person_cookie)
        assert person_principal is not None
        self.assertEqual(person_principal.email, "person@outside.org")
        self.assertEqual(
            admin_client.delete(
                "/api/cloud-auth/admin/grants/email/person%40outside.org",
                headers={"Origin": ORIGIN},
            ).status_code,
            200,
        )
        self.assertIsNone(cloud_auth.resolve_session(person_cookie))
        denied = self.finish("person@outside.org", "person-sub")
        self.assertEqual(denied.status_code, 303)
        self.assertNotIn(cloud_auth.SESSION_COOKIE, denied.cookies)
        self.assertIn("access=denied", denied.headers["location"])
        self.assertIn(cloud_auth.FLOW_COOKIE, denied.headers["set-cookie"])
        self.assertIn("Max-Age=0", denied.headers["set-cookie"])
        rule = admin_client.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "domain", "value": "Example.org"},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(rule.status_code, 200)
        member = self.finish("member@example.org", "member-sub")
        member_cookie = member.cookies[cloud_auth.SESSION_COOKIE]
        member_principal = cloud_auth.resolve_session(member_cookie)
        assert member_principal is not None
        self.assertEqual(member_principal.email, "member@example.org")
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, member_cookie)
        self.assertEqual(self.client.get("/api/cloud-auth/admin/grants").status_code, 403)
        self.assertEqual(
            admin_client.delete(
                "/api/cloud-auth/admin/grants/email/member%40example.org",
                headers={"Origin": ORIGIN},
            ).status_code,
            200,
        )
        self.assertIsNone(
            cloud_auth.resolve_session(member_cookie)
        )  # Remove ends the old session, even with a domain rule.
        lookalike = self.finish("member@notexample.org", "lookalike-sub")
        self.assertNotIn(cloud_auth.SESSION_COOKIE, lookalike.cookies)
        removed = admin_client.delete(
            "/api/cloud-auth/admin/grants/domain/example.org", headers={"Origin": ORIGIN}
        )
        self.assertEqual(removed.status_code, 200)
        self.assertIsNone(cloud_auth.resolve_session(member_cookie))
        accounts = admin_client.get("/api/cloud-auth/admin/grants").json()["sessions"]
        revoked = next(item for item in accounts if item["email"] == "member@example.org")
        self.assertEqual(revoked["status"], "revoked")
        self.assertFalse(revoked["authorized"])
        self.assertIn("held_usd", revoked["spending"])

    def test_fixture_member_domain_login_and_reload_request(self):
        admin_login = self.finish()
        self.assertEqual(admin_login.status_code, 303)
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, admin_login.cookies[cloud_auth.SESSION_COOKIE]
        )
        grant = self.client.post(
            "/api/cloud-auth/admin/grants",
            json={
                "kind": "domain",
                "value": "fixture-member.com",
                "role": "member",
                "allowance_usd": 1.25,
            },
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(grant.status_code, 200, grant.text)
        user_context = TestClient(app)
        user = user_context.__enter__()
        self.addCleanup(user_context.__exit__, None, None, None)
        login = self.finish(
            email="tester@fixture-member.com",
            subject="fixture-member-test-account",
            client=user,
        )
        self.assertEqual(login.status_code, 303)
        user.cookies.set(cloud_auth.SESSION_COOKIE, login.cookies[cloud_auth.SESSION_COOKIE])
        user_status = user.get("/api/cloud-auth/status").json()
        self.assertTrue(user_status["authenticated"])
        self.assertTrue(user_status["account"]["sponsorship"]["eligible"])
        self.assertEqual(user_status["account"]["access"]["role"], "member")
        with patch.object(cloud_auth, "_deliver_invitation") as deliver:
            reload_request = user.post(
                "/api/cloud-auth/invitation-request",
                json={"request_type": "reload"},
                headers={"Origin": ORIGIN},
            )
        self.assertEqual(reload_request.status_code, 200, reload_request.text)
        deliver.assert_called_once()
        self.assertEqual(deliver.call_args.args[0], "tester@fixture-member.com")
        self.assertEqual(deliver.call_args.kwargs["request_type"], "reload")
        requests = self.client.get("/api/cloud-auth/admin/invitation-requests").json()["requests"]
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["request_type"], "reload")
        self.assertEqual(requests[0]["email"], "tester@fixture-member.com")

    def test_spending_allowance_admin_policy_and_email_precedence(self):
        admin_context = TestClient(app)
        admin = admin_context.__enter__()
        self.addCleanup(admin_context.__exit__, None, None, None)
        admin_result = self.finish(client=admin)
        admin.cookies.set(
            cloud_auth.SESSION_COOKIE, admin_result.cookies[cloud_auth.SESSION_COOKIE]
        )
        domain = admin.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "domain", "value": "example.org", "allowance_usd": 5.0},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(domain.status_code, 200, domain.text)
        user_context = TestClient(app)
        user = user_context.__enter__()
        self.addCleanup(user_context.__exit__, None, None, None)
        signed = self.finish("member@example.org", "member-sub", client=user)
        self.assertEqual(signed.status_code, 303)
        self.assertEqual(cloud_auth.effective_spending_allowance("member@example.org", 2), 5.0)
        # Domain policy is resolved for each verified email; a specific entry
        # overrides it, including when that individual allowance is larger.
        personal = admin.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "email", "value": "member@example.org", "allowance_usd": 8.0},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(personal.status_code, 200, personal.text)
        self.assertEqual(cloud_auth.effective_spending_allowance("member@example.org", 2), 8.0)
        self.assertEqual(cloud_auth.effective_spending_allowance("other@example.org", 2), 5.0)
        lowered = admin.put(
            "/api/cloud-auth/admin/grants/email/member%40example.org/allowance",
            json={"allowance_usd": 0.5},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(lowered.status_code, 200, lowered.text)
        self.assertEqual(cloud_auth.effective_spending_allowance("member@example.org", 2), 0.5)
        overview = admin.get("/api/cloud-auth/admin/grants")
        self.assertEqual(overview.status_code, 200, overview.text)
        records = overview.json()
        administrator = next(
            item for item in records["sessions"] if item["email"] == "admin@example.org"
        )
        self.assertIsNone(administrator["allowance_usd"])
        self.assertIsNone(administrator["spending"]["remaining_usd"])
        self.assertEqual(
            admin.post(
                "/api/cloud-auth/invitation-request",
                json={"request_type": "reload"},
                headers={"Origin": ORIGIN},
            ).status_code,
            403,
        )
        member = next(item for item in records["sessions"] if item["email"] == "member@example.org")
        self.assertEqual(member["allowance_usd"], 0.5)
        self.assertIn("estimated_usage_usd", member["spending"])
        self.assertIn("held_usd", member["spending"])
        self.assertIn("remaining_usd", member["spending"])
        email_grant = next(
            item for item in records["grants"] if item["value"] == "member@example.org"
        )
        self.assertEqual(email_grant["effective_allowance_usd"], 0.5)
        self.assertEqual(email_grant["allowance_usd"], 0.5)

    def test_admin_can_reload_only_one_active_member_email_allowance(self):
        from types import SimpleNamespace

        admin_login = self.finish()
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, admin_login.cookies[cloud_auth.SESSION_COOKIE]
        )
        grant = self.client.post(
            "/api/cloud-auth/admin/grants",
            json={"kind": "email", "value": "member@example.org", "allowance_usd": 1.25},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(grant.status_code, 200, grant.text)
        member_context = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 12346))
        member = member_context.__enter__()
        self.addCleanup(member_context.__exit__, None, None, None)
        login = self.finish("member@example.org", "member-sub", client=member)
        member.cookies.set(cloud_auth.SESSION_COOKIE, login.cookies[cloud_auth.SESSION_COOKIE])
        with (
            patch(
                "sigma.cloud_workspaces.workspace_for_subject",
                return_value=SimpleNamespace(workspace_id="a" * 32),
            ),
            patch(
                "sigma.cloud_research.admin_reload_workspace_allowance",
                return_value="reload-time",
            ) as reload,
        ):
            response = self.client.post(
                "/api/cloud-auth/admin/grants/reload/member%40example.org",
                headers={"Origin": ORIGIN},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(),
            {"email": "member@example.org", "allowance_usd": 1.25, "reset_at": "reload-time"},
        )
        reload.assert_called_once_with("a" * 32, "admin@example.org")
        denied = member.post(
            "/api/cloud-auth/admin/grants/reload/member%40example.org",
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(denied.status_code, 403)

    def test_role_and_allowance_updates_are_atomic_and_domain_admin_is_rejected(self):
        admin_context = TestClient(app)
        admin = admin_context.__enter__()
        self.addCleanup(admin_context.__exit__, None, None, None)
        signed = self.finish(client=admin)
        admin.cookies.set(cloud_auth.SESSION_COOKIE, signed.cookies[cloud_auth.SESSION_COOKIE])
        for kind, value in (("email", "member@example.org"), ("domain", "example.org")):
            response = admin.post(
                "/api/cloud-auth/admin/grants",
                json={"kind": kind, "value": value, "allowance_usd": 2.0},
                headers={"Origin": ORIGIN},
            )
            self.assertEqual(response.status_code, 200, response.text)
        invalid = admin.put(
            "/api/cloud-auth/admin/grants/updates",
            json={
                "updates": [
                    {
                        "kind": "email",
                        "value": "member@example.org",
                        "role": "admin",
                        "allowance_usd": 4.0,
                    },
                    {
                        "kind": "domain",
                        "value": "example.org",
                        "role": "admin",
                        "allowance_usd": 5.0,
                    },
                ]
            },
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(invalid.status_code, 422, invalid.text)
        snapshot = admin.get("/api/cloud-auth/admin/grants").json()["grants"]
        self.assertEqual(
            next(row for row in snapshot if row["value"] == "member@example.org")["role"], "member"
        )
        saved = admin.put(
            "/api/cloud-auth/admin/grants/updates",
            json={
                "updates": [
                    {
                        "kind": "email",
                        "value": "member@example.org",
                        "role": "admin",
                        "allowance_usd": 4.0,
                    },
                    {
                        "kind": "domain",
                        "value": "example.org",
                        "role": "member",
                        "allowance_usd": None,
                    },
                ]
            },
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        snapshot = admin.get("/api/cloud-auth/admin/grants").json()["grants"]
        self.assertEqual(
            next(row for row in snapshot if row["value"] == "member@example.org")["role"], "admin"
        )
        self.assertEqual(
            next(row for row in snapshot if row["value"] == "member@example.org")["allowance_usd"],
            4.0,
        )

    def test_e2_local_subject_catalog_and_crucible_reference_snapshots(self):
        """Real local sign-ins must not share custom types or URL switches."""
        from sigma import papers, project_types, research_sessions
        from sigma.projects import create_strategy

        local_root = Path(self.temp.name) / "e2-local-projects"
        local_root.mkdir(mode=0o700)
        old_catalog = local_root / ".sigma-project-types.json"
        legacy_bytes = json.dumps({"schema_version": 1, "project_types": []}).encode()
        old_catalog.write_bytes(legacy_bytes)
        old_catalog.chmod(0o600)
        origin = "http://127.0.0.1:5173"
        headers = {"Origin": origin}
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": origin,
                "SIGMA_PROJECTS_ROOT": str(local_root),
                "SIGMA_MOCK_AUTH": "0",
            },
        ):
            from sigma import cloud_workspaces

            self.assertFalse(cloud_workspaces.enabled())
            with TestClient(app, base_url="http://127.0.0.1") as guest:
                public = guest.get("/api/project-types").json()
                self.assertEqual(public["reference_preferences"], {})
                self.assertFalse(any(row["user_defined"] for row in public["project_types"]))
            login_a = self.finish()
            self.assertEqual(login_a.status_code, 303, login_a.text)
            self.client.cookies.set("sigma_session", login_a.cookies["sigma_session"])
            grant = self.client.post(
                "/api/cloud-auth/admin/grants",
                json={"kind": "email", "value": "e2-member@example.org", "role": "member"},
                headers=headers,
            )
            self.assertEqual(grant.status_code, 200, grant.text)
            with TestClient(app, base_url="http://127.0.0.1") as client_b:
                login_b = self.finish(
                    client=client_b, email="e2-member@example.org", subject="e2-user-b"
                )
                self.assertEqual(login_b.status_code, 303, login_b.text)
                client_b.cookies.set("sigma_session", login_b.cookies["sigma_session"])
                a_before = self.client.get("/api/project-types").json()
                b_before = client_b.get("/api/project-types").json()
                self.assertEqual(a_before, b_before)
                common = a_before["common_references"]
                defaults = {}
                self.assertEqual(a_before["reference_preferences"], defaults)
                a_extra_r = "https://a.example.invalid/research"
                a_extra_p = "https://a.example.invalid/publication"
                a_math_p = "https://a.example.invalid/math"
                a_saved = self.client.put(
                    "/api/project-types",
                    json={
                        "project_types": [
                            {
                                "id": "e2-a-type",
                                "name": "A private type",
                                "scope": "A only",
                                "icon": a_before["icons"]["placeholder"],
                                "user_defined": True,
                            }
                        ],
                        "expected_revision": a_before["revision"],
                        "common_custom_references": {
                            "research_standards_references": [
                                {"name": "A research", "url": a_extra_r}
                            ],
                            "publication_standards_references": [
                                {"name": "A publication", "url": a_extra_p}
                            ],
                        },
                        "builtin_custom_references": {
                            "mathematical": {
                                "publication_standards_references": [
                                    {"name": "A math", "url": a_math_p}
                                ]
                            }
                        },
                        # Only the two curated Common links are enabled.
                        "reference_preferences": {
                            "common": {
                                "research_standards_references": [a_extra_r],
                                "publication_standards_references": [a_extra_p],
                            }
                        },
                    },
                    headers=headers,
                )
                self.assertEqual(a_saved.status_code, 200, a_saved.text)
                self.assertEqual(client_b.get("/api/project-types").json(), b_before)
                a_current = self.client.get("/api/project-types").json()
                math_p = next(
                    item for item in project_types.builtin_types() if item.id == "mathematical"
                ).publication_standards_references[0]["url"]
                b_extra_p = "https://b.example.invalid/publication"
                b_saved = client_b.put(
                    "/api/project-types",
                    json={
                        "project_types": [
                            {
                                "id": "e2-b-type",
                                "name": "B private type",
                                "scope": "B only",
                                "icon": b_before["icons"]["placeholder"],
                                "user_defined": True,
                            }
                        ],
                        "expected_revision": b_before["revision"],
                        "common_custom_references": {
                            "publication_standards_references": [
                                {"name": "B publication", "url": b_extra_p}
                            ]
                        },
                        "reference_preferences": {
                            **defaults,
                            "mathematical": {"publication_standards_references": [math_p]},
                        },
                    },
                    headers=headers,
                )
                self.assertEqual(b_saved.status_code, 200, b_saved.text)
                self.assertEqual(self.client.get("/api/project-types").json(), a_current)
                b_current = client_b.get("/api/project-types").json()
                self.assertIn("e2-a-type", str(a_current))
                self.assertNotIn("e2-a-type", str(b_current))
                self.assertIn("e2-b-type", str(b_current))
                self.assertNotIn("e2-b-type", str(a_current))
                self.assertNotIn(a_math_p, str(b_current))
                self.assertNotIn(b_extra_p, str(a_current))
                # Fresh browser/client and switching back preserve own state.
                with TestClient(app, base_url="http://127.0.0.1") as reopened:
                    reopened.cookies.set("sigma_session", login_a.cookies["sigma_session"])
                    self.assertEqual(reopened.get("/api/project-types").json(), a_current)
                self.assertEqual(client_b.get("/api/project-types").json(), b_current)
                self.assertEqual(old_catalog.read_bytes(), legacy_bytes)

                a_created = self.client.post(
                    "/api/projects/create",
                    json={
                        "title": "E2 Crucible A",
                        "problem": "Methodology",
                        "investigation_type": "literature",
                    },
                    headers=headers,
                )
                b_created = client_b.post(
                    "/api/projects/create",
                    json={
                        "title": "E2 Mathematics B",
                        "problem": "Methodology",
                        "investigation_type": "mathematical",
                    },
                    headers=headers,
                )
                self.assertEqual(a_created.status_code, 201, a_created.text)
                self.assertEqual(b_created.status_code, 201, b_created.text)
                literature = next(
                    item for item in project_types.builtin_types() if item.id == "literature"
                )
                expected_research = {
                    ref["url"] for ref in common["research_standards_references"]
                } | {literature.research_standards_references[0]["url"]}
                expected_publication = {
                    ref["url"] for ref in common["publication_standards_references"]
                } | {literature.publication_standards_references[0]["url"]}
                self.assertEqual((len(expected_research), len(expected_publication)), (3, 3))
                a_snapshot = a_created.json()["project"]["project_type_snapshot"]
                for field, expected in (
                    ("research_standards_references", expected_research),
                    ("publication_standards_references", expected_publication),
                ):
                    self.assertEqual({ref["url"] for ref in a_snapshot[field]}, expected)
                self.assertEqual(
                    {
                        ref["url"]
                        for ref in b_created.json()["project"]["project_type_snapshot"][
                            "publication_standards_references"
                        ]
                    },
                    {b_extra_p}
                    | {ref["url"] for ref in common["publication_standards_references"]},
                )
                b_research = {
                    next(
                        item for item in project_types.builtin_types() if item.id == "mathematical"
                    ).research_standards_references[0]["url"]
                } | {ref["url"] for ref in common["research_standards_references"]}
                for principal, path, research_urls, publication_urls in (
                    (
                        cloud_auth.Principal("google-sub-1", "admin@example.org", "admin"),
                        a_created.json()["path"],
                        expected_research,
                        expected_publication,
                    ),
                    (
                        cloud_auth.Principal("e2-user-b", "e2-member@example.org", "member"),
                        b_created.json()["path"],
                        b_research,
                        {b_extra_p}
                        | {ref["url"] for ref in common["publication_standards_references"]},
                    ),
                ):
                    context = cloud_auth._CURRENT_PRINCIPAL.set(principal)
                    try:
                        strategy = create_strategy(path, "Test methodology", "Inspect evidence")
                        frozen_paper, _ = papers._snapshot(path)
                        project_source = next(
                            row for row in frozen_paper["sources"] if row["kind"] == "project"
                        )
                        self.assertEqual(
                            set(project_source["data"]["publication_reference_urls"]),
                            publication_urls,
                        )
                        session = research_sessions.mock_session(
                            path, strategy.project.strategies[0].id, str(uuid4()), "completed"
                        )
                        frozen_research = research_sessions._read(path, session["id"])
                        self.assertEqual(
                            {ref["url"] for ref in frozen_research["research_method_references"]},
                            research_urls,
                        )
                        self.assertEqual(frozen_research["calls_used"], 0)
                    finally:
                        cloud_auth._CURRENT_PRINCIPAL.reset(context)
                # Preserved historical file and two private, 0700, subject dirs.
                self.assertEqual(old_catalog.read_bytes(), legacy_bytes)
                scopes = list((local_root / ".sigma-project-types-users").iterdir())
                self.assertEqual(len(scopes), 2)
                self.assertTrue(all(p.stat().st_mode & 0o077 == 0 for p in scopes))

    def test_explicit_local_google_mode_accepts_only_loopback_http_and_preserves_local_projects(
        self,
    ):
        local_origin = "http://127.0.0.1:5173"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "OPENAI_API_KEY": "",
            },
        ):
            cfg = cloud_auth.config()
            self.assertTrue(cfg.local)
            self.assertIsNone(cfg.error)
            self.assertEqual(cfg.origin, local_origin)
            response = self.client.get("/api/cloud-auth/login", follow_redirects=False)
            self.assertEqual(response.status_code, 302)
            flow_name = "sigma_oidc_flow"
            self.assertIn(flow_name, response.cookies)
            self.assertNotIn("Secure", response.headers["set-cookie"])
            query = parse_qs(urlsplit(response.headers["location"]).query)
            state = query["state"][0]
            self.assertEqual(query["redirect_uri"], [local_origin + "/api/cloud-auth/callback"])
            with cloud_auth._db(cfg) as db:
                nonce = db.execute(
                    "SELECT nonce FROM flows WHERE state_hash=?", (cloud_auth._hash(state),)
                ).fetchone()["nonce"]
            GoogleClient.token = token(nonce=nonce)
            self.client.cookies.set(flow_name, response.cookies[flow_name])
            with patch.object(cloud_auth.httpx, "AsyncClient", GoogleClient):
                signed = self.client.get(
                    "/api/cloud-auth/callback",
                    params={"state": state, "code": "fixture"},
                    follow_redirects=False,
                )
            self.assertEqual(signed.status_code, 303, signed.text)
            self.assertIn("sigma_session", signed.cookies)
            self.assertNotIn("Secure", signed.headers["set-cookie"])
            self.client.cookies.set("sigma_session", signed.cookies["sigma_session"])
            status = self.client.get("/api/cloud-auth/status").json()
            self.assertEqual(status["target"], "local")
            self.assertEqual(status["user"]["role"], "admin")
            self.assertEqual(status["account"]["model_access"]["connection"], "checking")
            with patch(
                "sigma.api.connection",
                return_value={
                    "mode": "api_key",
                    "status": "unconfigured",
                    "label": "OpenAI API key is not configured",
                    "guidance": "No provider request was made.",
                    "checked_at": None,
                },
            ):
                provider_status = self.client.get("/api/ai/connection")
            self.assertEqual(provider_status.status_code, 200, provider_status.text)
            self.assertNotEqual(
                provider_status.json().get("guidance"),
                "AI provider authorization is unavailable in cloud mode.",
            )
            refreshed = self.client.get("/api/cloud-auth/status").json()
            self.assertEqual(refreshed["account"]["model_access"]["connection"], "unconfigured")
            # Local Google authentication now provisions per-user workspaces.
            self.assertTrue((self.root / "workspaces" / "workspaces.sqlite3").exists())
            self.assertEqual(self.client.get("/api/projects/recent").status_code, 200)
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "http://remote.example:5173",
            },
        ):
            self.assertIsNotNone(cloud_auth.config().error)

    def test_local_explicitly_authorized_google_member_can_view_sponsored_allowance(self):
        local_origin = "http://127.0.0.1:5173"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
            },
        ):
            admin_context = TestClient(app)
            admin = admin_context.__enter__()
            self.addCleanup(admin_context.__exit__, None, None, None)
            admin_login = self.finish(client=admin)
            self.assertEqual(admin_login.status_code, 303)
            admin.cookies.set("sigma_session", admin_login.cookies["sigma_session"])
            member_context = TestClient(app)
            member_client = member_context.__enter__()
            self.addCleanup(member_context.__exit__, None, None, None)
            denied = self.finish(
                email="member@example.test",
                subject="fixture-member-local-member",
                client=member_client,
            )
            self.assertEqual(denied.status_code, 303)
            self.assertEqual(denied.headers["location"], "/")
            self.assertIn("sigma_session", denied.cookies)
            member_client.cookies.set("sigma_session", denied.cookies["sigma_session"])
            guest_status = member_client.get("/api/cloud-auth/status").json()
            self.assertEqual(guest_status["user"]["role"], "guest")
            self.assertFalse(guest_status["account"]["sponsorship"]["eligible"])
            grant = admin.post(
                "/api/cloud-auth/admin/grants",
                json={"kind": "email", "value": "member@example.test", "role": "member"},
                headers={"Origin": local_origin},
            )
            self.assertEqual(grant.status_code, 200, grant.text)
            signed_member = self.finish(
                email="member@example.test",
                subject="fixture-member-local-member",
                client=member_client,
            )
            self.assertEqual(signed_member.status_code, 303)
            member_client.cookies.set("sigma_session", signed_member.cookies["sigma_session"])
            status = member_client.get("/api/cloud-auth/status").json()
            self.assertEqual(status["target"], "local")
            self.assertTrue(status["authenticated"])
            self.assertTrue(status["account"]["sponsorship"]["eligible"])

    def test_local_sponsored_flag_forces_eligible_google_account_and_reads_its_grant(self):
        local_origin = "http://127.0.0.1:5173"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_LOCAL_SPONSORED_TEST_MODE": "1",
                "SIGMA_MOCK_AUTH": "0",
            },
        ):
            admin_login = self.finish()
            self.assertEqual(admin_login.status_code, 303)
            self.client.cookies.set("sigma_session", admin_login.cookies["sigma_session"])
            admin_status = self.client.get("/api/cloud-auth/status").json()
            self.assertEqual(admin_status["account"]["access"]["role"], "admin")
            self.assertTrue(admin_status["account"]["sponsorship"]["eligible"])
            self.assertEqual(admin_status["account"]["model_access"]["mode"], "sponsored")
            grant = self.client.post(
                "/api/cloud-auth/admin/grants",
                json={
                    "kind": "email",
                    "value": "local-sponsor@example.org",
                    "role": "member",
                    "allowance_usd": 1.25,
                },
                headers={"Origin": local_origin},
            )
            self.assertEqual(grant.status_code, 200, grant.text)
            member_context = TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 23456)
            )
            member = member_context.__enter__()
            self.addCleanup(member_context.__exit__, None, None, None)
            login = self.finish(
                email="local-sponsor@example.org",
                subject="local-sponsored-test-user",
                client=member,
            )
            self.assertEqual(login.status_code, 303)
            member.cookies.set("sigma_session", login.cookies["sigma_session"])
            status = member.get("/api/cloud-auth/status").json()
            self.assertFalse(status["mock_auth"])
            self.assertFalse(status["mock_identity"])
            self.assertTrue(status["sponsored_test_mode"])
            self.assertEqual(status["account"]["model_access"]["mode"], "sponsored")
            self.assertTrue(status["account"]["sponsorship"]["forced"])
            with (
                patch.dict(
                    os.environ,
                    {
                        "SIGMA_CLOUD_SPONSOR_EMAIL": "sponsor@example.test",
                    },
                ),
                patch(
                    "sigma.cloud_sponsor.sponsor_session",
                    new=AsyncMock(
                        return_value={
                            "status": "connected",
                            "account_id": "designated-admin",
                            "account": {
                                "email": "sponsor@example.test",
                                "access_token": "sponsor-token",
                            },
                        }
                    ),
                ) as sponsor_session,
                patch(
                    "sigma.openai_connection.chatgpt_auth.session",
                    new=AsyncMock(side_effect=AssertionError("local ChatGPT session was used")),
                ),
                patch(
                    "sigma.openai_connection._check",
                    new=AsyncMock(
                        return_value={
                            "status": "connected",
                            "checked_at": "2026-10-27T00:00:00Z",
                            "ttl_seconds": 60,
                        }
                    ),
                ),
            ):
                os.environ.pop("SIGMA_CLOUD_INFERENCE_PROVIDER", None)
                connection = member.get("/api/ai/connection")
            self.assertEqual(connection.status_code, 200, connection.text)
            self.assertEqual(connection.json()["mode"], "chatgpt")
            self.assertTrue(connection.json()["label"].startswith("SIGMA-sponsored ChatGPT"))
            self.assertEqual(sponsor_session.await_count, 1)
            budget = member.get("/api/cloud-research/budget")
            self.assertEqual(budget.status_code, 200, budget.text)
            self.assertEqual(budget.json()["allowance_usd"], 1.25)
            self.assertEqual(budget.json()["remaining_usd"], 1.25)
            personal = member.post(
                "/api/ai/mode",
                json={"mode": "personal"},
                headers={"Origin": local_origin},
            )
            self.assertEqual(personal.status_code, 403, personal.text)
            allowance = member.get("/api/cloud-auth/local-sponsored-allowance")
            self.assertEqual(allowance.status_code, 200, allowance.text)
            self.assertEqual(allowance.json()["allowance_usd"], 1.25)
            self.assertEqual(allowance.json()["remaining_usd"], 1.25)
            self.assertTrue(allowance.json()["local_preview"])
            self.assertFalse(allowance.json()["simulated"])

    def test_local_sponsored_service_key_starts_play_with_quarter_allowance(self):
        import asyncio
        from uuid import uuid4

        from sigma import openai_connection, research_sessions

        origin = "http://127.0.0.1:5173"
        project_root = Path(self.temp.name) / "local-projects"
        project_root.mkdir(mode=0o700)
        workspace_root = Path(self.temp.name) / "local-workspaces"
        workspace_root.mkdir(mode=0o700)
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": origin,
                "SIGMA_CLOUD_INFERENCE_PROVIDER": "api_key",
                "SIGMA_CLOUD_OPENAI_API_KEY": "fixture-sponsored-key",
                "OPENAI_API_KEY": "personal-key-must-not-be-used",
                "SIGMA_PROJECTS_ROOT": str(project_root),
                "SIGMA_CLOUD_WORKSPACES_ROOT": str(workspace_root),
                "SIGMA_LOCAL_SPONSORED_TEST_MODE": "0",
                "SIGMA_MOCK_AUTH": "0",
            },
        ):
            admin_login = self.finish()
            self.client.cookies.set("sigma_session", admin_login.cookies["sigma_session"])
            grant = self.client.post(
                "/api/cloud-auth/admin/grants",
                json={
                    "kind": "email",
                    "value": "member@example.org",
                    "role": "member",
                    "allowance_usd": 0.25,
                },
                headers={"Origin": origin},
            )
            self.assertEqual(grant.status_code, 200, grant.text)
            with TestClient(app, base_url="http://127.0.0.1") as member:
                login = self.finish(
                    email="member@example.org",
                    subject="local-service-key-member",
                    client=member,
                )
                member.cookies.set("sigma_session", login.cookies["sigma_session"])
                member.headers.update({"Origin": origin})
                cloud_auth.set_model_access("local-service-key-member", "sponsored")
                budget = member.get("/api/cloud-research/budget")
                self.assertEqual(budget.status_code, 200, budget.text)
                self.assertEqual(budget.json()["remaining_usd"], 0.25)

                principal = cloud_auth.Principal(
                    "local-service-key-member", "member@example.org", "member"
                )
                principal_token = cloud_auth._CURRENT_PRINCIPAL.set(principal)
                try:
                    credential = asyncio.run(openai_connection.auth_context())
                finally:
                    cloud_auth._CURRENT_PRINCIPAL.reset(principal_token)
                self.assertEqual(credential["mode"], "api_key")
                self.assertEqual(credential["token"], "fixture-sponsored-key")
                self.assertTrue(openai_connection.cloud_credential(credential))

                # A selected personal funding source must fail closed on a
                # temporary provider outage instead of silently spending the
                # sponsor allowance.
                self.seed_personal_plan_authorization("local-service-key-member")
                cloud_auth.set_model_access("local-service-key-member", "personal")
                with patch.object(
                    openai_connection.chatgpt_auth,
                    "session",
                    new=AsyncMock(
                        return_value={
                            "mode": "chatgpt",
                            "account": {"email": "personal@example.org", "access_token": ""},
                            "status": "unavailable",
                        }
                    ),
                ):
                    principal_token = cloud_auth._CURRENT_PRINCIPAL.set(principal)
                    try:
                        personal_credential = asyncio.run(openai_connection.auth_context())
                    finally:
                        cloud_auth._CURRENT_PRINCIPAL.reset(principal_token)
                self.assertEqual(personal_credential["status"], "unavailable")
                self.assertEqual(personal_credential["token"], "")
                self.assertFalse(openai_connection.cloud_credential(personal_credential))
                self.assertEqual(
                    cloud_auth.model_access_for_subject("local-service-key-member"), "personal"
                )
                cloud_auth.set_model_access("local-service-key-member", "sponsored")

                investigator = {
                    "claim": "The base case suggests the recurrence bound.",
                    "method": "Check the first recurrence value.",
                    "assumptions": ["The recurrence applies at positive indices."],
                    "evidence_status": "Unverified model derivation.",
                    "open_obligations": ["Check the next value."],
                    "python_code": None,
                    "sage_code": None,
                    "prior_session_failure_attempt_ids": [],
                    "human_guidance_reviews": [],
                    "computational_citations": [],
                }
                skeptic = {
                    "assessment": "continue",
                    "stop_reason": "recoverable_objection",
                    "response": "The next value remains to be checked.",
                    "objections": ["Verify the next value."],
                    "remaining_obligations": ["Verify the next value."],
                    "next_question": "What is the next recurrence value?",
                    "objective_status": "partial",
                    "solution_claim": "A partial bound is plausible.",
                    "argument_summary": "The first value supports only a partial bound.",
                    "assumptions_reviewed": ["The recurrence applies at positive indices."],
                    "proof_obligations": ["Verify the next value."],
                    "unresolved_objections": ["Verify the next value."],
                    "supporting_cycles": [1],
                    "verification_status": "incomplete",
                    "strategy_contribution": "productive",
                    "contribution_rationale": "The next check is explicit.",
                    "cross_strategy_relations": [],
                    "retracted_cross_strategy_source_artifact_ids": [],
                    "peer_handoff_reviews": [],
                    "human_guidance_reviews": [],
                    "computational_citations": [],
                }

                async def fake_call(record, role, context, timeout_seconds=None, step_id=None):
                    del record, context, timeout_seconds
                    self.assertIsInstance(step_id, str)
                    return (investigator if role == "investigator" else skeptic), {
                        "input_tokens": 90,
                        "cached_input_tokens": 0,
                        "output_tokens": 30,
                    }

                async def provider_fixture(request):
                    self.assertEqual(
                        request.headers["authorization"], "Bearer fixture-sponsored-key"
                    )
                    self.assertEqual(request.url.path, "/v1/models")
                    return httpx.Response(
                        200,
                        json={"object": "list", "data": [{"id": "gpt-6-luna"}]},
                    )

                real_client = httpx.AsyncClient
                with (
                    patch.object(
                        openai_connection.httpx,
                        "AsyncClient",
                        side_effect=lambda **kwargs: real_client(
                            transport=httpx.MockTransport(provider_fixture), **kwargs
                        ),
                    ),
                    patch.object(research_sessions, "execution_capabilities", return_value=[]),
                    patch.object(
                        research_sessions, "_call", new=AsyncMock(side_effect=fake_call)
                    ) as calls,
                    patch.object(sponsor_diagnostics, "record") as diagnostics,
                ):
                    created = member.post(
                        "/api/projects/create",
                        json={
                            "title": "Local sponsor Play",
                            "problem": "Check a recurrence bound",
                            "investigation_type": "mathematical",
                        },
                    )
                    self.assertEqual(created.status_code, 201, created.text)
                    path = created.json()["path"]
                    project_id = created.json()["project"]["id"]
                    model_update = member.put(
                        "/api/user-preferences/research-settings",
                        json={"ai_model": "gpt-6-luna", "reasoning_effort": "high"},
                    )
                    self.assertEqual(model_update.status_code, 200, model_update.text)
                    strategy = member.post(
                        "/api/projects/strategies",
                        json={
                            "path": path,
                            "title": "Induction",
                            "approach": "Check the base case and induction step.",
                        },
                    )
                    self.assertEqual(strategy.status_code, 201, strategy.text)
                    strategies = member.get(
                        "/api/projects/strategies", params={"path": path}
                    ).json()["strategies"]
                    limits = member.put(
                        "/api/projects/research-limits",
                        json={
                            "path": path,
                            "research_rounds": 1,
                            "model_calls": 12,
                            "session_duration_minutes": 15,
                            "output_tokens_per_call": 256,
                            "maximum_estimated_cost_usd": 0.25,
                        },
                    )
                    self.assertEqual(limits.status_code, 200, limits.text)
                    self.assertEqual(limits.json()["model_calls"], 12, limits.text)
                    reloaded_limits = member.get(
                        "/api/projects/research-limits", params={"path": path}
                    )
                    self.assertEqual(reloaded_limits.status_code, 200, reloaded_limits.text)
                    # The explicit v1 PUT persists its historical 12-call ceiling,
                    # while a fresh browser start previews the new v2 3x3 protocol.
                    self.assertEqual(
                        (
                            reloaded_limits.json()["scheduler_version"],
                            reloaded_limits.json()["research_rounds"],
                            reloaded_limits.json()["turns_per_round"],
                            reloaded_limits.json()["model_calls"],
                        ),
                        (2, 3, 3, 18),
                        reloaded_limits.text,
                    )
                    self.assertEqual(research_sessions.get_limits(path)["model_calls"], 18)
                    self.assertEqual(research_sessions.get_limits(path)["scheduler_version"], 2)
                    config = member.get("/api/projects/proposals/config", params={"path": path})
                    self.assertEqual(config.status_code, 200, config.text)
                    self.assertTrue(config.json()["available"], config.text)
                    self.assertEqual(config.json()["binding"], credential["identity"])
                    started = member.post(
                        "/api/projects/research-sessions/start",
                        json={
                            "path": path,
                            "strategy_id": strategies[0]["id"],
                            "idempotency_key": str(uuid4()),
                            "expected_project_id": project_id,
                            "expected_binding": credential["identity"],
                            "expected_limits": limits.json(),
                        },
                    )
                    self.assertEqual(started.status_code, 200, started.text)
                    self.assertEqual(
                        [item.args for item in diagnostics.call_args_list],
                        [
                            ("sponsor_context", "o0_b2_t0_a0_r0_p0"),
                            ("sponsor_play", "accepted"),
                        ],
                    )
                    session_id = started.json()["id"]
                    saved = started.json()
                    for _ in range(500):
                        saved = member.get(
                            f"/api/projects/research-sessions/{session_id}",
                            params={"path": path},
                        ).json()
                        if saved["status"] in {"ended", "failed", "paused"}:
                            break
                        time.sleep(0.01)
                    self.assertEqual(saved["status"], "ended", saved)
                    self.assertEqual(calls.await_count, 2)

    def test_local_expired_personal_connection_does_not_switch_funding_and_admin_can_renew(self):
        local_origin = "http://127.0.0.1:5173"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "sponsor@example.test",
                "SIGMA_LOCAL_SPONSORED_TEST_MODE": "0",
                "SIGMA_MOCK_AUTH": "0",
            },
        ):
            os.environ["SIGMA_CLOUD_SPONSOR_EMAIL"] = "sponsor@example.test"
            admin_login = self.finish(
                email="sponsor@example.test", subject="configured-local-admin"
            )
            self.client.cookies.update(admin_login.cookies)
            grant = self.client.post(
                "/api/cloud-auth/admin/grants",
                json={
                    "kind": "email",
                    "value": "member@example.test",
                    "role": "member",
                    "allowance_usd": 0.01,
                },
                headers={"Origin": local_origin},
            )
            self.assertEqual(grant.status_code, 200, grant.text)
            member_context = TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 23456)
            )
            member = member_context.__enter__()
            self.addCleanup(member_context.__exit__, None, None, None)
            login = self.finish(
                email="member@example.test",
                subject="local-sponsored-member",
                client=member,
            )
            self.assertEqual(login.status_code, 303)
            member.cookies.update(login.cookies)
            initial_status = member.get("/api/cloud-auth/status").json()
            self.assertTrue(initial_status["account"]["sponsorship"]["eligible"])
            self.assertEqual(initial_status["account"]["model_access"]["mode"], "sponsored")
            # Once the user explicitly selects personal mode, later status
            # refreshes must preserve that choice.
            self.seed_personal_plan_authorization("local-sponsored-member")
            with patch(
                "sigma.openai_connection._check",
                new=AsyncMock(
                    return_value={"status": "connected", "checked_at": "fixture", "ttl_seconds": 60}
                ),
            ):
                cloud_auth.set_model_access("local-sponsored-member", "personal")
            with (
                patch(
                    "sigma.openai_connection.chatgpt_auth.session",
                    new=AsyncMock(
                        return_value={"mode": "chatgpt", "status": "reauth_required", "account": {}}
                    ),
                ) as personal_session,
                patch(
                    "sigma.cloud_sponsor.sponsor_session",
                    new=AsyncMock(return_value={"status": "reauth_required", "account": {}}),
                ) as sponsor_session,
            ):
                connection = member.get("/api/ai/connection")
            self.assertEqual(connection.status_code, 200, connection.text)
            self.assertEqual(personal_session.await_count, 1)
            self.assertEqual(sponsor_session.await_count, 0)
            self.assertIn("session has expired", connection.json()["guidance"])
            self.assertNotIn("administrator", connection.json()["guidance"].lower())
            status = member.get("/api/cloud-auth/status").json()
            self.assertEqual(status["account"]["model_access"]["mode"], "personal")
            with (
                patch(
                    "sigma.cloud_sponsor.sponsor_account_id",
                    new=AsyncMock(return_value="sponsor-id"),
                ),
                patch(
                    "sigma.api.chatgpt_auth.begin",
                    new=AsyncMock(
                        return_value={
                            "id": "attempt",
                            "authorization_url": "/api/ai/auth/open/attempt",
                        }
                    ),
                ) as begin,
            ):
                member_denied = member.post(
                    "/api/ai/sponsor-auth/begin", json={}, headers={"Origin": local_origin}
                )
                self.assertEqual(member_denied.status_code, 403, member_denied.text)
                with patch.dict(os.environ, {"SIGMA_CLOUD_SPONSORED_ENABLED": "false"}):
                    disabled_member_denied = member.post(
                        "/api/ai/sponsor-auth/begin", json={}, headers={"Origin": local_origin}
                    )
                    self.assertEqual(
                        disabled_member_denied.status_code, 403, disabled_member_denied.text
                    )
                allowed = self.client.post(
                    "/api/ai/sponsor-auth/begin", json={}, headers={"Origin": local_origin}
                )
            self.assertEqual(allowed.status_code, 200, allowed.text)
            self.assertEqual(begin.await_count, 1)
            begin.assert_awaited_with(account_id="sponsor-id", sponsor=True)

    def test_local_personal_mode_cannot_use_or_disconnect_active_sponsor_credential(self):
        import asyncio

        from sigma.ai_store import sponsor_transaction

        local_origin = "http://127.0.0.1:5173"
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_LOCAL": "true",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": local_origin,
                "SIGMA_AUTH_HOME": str(Path(self.temp.name) / "sponsor-store"),
                "SIGMA_LOCAL_SPONSORED_TEST_MODE": "0",
                "SIGMA_MOCK_AUTH": "0",
            },
        ):
            admin_login = self.finish()
            self.client.cookies.set("sigma_session", admin_login.cookies["sigma_session"])
            grant = self.client.post(
                "/api/cloud-auth/admin/grants",
                json={
                    "kind": "email",
                    "value": "applicant@example.test",
                    "role": "member",
                    "allowance_usd": 0.01,
                },
                headers={"Origin": local_origin},
            )
            self.assertEqual(grant.status_code, 200, grant.text)
            member_context = TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 23456)
            )
            member = member_context.__enter__()
            self.addCleanup(member_context.__exit__, None, None, None)
            login = self.finish(
                email="applicant@example.test",
                subject="local-sponsored-member",
                client=member,
            )
            member.cookies.set("sigma_session", login.cookies["sigma_session"])
            self.seed_personal_plan_authorization("local-sponsored-member")
            cloud_auth.set_model_access("local-sponsored-member", "personal")

            async def seed():
                async with sponsor_transaction() as state:
                    state["mode"] = "chatgpt"
                    state["active"] = "sponsor"
                    state["accounts"] = {
                        "sponsor": {
                            "email": "sponsor@example.test",
                            "client_id": "fixture-client",
                            "access_token": "fixture-sponsor-token",
                            "refresh_token": "fixture-refresh-token",
                            "expires_at": time.time() + 3600,
                            "scopes": ["resource.invoke", "chatgpt.tokens.use.direct"],
                        }
                    }

            asyncio.run(seed())
            with patch(
                "sigma.openai_connection._check",
                new=AsyncMock(
                    return_value={"status": "connected", "checked_at": "fixture", "ttl_seconds": 60}
                ),
            ):
                connection = member.get("/api/ai/connection")
            self.assertEqual(connection.status_code, 200, connection.text)
            self.assertEqual(connection.json()["status"], "connected")
            self.assertNotIn("fixture-sponsor-token", connection.text)

            renew = member.post(
                "/api/ai/auth/begin",
                json={"account_id": "sponsor"},
                headers={"Origin": local_origin},
            )
            self.assertEqual(renew.status_code, 400, renew.text)
            sponsor_renew = member.post(
                "/api/ai/sponsor-auth/begin", json={}, headers={"Origin": local_origin}
            )
            self.assertEqual(sponsor_renew.status_code, 403, sponsor_renew.text)
            with patch(
                "sigma.api.chatgpt_auth.disconnect",
                new=AsyncMock(return_value={"message": "disconnected"}),
            ):
                disconnected = member.post(
                    "/api/ai/disconnect", json={}, headers={"Origin": local_origin}
                )
            self.assertEqual(disconnected.status_code, 200, disconnected.text)

            async def assert_intact():
                async with sponsor_transaction() as state:
                    self.assertEqual(
                        state["accounts"]["sponsor"]["access_token"], "fixture-sponsor-token"
                    )

            asyncio.run(assert_intact())

    def test_connection_choice_is_separate_from_allowance_and_hosted_personal_is_unsupported(self):
        signed_in = self.finish()
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_in.cookies[cloud_auth.SESSION_COOKIE]
        )
        initial = self.client.get("/api/cloud-auth/status").json()
        self.assertEqual(initial["account"]["model_access"]["mode"], "sponsored")
        headers = {"Origin": ORIGIN, "Content-Type": "application/json"}
        with patch("sigma.api.cloud_research.snapshot", return_value={"remaining_usd": 1.25}):
            selected = self.client.post("/api/ai/mode", json={"mode": "sponsored"}, headers=headers)
        self.assertEqual(selected.status_code, 200, selected.text)
        # The connection response's mode describes the provider adapter;
        # funding selection is the persistent cloud-auth account state below.
        self.assertEqual(selected.json()["mode"], "chatgpt")
        self.assertEqual(
            self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
            "sponsored",
        )
        with patch(
            "sigma.api.cloud_research.snapshot",
            side_effect=AssertionError("mode selection must not inspect spend ledger"),
        ):
            exhausted = self.client.post(
                "/api/ai/mode", json={"mode": "sponsored"}, headers=headers
            )
        self.assertEqual(exhausted.status_code, 200, exhausted.text)
        self.assertEqual(
            self.client.get("/api/cloud-auth/status").json()["account"]["model_access"]["mode"],
            "sponsored",
        )
        switched = self.client.post("/api/ai/mode", json={"mode": "personal"}, headers=headers)
        self.assertEqual(switched.status_code, 403, switched.text)
        refreshed = self.client.get("/api/cloud-auth/status").json()
        self.assertEqual(refreshed["account"]["model_access"]["mode"], "sponsored")

    def test_operator_can_disable_sponsor_without_removing_personal_connection(self):
        signed_in = self.finish()
        self.client.cookies.set(
            cloud_auth.SESSION_COOKIE, signed_in.cookies[cloud_auth.SESSION_COOKIE]
        )
        headers = {"Origin": ORIGIN, "Content-Type": "application/json"}
        with patch.dict(os.environ, {"SIGMA_CLOUD_SPONSORED_ENABLED": "false"}):
            status = self.client.get("/api/cloud-auth/status").json()
            self.assertTrue(status["authenticated"])
            self.assertEqual(status["account"]["model_access"]["mode"], "personal")
            self.assertFalse(status["account"]["sponsorship"]["eligible"])
            with patch(
                "sigma.api.cloud_research.snapshot",
                side_effect=AssertionError("disabled sponsor checked allowance"),
            ):
                blocked = self.client.post(
                    "/api/ai/mode", json={"mode": "sponsored"}, headers=headers
                )
            self.assertEqual(blocked.status_code, 403)
            self.assertEqual(self.client.get("/api/cloud-research/connection").status_code, 404)
            personal = self.client.post("/api/ai/mode", json={"mode": "personal"}, headers=headers)
            self.assertEqual(personal.status_code, 200)
            self.assertEqual(personal.json()["status"], "unavailable")

    def test_force_sponsored_mode_is_opt_in_and_enforced_for_eligible_users(self):
        self.assertFalse(cloud_auth.force_sponsored_mode_enabled())
        admin = self.finish()
        self.client.cookies.set(cloud_auth.SESSION_COOKIE, admin.cookies[cloud_auth.SESSION_COOKIE])
        granted = self.client.post(
            "/api/cloud-auth/admin/grants",
            headers={"Origin": ORIGIN},
            json={
                "kind": "email",
                "value": "member@example.org",
                "role": "member",
                "allowance_usd": 0.75,
            },
        )
        self.assertEqual(granted.status_code, 200, granted.text)

        headers = {"Origin": ORIGIN, "Content-Type": "application/json"}
        with patch.dict(os.environ, {"SIGMA_CLOUD_FORCE_SPONSORED_MODE": "true"}):
            self.assertTrue(cloud_auth.force_sponsored_mode_enabled())
            admin_status = self.client.get("/api/cloud-auth/status").json()
            self.assertTrue(admin_status["account"]["sponsorship"]["forced"])
            self.assertEqual(admin_status["account"]["model_access"]["mode"], "sponsored")
            denied_change = self.client.post(
                "/api/ai/mode", json={"mode": "personal"}, headers=headers
            )
            self.assertEqual(denied_change.status_code, 403)

            member = self.finish(email="member@example.org", subject="forced-member")
            self.client.cookies.set(
                cloud_auth.SESSION_COOKIE, member.cookies[cloud_auth.SESSION_COOKIE]
            )
            member_status = self.client.get("/api/cloud-auth/status").json()
            self.assertTrue(member_status["account"]["sponsorship"]["eligible"])
            self.assertTrue(member_status["account"]["sponsorship"]["forced"])
            self.assertEqual(member_status["account"]["model_access"]["mode"], "sponsored")
            denied_change = self.client.post(
                "/api/ai/mode", json={"mode": "personal"}, headers=headers
            )
            self.assertEqual(denied_change.status_code, 403)

            self.client.cookies.clear()
            guest = self.client.post("/api/ai/mode", json={"mode": "personal"}, headers=headers)
            self.assertEqual(guest.status_code, 401)

        self.assertFalse(cloud_auth.force_sponsored_mode_enabled())

    def test_session_expiration_is_enforced(self):
        signed_in = self.finish()
        raw = signed_in.cookies[cloud_auth.SESSION_COOKIE]
        with cloud_auth._db(cloud_auth.config()) as db:
            expiry = db.execute(
                "SELECT expires_at FROM sessions WHERE token_hash=?", (cloud_auth._hash(raw),)
            ).fetchone()["expires_at"]
        with patch.object(cloud_auth, "_now", return_value=expiry):
            self.assertIsNone(cloud_auth.resolve_session(raw))
            self.client.cookies.set(cloud_auth.SESSION_COOKIE, raw)
            self.assertEqual(self.client.get("/api/projects/recent").json(), {"projects": []})

    def test_invalid_identity_claims_nonce_and_state_replay(self):
        invalid = [
            {"verified": False},
            {"iss": "https://attacker.test"},
            {"aud": "other-client"},
            {"exp": int(time.time()) - 1},
            {"azp": "other-client"},
        ]
        for changes in invalid:
            response = self.finish(changes=changes)
            self.assertEqual(response.status_code, 401, changes)
            self.assertNotIn(cloud_auth.SESSION_COOKIE, response.cookies)
        state, flow_cookie = self.start_flow()
        self.client.cookies.set(cloud_auth.FLOW_COOKIE, flow_cookie)
        bad_state = self.client.get(
            "/api/cloud-auth/callback", params={"state": "wrong", "code": "fixture"}
        )
        self.assertEqual(bad_state.status_code, 400)
        GoogleClient.token = token(nonce="wrong")
        self.client.cookies.set(cloud_auth.FLOW_COOKIE, flow_cookie)
        with patch.object(cloud_auth.httpx, "AsyncClient", GoogleClient):
            bad_nonce = self.client.get(
                "/api/cloud-auth/callback", params={"state": state, "code": "fixture"}
            )
        self.assertEqual(bad_nonce.status_code, 401)
        replay_state, replay_cookie = self.start_flow()
        with cloud_auth._db(cloud_auth.config()) as db:
            nonce = db.execute(
                "SELECT nonce FROM flows WHERE state_hash=?", (cloud_auth._hash(replay_state),)
            ).fetchone()["nonce"]
        GoogleClient.token = token(nonce=nonce)
        parts = GoogleClient.token.split(".")
        GoogleClient.token = ".".join(
            [parts[0], parts[1], parts[2][:-1] + ("a" if parts[2][-1] != "a" else "b")]
        )
        self.client.cookies.set(cloud_auth.FLOW_COOKIE, replay_cookie)
        with patch.object(cloud_auth.httpx, "AsyncClient", GoogleClient):
            bad_signature = self.client.get(
                "/api/cloud-auth/callback", params={"state": replay_state, "code": "fixture"}
            )
            replay = self.client.get(
                "/api/cloud-auth/callback", params={"state": replay_state, "code": "fixture"}
            )
        self.assertEqual(bad_signature.status_code, 401)
        self.assertEqual(replay.status_code, 400)

    def test_every_api_group_is_protected_and_origin_is_checked(self):
        for path in [
            f"/api/projects/inspect?path={self.project_path}",
            f"/api/projects/research-sessions?path={self.project_path}",
            f"/api/projects/research-executions?path={self.project_path}",
        ]:
            self.assertEqual(self.client.get(path).status_code, 401, path)
        # My Work is an isolated, empty guest workspace; protected member
        # endpoints above must still reject the anonymous caller.
        self.assertEqual(self.client.get("/api/projects/recent").json(), {"projects": []})
        rejected = self.client.post(
            "/api/projects/close",
            json={"path": str(self.project_path)},
            headers={"Origin": "https://attacker.test"},
        )
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(self.client.get("/api/ai/connection").status_code, 401)

    def test_missing_config_fails_closed_and_local_mode_remains_available(self):
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "true",
                "GOOGLE_OIDC_CLIENT_ID": "",
                "GOOGLE_OIDC_CLIENT_SECRET": "",
                "SIGMA_CLOUD_PUBLIC_ORIGIN": "",
                "SIGMA_CLOUD_AUTH_HOME": "",
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "",
            },
        ):
            self.assertIsNotNone(cloud_auth.config().error)
            self.assertEqual(self.client.get("/api/projects/research-executions").status_code, 503)
        with patch.dict(os.environ, {"SIGMA_CLOUD_AUTH_ENABLED": "false"}):
            self.assertFalse(self.client.get("/api/cloud-auth/status").json()["enabled"])
            self.assertEqual(self.client.get("/api/research-tools").status_code, 200)

    def test_local_status_reports_missing_admin_contact_without_exposing_credentials(self):
        with patch.dict(
            os.environ,
            {
                "SIGMA_CLOUD_AUTH_ENABLED": "false",
                "GOOGLE_OIDC_CLIENT_ID": CLIENT_ID,
                "GOOGLE_OIDC_CLIENT_SECRET": "local-test-secret",
                "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "",
            },
        ):
            response = self.client.get("/api/cloud-auth/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["enabled"])
        self.assertEqual(body["local_setup_missing"], ["SIGMA_CLOUD_ADMIN_CONTACT_EMAIL"])
        self.assertNotIn("local-test-secret", response.text)
        self.assertNotIn("admin@example.org", response.text)


if __name__ == "__main__":
    main()
