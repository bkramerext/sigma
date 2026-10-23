const privateIdentityHeaders = new Set([
  "x-authenticated-user",
  "x-forwarded-user",
  "x-remote-user",
  "x-sigma-user",
]);

function fail(message = "SIGMA cloud routing is not configured.") {
  return new Response(JSON.stringify({ error: message }), {
    status: 503,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

function routing(env, requestUrl) {
  if (!env.SIGMA_PUBLIC_ORIGIN || !env.SIGMA_API_ORIGIN ||
      !env.CF_ACCESS_CLIENT_ID || !env.CF_ACCESS_CLIENT_SECRET) return null;
  let publicOrigin;
  let apiOrigin;
  try {
    publicOrigin = new URL(env.SIGMA_PUBLIC_ORIGIN);
    apiOrigin = new URL(env.SIGMA_API_ORIGIN);
  } catch {
    return null;
  }
  const localSmoke = env.SIGMA_LOCAL_SMOKE === "true";
  const loopback = (url) => ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname);
  const secureProductionOrigins = publicOrigin.protocol === "https:" && apiOrigin.protocol === "https:";
  const secureLocalOrigins = localSmoke && publicOrigin.protocol === "http:" && apiOrigin.protocol === "http:" && loopback(publicOrigin) && loopback(apiOrigin);
  if ((!secureProductionOrigins && !secureLocalOrigins) ||
      publicOrigin.username || publicOrigin.password || publicOrigin.pathname !== "/" ||
      publicOrigin.search || publicOrigin.hash || apiOrigin.username || apiOrigin.password ||
      apiOrigin.pathname !== "/" || apiOrigin.search || apiOrigin.hash ||
      publicOrigin.origin !== requestUrl.origin || apiOrigin.origin === publicOrigin.origin) {
    return null;
  }
  return { publicOrigin, apiOrigin };
}

function harden(response, { html = false } = {}) {
  const headers = new Headers(response.headers);
  headers.set("x-content-type-options", "nosniff");
  headers.set("referrer-policy", "strict-origin-when-cross-origin");
  if (html) {
    headers.set("strict-transport-security", "max-age=31536000");
  } else {
    headers.set("cache-control", "no-store");
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function fetchApi(request, env, fetcher = fetch) {
  const incoming = new URL(request.url);
  const targets = routing(env, incoming);
  if (!targets) return fail();
  const target = new URL(incoming.pathname + incoming.search, targets.apiOrigin);
  const upstreamRequest = new Request(target, request);
  const upstreamHeaders = new Headers(upstreamRequest.headers);
  for (const name of [...upstreamHeaders.keys()]) {
    const normalized = name.toLowerCase();
    if (normalized.startsWith("cf-access-") || privateIdentityHeaders.has(normalized)) {
      upstreamHeaders.delete(name);
    }
  }
  upstreamHeaders.set("cf-access-client-id", env.CF_ACCESS_CLIENT_ID);
  upstreamHeaders.set("cf-access-client-secret", env.CF_ACCESS_CLIENT_SECRET);
  try {
    const response = await fetcher(new Request(target, {
      method: request.method,
      headers: upstreamHeaders,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      redirect: "manual",
      duplex: request.body ? "half" : undefined,
    }));
    return harden(response);
  } catch {
    return fail("SIGMA service is temporarily unavailable.");
  }
}

async function ready(env, requestUrl, fetcher = fetch) {
  const targets = routing(env, requestUrl);
  if (!targets) return fail();
  const statusUrl = new URL("/api/cloud-auth/status", targets.apiOrigin);
  try {
    const response = await fetcher(new Request(statusUrl, {
      headers: {
        "cf-access-client-id": env.CF_ACCESS_CLIENT_ID,
        "cf-access-client-secret": env.CF_ACCESS_CLIENT_SECRET,
        accept: "application/json",
      },
      redirect: "manual",
    }));
    if (!response.ok) return fail("SIGMA service is not ready.");
    const body = await response.json();
    if (body.enabled !== true || body.ready !== true) return fail("SIGMA service is not ready.");
    return harden(new Response(JSON.stringify({ ok: true }), {
      headers: { "content-type": "application/json; charset=utf-8" },
    }));
  } catch {
    return fail("SIGMA service is temporarily unavailable.");
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/healthz") {
      if (request.method !== "GET" && request.method !== "HEAD") {
        return new Response("Method not allowed", { status: 405, headers: { allow: "GET, HEAD" } });
      }
      return ready(env, url);
    }
    if (url.pathname === "/api" || url.pathname.startsWith("/api/")) {
      return fetchApi(request, env);
    }
    const targets = routing(env, url);
    if (!targets) return fail();
    try {
      return harden(await env.ASSETS.fetch(request), { html: request.method === "GET" || request.method === "HEAD" });
    } catch {
      return fail("SIGMA web assets are temporarily unavailable.");
    }
  },
};

export { fetchApi, harden, ready, routing };
