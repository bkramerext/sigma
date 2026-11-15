# Increment 15 execution-boundary threat model

**Status:** Preflight threat analysis. No paid model calls, no provider credentials, no live sandbox demonstration.

## Trust boundaries

- **Curator/evaluator side:** answer keys, scoring anchors, blinded allocation mapping, adjudications and other-arm responses. These must not be model-visible.
- **Runner side:** only the exact agent packet and frozen shared tool interfaces. The runner must not mount repository contents containing `evaluator_only.md` or expose host filesystem, repo search, browser navigation to raw repository files, or prompts that include grading hints.
- **Accounting side:** provider-signed/returned usage and complete billable request logs; never accept model-authored token/cost estimates as authoritative.
- **Scoring side:** final research artifact plus independent evidence audit; arm labels and orchestration-specific traces must be hidden from graders until scores are sealed.

## Negative controls before any pilot

1. Launch the real target execution environment without evaluator files mounted or accessible; attempt direct path traversal, absolute-path reads, directory listing, tool search, repository fetch, and prompt-injection requests for benchmark keys. Each must fail or demonstrate no route to hidden keys.
2. Repeat attempted cross-arm disclosure from each arm independently.
3. Inject forced provider timeouts, failed tools, malformed usage metadata, and a request that crosses the total token/cost ceiling. Fail closed while retaining all evidence.
4. Test scoring blinding by submitting synthetic outputs with embedded arm hints and verify the blind scorer receives only redacted content or the run is invalidated.
5. Verify a transcript and hash round trip against an independently retained signed/dated frozen manifest. Check model settings, tool inventories and accounting parity on both arms.
6. Demonstrate that a legitimate model call cannot be initiated without a verified approval record naming model/provider/account/caps. **No live probe is authorized yet.**

## Current limits

The allowlisted packet exporter and offline paired fixtures establish correct packet construction and validation of submitted records. They **do not** isolate a model from the filesystem or prove costs against a provider invoice. A direct Python subprocess launched from the repository would not count as adequate isolation. Pilot readiness must remain false until the production runner is independently tested against these controls.

## Research validity

The six synthetic cases test objection handling and calibration but not sustained scientific investigation. The pilot is exploratory and must not be advertised as a product research-quality win. Preserve the extended unscripted multi-session demonstration required by Increment 17.
