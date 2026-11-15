#!/usr/bin/env bash
# Shared, non-mutative Ubuntu host identity guard for the GCE installer.

require_ubuntu_2404() {
  local release_file=${1:-/etc/os-release}
  local ID VERSION_ID
  if [[ ! -r $release_file ]]; then
    printf 'BLOCKED: host must be Ubuntu 24.04 LTS amd64\n' >&2
    return 2
  fi

  # os-release is a shell assignment file by specification. Sourcing this
  # helper is safe for the trusted system file and controlled test fixtures.
  # shellcheck disable=SC1090
  . "$release_file"
  if [[ ${ID:-} != ubuntu || ${VERSION_ID:-} != 24.04 ]]; then
    printf 'BLOCKED: host must be Ubuntu 24.04 LTS\n' >&2
    return 2
  fi
  return 0
}
