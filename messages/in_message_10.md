# Round 10 — issue #336 final controlled evaluation

## Execution and preflight

- Candidate implementation: `chat/336-paper-editorial-prompts`, exact SHA `5066703702c9777f1fe7ee4b8125e43060445e3c`.
- The required no-provider `_safe_math` / `_latex_prose` preflight passed before generation. Cases were: Maximum Regions `$x=-(i+k),\qquad y=-ik$`; the residue transition `$D_i(r,1)=D_{i-1}(r-i,0)$`; `\#\{...\}` set notation; the Gaussian-binomial sum; powers; comparison signs; and escaped delimiters. Every test body returned `_safe_math=True`; `_latex_prose` preserved the expressions as math, with none of `\$`, `\textbackslash{}`, or `\textasciicircum{}` in the result.
- No provider calls occurred before that preflight passed. The authorized sponsor was connected as `zetacontinuation@gmail.com`, in ChatGPT sponsor mode. All six requests used `gpt-6.1-sol`, high reasoning effort, and explicitly submitted claim details ON, legacy research details OFF. Validation notes and research excerpts were OFF except in their respective Maximum Regions probes.
- Four primary inputs were fresh isolated imports of the saved project versions, with existing paper archives excluded from the copies. Project IDs and primary source counts matched: Maximum Regions `01af8ffa-60c3-4eea-bc15-36dca347ddfa` (5); Nonconsecutive `57d67c57-15dc-433d-828a-7953f7986ff8` (15); Xenopus `01de54c9-9593-413a-9577-1a952d28da70` (12); ONP `4060cb04-3ed7-4ae4-9f61-2c3691313759` (4).
- ONP was imported with `project_bundle.import_bundle`. `export_project_view` exposed the exact saved session `62290dab-19f0-4c6e-9785-7c8e02193a18`; its two strategy IDs were `68724357-fe46-4e32-80e4-fb9c1c5ec657` and `581b61a1-a7ed-40ff-abf6-88fed330703d`. `papers.preflight` reported exactly 4 sources and zero prior provider calls. The saved session's strategy assessments are `not_used`; the paper does not present their plans as completed research.
- Six generation requests took 1,251.3 seconds total and attempted 20 provider calls. All produced PDF, TeX, and TXT files. No app source, saved source project, research session, or original paper archive was changed. No tests, CI, browser suites, or new research sessions were run.

## Results

| Project / run | Paper ID | Time / calls | Sources; omitted metadata fields | Snapshot SHA-256 | Assessment |
|---|---|---:|---:|---|---|
| Maximum Regions — primary | `a4441822d78b42deb84c4866ad83e407` | 146.5 s / 1 | 5; 0 | `658b19c06eebe64b26a4263325555a6ad4118184bcd74591d858478c93b17868` | **Pass**, with unused C9 |
| Maximum Regions — validation ON | `3a958e0ba90340be898df8288cf265db` | 124.8 s / 1 | 5; 0 | `56e843297cd316019f170c929023fd090bf8ba9772274635c121e66a40f9c3a9` | **Defect**: validation material is noisy and partly misleading |
| Maximum Regions — excerpts ON | `da6af6b8efb44ce8afb9e76af1d2fdb8` | 133.2 s / 1 | 5; 0 | `9de7d5ac44057e15253d000d09342ae243d88863e649fcb28165aeca50442e43` | **Defect**: no distinct research excerpts are visible |
| Nonconsecutive — primary | `944f16686a7146afb0fe069f6c1aab17` | 278.7 s / 5 | 15; 1,027 | `685065ef044b24a435467ace0abdf7749a50787a846891c2aa22980e481618de` | **Defect**, generated math repaired in attached TeX/PDF |
| Xenopus — primary | `66bb5fa3d8174156a63f53ff5bed1c9c` | 253.3 s / 5 | 12; 1,863 | `5addca2c08d77827a380fda2049470f2134aec5a5eb4ecb535402e4903b73fbe` | **Defect**: all claim-register IDs are unused |
| ONP — primary | `81b9b61d61db43d0b31f8a8fa42451a1` | 314.8 s / 7 | 4; 0 | `2092017a771b8fc8dd0622b8ea2ce0f51fa90f8f0cf50507796fcbfffa7c887a` | **Pass**, with 3 unused claims |

### Manuscript review

