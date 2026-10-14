# Reference verification, version 4

Every source cited in the version 4 documents, with what was checked and where. The version 3
table is kept in [v3/REFERENCE_VERIFICATION.md](v3/REFERENCE_VERIFICATION.md); its nine fully read
papers are listed again here without repeating the details.

"Status": **peer-reviewed** (venue confirmed on the venue's or publisher's page), **preprint**
(no peer-reviewed venue confirmed), **unconfirmed** (some field could not be checked; say which).

## Read in full in version 3 (details in the version 3 table)

| # | Reference | Status |
|---|---|---|
| 1 | Mündler, He, Wang, Sen, Song, Vechev. Type-Constrained Code Generation with Language Models. PLDI 2025. arXiv:2504.09246 | peer-reviewed |
| 2 | Abreu, Zoeteweij, van Gemund. Spectrum-Based Multiple Fault Localization. ASE 2009 | peer-reviewed |
| 3 | Pearson et al. Evaluating and Improving Fault Localization. ICSE 2017 | peer-reviewed |
| 4 | Zou, Liang, Xiong, Ernst, Zhang. An Empirical Study of Fault Localization Families and Their Combinations. IEEE TSE 2021 | peer-reviewed |
| 5 | Rezaalipour, Furia. An Empirical Study of Fault Localization in Python Programs. Empirical Software Engineering 2024. arXiv:2305.19834 | peer-reviewed |
| 6 | Lin, Koppel, Chen, Solar-Lezama. QuixBugs. SPLASH Companion 2017 | peer-reviewed |
| 7 | Spiess et al. Calibration and Correctness of Language Models for Code. ICSE 2025 | peer-reviewed |
| 8 | Kang, An, Yoo. A Quantitative and Qualitative Evaluation of LLM-Based Explainable Fault Localization (AutoFL). FSE 2024 | peer-reviewed |
| 9 | Guo, Pleiss, Sun, Weinberger. On Calibration of Modern Neural Networks. ICML 2017 | peer-reviewed |

## New in version 4

