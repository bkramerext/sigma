# Phase 2 Iteration 2 — completed protocol archives

These five archival project directories preserve the project identity, strategies, complete session records, artifacts and history for the five Phase 2 investigations. They were copied from `/private/tmp/sigma-phase2-green-i2/projects/`; the source projects remain there. `diff -qr --exclude='*.lock'` verified each archive against its source. Empty runtime lock files are omitted.

“Completed” means the configured two-strategy, three-round protocol has all 12 accepted Investigator/Skeptic role turns. It does **not** establish scientific validity, novelty, or independent source verification. Each session's lifecycle status remains `ended`; its current action is now `Completed · configured protocol`. The only changes to the saved session JSON for this label correction are the `termination_reason_code`, display action/message, `updated_at`, and an additive `session.protocol_complete` event. Accepted steps, invalid attempts, artifacts and evidence are unchanged.

| Project | Project ID | Session ID | Accepted turns | Attempts | Archive tree SHA-256* |
|---|---|---|---:|---:|---|
| AI Agent Reliability and Evaluation v1 | `da4580f5-7620-49b0-882e-aee34fcdc05d` | `e3f02cce-aed5-42f7-aa01-a5cad3c99c18` | 12/12 | 21/21 | `293cef2ff93aeae243aa23bbf0b5e8975deaee196a4385b77f3eb0c0e78ebae1` |
| Sovereign AI Federation v2 | `9175d73d-62aa-4523-a286-445f5390ae1d` | `d82391f1-956a-4546-adfd-20f030e33688` | 12/12 | 18/18 | `89ba5b8410735334622ce7e1fb36fbe0b6f50062cbf9aff94ab53178b783994f` |
| Nonconsecutive Subset Sums Modulo 3 | `7a8cbb3b-da78-4249-8e9e-8f7c15b8ae7a` | `6ce6a07a-c844-4681-a6ec-ede98aa923ea` | 12/12 | 15/18 | `cbd1eb4c09f11445361bcd00851b46d3fed10618781db481c54f5e153c8ae8c1` |
| Warp Drive Design | `e8211dc4-b70f-49d1-a514-671f44ed7e8c` | `71bc9990-fab0-4c1a-b03c-1d6daa976a3e` | 12/12 | 16/18 | `f879967a078e2154bb704e8e2429f5300eba0b7ef49a36ce390f492b5494bc1e` |
| Xenopus Tadpoles v9 | `01de54c9-9593-413a-9577-1a952d28da70` | `44e759ac-38bb-4e8d-8c4c-4850541ad3dd` | 12/12 | 22/22 | `2f5abc0d7e697de93d6c853d8b6f576addff731496599d0d8492087179649920` |

\* Deterministic digest over sorted relative file paths, file lengths and each file's SHA-256; empty `*.lock` files excluded.
