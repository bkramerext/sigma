"""Second disjoint half of research-session verification group three.

The existing scenario definitions and assertions remain in part3.py; the
split driver selects alternating test definitions without changing their bodies.
"""

from research_sessions_split_runner import run


if __name__ == "__main__":
    run(3, half=2)
