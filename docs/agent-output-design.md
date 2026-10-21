# Future mathematical output reader

A later assignment can add a read-only run transcript independently of scheduling
or agent execution. This is a design proposal; no agent runtime or transcript
renderer is implemented in A9.

Persist an append-only stream with stable run/event IDs, sequence numbers,
timestamps and typed payloads: public progress summaries, formal claims,
tests, tool actions/results, artifact links, warnings and final outcomes. Keep
claims distinct from verified proofs, and retain evidence/artifact references.
Never expose or imply access to hidden model chain-of-thought.

Render explicit public Markdown with inline/display LaTeX using a reviewed
react-markdown + remark-math + rehype-katex pipeline. Disable raw HTML and KaTeX
trust, restrict link/image schemes, sanitize any allowed extensions, bound content
size, and avoid remote-content execution. Add accessible code highlighting,
copy/select controls and exact original Markdown/LaTeX export; rendered HTML is
not the source of truth.

SSE can deliver persisted events with Last-Event-ID replay. Commit ordered events
before publishing, deduplicate stable IDs on reconnect, and show a clear paused/
disconnected state rather than inventing missing progress. Buffer incomplete
Markdown/math blocks during streaming and render on bounded stable boundaries
to avoid flicker or broken equations. Reload should restore the same ordered
transcript; older steps can fold without dropping source, and artifacts open
independently. Start with a fixture-driven reader and replay/export checks before
connecting any executor. Provider reasoning internals are outside this contract.
