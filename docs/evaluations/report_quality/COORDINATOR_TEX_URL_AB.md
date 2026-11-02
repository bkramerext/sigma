# Coordinator TeX URL line-breaking A/B — independent local reproduction

**Executed:** 2026-11-01 PST in a local `pdflatex` environment; no SIGMA runtime, live provider or network calls. Reproduction script: `analysis/tex_url_break_ab.py`. **This is an isolated fixture experiment, not recompilation of the full 42-page Sovereignty paper.**

## Controlled setup

Recreated the substantive paragraph from Sovereignty TeX lines ~59–60, including the two primary-source URLs. Kept surrounding prose, page width, font encoding and URL bytes identical. Only the TeX treatment of the two URLs changed:

1. **raw:** original text with escaped underscores and unwrapped `https://...` strings.
2. **url_both:** `\usepackage{url}`, both URLs wrapped with `\url{...}`.
3. **xurl_both:** `\usepackage{xurl}`, both URLs wrapped with `\url{...}`.

All three documents compiled successfully with `pdflatex -interaction=nonstopmode -halt-on-error`.

| Variant | Overfull boxes | Maximum overfull width |
|---|---:|---:|
| raw | 2 | **277.68018 pt** |
| url_both | 1 | **28.159 pt** |
| xurl_both | **0** | **0 pt** |

This demonstrates a **real, reproducible mechanism** by which raw long URLs cause horizontal overflow in a comparable paragraph and that breakable URL rendering can remove it. It **does not** prove the full Sovereignty PDF's page-31 issue is completely fixed; that requires applying a safe change to SIGMA, recompiling the same frozen TeX and checking all pages.

## Engineering constraints for later isolated repair

- Recognize URLs in ordinary prose **without treating arbitrary user text as TeX code**. Validate URL boundaries and escape/sanitize all other text. Avoid double escaping underscores or changing source URLs.
- Preserve actual bibliographic/source identity and hash. `\url{...}` should not silently convert a URL into an unsupported citation or imply retrieval.
- Test URL percent signs, underscores, query strings, parentheses, long path segments, Unicode and adjacent punctuation. Avoid unsafe TeX command injection.
- Verify `xurl` package availability in the deployed Tectonic/TeX environment; local `pdflatex` availability is not a guarantee of deployment availability.
- The Agent and Xenopus overflows have **different** nearby causes (long identifiers/obligations and provider JSON schema); do not claim URL handling fixes those.
- Keep this TeX fix separate from the H2-A semantic fallback experiment already dispatched to Blue, so its quality improvement can be attributed correctly.

## Interpretation

The A/B isolates a *typesetting mechanism*, not a scientific result. The larger publication failure remains evidence selection and claim-to-source fidelity. A clean PDF cannot validate a scientific conclusion.
