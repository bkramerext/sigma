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



# Representative expressions preserved verbatim from the two Warp Drive PDFs.
# v3 page 6 (\gg), pages 13–14 (\rm), and v2 page 15 (\dfrac).
WARP_DRIVE_MATH_EXPRESSIONS = (
    r"qL_{\mathrm{bg}}\gg1",
    r"|\Omega|L_{\mathrm{bg}}\gg1",
    r"\|\mathcal A_{\rm control}\|^2=\gamma^4|\dot u|^2+\gamma^6(u\cdot\dot u)^2",
    r"\|\mathcal A_{\rm gradient}\|^2=\gamma^4u_q^2[|\nabla a|^2-(\nabla a\cdot u)^2]",
    r"m_{\rm p}c^2\alpha",
    r"j_{\rm p}^\mu",
    r"T_{\rm app}^{\mu\nu}",
    r"\nabla_\mu T_{\rm p}^{\mu\nu}=F^{\nu\rho}j_{{\rm p}\rho}",
    r"\alpha\leq\dfrac{\Omega}{(2\eta-\eta^2)^{3/2}}+\dfrac{(1-\eta)K}{2\eta-\eta^2}",
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


    def test_warp_drive_formulas_are_rendered_as_math(self) -> None:
        for body in WARP_DRIVE_MATH_EXPRESSIONS:
            with self.subTest(math=body):
                self.assertTrue(papers._safe_math(body))
                rendered = papers._latex_prose("The result is $" + body + "$.")
                self.assertIn("$" + body + "$", rendered)
                self.assertNotIn(r"\textbackslash{}", rendered)
                self.assertNotIn(r"\$", rendered)

    def test_warp_drive_escaped_math_is_recovered_without_rewriting(self) -> None:
        for body in WARP_DRIVE_MATH_EXPRESSIONS:
            with self.subTest(math=body):
                original = "$" + body + "$"
                escaped = project_reports._latex(original)
                repaired, count = papers._restore_escaped_math_in_tex(
                    r"\begin{document}" + "\n" + escaped + "\n" + r"\end{document}"
                )
                self.assertEqual(count, 1)
                self.assertIn(original, repaired)
                self.assertNotIn(r"\textbackslash{}", repaired)
                self.assertNotIn(
                    "An inline mathematical expression was escaped into printable text.",
                    papers._tex_static_diagnostics(repaired),
                )

    def test_warp_drive_consecutive_formulas_and_prose(self) -> None:
        section = (
            r"The frequency window requires $qL_{\mathrm{bg}}\gg1$ "
            r"and $|\Omega|L_{\mathrm{bg}}\gg1$."
        )
        rendered = papers._latex_prose(section)
        self.assertIn(r"$qL_{\mathrm{bg}}\gg1$", rendered)
        self.assertIn(r"$|\Omega|L_{\mathrm{bg}}\gg1$", rendered)
        self.assertNotIn(r"\textbackslash{}", rendered)
        self.assertNotIn(r"\$", rendered)


if __name__ == "__main__":
    unittest.main()
