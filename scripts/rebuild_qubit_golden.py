"""Rebuild Qubit v1 from the archived structured paper draft without provider calls."""

from rebuild_golden5_papers import ROOT, rebuild

if __name__ == "__main__":
    rebuild("qubit-non-markovian-v1", ROOT / "papers", "tectonic")
