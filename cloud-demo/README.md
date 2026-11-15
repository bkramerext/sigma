# Curated hosted Demo snapshot

`handshake-demo-audit.json` is the single public audit snapshot used by hosted
guest routes. Its project content is adapted from the approved
`samples/handshake-count-easy/project.json` sample. The stable Demo IDs and
timestamps make the checked-in snapshot reproducible. The saved session,
outcome, analysis, and finite Python example are illustrative curated data; they
are read as captured content and are never generated or executed by guest
requests. The result is explicitly limited to n = 1 through 5 and does not
replace the general counting argument.

Configure `SIGMA_CLOUD_DEMO_AUDIT` to an absolute path to this file in the cloud
deployment. Keep that file service-readable and deployment-managed; the guest
API has no caller-selected path and exposes no write operation. The curated
snapshot must remain outside private workspace storage.
