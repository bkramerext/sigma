import test from "node:test";
import assert from "node:assert/strict";
import worker, { fetchApi, ready, routing } from "../src/index.js";

const env = {
  SIGMA_PUBLIC_ORIGIN: "https://sigma.example.test",
  SIGMA_API_ORIGIN: "https://origin.example.test",
  CF_ACCESS_CLIENT_ID: "test-id",
  CF_ACCESS_CLIENT_SECRET: "test-secret",
};

test("routing requires complete secure exact-origin configuration", () => {
  const url = new URL("https://sigma.example.test/demo");
  assert.ok(routing(env, url));
  assert.equal(routing({ ...env, CF_ACCESS_CLIENT_SECRET: "" }, url), null);
  assert.equal(routing({ ...env, SIGMA_API_ORIGIN: "http://origin.example.test" }, url), null);
  assert.equal(routing(env, new URL("https://attacker.example.test/demo")), null);
});

test("API proxy replaces identity headers and injects the configured Access token", async () => {
  let upstream;
  const response = await fetchApi(new Request("https://sigma.example.test/api/private?x=1", {
    headers: {
      "x-authenticated-user": "attacker@example.test",
      "cf-access-jwt-assertion": "forged",
      origin: "https://sigma.example.test",
    },
  }), env, async (request) => {
    upstream = request;
    return new Response("ok");
  });
  assert.equal(response.status, 200);
  assert.equal(upstream.url, "https://origin.example.test/api/private?x=1");
  assert.equal(upstream.headers.get("x-authenticated-user"), null);
  assert.equal(upstream.headers.get("cf-access-jwt-assertion"), null);
  assert.equal(upstream.headers.get("cf-access-client-id"), "test-id");
  assert.equal(upstream.headers.get("cf-access-client-secret"), "test-secret");
  assert.equal(upstream.headers.get("origin"), "https://sigma.example.test");
});

test("health reports ready only when backend cloud auth is ready", async () => {
  const url = new URL("https://sigma.example.test/healthz");
  const good = await ready(env, url, async () => Response.json({ enabled: true, ready: true }));
  const bad = await ready(env, url, async () => Response.json({ enabled: false, ready: false }));
  assert.equal(good.status, 200);
  assert.equal((await good.json()).ok, true);
  assert.equal(bad.status, 503);
});

test("unconfigured API requests fail closed without exposing settings", async () => {
  const response = await worker.fetch(new Request("https://sigma.example.test/api/health"), {});
  assert.equal(response.status, 503);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.doesNotMatch(await response.text(), /secret|example\.test/);
});
