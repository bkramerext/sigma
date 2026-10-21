# Readings

Notes on outside work that informs SIGMA's design. These are interpretations and possible lessons, not adopted implementation requirements.

## On the Nature of the Swarm

**Source:** [“On the Nature of the Swarm,” section “Multi-Agent Systems”](https://hallerite.com/posts/on-the-nature-of-the-swarm/#multi-agent-systems), Hallerite.  
**Read:** October 21, 2026.

### The argument worth retaining

The interesting justification for multiple agents is not simply that they can execute tasks in parallel. **They can distribute working context.**

Context compaction asks an agent to decide *in advance* which details from its history will matter later. That is an inherently lossy prediction. Delegating a focused question to another agent changes the timing: the agent assembles the relevant context for a particular question and returns a targeted result. If that specialist remains available, subsequent questions may benefit from its accumulated understanding.

The article also explores moving beyond a strict coordinator/sub-agent tree toward a network of agents that communicate more directly and develop specialties through their work.

### What this suggests for SIGMA

**1. Treat specialized understanding as a reusable resource.** In a substantial investigation, an agent might learn the intricacies of a particular mathematical argument, historical source tradition, or experimental method. Reusing that working context could be more efficient and insightful than repeatedly starting from a generic prompt. Specialization need not be completely predetermined; it can emerge from the investigation.

**2. Separate agent context from the durable research record.** An agent's accumulated context includes intuitions, tentative assumptions, partial work and dead ends. SIGMA's authoritative investigation record should instead contain inspectable claims, evidence, derivations, counterexamples, unresolved proof obligations, decisions and results. Losing an agent session must not mean losing the investigation's established work.

**3. Make conclusions independently challengeable.** A persistent specialist may also preserve its mistakes and intellectual commitments. A fresh agent, without the specialist's accumulated assumptions, can be valuable for adversarial review. Persistent expertise and independent skepticism serve different purposes.

**4. Don't confuse decentralized communication with reliable synthesis.** Allowing specialists to communicate directly may reduce unnecessary routing through one coordinator. But research still needs a coherent account of what is established, what conflicts, and what remains unknown. More agent conversations do not automatically produce a stronger conclusion.

### Limits of the argument

Persistence does not create unlimited context. Every agent eventually encounters its own context constraints, and integrating knowledge across agents introduces communication and synthesis costs. The apparent aggregate context capacity of a swarm is useful when work is decomposable, not a guarantee that a globally integrated reasoning task scales the same way.

Likewise, a mesh of agents is an interesting architectural possibility, not evidence that a leaderless swarm is superior for rigorous research. The shape of communication should follow actual research needs.

### Practical implication, not a feature commitment

The important future design distinction is between **ephemeral or persistent agent working state** and **durable, independently auditable investigation state**. If SIGMA later supports autonomous multi-agent investigations, it may reuse specialists' accumulated context while requiring their substantive contributions to enter the shared research record in a form others can verify.

**Open research-design question:** How can distributed specialists combine their understanding into a reliable, testable conclusion without recreating the central context bottleneck they were intended to avoid?

This reading does **not** justify implementing a swarm, mesh, persistent agent sessions or a coordination framework now. SIGMA remains a focused showcase, and any such machinery should wait for a concrete demonstration need.
