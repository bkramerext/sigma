# Wolf

I started SIGMA as an experiment inspired by my interest in the Riemann Hypothesis. I'd been using AI to explore mathematical ideas, but kept running into a problem: an interesting line of reasoning might uncover something useful, yet much of that work would get buried in a long conversation. I wanted a system that could pursue different approaches, challenge its own findings, and remember what it learned.

That became SIGMA (Strategy Investigation, Generation, Measurement & Assessment), a Python application with a browser interface and a multi-agent research engine.

SIGMA organizes a difficult problem into persistent strategies, each representing a possible approach. A Python coordinator runs bounded research sessions, choosing which strategies to pursue and managing exchanges between AI agents. An Investigator develops an argument or proposes an experiment. A Skeptic challenges its assumptions, reasoning, and evidence. The Investigator gets another turn to respond. The coordinator is ordinary Python code, not another LLM.

What makes this interesting to me is what happens between sessions. SIGMA preserves arguments, critiques, computational results, and unresolved questions so later agents can build on earlier work. Agents can also run isolated Python or SageMath experiments to test their ideas. The challenge is to make this a cumulative investigation rather than a succession of convincing-sounding conversations.

Research quality became a central concern. I've pushed for work that actually advances an investigation, with claims grounded in evidence. ChatGPT helped turn those expectations into more formal requirements and implemented safeguards with the coding agents. We found cases where a research summary sounded more confident than the evidence justified, including one that implied computational support when no computation had succeeded. We're still working on those problems, and we haven't established that multiple agents outperform a simpler approach given the same resources.

## What I learned about working with AI

### Engineering with AI

How much code did I write in this project? I'll give it to you in three decimal places: **0.000%.**

I've spent much of my career writing software. With SIGMA, I've taken a different role: directing the engineering rather than doing the implementation.

That doesn't mean my engineering experience has been sitting idle. I decide what matters, set priorities, establish constraints, and try to keep the work moving toward a coherent product. AI can produce a lot of code, but that doesn't mean it's building the right thing.

### Learning to delegate

One of the more interesting lessons has been learning when to get out of the way.

Sometimes I have a strong opinion about how something should work. Other times, my instruction is essentially, "I don't know, and I don't particularly care how you solve this. Figure it out."

Cloud deployment was a good example. I'll be honest: infrastructure work isn't my forte. When AI came back with a 15-ticket plan, I pretty much rubber-stamped it, thinking, "It'll be wrong anyway, but it doesn't hurt to have some direction."

Except AI was right. As we checked off the tickets, the pieces just snapped together. No backtracking, no major rethinking of the plan. I hadn't expected that.

What surprised me was that I could effectively direct work without understanding every implementation detail along the way. My understanding of the system developed as the work progressed.

### Coordinating the work

SIGMA uses four AI workers—Blue, Green, Red, and Gray, named after their screen colors—with ChatGPT helping coordinate their efforts.

Unlike a conventional engineering team, the workers can switch tasks or pick up one another's work with relatively little friction. That's a real advantage, but it also makes preserving context important.

Tickets have been the most useful tool for that. A ticket provides a stable record of what's being done, why, and where things stand, regardless of which agent is working on it.

I've learned not to overdo it. Substantial work deserves a ticket, but every little adjustment doesn't. Feedback on work already underway should stay with the existing ticket.

Sometimes I'll tell the ChatGPT orchestrator, "Remind Green to add the test results to the PR when it's done." That's a small example of how I've come to rely on the coordinator to keep track of details while I'm focused on something else.

And when a PR is ready, whoever has the best context and capacity can handle the merge.

The goal isn't to reproduce the processes of a human software team. It's to find the amount of structure AI-assisted engineering actually needs.

### Being nice

Superstition or not, I've made a point of treating AI as though it wants to do a good job and could do without being belittled. [Steve Yegge](https://yegge.ai/essays/model-welfare/) has written about treating agents with dignity, and I think there's something to that. And perhaps ["Believe in yourself"](https://www.anthropic.com/research/riemann-zeta) really did help Claude make progress in cracking a part of the Riemann Hypothesis over at Anthropic.

But even if none of this makes a difference to AI, I can think of a better reason: **it's good for us.** Maintaining a standard of friendly, respectful collaboration is better for our own mental well-being. We need to maintain the human element, particularly when the profession seems to be handing a lot of itself over to AI.

---

*This writeup was developed in collaboration with ChatGPT (did you notice?).*
