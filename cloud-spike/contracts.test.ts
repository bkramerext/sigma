import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { Miniflare } from "miniflare";
import { SpikeStore } from "./store.ts";

test("D1/R2 concurrency, ownership, restart and ambiguous dispatch", async () => {
  const state = await mkdtemp(join(tmpdir(), "sigma-t221-"));
  const options = {
    modules: true,
    script: "export default {fetch(){return new Response('internal test binding')}}",
    compatibilityDate: "2026-07-30",
    d1Databases: ["DB"], r2Buckets: ["ARTIFACTS"],
    d1Persist: join(state, "d1"), r2Persist: join(state, "r2"),
  };
  let runtime = new Miniflare(options);
  async function connect() {
    const db = await runtime.getD1Database("DB");
    const r2 = await runtime.getR2Bucket("ARTIFACTS");
    // Miniflare's Node proxy types differ from workerd's binding declarations.
    return new SpikeStore(db as unknown as D1Database, r2 as unknown as R2Bucket);
  }
  try {
    let store = await connect();
    const schema = await readFile(new URL("schema.sql", import.meta.url), "utf8");
    const statements = schema.replace(/^--.*$/gm, "")
      .split(/(?=CREATE (?:TABLE|TRIGGER))/).map(sql => sql.trim()).filter(Boolean);
    await store.db.batch(statements.map(sql => store.db.prepare(sql)));
    await store.db.batch([
      store.db.prepare("INSERT INTO budgets(scope,ceiling,concurrency) VALUES('global',5,3)"),
      ...["alice", "bob", "carol"].map(owner => store.db.prepare(
        "INSERT INTO budgets(scope,ceiling,concurrency) VALUES(?,2,1)",
      ).bind(owner)),
      store.db.prepare("INSERT INTO projects(id,owner,document) VALUES('p','alice','original')"),
    ]);
    const writes = await Promise.all(Array.from({ length: 20 }, (_, i) =>
      store.revise("alice", "p", 0, `revision-${i}`)));
    assert.equal(writes.filter(Boolean).length, 1, "exactly one CAS revision wins");
    assert.equal(await store.revise("bob", "p", 1, "foreign"), false);

    // Batch failures roll back preceding statements, not just the bad update.
    await assert.rejects(store.db.batch([
      store.db.prepare("UPDATE projects SET document='must roll back' WHERE id='p'"),
      store.db.prepare("UPDATE budgets SET spent=100 WHERE scope='global'"),
    ]));
    assert.notEqual(await store.db.prepare("SELECT document FROM projects WHERE id='p'").first("document"), "must roll back");

    const duplicates = await Promise.all(Array.from({ length: 12 }, (_, i) =>
      store.enqueue("alice", `duplicate-${i}`, "same-request")));
    assert.equal(new Set(duplicates.map(job => job!.id)).size, 1);
    const alice = duplicates[0]!.id;
    await store.enqueue("bob", "b", "b");
    await store.enqueue("carol", "c", "c");
    await store.enqueue("alice", "waiting", "waiting");
    const contenders = await Promise.all(Array.from({ length: 20 }, (_, i) =>
      store.claim("alice", alice, `alice-${i}`, 0)));
    assert.equal(contenders.filter(Boolean).length, 1);
    await assert.rejects(store.claim("alice", "waiting", "blocked", 0));
    assert.equal((await store.get("alice", "waiting"))!.state, "queued");
    assert.equal(await store.claim("bob", alice, "foreign", 0), false);
    assert.equal(await store.claim("bob", "b", "b-lease", 0), true);
    assert.equal(await store.claim("carol", "c", "c-lease", 0), true);
    await store.db.prepare("UPDATE budgets SET concurrency=2 WHERE scope='alice'").run();
    await assert.rejects(store.claim("alice", "waiting", "global-slot-denied", 0), /global limit/);
    await store.db.prepare("UPDATE budgets SET concurrency=1 WHERE scope='alice'").run();
    assert.equal(await store.get("carol", alice), null);
    assert.equal(await store.finish("carol", "b", "b-lease", "foreign"), false);
    assert.equal(await store.finish("bob", "b", "wrong-lease", "stale"), false);
    const completions = await Promise.all(Array.from({ length: 6 }, () =>
      store.finish("bob", "b", "b-lease", "saved output")));
    assert.equal(completions.filter(Boolean).length, 1, "one completion checkpoint wins");
    assert.equal(await store.result("alice", "b"), null);

    // R2 publication without the D1 checkpoint cannot be claimed as recovery.
    await store.artifacts.put("orphan-from-killed-publisher", "not checkpointed");
    await runtime.dispose();
    runtime = new Miniflare(options);
    store = await connect();
    assert.equal(await store.result("bob", "b"), "saved output");
    assert.equal((await store.get("alice", "waiting"))!.state, "queued");
    await store.recover(60_001);
    for (const [owner, id] of [["alice", alice], ["carol", "c"]]) {
      assert.equal((await store.get(owner, id))!.state, "uncertain");
      assert.equal(await store.claim(owner, id, "must-not-replay", 70_000), false);
      assert.equal(await store.result(owner, id), null);
    }
    assert.equal(await store.finish("carol", "c", "c-lease", "late result"), false);
    assert.equal((await store.db.prepare("SELECT spent FROM budgets WHERE scope='global'").first("spent")), 3);
    // Queued work can resume after restart, but ambiguous calls stay charged.
    assert.equal(await store.claim("alice", "waiting", "new", 70_000), true);
    await store.recover(140_000);
    await store.enqueue("alice", "over-user-budget", "new-request");
    await assert.rejects(store.claim("alice", "over-user-budget", "denied", 140_000));
    assert.equal(await store.claim("bob", "b", "duplicate-success", 140_000), false);
    await store.enqueue("bob", "b2", "b2");
    await store.enqueue("carol", "c2", "c2");
    const final = await Promise.allSettled([
      store.claim("bob", "b2", "b2", 140_000),
      store.claim("carol", "c2", "c2", 140_000),
    ]);
    assert.equal(final.filter(r => r.status === "fulfilled" && r.value).length, 1);
    assert.equal(await store.db.prepare("SELECT spent FROM budgets WHERE scope='global'").first("spent"), 5);
    await store.enqueue("bob", "cancel", "cancel");
    await store.stop("bob", "cancel");
    assert.equal(await store.claim("bob", "cancel", "denied", 140_000), false);
    // Fail closed on missing/corrupt committed output.
    const saved = (await store.get("bob", "b"))!;
    await store.artifacts.put(saved.artifact_key!, "tampered");
    await assert.rejects(store.result("bob", "b"), /digest mismatch/);
    await store.artifacts.delete(saved.artifact_key!);
    await assert.rejects(store.result("bob", "b"), /Missing committed/);
  } finally {
    await runtime.dispose();
    await rm(state, { recursive: true, force: true });
  }
});
