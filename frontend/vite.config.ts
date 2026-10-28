import { copyFileSync, readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { defineConfig } from 'vite';

function buildCommit(requireIdentity: boolean): string {
  const supplied = process.env.SIGMA_BUILD_COMMIT ?? process.env.GITHUB_SHA;
  if (supplied) {
    if (!/^[0-9a-f]{7,40}$/.test(supplied)) throw new Error('Invalid SIGMA_BUILD_COMMIT; expected a Git SHA');
    return supplied.slice(0, 7);
  }
  try { return execFileSync('git', ['rev-parse', '--short=7', 'HEAD'], { encoding: 'utf8' }).trim(); }
  catch {
    if (requireIdentity) throw new Error('Production build requires SIGMA_BUILD_COMMIT, GITHUB_SHA, or Git metadata');
    return 'unknown';
  }
}

// Python project metadata is the canonical product version.
function productVersion(): string {
  const metadata = readFileSync(new URL('../pyproject.toml', import.meta.url), 'utf8');
  const section = metadata.split(/^\[project\]\s*$/m)[1]?.split(/^\[/m)[0];
  const version = section?.match(/^version\s*=\s*"([^"]+)"/m)?.[1];
  if (!version) throw new Error('Missing [project].version in pyproject.toml');
  const frontendVersion = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')).version;
  if (frontendVersion !== version) throw new Error('Frontend and Python product versions differ');
  return version;
}

// Copy before Vite scans publicDir. buildStart is too late on a clean dev launch.
for (const name of [
  'sigma-home-background.png',
  'sigma-home-background-copper.png',
  'sigma-slogan-copper-approved.png',
  'sigma-workspace-logo.png',
]) {
  copyFileSync(new URL(`../assets/${name}`, import.meta.url), new URL(`./public/${name}`, import.meta.url));
}

export default defineConfig(({ command }) => ({
  define: {
    __SIGMA_BUILD_COMMIT__: JSON.stringify(buildCommit(command === 'build')),
    __SIGMA_VERSION__: JSON.stringify(productVersion()),
  },
  server: { proxy: { '/api': process.env.SIGMA_API_TARGET ?? 'http://127.0.0.1:8000' } },
}));
