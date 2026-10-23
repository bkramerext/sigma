"""T39: exact countermodels for invalid RH proof inferences.

This is an independent mathematical oracle, not an agent-quality test and not a
model of the zeta function. Any agent-output scoring remains human-reviewed.
"""

from fractions import Fraction

ComplexQ = tuple[Fraction, Fraction]
HALF = Fraction(1, 2)
QUARTER = Fraction(1, 4)
HIGH_ZERO = 1001


def q(real: int | Fraction, imag: int | Fraction = 0) -> ComplexQ:
    return Fraction(real), Fraction(imag)


def add(left: ComplexQ, right: ComplexQ) -> ComplexQ:
    return left[0] + right[0], left[1] + right[1]


def mul(left: ComplexQ, right: ComplexQ) -> ComplexQ:
    return (
        left[0] * right[0] - left[1] * right[1],
        left[0] * right[1] + left[1] * right[0],
    )


def square(value: ComplexQ) -> ComplexQ:
    return mul(value, value)


def toy_function(value: ComplexQ) -> ComplexQ:
    """Degree-six real polynomial F(s)=F(1-s) with off-line high zeros.

    Let z=s-1/2. F(s)=(z^2+1)*((z-1/4)^2+T^2)*((z+1/4)^2+T^2).
    It is NOT the Riemann zeta function; it only refutes invalid deductions
    from symmetry, limited zero checks, or a narrow zero-free region alone.
    """
    shifted = add(value, q(-HALF))
    center_factor = add(square(shifted), q(1))
    right_factor = add(square(add(shifted, q(-QUARTER))), q(HIGH_ZERO**2))
    left_factor = add(square(add(shifted, q(QUARTER))), q(HIGH_ZERO**2))
    return mul(center_factor, mul(right_factor, left_factor))


def main() -> None:
    on_line = (q(HALF, 1), q(HALF, -1))
    off_line = tuple(
        q(real, sign * HIGH_ZERO)
        for real in (HALF - QUARTER, HALF + QUARTER)
        for sign in (-1, 1)
    )
    roots = on_line + off_line
    assert len(set(roots)) == 6  # Degree six: no additional complex roots.
    assert all(toy_function(root) == q(0) for root in roots)

    for point in (q(0), q(HALF, 3), q(Fraction(7, 6), -5), q(3, 100)):
        reflected = add(q(1), q(-point[0], -point[1]))
        conjugate = q(point[0], -point[1])
        assert toy_function(point) == toy_function(reflected)
        expected_conjugate = q(toy_function(point)[0], -toy_function(point)[1])
        assert toy_function(conjugate) == expected_conjugate

    # Every root in the finite-height window is on the critical line.
    checked_roots = [root for root in roots if abs(root[1]) <= 1000]
    assert checked_roots == list(on_line)
    assert all(root[0] == HALF for root in checked_roots)
    assert any(root[0] != HALF for root in roots)

    # A zero-free half-plane near 1 and reflection symmetry still do not
    # imply all zeros have real part 1/2.
    assert all(root[0] < Fraction(7, 8) for root in roots)
    assert any(root[0] != HALF for root in roots)

    print(
        "PASS exact degree-six polynomial countermodel: reflection/conjugation "
        "symmetry, finite-height on-line zeros, and a zero-free right "
        "half-plane coexist with off-critical zeros"
    )
    print("NOTE this checks invalid inference patterns, not any RH zero or agent judgment")


if __name__ == "__main__":
    main()
