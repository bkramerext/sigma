import { copyFileSync } from 'node:fs';
import { defineConfig } from 'vite';

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
  server: { proxy: { '/api': process.env.SIGMA_API_TARGET ?? 'http://127.0.0.1:8000' } },
});
