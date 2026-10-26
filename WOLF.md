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

Maybe this work bites off more than it can chew, but the goal really was to build a product that looks credible and supports ideas such as reformatting plain-text mathematical descriptions and Conclusions into Markdown with typeset equations. The AI formatter leaves the saved text available, but its mathematical output still needs review. I also want SIGMA to stay open to future ideas such as on-demand TeX paper generation, and to inspire others to try it out. I appreciate you taking a second reading.

---

*Authorship note: I wrote my original essay myself. This essay was developed in collaboration with ChatGPT.*


## What I learned about working with AI

I haven't been writing the code, but that doesn't mean my software engineering experience has been sitting idle. I've used it to set direction, decide what matters, organize phases, and keep the work moving toward a coherent product. Without that guidance, there's a risk of the inmates running the asylum: lots of activity, but no steady course. Constraints and priorities matter, even when AI is doing the implementation.

At the same time, I've learned when to give AI a lot of room. Sometimes my instruction is essentially, "I don't know, and I don't particularly care how you solve this. Figure it out." Often it does, and the result isn't just plausible-looking code. The interesting part is what happens as you keep turning the crank. A mental map of the system gradually emerges for me, even though I'm not the one constructing every piece. The cloud deployment was the clearest example. AI laid out the plan and divided it into tasks; I largely approved the direction. We solved those tasks one at a time, sometimes in an order that seemed arbitrary to me. I didn't always understand how the pieces would fit until they did. That was impressive, and it changed how I think about the relationship between directing engineering work and understanding the system being built.

The four-worker setup taught me something else. These agents can move between tasks, pick up work another agent started, or be reassigned as priorities change. They don't have the same ownership boundaries, specialization costs, or coordination habits that human teams develop. That flexibility is a genuine advantage, although it puts more responsibility on the coordinator to preserve context, keep interfaces stable, and make sure the pieces still fit together.
