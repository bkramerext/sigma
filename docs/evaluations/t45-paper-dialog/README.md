# TeX paper dialog screenshots

`before-desktop.png` is the owner-provided dialog before this cleanup.
`after-desktop.png` shows the completed paper preview inside the dialog's scroll
area. `after-mobile.png` shows the dialog at 390px with its own scrollable body.
`authoring-progress.png` shows the in-dialog “Cancel generation” button
replacing Generate. The browser check also injects a temporary failure and
confirms Generate is active again for retry; `retry-available.png` captures
that state.

The cleanup tightened unused vertical space, raised explanatory text to 14px,
removed the redundant disabled Authoring button and the browser-native long-form
confirmation, and added the export-matching “Open in browser tab” choice. The
existing provider-use bounds remain visible before generation.