- **Maximum Regions primary:** The full TeX gives a continuous deductive proof: sign cells are open and convex; a noncoincident inserted line with `m` distinct intersections adds exactly `m+1` regions; summation gives the upper bound; and `L_i: y=ix+i^2` attains every increment. The construction coordinates `x=-(i+k)` and `y=-ik` are valid math in TeX. All 8 IDs used in “Claims discussed” resolve; C9 is unused. There are no evidence omissions or citations. Compared with round 9, the targeted construction equation improved from 2 escaped dollar signs and 1 `textbackslash` escape to no escaped math tokens. The proof remains explicitly unverified independently, appropriately.
- **Maximum Regions validation ON:** The option persisted as requested and adds `About this paper`, `Open obligations`, `Frozen obligation reconciliation`, and `Validation warnings`. The added material is not cleanly bounded: it labels five already-proved steps “Not listed by author; not presumed resolved,” then repeats two warnings for each established claim C1–C8 about unresolved/conjectural or contradictory source content. This creates administrative clutter and false uncertainty around the reproduced proof. All 9 claim IDs resolve in this variant.
- **Maximum Regions excerpts ON:** The option persisted as requested. The generated TeX contains the same kind of `Evidence:` source-ID lines as the primary version, but no clear excerpt section or identifiable quoted research passages. C9 remains unused and the other eight references resolve. As these are separate generations, title and prose also changed; this is not a controlled textual diff proving that only the option changed.
- **Nonconsecutive:** The argument is substantially useful and careful: the residue transition and set-count notation are valid math; the short recurrence is correctly refuted at `a_5=5` versus `a_4+a_2=4`; the order-twelve recurrence and density limit remain labeled unproved; and open obligations are specific. However, the generated TeX still encoded four Gaussian-binomial formulas as escaped literal text: 8 `\$`, 20 `\textbackslash{}`, and 8 `\textasciicircum{}`. This improves on round 9's 24 / 37 / 8 counts but does not fix the Gaussian derivation. The generated output also has no “Claims discussed” IDs: all 13 claim-register IDs C176–C188 are unused, a regression from round 9 where all 13 were referenced. Coverage remains inconsistent: the TeX/PDF notice says 996 material fields across 6 sources; generation metadata says 1,027 omitted fields; the persisted material omission ledger has exactly 996 entries across those same 6 sources. The TXT companion has no coverage notice. The discrepancy matches round 9's 996/1,027 issue.
- **Nonconsecutive direct artifact repair (human-requested):** After review, I corrected the four malformed Gaussian formulas directly in the round 10 TeX artifact, using `\genfrac` and valid math delimiters, and rebuilt its PDF from that exact TeX with Tectonic. The corrected TeX now has zero `\$`, `\textbackslash{}`, or `\textasciicircum{}` tokens; the rebuilt file is a valid PDF. The initial provider-generated TeX/PDF are preserved as `_model-output.tex` and `_model-output.pdf` sidecars. No provider call or app/source edit was made for this repair. The paper record and TXT companion remain the original generation; the corrected TeX/PDF are the repaired publication artifacts. This rendering repair does not resolve the unused claim register or omission-count mismatch.
- **Xenopus:** The manuscript is a cautious, discipline-appropriate hypothesis analysis. It distinguishes developmental stage from individual regeneration outcome, separates conditional coupling from input strength, tissue composition, and cell-state alternatives, and does not invent a numerical effect or validated intervention. The coverage notice and metadata/ledger agree at 1,863 fields across 6 sources. No math escaping was found. The DOI `10.1186/s13059-024-03396-3` appears in prose, but there are no structured citations or bibliography entries; this remains unverified here and is unchanged from round 9. Claim linkage regressed: 11 claim definitions appear in the register but none is referenced in “Claims discussed.” Round 9 referenced all 9 claims.
- **ONP:** The valid 4-source paper is conditional operational analysis rather than generic scenario paraphrase. It distinguishes fictional stipulated events from unverified damage and attribution, refuses to treat the six-hour deadline as a safe planning window, constructs an explicitly hypothetical counterexample to guaranteed success, and keeps holding / evacuation with continuity conditional on feasibility. It does not claim the adverse continuation is a forecast, rank unsupported options, or present legal/operational validation as complete. All 24 IDs used in “Claims discussed” resolve among 27 definitions; C96 (provider interruption), C98 (unverified cross-strategy relations), and C99 (bounded evidence preview) are unused. No dangling IDs, omitted fields, or citations. There is no valid round-9 ONP paper for comparison; the 3-source, 829-second round-9 run is excluded.

## Maximum Regions option settings

| Run | Claims | Validation notes | Research excerpts | Legacy research details | Visible effect |
|---|---:|---:|---:|---:|---|
| Primary | ON | OFF | OFF | OFF | Baseline coherent proof |
| Probe A | ON | ON | OFF | OFF | Adds validation sections; currently noisy and internally confusing as detailed above |
| Probe B | ON | OFF | ON | OFF | No distinct excerpt material identifiable in TeX; only source-ID evidence lines |

