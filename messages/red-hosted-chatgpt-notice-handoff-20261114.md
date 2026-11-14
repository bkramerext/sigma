# Coordinator handoff — hosted ChatGPT notice WIP

**Branch:** `red/hosted-chatgpt-personal-notice`

## Requested behavior in this WIP

- Deployment flag: `SIGMA_CLOUD_PERSONAL_CHATGPT_NOTICE_ENABLED`, default
  `false` in Compose and `deploy/env.example`.
- The cloud-auth status endpoint reports the flag only when cloud auth is
  enabled, non-local, and the environment value is true. The client opens the
  notice only for the hosted Personal ChatGPT unavailable pill when enabled.
- Dialog copy is exactly: “Unfortunately, Open AI doesn't let us connect using
  personal accounts while using a hosted application. Installing and running
  SIGMA locally allows this.”
- Dialog is centered and uses the standard SIGMA X close control at the upper
  right with its standard copper hover/focus treatment.
- Sponsored ChatGPT pill hovertext is the single sentence “SIGMA covers
  eligible ChatGPT model calls.” The separate allowance control still exposes
  its fuller usage details.
- `browser_checks/local_auth_real_backend.py` includes a hosted status fixture
  assertion for the dialog, copy, close position, and hover effect.

Set `SIGMA_CLOUD_PERSONAL_CHATGPT_NOTICE_ENABLED=true` in the production
`/etc/sigma/deploy.env` to turn the notice on during a guarded deployment; set
it to `false` and redeploy to turn it off. Production has not been changed.

## Required remaining work

1. Resolve the invitation welcome dialog button borders requested earlier.
   Its current `.invitation-welcome-link` rule already sets `border: 0`, so
   inspect the rendered computed styles and identify the overriding selector;
   verify that only “Invite Me” and “Explore as Guest” lose their visible
   borders.
2. Reproduce and pass the new dialog browser assertion. The current local
   browser runs stopped earlier in existing fixture assertions, before the
   hosted-dialog scenario: `local_auth_real_backend.py` expected an existing
   Google cookie to render “Sign out of Google” but saw “Sign in with Google”;
   `local_admin_sponsor_pill.py` stopped at its pre-existing personal-pill
   tooltip assertion. Fix the test setup or isolate a reliable fixture.
3. Correct the built-in administrator identity as part of the next production
   deployment. The operator has confirmed that
   `zetacontinuation@gmail.com` is the intended built-in administrator. Before
   calling the deployment complete, the deployed auth database and
   Administrator Settings must identify zeta as the built-in administrator;
   zeta being an additional admin grant is not sufficient. Production
   inspection found
   `brian.kramer.personal@gmail.com` bound to the persisted `bootstrap_subject`;
   `zetacontinuation@gmail.com` is separately authorized as an admin. Changing
   `SIGMA_CLOUD_ADMIN_CONTACT_EMAIL` alone will not transfer bootstrap status:
   code intentionally preserves an established subject-bound administrator.
   Implement and test a safe, explicit transfer that preserves all projects,
   users, credentials, and audit/accounting data. Verify Brian's resulting
   role/access explicitly and document it; do not copy credentials.
4. Run CI and resolve failures before merging. Local `./sigma test` failed in
   `project_collaboration.py` and `research_qa.py` with temporary-path symlink
   errors on macOS/Python 3.14; the focused cloud-auth tests passed.
5. After review/merge, include the built-in administrator transfer above and
   set `SIGMA_CLOUD_PERSONAL_CHATGPT_NOTICE_ENABLED=true` in the production
   environment if the notice is approved for launch. Deploy using the normal
   guarded production procedure. Neither the production environment nor
   administrator database was changed as part of this WIP request.

## Verification already run

- `tests/cloud_auth_part1.py`: 59 passed, including flag enabled/disabled and
  local-target-off behavior.
- Frontend `npm run typecheck`: passed.
- Frontend `npm run build`: passed (existing chunk-size and mixed dynamic/static
  import advisories).
- Ruff check and format for changed Python/browser files: passed.
- `./sigma test`: failed in the two unrelated filesystem-symlink suites noted
  above; later safe/read-only checks continued and passed.
- The hosted-dialog real-browser assertion is present but not yet reached in a
  passing browser run.
