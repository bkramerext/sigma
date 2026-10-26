#!/usr/bin/env bash
# Shared, repository-local environment for SIGMA Codex workers.
# Safe to source repeatedly; this file never changes global gcloud settings.

_sigma_codex_env_source=${BASH_SOURCE[0]}
_sigma_codex_env_dir=$(cd -- "$(dirname -- "$_sigma_codex_env_source")" 2>/dev/null && pwd -P) || return 1
SIGMA_REPO_ROOT=$(cd -- "$_sigma_codex_env_dir/.." 2>/dev/null && pwd -P) || return 1
export SIGMA_REPO_ROOT

# Values confirmed in the existing authenticated gcloud context and runbook.
export SIGMA_GCP_PROJECT=${SIGMA_GCP_PROJECT:-sigma-research-prod}
export SIGMA_GCP_ZONE=${SIGMA_GCP_ZONE:-us-west1-b}
export SIGMA_GCE_VM=${SIGMA_GCE_VM:-sigma-gce-01}
export SIGMA_GCE_HOSTNAME=${SIGMA_GCE_HOSTNAME:-sigma-research.duckdns.org}

# Add common user-managed tool locations when present. No credentials are read,
# copied, or created here, and no Docker socket is assumed.
for _sigma_codex_candidate in \
  "$HOME/.local/bin" "$HOME/bin" \
  "$HOME/google-cloud-sdk/bin" \
  /opt/homebrew/bin /usr/local/bin /usr/bin /bin; do
  if [ -d "$_sigma_codex_candidate" ]; then
    case ":${PATH-}:" in
      *":$_sigma_codex_candidate:"*) ;;
      *) PATH="$_sigma_codex_candidate${PATH:+:$PATH}" ;;
    esac
  fi
done
export PATH
unset _sigma_codex_candidate _sigma_codex_env_source _sigma_codex_env_dir