| # | Reference | Checked at | Read | Status |
|---|---|---|---|---|
| 10 | Sungmin Kang, Wonkeun Choi, Shin Yoo. A Bayesian Framework for Automated Debugging. ISSTA 2023. arXiv:2212.13773 | arXiv record; venue from the paper's own ACM reference block | sections 3.3, 3.5, 7 of the PDF | peer-reviewed |
| 11 | Dylan Callaghan, Bernd Fischer. Improving Spectrum-Based Localization of Multiple Faults by Iterative Test Suite Reduction. ISSTA 2023. arXiv:2306.09892 | ISSTA 2023 programme page; arXiv | algorithm sections, through an automated reader of the arXiv HTML version (not read line by line by me) | peer-reviewed |
| 12 | Sara Baradaran, Yifei Huang, Mukund Raghothaman, Wei Le. Prosecutor: Bayesian Counterfactual Fault Localization. OOPSLA 2026 (SPLASH 2026). DOI 10.1145/3839469 | SPLASH 2026 programme page | abstract | peer-reviewed; full text not obtained |
| 13 | Muhan Zeng, Yiqian Wu, Zhentao Ye, Yingfei Xiong, Xin Zhang, Lu Zhang. Fault Localization via Efficient Probabilistic Modeling of Program Semantics. ICSE 2022. Journal version: SmartFL: Semantics Based Probabilistic Fault Localization, IEEE TSE 2025, arXiv:2503.23224 | ICSE 2022 programme page; arXiv record | abstracts | peer-reviewed. The two Top-1 figures (21% and 14%) are from different Defects4J versions |
| 14 | Yiğit Küçük, Tim A. D. Henderson, Andy Podgurski. Improving Fault Localization by Integrating Value and Predicate Based Causal Inference Techniques. ICSE 2021. arXiv:2102.06292 | ICSE 2021 programme page | abstract | peer-reviewed |
| 15 | Yiling Lou, Ali Ghanbari, Xia Li, Lingming Zhang, Haotian Zhang, Dan Hao, Lu Zhang. Can Automated Program Repair Refine Fault Localization? A Unified Debugging Approach. ISSTA 2020. arXiv:1910.01270 | ISSTA 2020 programme page | abstract | peer-reviewed |
| 16 | Chenliang Xing, Gong Chen, Qi Xin, Xiaoyuan Xie. Revisit the Intuition of Mutation-Based Fault Localization in Real-world Programs. Internetware 2025 | Internetware 2025 programme page | abstract | peer-reviewed. The share of real faults that mutants fix is not in the abstract and is not quoted |
| 17 | Hengyuan Liu, Zheng Li, Donghua Wang, Yankai Wu, Xiang Chen, Yong Liu. FLIMs: Fault Localization Interference Mutants, Definition, Recognition and Mitigation. arXiv:2511.23302 | arXiv record | abstract | **preprint**. One search summary called it a TSE 2025 paper; the arXiv page names no venue, so it is treated as a preprint |
| 18 | Nicholas DiGiuseppe, James A. Jones. On the Influence of Multiple Faults on Coverage-Based Fault Localization. ISSTA 2011, pp. 210-220 | ISSTA 2011 programme; DBLP | record | peer-reviewed |
| 19 | Dylan Callaghan, Bernd Fischer. Mining Bug Repositories for Multi-Fault Programs. arXiv:2403.19171 | arXiv record | abstract | **preprint** as far as checked |
| 20 | An et al. Searching for Multi-Fault Programs in Defects4J. SSBSE 2021 (challenge track). arXiv:2108.04455 | conference page title via search; arXiv | search summary | **unconfirmed**: the full author list was not checked |
| 21 | David Heckerman. A Tractable Inference Algorithm for Diagnosing Multiple Diseases. UAI 1989. arXiv:1304.1511 | arXiv record; proceedings index | abstract | peer-reviewed |
| 22 | David Heckerman, Michael Shwe. Diagnosis of Multiple Faults: A Sensitivity Analysis. UAI 1993. arXiv:1303.1463 | arXiv record; proceedings index | abstract | peer-reviewed. The second author's first name is from memory of the record and should be re-checked before formal citation |
| 23 | Cristiano Varin, Nancy Reid, David Firth. An Overview of Composite Likelihood Methods. Statistica Sinica 21 (2011), 5-42 | journal page | abstract | peer-reviewed |
| 24 | Ratnadira Widyasari et al. Real World Projects, Real Faults: Evaluating Spectrum Based Fault Localization Techniques on Python Projects. Empirical Software Engineering 27 (2022). DOI 10.1007/s10664-022-10189-4 | institutional repository record | abstract | peer-reviewed. A search summary first placed it at FSE 2022; that is wrong. Co-authors not listed here because not checked |
| 25 | Kui Liu et al. You Cannot Fix What You Cannot Find! An Investigation of Fault Localization Bias in Benchmarking Automated Program Repair Systems. ICST 2019. arXiv:1812.07283 | arXiv record | abstract | peer-reviewed |
| 26 | Niklas Muennighoff et al. OctoPack: Instruction Tuning Code Large Language Models. ICLR 2024. arXiv:2308.07124 | ICLR 2024 proceedings page | abstract; the data set itself | peer-reviewed. Bug-type counts were computed from the downloaded data, not taken from the paper |
| 27 | ConformalFL: Calibrated Inspection Cutoffs for Spectrum-Based Fault Localization. Research Square, article rs-10559885, version 1 | title confirmed on the hosting page | search summary only | **preprint, unconfirmed**: authors and date could not be read. Its findings are quoted only as "by a search summary" |
| 28 | Pedro Orvalho et al. CFaults: Model-Based Diagnosis for Fault Localization in C Programs with Multiple Test Cases. arXiv:2407.09337 | arXiv identifier via search | search summary | **unconfirmed**: authors and venue not checked |

## Cited from the record only (carried over from version 3)

Papadakis and Le Traon, Metallaxis-FL, STVR 2015; Moon, Kim, Kim and Yoo, MUSE, ICST 2014; Xie,
Chen, Kuo and Xu, TOSEM 2013; Baah, Podgurski and Harrold (probabilistic program dependence
graph); Nath and Domingos (tractable probabilistic models for fault localisation, arXiv:1507.01698);
Landsberg et al. (Doric).

## Not cited because they could not be verified well enough

* Debroy and Wong, "Insights on Fault Interference for Programs with Multiple Bugs", ISSRE 2009:
  a search returned a listing with the same title and different authors. Not cited.
* Zakari et al., systematic review of multiple fault localisation, Information and Software
  Technology 2020: the article page could not be matched to the authors. Not cited.
* Higher-order-mutant studies of multi-fault localisation and the method for deep-learning
  programs are mentioned in the review only as search results, without bibliographic claims.

## Data sets used

| Data set | Source | Licence | Version used |
|---|---|---|---|
| QuixBugs | github.com/jkoppel/QuixBugs | MIT | commit 4257f44b0ff1181dedaedee6a447e133219fcebf |
| HumanEvalPack, Python split | huggingface.co/datasets/bigcode/humanevalpack, file `python/test-00000-of-00001.parquet` | MIT (data set card) | downloaded 2026-10-13; SHA-256 in BASELINE_FREEZE.md |
