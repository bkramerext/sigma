"""Offline tests for TeX option consistency gate."""
import unittest
from tex_option_gate import audit_tex


class TexOptionGateTests(unittest.TestCase):
    def test_disabled_excerpts_with_provider_schema(self):
        tex = ("\\section{Body}\nA useful paragraph.\n"
               "\\section{Selected source-linked research excerpts}\n"
               "\\subsection{Research excerpt 1}\n"
               "\\textit{Source: }steps/0/provider\\_input\\_audit/request\\_body/text/format/schema\n"
               r'\{"items": "type": "array"\}' + "\n")
        metadata = {"generation": {"include_research_excerpts": False,
                    "layout_warnings": ["warning: report.tex:5: Overfull \\hbox (12pt too wide)"]}}
        result = audit_tex(tex, metadata)
        self.assertEqual(result["excerpt_subsections"], 1)
        self.assertEqual(len(result["review_flags"]), 2)
        self.assertEqual(result["provider_schema_lines"], [5])

    def test_explicit_excerpts_allowed(self):
        tex = "\\section{Selected source-linked research excerpts}\n\\subsection{Research excerpt 1}\nA legitimate source.\n"
        result = audit_tex(tex, {"generation": {"include_research_excerpts": True}})
        self.assertEqual(result["review_flags"], [])

    def test_long_url_warning_is_context_not_proof(self):
        tex = "Header\nhttps://example.org/long_path/file.pdf\n"
        result = audit_tex(tex, {"generation": {"layout_warnings": ["warning: report.tex:2: Overfull \\hbox (99pt too wide)"]}})
        self.assertEqual(result["overfull_line_contexts"][0]["candidate_signals"], ["nearby_raw_url"])
        self.assertEqual(result["review_flags"], [])


if __name__ == "__main__":
    unittest.main()