All settings, model, and effort are recorded in each paper's generation metadata. Source project data and model/effort were held constant; each probe used a fresh import. Different snapshot hashes reflect the distinct imported copies and are recorded above.

## Artifact paths and SHA-256

All paths below are under `messages/artifacts/`. The stem is the complete basename before the extension; PDF, TeX, and TXT share that stem.

| Stem | PDF SHA-256 | TeX SHA-256 | TXT SHA-256 |
|---|---|---|---|
| `maximum-regions-v2-50667037-primary_a4441822d78b42deb84c4866ad83e407` | `925956a3bec3d2390dbb9538d7e95c56466a8a9b0b4dc4fcbca0ca2e7c4927c6` | `adb8f71f5f8f84fb964ae546a026aa18c0a5121efd2d4fd3eb26eec8becaa1a4` | `19e10f36a52f26b54e610a168a0882c3e49141d3fa852ed71b4a8499c11c8535` |
| `maximum-regions-v2-50667037-validation-on_3a958e0ba90340be898df8288cf265db` | `b321b84eba22bb40f331c53dd9129555e6f844de9acf5e8f4dc16ba0855e84af` | `68f47f90474a098e554b0d9909845afff083ae169c76c302a1ee47b85cf117ca` | `d182adda89227bc1cd3d133c047ab1275216a5b4e53a9067e8b5883aad653402` |
| `maximum-regions-v2-50667037-excerpts-on_da6af6b8efb44ce8afb9e76af1d2fdb8` | `467d6524eb97526ee5f7cf029bd9cc9e912d11f60cd17b6712433fc915cc0a7a` | `d16e856e5bd64aa791fbf14b3a694206052fc6ef03421c95be35a4e88754e06d` | `232aaa02ce58511cbd9c0731bb3aea2d2633825257a0aafbd7fa23a20dd00e5e` |
| `nonconsecutive-subset-sums-v9-50667037-primary_944f16686a7146afb0fe069f6c1aab17` — corrected artifacts | `5ed81c42536a32715f3bafdee080159dfede6b27e3a1fe6ceaae853955cfe917` | `bc1d305bfe6cea5eef429bc41ad7267fa7cc8b4358b741c3ec02e90a5ce2bb84` | `25a179d3ffb4af8ed76583681e3f8100c3a23a64128441a44ce0ce7cac864906` |
| `xenopus-tail-regeneration-v9-50667037-primary_66bb5fa3d8174156a63f53ff5bed1c9c` | `96111b179255c9c07018b6dc4bdf2ea266450c1e8c7d9fb8b1cc4a6dbffed895` | `b6260b6b819892fa3725ef661e742c16fdf96951eb14cab5bcc61d7a864cf7e8` | `11784317481c7cd5cff046466c5b8c04cc8d157a4eb260fe847847ff64a2de93` |
| `operation-narrow-passage-v3-50667037-primary_81b9b61d61db43d0b31f8a8fa42451a1` | `fa099d28d4e1a2fab42e231f682310a6f0e2f77913ebb4d5b256c29abc552103` | `c6a88986aa08ac3c43bcbcb340b8f1f2f85f238ff9f93a100bf6c9ee54a0514c` | `cb1391eda275dfe29330264eb9e47b142b8a86749d0859ed0d39234edc90af27` |

The original model-generated Nonconsecutive TeX/PDF sidecars are `nonconsecutive-subset-sums-v9-50667037-primary_944f16686a7146afb0fe069f6c1aab17_model-output.tex` (SHA-256 `8eec9c516acd1b03a2af37d854391eacba1aa11a13e30de5a909904b78841c68`) and the matching `.pdf` (SHA-256 `303250dbecaab4b0817849d76ef07f35326a5a84291d0a995a903baa8deb85d6`).

## Outstanding findings for coordinator

1. The generator's TeX rendering still corrupts a class of model-produced Gaussian-binomial expressions even though the isolated `_latex_prose` preflight passes. The direct artifact repair makes this paper readable but does not fix the generation path.
2. Nonconsecutive's 1,027 metadata count versus 996 material-ledger/TeX count needs an explicit definition or reconciliation; the same discrepancy persisted from round 9.
3. Claim-detail references regressed for Nonconsecutive and Xenopus (zero body references with 13 and 11 registered claims respectively); resolve this before final acceptance.
4. The validation-notes probe creates false-looking obligation reconciliation and repeated claim warnings; the research-excerpts probe has no clearly visible excerpts. Review option behavior before acceptance.
5. Xenopus still has an unstructured DOI assertion without a bibliography; verify or add bibliographic support if retained.

No round 11 work was started.
