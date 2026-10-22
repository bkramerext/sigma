# Independent verification of the included mathematical fixture

This note verifies the supplied exercise. It is not a research result produced
by SIGMA and is deliberately outside the active project template.

Let P_n(q) sum q raised to the selected-index sum over all nonconsecutive subsets
of {1,...,n}. Separating subsets according to whether n is selected gives
P_n(q)=P_(n-1)(q)+q^n P_(n-2)(q), with P_0=1 and P_1=1+q. For a primitive cube
root omega, the roots-of-unity filter gives

    a_n = (P_n(1) + P_n(omega) + P_n(omega^2))/3.

Use A_i(q)=[[1,q^i],[1,0]] to advance the vector (P_i,P_(i-1)).
For q^3=1, the three-step matrix B_r=A_(r+3) A_(r+2) A_(r+1)
is constant along each phase modulo 3. Its determinant is -1 and its trace is
1+q^(r+1)+q^(r+2)+q^(r+3). This is 4 for q=1, and 1 for either primitive cube
root. Cayley–Hamilton therefore gives B_r^2-4B_r-I=0 in the first case and
B_r^2-B_r-I=0 in the other two. This applies to each phase, including n=0 by
advancing the valid initial pair (P_1,P_0).

Let E shift n by three. The filtered sum is annihilated by the product

    (E^2-4E-1)(E^2-E-1) = E^4-5E^3+2E^2+5E+1.

Consequently, for every n>=0,

    a_(n+12) = 5a_(n+9)-2a_(n+6)-5a_(n+3)-a_n.

Sufficient initial values a_0,...,a_11 are
1,1,1,2,3,5,8,12,19,31,49,79. Independent residue/adjacency DP and exhaustive
subset enumeration through n=12 give a_12=128. The executable scenario also
checks the recurrence through n=120. Those finite checks alone are not the proof;
the periodic transfer identity establishes it for all n.

For the limiting density, P_n(1)=F_(n+2). The nontrivial three-step characteristic
roots satisfy x^2-x-1=0, so both complex weighted terms are O(phi^(n/3)), phase
by phase, with phi=(1+sqrt(5))/2. The ordinary Fibonacci term grows as a positive
constant times phi^n. Their ratio tends to zero, and the filter yields

    a_n / F_(n+2) -> 1/3.

`tests/example_math.py` uses exact integer-pair arithmetic in Z[omega] to
verify the traces, determinants and matrix identities in all three phases. Its
DP separately tracks residue and whether the previous index was selected, and
cross-checks against exhaustive enumeration. No answer, proof, completed stage,
AI provenance, Lean artifact or claimed agent activity is inserted into the seed.
