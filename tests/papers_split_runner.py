"""Two independent paper test groups."""

from split_test_driver import run_split


def run(part: int) -> None:
    run_split("papers", 2, part, paper=True)
