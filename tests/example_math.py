"""Independent DP/enumeration and exact period-three matrix identity, outside research."""

# Arithmetic in Z[omega], omega^2 + omega + 1 = 0, as integer pairs.
ZERO, ONE = (0, 0), (1, 0)
OMEGA = (0, 1)


def add(a, b):
    return a[0] + b[0], a[1] + b[1]


def neg(a):
    return -a[0], -a[1]


def mul(a, b):
    return a[0] * b[0] - a[1] * b[1], a[0] * b[1] + a[1] * b[0] - a[1] * b[1]


def product(a, b):
    return [
        [add(mul(a[row][0], b[0][column]), mul(a[row][1], b[1][column])) for column in range(2)]
        for row in range(2)
    ]


def main():
    identity = [[ONE, ZERO], [ZERO, ONE]]
    for weights, trace in (
        ((ONE, ONE, ONE), (4, 0)),
        ((ONE, OMEGA, (-1, -1)), ONE),
        ((ONE, (-1, -1), OMEGA), ONE),
    ):
        for phase in range(3):
            block = identity
            for number in range(phase + 1, phase + 4):
                block = product([[ONE, weights[number % 3]], [ONE, ZERO]], block)
            assert add(block[0][0], block[1][1]) == trace
            assert add(mul(block[0][0], block[1][1]), neg(mul(block[0][1], block[1][0]))) == (-1, 0)
            squared = product(block, block)
            assert all(
                add(
                    add(squared[row][column], neg(mul(trace, block[row][column]))),
                    neg(identity[row][column]),
                )
                == ZERO
                for row in range(2)
                for column in range(2)
            )
    state = [[1, 0], [0, 0], [0, 0]]
    counts = [1]
    for number in range(1, 121):
        following = [[0, 0] for _ in range(3)]
        for residue in range(3):
            following[residue][0] += sum(state[residue])
            following[(residue + number) % 3][1] += state[residue][0]
        state = following
        counts.append(sum(state[0]))
        if number <= 12:
            brute = sum(
                1
                for mask in range(1 << number)
                if not mask & (mask << 1)
                and sum(index + 1 for index in range(number) if mask & (1 << index)) % 3 == 0
            )
            assert counts[-1] == brute
    assert counts[12] == 128
    for number in range(109):
        assert (
            counts[number + 12]
            == 5 * counts[number + 9]
            - 2 * counts[number + 6]
            - 5 * counts[number + 3]
            - counts[number]
        )
    print(
        f"PASS independent residue/adjacency DP and enumeration; a_12=128; initial values {counts[:12]}; recurrence through n=120"
    )
    print(
        "PASS exact period-three traces/determinants/Cayley-Hamilton over Z[omega] in all three phases; analytic recurrence/density proof is in docs/example-math-verification.md"
    )


if __name__ == "__main__":
    main()
