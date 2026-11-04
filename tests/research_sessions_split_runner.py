"""Four independent research session test groups."""

from split_test_driver import run_split


def run(part: int) -> None:
    run_split("research_sessions", 4, part)
