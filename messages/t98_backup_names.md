# T98 backup correction


Found two defects during coordinator source review of daily backups: generated
snapshot names used uppercase T/Z, contrary to GCE's lowercase resource-name
contract; and an empty retention plan printed a blank line that the shell
consumer rejected as an invalid deletion candidate. Use lowercase timestamp
separators consistently and emit no lines when nothing should be deleted.

All 10 offline state-backup tests pass, including generated-name validation
against the GCE contract and empty-plan stdout. Ruff check/format, shell syntax,
and diff whitespace checks pass. Full `./sigma test` completed with environment failures: SOCKS support missing
for workspace/storage/cloud HTTP checks, restricted sockets in ownership/UI
registry checks, and absent frontend dependencies (`tsc`); build was skipped.
Workspace and cloud API checks pass when proxy variables are removed. All
backup/deployment/monitor checks, Ruff and Pyright pass. No full-suite PASS is
claimed. Shell push was unavailable; owner authorized publication through the GitHub connector.
No GCE snapshot, deletion, deployment, live inference, or production operation
was performed. Live scheduler/restore acceptance remains unverified. Reference:
https://docs.cloud.google.com/compute/docs/reference/rest/v1/snapshots
