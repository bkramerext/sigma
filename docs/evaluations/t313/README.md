# T313 UI audit evidence

## Findings and changes

| Area | Finding | Result |
|---|---|---|
| Home, narrow view | The large copper slogan and bright background art competed with the sample list at 320–390px. | Hide the slogan below 900px and dim the existing background image; desktop presentation is unchanged. |
| ChatGPT status | The connected control's native tooltip exposed the provider account email. | Tooltip now says “ChatGPT is connected. Click to return to sponsorship.” Visible state and click behavior are unchanged. |
| Admin allowances | Main already contains the alignment fix from PR #232. | Added browser regression coverage for finite and unlimited values at desktop and narrow widths; no accounting or redundant styling change. |
| Project About | Existing disclosure, legal links, close behavior, and narrow layout. | Browser checked at 1440px and 390px; keyboard Escape closes and returns focus. No further defect observed. |
| Home connection state | Connected, disconnected, and sponsored status visibility. | Browser checked at 1440px, 390px, and 320px; connected tooltip is generic and sponsored Unlimited allowance remains visible. |
| New Project dialog | Dialog sizing, scrolling, close/focus behavior at narrow width. | Opened and checked at 390px; no horizontal overflow or clipped actions observed. |

## Browser evidence

Captured in real Chrome against the local SIGMA frontend with deterministic local API fixtures. No paid provider calls were made.

- Admin before/after: `evidence/admin-allowance-before-1440.png`, `evidence/admin-allowance-after-1440.png`, and corresponding `390` screenshots. The alignment was already fixed in the base revision, so these screenshots demonstrate the existing consistent axis and its tested finite/unlimited values.
- Tooltip before/after: `evidence/home-connection-before.png`, `evidence/home-connection-after.png`. The before screenshot uses a synthetic fixture account label, not a real user's account.
- Home responsive contrast: `evidence/home-disconnected-before-320.png` versus `evidence/home-disconnected-320.png`, plus 390px and 1440px variants. The mobile slogan is removed and the art is dimmed to keep sample text legible.
- Status states: `evidence/home-sponsored-{1440,390,320}.png` and `evidence/home-disconnected-{1440,390}.png`.
- New Project dialog: `evidence/new-project-dialog-390.png`.
- Project About: `evidence/project-about-{1440,390}.png`.

## Coverage limits

The broad A17 real-browser project/session flow opened a local sample and inspected project controls, export choices, and the connected status. It stopped when its account-change action was rejected by the fixture with HTTP 403 (“Account changes require the local SIGMA browser origin and JSON”). That area overlaps Green's active authentication/account-change ownership; no related product code was changed. Consequently session configuration, playback/progress, completion/failure results, and research-output visual states were not fully exercised in Chrome during this pass. The automated `./sigma test` suite covers backend/session behavior but is not a substitute for those browser states.

The Admin allowance alignment itself was already present in base main (PR #232); this pass adds regression coverage and evidence, rather than changing sponsorship accounting or duplicating the existing CSS fix.
