import { copyFileSync } from 'node:fs';
import { env } from 'node:process';
import { defineConfig } from 'vite';
import { adminPreview } from './admin-preview';

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
  plugins: env.SIGMA_ADMIN_PREVIEW === 'true' ? [{
    name: 'sigma-loopback-admin-preview',
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        void adminPreview(request, response).then(handled => { if (!handled) next(); })
          .catch(() => { response.writeHead(500); response.end('Preview failed.'); });
      });
    },
  }] : [],
  server: { proxy: { '/api': env.SIGMA_API_TARGET ?? 'http://127.0.0.1:8000' } },
});
