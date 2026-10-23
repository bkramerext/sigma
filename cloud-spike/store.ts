// Internal adapter contract, exercised against real local D1/R2 bindings.
// No HTTP routes, identity verification, scheduler or live provider in this spike.
export interface Job {
  id: string;
  owner: string;
  state: "queued" | "dispatched" | "succeeded" | "uncertain" | "stopped";
  revision: number;
  lease: string | null;
  artifact_key: string | null;
  digest: string | null;
}

export class SpikeStore {
  constructor(readonly db: D1Database, readonly artifacts: R2Bucket) {}

  async enqueue(owner: string, id: string, requestKey: string) {
    // owner must come from a future verified session, never request headers.
    if (owner === "global") throw new Error("Reserved scope");
    await this.db.prepare(
      "INSERT INTO jobs(id,owner,request_key) VALUES(?,?,?) ON CONFLICT(owner,request_key) DO NOTHING",
    ).bind(id, owner, requestKey).run();
    return this.db.prepare("SELECT * FROM jobs WHERE owner=? AND request_key=?")
      .bind(owner, requestKey).first<Job>();
  }

  get(owner: string, id: string) {
    return this.db.prepare("SELECT * FROM jobs WHERE owner=? AND id=?")
      .bind(owner, id).first<Job>();
  }

  async claim(owner: string, id: string, lease: string, now: number) {
    // Persist intent BEFORE dispatch. A crash even just before network I/O is
    // ambiguous; its unit remains spent. Never automatically repeat this call.
    const result = await this.db.prepare(
      `UPDATE jobs SET state='dispatched',lease=?,expires=?,revision=revision+1
       WHERE owner=? AND id=? AND state='queued' RETURNING id`,
    ).bind(lease, now + 60_000, owner, id).first<{ id: string }>();
    // D1 meta.changes includes trigger writes; RETURNING identifies the job.
    return result !== null;
  }

  async recover(now: number) {
    return this.db.prepare(
      `UPDATE jobs SET state='uncertain',revision=revision+1
       WHERE state='dispatched' AND expires<=?`,
    ).bind(now).run();
  }

  async stop(owner: string, id: string) {
    // A dispatched call may still complete/bill. Keep its slot until expiry;
    // cancellation of an external call is not established by a client request.
    return this.db.prepare(
      `UPDATE jobs SET state='stopped',revision=revision+1
       WHERE owner=? AND id=? AND state='queued'`,
    ).bind(owner, id).run();
  }

  async finish(owner: string, id: string, lease: string, body: string) {
    const job = await this.get(owner, id);
    if (!job || job.state !== "dispatched" || job.lease !== lease) return false;
    const bytes = new TextEncoder().encode(body);
    const hash = await crypto.subtle.digest("SHA-256", bytes);
    const digest = Array.from(new Uint8Array(hash), b => b.toString(16).padStart(2, "0")).join("");
    // UUID avoids overwriting committed objects. R2 and D1 have no joint
    // transaction: publish bytes first, then commit their pointer conditionally.
    const key = `results/${crypto.randomUUID()}`;
    const saved = await this.artifacts.put(key, body, { onlyIf: { etagDoesNotMatch: "*" } });
    if (!saved) throw new Error("Artifact key collision");
    const result = await this.db.prepare(
      `UPDATE jobs SET state='succeeded',artifact_key=?,digest=?,revision=revision+1
       WHERE owner=? AND id=? AND state='dispatched' AND lease=?`,
    ).bind(key, digest, owner, id, lease).run();
    // A failed commit leaves an unreferenced object, never a successful job.
    // Future GC must compare against D1 references after a conservative grace.
    return result.meta.changes === 1;
  }

  async result(owner: string, id: string) {
    const job = await this.get(owner, id);
    if (!job || job.state !== "succeeded" || !job.artifact_key) return null;
    const object = await this.artifacts.get(job.artifact_key);
    if (!object) throw new Error("Missing committed artifact");
    const bytes = await object.arrayBuffer();
    const hash = await crypto.subtle.digest("SHA-256", bytes);
    const digest = Array.from(new Uint8Array(hash), b => b.toString(16).padStart(2, "0")).join("");
    if (digest !== job.digest) throw new Error("Artifact digest mismatch");
    return new TextDecoder().decode(bytes);
  }

  async revise(owner: string, id: string, revision: number, document: string) {
    const result = await this.db.prepare(
      "UPDATE projects SET revision=revision+1,document=? WHERE owner=? AND id=? AND revision=?",
    ).bind(document, owner, id, revision).run();
    return result.meta.changes === 1;
  }
}
