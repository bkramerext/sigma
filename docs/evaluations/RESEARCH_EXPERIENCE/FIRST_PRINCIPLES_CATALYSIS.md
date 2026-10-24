# Can We Predict Chemical Reactions from Quantum Mechanics? — research experience evaluation

Study in progress. Blue; assignment supplied directly by the human, 2026-10-24.

## Sample identity and research objective

`first-principles-catalysis` — FUNDAMENTAL OPEN QUESTION. Can molecular quantum mechanics be turned into a reliable, predictive theory of chemical reactivity: given reactants, conditions and no fitted outcome for the target reaction, predict the kinetically accessible pathways, activation free energies, relative rates and product distribution with calibrated uncertainty? Focus on a tractable but genuinely hard subproblem: predicting when approximate electronic-structure calculations mis-rank competing reaction pathways in an unseen class of elementary organic reactions, and devising a physically justified, testable diagnostic that anticipates the failure. The scientific challenge is not computing a known transition state or training another random-split reaction classifier; it is out-of-domain, rate-relevant generalization.

EXISTING WORK, NOT NOVEL. Quantum mechanics governs molecules, and quantum chemical transition-state calculations and machine-learned barrier corrections are well-established. The public RDB7 dataset (about 12,000 H/C/N/O elementary reactions with up to seven heavy atoms) includes reaction/transition state geometries and high-level quantum reference energies; recent benchmark work re-evaluates its DFT errors. Regenerating a published error table, applying a standard model on a random train/test split, or reporting one unvalidated transition state is not a novel result.

BOUNDED QUESTION. Can a diagnostic based on physically interpretable electronic and geometric descriptors predict *before a high-level calculation* which low-cost approximate barrier computations will fail, or which of two closely competing reaction channels will reverse ordering? Compare distinct electronic-structure error regimes, including reactions with multiple channels, and attempt a correction or adaptive escalation rule. Select one public curated reaction family or cluster for discovery, then reserve a chemically disjoint family or independently published dataset for a blinded test. Verify dataset coverage and method/fidelity comparability; perform grouping by parent reactant, reaction family and near-duplicate transition-state structures to prevent leakage. Do not confuse calculated energies with experimental rates.

CANDIDATE MECHANISMS. Hypotheses include multireference character, charge transfer, bond rearrangement complexity, strain, competing conformations and limitations of DFT error cancellation. Screen each against prior work. Seek a previously unreported *conditional pattern* or error predictor that changes a concrete chemical prediction, not a generic accuracy improvement without explanatory value.

METHOD. Start with a cited prior-art review and metadata audit; recompute a small reproducing baseline. State quantum methods, reference levels, conformer and stereochemical assumptions, gas-phase or solvent context, standard states, temperature and uncertainty. Provide a preregistered train/validation split and metrics: barrier MAE, pairwise pathway-order error, ranking calibration and computational cost. Compare to baseline low-cost DFT alone, a naive error threshold and at least one documented published correction if reproducible. Track resources and failures, avoid claiming use of unavailable proprietary solvers or inventing computed values.

EXIT CRITERIA. A NOVEL COMPUTATIONAL RESULT requires (1) a literature-screened, specific and chemically interpretable new relationship or decision rule, (2) a prospective prediction on a chemically held-out test set or new high-fidelity quantum calculations not used in design, (3) a reported effect with bootstrap uncertainty and a meaningful, prespecified improvement over known baselines, (4) reproducible input structures, code/parameters, energy units, reference levels and error analysis, and (5) at least one mechanistically informative counterexample. A VERIFIED CHEMICAL PREDICTION requires additional independent high-quality computation or experimental kinetics/product data appropriately matched to conditions; the RDB7 reference itself is theoretical, not independent experimental truth. If tests fail, report NEGATIVE/UNRESOLVED with the failed hypothesis, exact counterexample and limits. A neat derivation or literature summary alone is NOT success. Solving this narrow benchmark is not solving the general quantum prediction problem.

STARTING SOURCES. Grambow, Pattanaik and Green, Scientific Data 7, 137 (2020), DOI 10.1038/s41597-020-0460-4; reanalysis in PCCP 2025, DOI 10.1039/D5CP01181G. Search for newer overlapping error-calibration and barrier-prediction methods before selecting a candidate.

## Researcher expectation

A useful first advance is an auditable data-coverage and leakage audit, followed by one preregistered pathway-order diagnostic against a cheap baseline. Reference electronic energies are not experimental product yields, and a novel chemical mechanism needs evidence beyond polished proposals.

## Evaluation status

Expectation recorded before detailed outcome assessment. Browser and evidence findings will replace this provisional status. No live model calls authorized.
