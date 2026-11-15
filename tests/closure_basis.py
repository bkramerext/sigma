"""Regression checks for reusable research evidence."""

from sigma.research_sessions import _usable_addressed_obligation_basis


def main():
    prior = {"id": "prior", "reasoning_steps": [{"argument": "Claim with saved steps"}]}
    assert _usable_addressed_obligation_basis(prior, [])
    assert not _usable_addressed_obligation_basis(
        {**prior, "retracted_by_artifact_ids": ["newer"]}, []
    )
    print("PASS closure evidence checks")


if __name__ == "__main__":
    main()
