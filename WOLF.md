Wolf

I started SIGMA as an experiment inspired by my interest in the Riemann Hypothesis. I'd been using AI to explore mathematical ideas, but kept running into a problem: an interesting line of reasoning might uncover something useful, yet much of that work would get buried in a long conversation. I wanted a system that could pursue different approaches, challenge its own findings, and remember what it learned.

That became SIGMA (Strategy Investigation, Generation, Measurement & Assessment), a Python application with a browser interface and a multi-agent research engine.

SIGMA organizes a difficult problem into persistent strategies, each representing a possible approach. A Python coordinator runs bounded research sessions, choosing which strategies to pursue and managing exchanges between AI agents. An Investigator develops an argument or proposes an experiment. A Skeptic challenges its assumptions, reasoning, and evidence. The Investigator gets another turn to respond. The coordinator is ordinary Python code, not another LLM.

What makes this interesting to me is what happens between sessions. SIGMA preserves arguments, critiques, computational results, and unresolved questions so later agents can build on earlier work. Agents can also run isolated Python or SageMath experiments to test their ideas. The challenge is to make this a cumulative investigation rather than a succession of convincing-sounding conversations.

Research quality became a central concern. I've pushed for work that actually advances an investigation, with claims grounded in evidence. ChatGPT helped turn those expectations into more formal requirements and implemented safeguards with the coding agents. We found cases where a research summary sounded more confident than the evidence justified, including one that implied computational support when no computation had succeeded. We're still working on those problems, and we haven't established that multiple agents outperform a simpler approach given the same resources.

There's a second multi-agent story in how we built SIGMA.

I started by discussing designs with ChatGPT and having Codex write the code. Eventually I had four Codex workers running in parallel, Blue, Green, Red, and Gray, with ChatGPT coordinating their work. Each had its own branch and responsibilities. GitHub tickets and pull requests became the shared record between agents that couldn't talk directly to each other.

I'd discuss what I wanted with ChatGPT, we'd work through the design, and the workers would implement it. Then I'd run the software and see whether it actually did what I'd intended. Often it didn't, despite passing its tests. We'd revise the design or implementation and try again. Meanwhile, ChatGPT was reviewing code, resolving integration issues, and sometimes contributing changes directly.

We got a surprising amount done this way, but it wasn't effortless. Keeping four workers aligned was its own engineering problem. Branches diverged, changes conflicted, and passing tests sometimes concealed misunderstandings about what the product was supposed to do.

SIGMA now has a working research engine, a browser UI, persistent investigations, computational tools, research reports, and automated tests. But getting the software to work is different from demonstrating that it produces genuinely better research.

Maybe this work bites off more than it can chew, but the goal really was to build a product that looks credible, supports Markdown and stays open to new ideas such as on-demand TeX paper generation, and inspires others to try it out. I appreciate you taking a second reading.

---

*Authorship note: I wrote my original essay myself. This essay was developed in collaboration with ChatGPT.*
