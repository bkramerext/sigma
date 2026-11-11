"""Second disjoint half of research-session verification group three.

The existing scenario definitions and assertions remain in part3.py; the
split driver selects alternating test definitions without changing their bodies.
"""

if __name__ == "__main__":
    from research_sessions_split_runner import run

    run(3, half=2)
