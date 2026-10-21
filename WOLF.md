# SIGMA: Building with agents, then building for agents

SIGMA (Strategy Investigation, Generation, Measurement & Assessment) is a local-first application for organizing research into difficult problems. Its development uses a deliberately structured collaboration between a human, ChatGPT Chat, and Codex.

## 1. Development workflow

**Human:** Sets product direction, collaborates on design, evaluates decisions, and exercises the running system.

**ChatGPT Chat:** Works with the human on architecture and specifications, inspects the repository, writes detailed Codex assignments, and reviews implementation evidence.

**Codex:** Implements assigned changes, maintains the code and tests, verifies behavior, and commits results.

**GitHub:** Carries the durable handoff between Chat and Codex. The two agents do not share an ongoing conversation or internal state.

### Information flow

```mermaid
flowchart TB
    H["Human<br/>Product direction and judgment"]
    C["ChatGPT Chat<br/>Design and assignment authoring"]
    G[("GitHub<br/>Shared repository and handoff")]
    X["Codex<br/>Implementation and verification"]
    M(["Markdown documents<br/>Architecture, decisions,<br/>human–AI governance"])
    L["SIGMA CLI<br/>Test and launch"]
    U["SIGMA UI<br/>Running product"]

    H <-->|"Collaborate on design"| C
    H --> M
    C --> M
    M -.->|"Versioned"| G

    C <-->|"Specifications and code review"| G
    G <-->|"Assignments and implementation"| X

    G -->|"Checkout"| L
    H -->|"Run"| L
    L --> U

    classDef participant fill:#17324b,color:#fff,stroke:#6086aa,stroke-width:1.5px;
    classDef artifact fill:#fff7e9,color:#30251a,stroke:#ad8350,stroke-width:1.5px;
    classDef running fill:#173e35,color:#fff,stroke:#5f9b89,stroke-width:1.5px;
    class H,C,X participant;
    class G,M artifact;
    class L,U running;
```

The process begins with an open-ended conversation between the human and Chat. We work through the intent, scope, tradeoffs, and acceptance criteria before producing a coding assignment. Chat commits the assignment to GitHub as Markdown. Codex reads it from the repository, implements the change, tests it, and commits the resulting code and verification record. Chat can then inspect the committed work. The human pulls the code and runs SIGMA through its CLI and UI, informing the next cycle of design.

The **shape of information changes across these boundaries**. Human–Chat exchanges can be broad, exploratory, and informal. Chat–Codex handoffs are precise, versioned instructions with explicit constraints and proof of completion. Codex returns executable software and test evidence rather than a conversational assurance that the work is done.

### Shared documents and governance

The human and Chat jointly maintain higher-level Markdown documents alongside coding assignments: architecture, product direction, technical decisions, and rules governing human–AI interaction itself. These are not ephemeral prompts. They become part of the repository's durable context for future assignments. [`docs/HUMAN-AI-INTERACTION.md`](docs/HUMAN-AI-INTERACTION.md) specifies responsibilities and authorization boundaries, how to respond to criticism, how to distinguish proposals from verified facts, and when prior design decisions remain binding.

### Co-maintaining CLI, UI, and tests

**Every assignment maintains the CLI, UI, and test suite together.** They are different interfaces to the same underlying behavior, not separately evolving products. Codex must account for command-line behavior, browser behavior, and the tests that exercise both. Implementation and verification travel together through the same GitHub handoff. Keeping these three surfaces synchronized makes the CLI useful for direct inspection, the UI consistent with the underlying system, and the test suite a durable statement of expected behavior.

### Engineering roles and boundaries

This is human-directed agent-assisted software development, rather than an autonomous swarm. The human remains engaged in design and judgment; Chat contributes independent engineering reasoning and explicit assignments; Codex supplies implementation and verifiable results. The division is deliberate: it allows fast iteration without treating generated code, agent confidence, or a successful demo as sufficient evidence of correctness.

The central challenge is **continuity across separate agents and repeated iterations**. Durable specifications, shared governance documents, source control, and co-maintained tests are the mechanisms that preserve that continuity.

## 2. Agents within SIGMA

The architecture and information flow of SIGMA's future multi-agent research engine remain to be determined. That is a separate design problem from the development workflow described above.
