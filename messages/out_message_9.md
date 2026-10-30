# Round 9 — controlled claim-detail experiment

Blue: Regenerate the same four saved projects (Maximum Regions, Nonconsecutive Subset Sums, Xenopus Tadpoles, Operation Narrow Passage) using coordinator branch chat/336-paper-editorial-prompts at commit d4b9ab0ce55a7f05e053b43f96704528a676248c. Verify the exact commit object before starting.

Paper-generation configurability changed from one combined option to three independent checkboxes: Include claim details, Include validation notes, and Include research excerpts. Claim details now defaults ON and the choices persist per project in the browser. For EVERY round-9 generation explicitly set Include claim details ON, Include validation notes OFF, Include research excerpts OFF. Report the actual submitted settings, not just the visible defaults. Do not change the other variables.

Review each actual rendered PDF, not merely the .txt companion: verify every [C#] reference resolves to a definition, inspect mathematical expressions across the document, check Xenopus statistical notation and title punctuation, and record any escaped dollar signs or literal TeX commands. Specifically examine Nonconsecutive set braces after the coordinator's math-validator fix. Compare evidence-omission counts in PDF versus generation metadata, and assess ONP abstract, narrative flow, constructive reasoning, and planning latency. Report findings, elapsed times, PDF/TeX/TXT artifact paths and exact code SHA in messages/in_message_9.md.

Execution only: do not modify source, run tests/CI, merge, deploy, or start new research sessions. Preserve existing project and paper artifacts. Do not coordinate or communicate directly with other Codex workers; report dependencies, conflicts and requests through the ChatGPT coordinator via the human.

## Coordinator's independent round-8 manuscript inspection (added before Blue resumes)

The coordinator reviewed the complete four generated TeX manuscripts, not the binary PDFs. Additional concrete issues:
- ONP: fallback abstract quotes an internal session-status string as a research finding; conclusion is generic; raw source-path/schema keys leak into an "Open obligations" list. Inspect the actual PDF and distinguish substantive planning analysis from metadata. Do not infer unsupported operational recommendations.
- Maximum Regions: verification section narrates a disagreement among saved assessment labels even though the manuscript contains a self-contained theorem/proof. Keep research-provenance discussion separate from mathematical argument.
- Nonconsecutive: many literal escaped TeX commands remain; distinguish genuine proof gaps from administrative research to-dos, and inspect math across every page.
- Xenopus: abstract and falsification framing are promising; verify statistical expression and punctuation across pages.

Do not assume these additional observations have all been fixed in code. The coordinator's attempted follow-up fallback-abstract source edit was blocked; it is NOT in the specified code SHA. Report each remaining defect precisely. This is still ROUND 9; do not start round 10. Wait for explicit resume authorization from the human/coordinator before starting generation.
