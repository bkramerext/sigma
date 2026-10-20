import { copyFileSync } from 'node:fs';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [{
    name: 'sigma-canonical-artwork',
    buildStart() {
      for (const name of ['sigma-home-background.png', 'sigma-workspace-logo.png']) {
        copyFileSync(new URL(`../assets/${name}`, import.meta.url), new URL(`./public/${name}`, import.meta.url));
      }
    },
  }],
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
});
