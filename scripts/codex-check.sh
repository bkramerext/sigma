#!/usr/bin/env bash
# Safe, read-only preflight. Diagnostic output deliberately omits identities,
# command output, addresses, and authentication material.
set -u
_script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" 2>/dev/null && pwd -P) || exit 1
. "$_script_dir/codex-env.sh" || exit 1

overall=PASS
blocked=0
fail=0
gcp_ready=1
report() { printf '%-7s %s\n' "$1" "$2"; }
failed() { fail=1; overall=FAIL; report FAIL "$1"; }
is_blocked() { [ "$fail" -eq 0 ] && overall=BLOCKED; blocked=1; report BLOCKED "$1"; }

for tool in git gh gcloud ssh; do
  if command -v "$tool" >/dev/null 2>&1; then report PASS "$tool available"; else failed "$tool missing"; fi
done
if type -P codex >/dev/null 2>&1 && [ "$(type -P codex)" != "$_script_dir/codex" ]; then
  report PASS 'Codex CLI available'
else
  failed 'Codex CLI missing'
fi

if ! command -v gcloud >/dev/null 2>&1; then
  failed 'gcloud missing; GCP authentication and configuration not checked'
  gcp_ready=0
else
  _auth=$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null)
  _auth_rc=$?
  if [ "$_auth_rc" -ne 0 ]; then failed 'GCP authentication check failed'; gcp_ready=0
  elif [ -z "$_auth" ]; then failed 'GCP authentication missing'; gcp_ready=0
  else report PASS 'GCP authentication active (identity withheld)'; fi
  unset _auth
  _project=$(gcloud config get-value project 2>/dev/null); _project_rc=$?
  _zone=$(gcloud config get-value compute/zone 2>/dev/null); _zone_rc=$?
  if [ "$_project_rc" -eq 0 ] && [ "$_project" = "$SIGMA_GCP_PROJECT" ]; then report PASS 'GCP project configured'; else failed 'GCP project missing or differs from SIGMA configuration'; gcp_ready=0; fi
  if [ "$_zone_rc" -eq 0 ] && [ "$_zone" = "$SIGMA_GCP_ZONE" ]; then report PASS 'GCP zone configured'; else failed 'GCP zone missing or differs from SIGMA configuration'; gcp_ready=0; fi
  unset _project _zone

  if [ "$gcp_ready" -eq 1 ]; then
    _probe=$(python3 - "$(command -v gcloud)" "$SIGMA_GCE_VM" "$SIGMA_GCP_PROJECT" "$SIGMA_GCP_ZONE" <<'PY'
import subprocess, sys

try:
    p = subprocess.run(
        [sys.argv[1], "compute", "ssh", sys.argv[2], "--project=" + sys.argv[3],
         "--zone=" + sys.argv[4], "--tunnel-through-iap", "--command=true", "--quiet"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30,
    )
    detail = (p.stdout + "\n" + p.stderr).lower()
    if p.returncode == 0:
        print("PASS   read-only SSH connectivity to configured VM")
    elif any(x in detail for x in ("permission_denied", "permission denied", "403", "not authorized", "does not have")):
        print("FAIL   SSH permission denied")
    elif any(x in detail for x in ("not authenticated", "reauth", "invalid_grant", "no active account")):
        print("FAIL   GCP authentication unavailable for SSH")
    elif any(x in detail for x in ("timed out", "timeout", "network is unreachable", "connection refused", "could not connect", "dns")):
        print("BLOCKED SSH network connectivity failed")
    else:
        print("BLOCKED SSH connectivity failed (cause not classified)")
except subprocess.TimeoutExpired:
    print("BLOCKED SSH connectivity timed out")
PY
    )
    _probe_rc=$?
    if [ "$_probe_rc" -ne 0 ]; then
      is_blocked 'SSH connectivity check could not run (Python unavailable)'
    else
      case "$_probe" in
        PASS\ *) report PASS 'read-only SSH connectivity to configured VM' ;;
        FAIL\ *) failed "${_probe#FAIL   }" ;;
        BLOCKED\ *) is_blocked "${_probe#BLOCKED }" ;;
        *) is_blocked 'SSH connectivity result unavailable' ;;
      esac
    fi
  else
    is_blocked 'SSH connectivity not attempted because authentication, project, or zone preflight failed'
  fi
fi

report "$overall" 'preflight summary'
[ "$overall" = PASS ]
