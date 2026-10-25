import { copyFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { defineConfig } from 'vite';

function buildCommit(): string {
  const supplied = process.env.SIGMA_BUILD_COMMIT ?? process.env.GITHUB_SHA;
  if (supplied) return supplied.slice(0, 7);
  try { return execFileSync('git', ['rev-parse', '--short=7', 'HEAD'], { encoding: 'utf8' }).trim(); }
  catch { return 'unknown'; }
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

export default defineConfig({
  define: { __SIGMA_BUILD_COMMIT__: JSON.stringify(buildCommit()) },
  server: { proxy: { '/api': process.env.SIGMA_API_TARGET ?? 'http://127.0.0.1:8000' } },
});
