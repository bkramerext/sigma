/** Loopback-only UI preview. Never forwards forged administrator identity to FastAPI. */
import type { IncomingMessage, ServerResponse } from 'node:http';

type Rule = { kind: 'email' | 'domain'; value: string; role: 'member' | 'admin'; active: number; allowance_usd: number | null; effective_allowance_usd: number };
const rules = new Map<string, Rule>();
const email = 'admin-preview@local.invalid';

function json(response: ServerResponse, code: number, value: unknown): void {
  response.writeHead(code, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
  response.end(JSON.stringify(value));
}

function isLoopback(request: IncomingMessage): boolean {
  const remote = request.socket.remoteAddress;
  const host = request.headers.host?.split(':')[0];
  return (remote === '127.0.0.1' || remote === '::1' || remote === '::ffff:127.0.0.1')
    && (host === '127.0.0.1' || host === 'localhost' || host === '[::1]');
}

async function body(request: IncomingMessage): Promise<unknown> {
  let value = '';
  for await (const chunk of request) {
    value += String(chunk);
    if (value.length > 4096) throw new Error('Request is too large.');
  }
  return JSON.parse(value);
}

export async function adminPreview(request: IncomingMessage, response: ServerResponse): Promise<boolean> {
  const url = new URL(request.url ?? '/', 'http://127.0.0.1');
  if (!url.pathname.startsWith('/api/cloud-auth/') && url.pathname !== '/api/cloud-research/budget') return false;
  if (!isLoopback(request)) {
    json(response, 403, { error: 'Admin preview is loopback-only.' });
    return true;
  }
  if (url.pathname === '/api/cloud-research/budget' && request.method === 'GET') {
    json(response, 200, { allowance_usd: 2, estimated_usage_usd: 0, held_usd: 0, remaining_usd: 2, unknown_provider_attempts: 0 });
    return true;
  }
  if (url.pathname === '/api/cloud-auth/status' && request.method === 'GET') {
    json(response, 200, { preview: true, enabled: true, ready: true, authenticated: true,
      user: { email, role: 'admin' }, admin_contact_email: email });
    return true;
  }
  if (url.pathname === '/api/cloud-auth/admin/grants' && request.method === 'GET') {
    json(response, 200, { grants: [...rules.values()], sessions: [], bootstrap_admin: email });
    return true;
  }
  if (url.pathname === '/api/cloud-auth/admin/grants' && request.method === 'POST') {
    try {
      const input = await body(request) as Record<string, unknown>;
      const kind = input.kind;
      const value = typeof input.value === 'string' ? input.value.trim().toLowerCase() : '';
      const role = kind === 'domain' ? 'member' : input.role;
      if ((kind !== 'email' && kind !== 'domain') || !value ||
          (role !== 'member' && role !== 'admin') ||
          (kind === 'email' && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value)) ||
          (kind === 'domain' && !/^[a-z0-9-]+(?:\.[a-z0-9-]+)+$/.test(value))) {
        json(response, 422, { error: 'Enter a valid email address or domain.' });
        return true;
      }
      const amount = input.allowance_usd;
      if (amount !== null && amount !== undefined && (typeof amount !== 'number' || !Number.isFinite(amount) || amount < 0.01 || amount > 15)) {
        json(response, 422, { error: 'Invalid allowance.' }); return true;
      }
      const allowance_usd = typeof amount === 'number' ? amount : null;
      const rule: Rule = { kind, value, role, active: 1, allowance_usd, effective_allowance_usd: allowance_usd ?? 2 };
      rules.set(`${kind}:${value}`, rule);
      json(response, 200, rule);
    } catch {
      json(response, 400, { error: 'Invalid preview request.' });
    }
    return true;
  }
  const prefix = '/api/cloud-auth/admin/grants/';
  if (url.pathname.startsWith(prefix) && request.method === 'PUT' && url.pathname.endsWith('/allowance')) {
    const parts = url.pathname.slice(prefix.length, -'/allowance'.length).split('/');
    const kind = parts.shift();
    let value: string;
    try { value = decodeURIComponent(parts.join('/')).toLowerCase(); }
    catch { json(response, 400, { error: 'Invalid rule.' }); return true; }
    const key = `${kind}:${value}`;
    const rule = rules.get(key);
    if (!rule) { json(response, 404, { error: 'Preview rule not found.' }); return true; }
    try {
      const input = await body(request) as Record<string, unknown>;
      const amount = input.allowance_usd;
      if (amount !== null && (typeof amount !== 'number' || !Number.isFinite(amount) || amount < 0.01 || amount > 15)) {
        json(response, 422, { error: 'Invalid allowance.' }); return true;
      }
      const allowance_usd = amount as number | null;
      rules.set(key, { ...rule, allowance_usd, effective_allowance_usd: allowance_usd ?? 2 });
      json(response, 200, { kind, value, allowance_usd });
    } catch { json(response, 400, { error: 'Invalid preview request.' }); }
    return true;
  }
  if (url.pathname.startsWith(prefix) && request.method === 'DELETE') {
    const parts = url.pathname.slice(prefix.length).split('/');
    const kind = parts.shift();
    let value: string;
    try { value = decodeURIComponent(parts.join('/')).toLowerCase(); }
    catch { json(response, 400, { error: 'Invalid rule.' }); return true; }
    if ((kind !== 'email' && kind !== 'domain') || !rules.has(`${kind}:${value}`)) {
      json(response, 404, { error: 'Preview rule not found.' });
    } else {
      rules.set(`${kind}:${value}`, { ...rules.get(`${kind}:${value}`)!, active: 0 });
      json(response, 200, { kind, value, active: false });
    }
    return true;
  }
  if (url.pathname === '/api/cloud-auth/logout' && request.method === 'POST') {
    response.writeHead(204); response.end(); return true;
  }
  json(response, 404, { error: 'Preview does not provide cloud authentication or live provider access.' });
  return true;
}
