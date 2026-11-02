# Sovereign AI Federation v2 paper recovery

The first generation stopped at section 6/7 when its streamed response exceeded the bound. The saved evidence index, outline, and completed sections were preserved. That attempt had 8 provider calls.

The first checkpoint continuation stopped at section 6/7 because a generated table in “The comparison contract” cited claims outside that section's outline. That attempt added one provider call; the invalid section response was not saved as a paper.

The final checkpoint continuation used the same frozen source snapshot and saved section prose with `include_diagrams=False`. This removed table authoring from the remaining calls, so the offending table was excluded while the paper continued. Existing saved sections were reused. The final paper has no diagrams or tables. The paper's generation metadata records 18 cumulative provider calls; the final continuation took 143.11 seconds. Its PDF and TeX were copied to `papers/sovereign-ai-federation-v2-golden5.{pdf,tex}` with byte-identical hashes.

The PDF is 27 pages and its automatic layout status is `needs_review`. TeX proofreading was attempted across 8 chunks, with fallback status and 0 accepted corrections. The paper requires editorial and layout review before publication.
