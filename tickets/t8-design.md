# A8 design and compatibility

One shared Create/Edit dialog owns name, problem, mode, model and Thinking level.
Create previews a managed destination; Edit shows the unchanged location and saves
one atomic settings transaction. A small pencil next to the main project title
opens Edit. Cancel/Escape and success restore the initiating button's focus.

Schema v6 persists model/effort and project.updated before/after snapshots. Older
formats derive a deterministic documented Sol/High default without rewriting.
All new init/create operations write v6. Real edits/acceptance of reasoning provenance migrate old files;
existing manual strategy write versions remain compatible. Compare the complete
settings snapshot under the existing lock to reject stale settings editors while
allowing independent strategy writes. UUID/path/order/archives stay fixed.

Reviewed catalog: Sol, Luna, Astra, with explicit low/medium/high/xhigh options.
Official model pages verify Responses, text, structured output and effort support.
No numerical pricing. Account discovery intersects only these reviewed IDs, with
bounded cached GET /v1/models. Offline settings remain editable; unavailable or
historical selections stay visible and cannot be silently replaced. Sol/High is
the documented preferred default; without discovery it is clearly unverified.
No generation substitutes another model or drops reasoning.

A quiet top-right status dot/text/details checks authentication once per app load,
with shared server cache/coalescing and explicit Retry. Green requires fresh HTTP
200 and validated model-list JSON, not just environment variables. Authentication,
permissions, rate limits and network failures get distinct safe messages. No paid
generation for status checks. Expired success becomes Stale until refreshed.

Generation snapshots settings/context together, sends reasoning.effort and raises
the bounded output budget to 25,000 including reasoning. Receipt carries actual
returned model plus requested effort; old provenance has no invented effort.
Close remains navigation only. Future real running agents will need an explicit
active-work/continue confirmation policy; no imaginary work is introduced now.

Cost labels are relative tiers ($/$$/$$$) linked to official current pricing; no
model-list response is treated as token pricing. A fresh-dev check found the old
asset copier ran after Vite's public scan. Move it to config evaluation so the
unchanged canonical Home PNG is present on first launch.
