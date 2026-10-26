#!/usr/bin/env bash
# Build both application images from one clean, exact Git release checkout.
set -Eeuo pipefail
fail() { echo "FAIL: $*" >&2; exit 1; }
[[ $# -eq 1 && $1 =~ ^[0-9a-f]{40}$ ]] || fail 'usage: build-release-images.sh RELEASE_40_CHAR_SHA'
release=$1
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
git -C "$root" rev-parse --verify HEAD >/dev/null || fail 'release source is not a Git checkout'
actual=$(git -C "$root" rev-parse HEAD)
[[ $actual == "$release" ]] || fail "checkout HEAD $actual does not match requested release $release"
[[ -z $(git -C "$root" status --porcelain) ]] || fail 'release checkout must have a clean worktree and index'
for target in backend frontend; do
  case $target in
    backend) dockerfile=Dockerfile ;;
    frontend) dockerfile=deploy/frontend.Dockerfile ;;
  esac
  docker build --pull --tag "sigma-$target:$release-staging" \
    --label "org.opencontainers.image.revision=$release" \
    --file "$root/$dockerfile" "$root" || fail "$target release image build failed; do not change SIGMA_RELEASE"
done
docker image tag "sigma-backend:$release-staging" "sigma-backend:$release"
docker image tag "sigma-frontend:$release-staging" "sigma-frontend:$release"
docker image rm "sigma-backend:$release-staging" "sigma-frontend:$release-staging" >/dev/null
echo "PASS: backend and frontend images built from clean release $release"
