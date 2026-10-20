# ASN-3 design note

- **Home** (`/`) launches projects; **Project** (`/project?path=...`) is the workspace. URLs support reload and browser history. Close returns Home.
- **Workspace:** Project title and problem lead; strategy pool follows. Technical details/history sit in a secondary disclosure.
- **New strategy:** Inline title/approach form; focus management, cancel/Escape, and retained text on failure.
- **Strategy commands:** An unlabelled chevron beside the strategy name reveals sibling Scheduling, Artifact, and Actions groups. Only one group opens at a time; Fork lives under Actions. Unimplemented commands are visibly unavailable, never simulated.
- **Accessibility:** Native disclosures and keyboard/mobile controls.
- **Persistence:** Schema v2 adds stable strategy IDs and linked events. First v1 write preserves an exact backup; cooperative writers lock, stage, and atomically replace local JSON. See [DECISIONS](DECISIONS.md) for limits.
