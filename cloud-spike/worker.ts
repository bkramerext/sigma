import { Container } from "@cloudflare/containers";

// Trusted, read-only compatibility probe. Never execute model-authored code here.
export class FastAPI extends Container {
  defaultPort = 8080;
  sleepAfter = "30s";
  enableInternet = false;
}

export default {
  async fetch(request: Request, env: { API: DurableObjectNamespace<FastAPI> }) {
    const path = new URL(request.url).pathname;
    if (request.method !== "GET" || !["/health", "/events"].includes(path)) {
      return new Response("Not found", { status: 404 });
    }
    // Fixed identity: arbitrary URL paths cannot allocate more instances.
    // Forward no cookies, credentials, identity claims, or client Host header.
    return env.API.getByName("compatibility-probe").fetch(
      new Request(`http://container${path}`),
    );
  },
};
