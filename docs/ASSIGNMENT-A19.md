# A19 — Autonomous Python execution for research agents

**Status:** integrated with A18's portfolio Investigator/Skeptic loop. This
assignment extends A18's local research loop without waiting for the open
A17.8 research-quality gate.

## Goal

Allow a bounded research Investigator to propose Python code, run it against
scientific Python libraries in a fresh isolated container, and have the Skeptic
inspect both the code and its captured result. Preserve the existing research
session, call-budget, cancellation, artifact, and uncertainty contracts. A
computation is evidence for the executed finite computation only; it is not a
proof of a general mathematical claim.

## Prerequisite review

- A20 is merged in `origin/main` (PR #5); this A19 branch starts from that
  merged main.
- `docs/ASSIGNMENT-A18.md` is active and being handled concurrently in another
  checkout. Its portfolio role-call seam is the integration point. A19 was
  initially based on reviewed A18 commit `1114aba` and has since merged the
  latest A18 branch head into the Green feature branch; Blue's branch remains
  untouched and the PR's net diff contains A19 work only.
- A17.8 remains an open research-acceptance gate in `docs/STATUS.md`. It limits
  claims about autonomous research quality, but does not block implementing a
  strictly bounded local computation facility.
- A prior A19 specification was not present on merged main. Earlier A14 and
  A18 documentation explicitly said no code was executed; this assignment
  supersedes that limitation for research sessions only.
- `docs/LEAN_VERIFICATION_PLAN.md` remains a future, separate formal-checking
  proposal. Python execution does not provide Lean verification or formal proof.

## Required behavior

1. Develop and demonstrate a standalone proof of concept before integrating it.
2. Run only in a locally built, pinned scientific-Python image. Runtime must
   never pull or build images and must disable all container networking.
3. Enforce bounded source, wall time, memory, CPU, process count, writable
   storage, and returned output. Use a non-root UID, read-only root filesystem,
   no capabilities, and no-new-privileges. Do not mount the checkout, project,
   credentials, or host home into the container.
4. Provide NumPy, SciPy, pandas, SymPy, and Matplotlib in the image.
5. Integrate optional Investigator `python_code` into the portfolio
   Investigator → Skeptic cycle. Keep code, execution record, and file metadata
   in the durable session evidence with project/session/strategy/cycle
   provenance. The Skeptic receives source, status, exit code, stdout/stderr,
   execution ID, and captured file metadata. Unsupported execution, timeout, or
   nonzero exit remains visible and is never labeled a successful test.
6. Keep execution synchronous per Investigator proposal: no autonomous repair
   loop or extra provider calls. Cancellation/worker interruption must retain
   truthful state and never claim a result that was not captured.
7. Do not let research code access the network. A build-time package-install
   network is distinct from execution networking and must not be available in
   runtime containers.
8. Add deterministic validation for command constraints, input/output limits,
   timeout/error behavior, and session artifact/context propagation. Where a
   container engine is available, perform actual isolated runs including an
   attempted network connection and resource-limit behavior.

## Verification and reporting

Run `./sigma test`, relevant browser checks, lint/type checks via the project
test command, and an actual local container smoke test if the runtime is
available. Record exact outcomes and any engine limitation in `docs/STATUS.md`.
Do not use live provider calls or claim independent mathematical verification.
Keep the PR based on the active A18 integration branch until A18 lands; do not
self-merge.
