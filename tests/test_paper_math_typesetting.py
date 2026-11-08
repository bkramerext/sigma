"""Regression coverage for escaped mathematical notation in authored papers."""

from __future__ import annotations

import unittest

from sigma import papers, project_reports

# Exact math shapes previously rendered as visible dollar signs and
# printable backslash commands in an RH paper (not a special-case repair).
RH_MATH_EXPRESSIONS = (
    r"\xi(s)=\tfrac12s(s-1)\pi^{-s/2}\Gamma(s/2)\zeta(s)",
    r"\Xi(z)=\xi(\tfrac12+iz)",
    r"g(t)=e^{-64\cosh t}",
    r"128\cosh(t)\sinh(a)<128\cdot2\cdot2a\leq8",
    r"|V_i'-V_j'|=d_{ij}\coth(t-m_{ij})<2d_{ij}",
    r"\limsup_{R\to\infty}\log\log M_H(R)/\log R",
    r"\sqrt r\,e^rU_z(\log r)\longrightarrow\sqrt{\pi/2}",
    r"\theta=\arctan(4/3)",
    r"\liminf_{x\to\infty}(\Psi(x)-x)/x^{3/4}=-8/5",
    r"\Phi(t-a)+2\cosh(a\delta)\Phi(t)+\Phi(t+a)",
    r"a\downarrow0",
)


class MathTypesettingTests(unittest.TestCase):
    def test_valid_research_math_remains_math(self) -> None:
        for body in RH_MATH_EXPRESSIONS:
            with self.subTest(math=body):
                self.assertTrue(papers._safe_math(body))
                rendered = papers._latex_prose("Given $" + body + "$.")
                self.assertNotIn(r"\textbackslash{}", rendered)
                self.assertNotIn(r"\$", rendered)
                self.assertTrue("$" + body + "$" in rendered or r"\[" + body in rendered)

    def test_legacy_escaped_math_is_recovered_exactly(self) -> None:
        for body in RH_MATH_EXPRESSIONS:
            with self.subTest(math=body):
                original = "$" + body + "$"
                escaped = project_reports._latex(original)
                repaired, count = papers._restore_escaped_math_in_tex(
                    r"\begin{document}" + "\n" + escaped + "\n" + r"\end{document}"
                )
                self.assertEqual(count, 1)
                self.assertNotIn(r"\textbackslash{}", repaired)
                self.assertNotIn(r"\$", repaired)
                self.assertNotIn(
                    "An inline mathematical expression was escaped into printable text.",
                    papers._tex_static_diagnostics(repaired),
                )

    def test_unknown_tex_command_is_never_unescaped(self) -> None:
        unsafe = project_reports._latex(r"$\input{private-file}$")
        rendered = papers._latex_prose(r"$\input{private-file}$")
        self.assertEqual(rendered, unsafe)
        repaired, count = papers._restore_escaped_math_in_tex(
            r"\begin{document}" + "\n" + unsafe + "\n" + r"\end{document}"
        )
        self.assertEqual(count, 0)
        self.assertIn(unsafe, repaired)
        self.assertIn(
            "An inline mathematical expression was escaped into printable text.",
            papers._tex_static_diagnostics(repaired),
        )


if __name__ == "__main__":
    unittest.main()
