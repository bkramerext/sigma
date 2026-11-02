# Reference curation audit — 2026-11-02

This audit applies to the curated project-type links in `src/sigma/data/builtin_project_types.json`. It evaluates **source fitness for SIGMA's AI agents**, not the scientific standing of the authors or correctness of any research conclusion. See #468 for extracting, synthesizing and reviewing source-controlled digests.

## Rubric

- **Brevity (B, 0–5)**: 5 for roughly 1–10 pages or an equivalent compact substantive HTML text; 3 for ~11–20 pages or a focused chapter; 0–1 for full textbooks/handbooks.
- **Density (D, 0–5)**: proportion of useful, specific instruction without boilerplate or repetition.
- **Coverage (C, 0–5)**: coverage of important methodological/editorial steps *appropriate to the assigned discipline*. Specialized documents may earn less, even when excellent.
- **AI readability (A, 0–5)**: accessible selectable text, minimal visual overhead/navigation, and a simple extraction path.
- **Total (0–20)**: target ≥16. A dead, gated, or substantively empty link **fails regardless of score**. These scores are editorial judgments, not automated, reproducible benchmarks.

## Source scores

| Scope | Purpose | Named source (clickable) | B | D | C | A | /20 | Assessment |
|---|---|---|---:|---:|---:|---:|---:|---|
| Common | Research | [University of Connecticut — Critical Reading Methods for Scientific Research](https://guides.lib.uconn.edu/c.php?g=1067492&p=7986329) | 4 | 4 | 4 | 4 | **16** | Cross-disciplinary critical reading; library chrome but substantive questions. |
| Common | Research | [Brandeis University — Writing a Literature Review: Critical Source Synthesis](https://www.brandeis.edu/writing-program/resources/faculty/handouts/writing-a-literature-review.html) | 5 | 5 | 4 | 4 | **18** | Research synthesis, contrasting claims and comparing sources. |
| Common | Publication | [UW–Madison — Writing a Research Paper: Organization and Evidence](https://writing.wisc.edu/handbook/academicwriting/planresearchpaper/) | 5 | 4 | 4 | 3 | **16** | Cross-genre research-paper structure; modest site navigation. |
| Common | Publication | [Brandeis University — Concision: Five Editing Rules](https://www.brandeis.edu/writing-program/resources/faculty/handouts/concision.html) | 5 | 5 | 4 | 4 | **18** | Five concrete concision edits; compact web page. |
| Biology | Research | [NIH — Experimental Design and Reproducibility, Introduction (PDF)](https://oir.nih.gov/system/files/media/file/2021-08/rcr_training-introduction.pdf) | 5 | 4 | 3 | 5 | **17** | Two-page NIH reproducibility module introduction; limited experimental-design depth. |
| Biology | Publication | [University of Georgia — Biology Research Paper Guidelines (6-page PDF)](https://biosciences.uga.edu/sites/default/files/2026-01/BIOL%2049X0R%20Research%20paper%20guidelines_Jan2026.pdf) | 5 | 3 | 4 | 4 | **16** | Six-page paper guidance; some course-specific administrative rules. |
| Chemistry | Research | [UCLA Chemistry — Research Proposal Guidelines: Questions, Methods, Evidence](https://www.chemistry.ucla.edu/undergraduate/undergraduate-research/research-proposal-guidelines/) | 5 | 4 | 4 | 5 | **18** | Compact UCLA chemistry research framing, hypotheses, methods and evidence. |
| Chemistry | Publication | [Kenyon College — A Brief Guide to Writing in Chemistry (PDF)](https://chemistry.kenyon.edu/getzler/08F-CourseFiles/BriefGuideWritingChemistry.pdf) | 5 | 4 | 4 | 5 | **18** | Nine-page Kenyon chemistry report-writing handout. |
| Computer Science | Research | [ACM SIGSOFT — Engineering Research Standard (plain Markdown)](https://raw.githubusercontent.com/acmsigsoft/EmpiricalStandards/master/docs/standards/EngineeringResearch.md) | 4 | 5 | 5 | 5 | **19** | Raw, extractable ACM SIGSOFT Markdown; empirical engineering research standard. |
| Computer Science | Publication | [Jennifer Widom (Stanford) — Tips for Writing Technical Papers](https://cs.stanford.edu/people/widom/paper-writing.html) | 5 | 5 | 5 | 5 | **20** | Minimal HTML, section-by-section paper instructions by Jennifer Widom. |
| Economics | Research | [Reed College — Guide to Reading and Evaluating Economics Papers](https://www.reed.edu/economics/parker/354/guide.html) | 5 | 5 | 5 | 4 | **19** | Reed distinguishes theoretical, empirical, case, synthesis and robustness. |
| Economics | Publication | [Brandeis University — Writing Tips for an Economics Paper](https://www.brandeis.edu/writing-program/resources/faculty/wi-instructor-resources/econ-tips.html) | 5 | 5 | 5 | 4 | **19** | Concise discipline-specific paper structure, evidence, theory and data. |
| Engineering | Research | [NASA — Systems Engineering: 6.8 Decision Analysis](https://www.nasa.gov/reference/6-8-decision-analysis/) | 4 | 5 | 4 | 3 | **16** | Focused NASA decision analysis subsection; website navigation/figures remain. |
| Engineering | Publication | [University of Toronto — Short Engineering Reports: Structure, Analysis, Recommendations](https://ecp.engineering.utoronto.ca/resources/online-handbook/types-of-documents/short-reports/) | 4 | 5 | 5 | 4 | **18** | Toronto short technical report: scope, structure, results, recommendations. |
| Law | Research | [Chapman University Law — Legal Research: The Research Process](https://libguides.law.chapman.edu/legalresearchbasics/researchprocess) | 5 | 5 | 4 | 4 | **18** | Legal authority research workflow and jurisdiction/source distinctions. |
| Law | Publication | [Columbia Law School — Organizing a Legal Discussion: IRAC/CRAC (PDF)](https://www.law.columbia.edu/sites/default/files/2021-07/organizing_a_legal_discussion.pdf) | 5 | 5 | 4 | 5 | **19** | Five-page Columbia legal IRAC/CRAC argument organization. |
| Literature | Research | [Brandeis University — Close Reading: A Step-by-Step Guide](https://www.brandeis.edu/writing-program/resources/faculty/writing-handbook/01-critical-thinking/close-reading-step-by-step.html) | 5 | 5 | 4 | 4 | **18** | Close reading sequence and textual evidence; concise substantive text. |
| Literature | Publication | [Harvard — A Brief Guide to Writing the English Paper (PDF)](https://writingprogram.fas.harvard.edu/sites/g/files/omnuum4511/files/2025-11/BG%20Writing%20English.pdf) | 5 | 5 | 5 | 4 | **19** | Six-page Harvard literary analysis report writing. |
| Mathematics | Research | [Northeastern University — Mathematical Problem Solving and Proof Strategies](https://dummit.cos.northeastern.edu/teaching_fa19_1365/1365_problemsolving) | 5 | 4 | 5 | 5 | **19** | Northeastern problem-solving strategies, counterexamples and proof checks. |
| Mathematics | Publication | [Keith Conrad — Advice on Mathematical Writing (full text)](https://kconrad.math.uconn.edu/blurbs/proofs/writingtips.pdf) | 5 | 5 | 5 | 4 | **19** | Ten-page Keith Conrad writing guidance; mathematical symbols require extraction care. |
| Military | Research | [U.S. Army — MDMP & Risk: Critical Assumptions, Courses of Action, Wargaming](https://www.army.mil/article/289381/mdmp_risk) | 5 | 5 | 4 | 4 | **18** | U.S. Army risk-driven decision process; tactical framing needs ONP adaptation. |
| Military | Publication | [Virginia Defense Force — Decision Paper Writing and Format (PDF)](https://www.vdf.virginia.gov/pdf/FORMS/VDF%20Decision%20Paper.pdf) | 5 | 4 | 4 | 4 | **17** | Direct PDF of decision-paper rules and example; some administrative form fields. |
| Philosophy | Research | [Connie Rosati (University of Arizona) — How to Analyze a Philosophical Argument (PDF)](https://philosophy.arizona.edu/sites/philosophy.arizona.edu/files/Rosati%2C%20How%20to%20Read%20a%20Philosophical%20Article%20or%20Book.pdf) | 5 | 5 | 4 | 5 | **19** | Brief Arizona handout for identifying premises, arguments and objections. |
| Philosophy | Publication | [Harvard Writing Center — A Brief Guide to Writing the Philosophy Paper (7-page PDF)](https://philosophy.fas.harvard.edu/sites/g/files/omnuum4436/files/phildept/files/brief_guide_to_writing_philosophy_paper.pdf) | 5 | 5 | 5 | 4 | **19** | Seven-page Harvard guide, concise argument and objection structure. |
| Physics | Research | [NASEM — Assessing the Reliability of Complex Models](https://www.nationalacademies.org/read/13395/chapter/2) | 3 | 5 | 5 | 3 | **16** | NASEM model-validation summary chapter, not whole book; HTML site boilerplate. |
| Physics | Publication | [Georgetown University Physics — General Guidelines for Scientific Writing](https://physics.georgetown.edu/general-guidelines-scientific-writing/) | 5 | 5 | 4 | 3 | **17** | Georgetown physics writing guidelines; website navigation. |
| Religion | Research | [Oliver Freiberger — Elements of a Comparative Methodology in the Study of Religion (14-page article PDF)](https://www.wisdomlib.org/uploads/journals/mdpi-relig/2018-volume-9-issue-2--2077-1444-9-2-38-.pdf) | 3 | 5 | 4 | 5 | **17** | 14-page primary methodology article; comparison only, not every religion question. |
| Religion | Publication | [UNC Charlotte Religious Studies — Writing Papers That Develop a Thesis](https://religiousstudies.charlotte.edu/writing-papers-develop-thesis) | 5 | 5 | 5 | 3 | **18** | UNC Charlotte writing thesis, evidence, critical analysis; site navigation. |

## Notes / follow-up

- All linked candidates were screened against retrievable public content, or a matching GitHub source document for the raw ACM Markdown. This is **not** proof that SIGMA's stricter runtime fetch/extraction path accepts every link; runtime validation and source retention belongs in #468.
- Avoid PDF-only selection rules: a compact, plain HTML page or raw Markdown file is often more useful for AI than a PDF with figures/columns.
- The two highest-risk residual sources are **Physics research** (NASEM summary page has extensive site chrome) and **Engineering research** (NASA chapter contains navigation/figures). Their subject coverage justifies retaining them for now; digest processing in #468 should extract only the substantive section.
- **Military** research and publication must remain decision/strategy-oriented, not laboratory prose; **Literature** should prioritize close reading and argument, not IMRaD.
- **Chemistry** research is no longer an 86-page analytical method-validation book. It is a compact UCLA methodology outline.
- The former **NASA 356-page**, **Hammack 380-page**, and **JBI 190-page** guides and inaccessible Buffalo/Army War College PDF URLs have been removed.
