# Reference verification

Checked on 13 October 2026. "Full text read" means the PDF itself was read (the base paper from the
supplied file, the others from open-access copies). "Record" means the bibliographic data were
confirmed against a publisher, conference, DBLP, OpenAlex or author page, but the paper was not read.

No venue is described here as "top tier". Venue names are given as they appear in the records.

## Papers read in full

| # | Reference | Venue and year | DOI or identifier | How the record was verified | Full text source |
|---|---|---|---|---|---|
| 1 | Mündler, He, Wang, Sen, Song, Vechev. Type-Constrained Code Generation with Language Models | Proceedings of the ACM on Programming Languages (PLDI), 2025; page headers show article 171 | 10.1145/3729274; arXiv:2504.09246v2 | PLDI 2025 programme page; OpenAlex record for the DOI; arXiv record links the DOI | PDF supplied by the user (38 pages) |
| 2 | Abreu, Zoeteweij, van Gemund. Spectrum-based Multiple Fault Localization | 24th IEEE/ACM International Conference on Automated Software Engineering (ASE), 2009, pp. 88-99 | DOI not checked | University of Minho archive of the first author's publications | Author-archive PDF |
| 3 | Pearson, Campos, Just, Fraser, Abreu, Ernst, Pang, Keller. Evaluating and Improving Fault Localization | 39th International Conference on Software Engineering (ICSE), 2017, pp. 609-620 | 10.1109/ICSE.2017.62 | Authors' publication pages (Just, Ernst) | Author-page PDF |
| 4 | Zou, Liang, Xiong, Ernst, Zhang. An Empirical Study of Fault Localization Families and Their Combinations | IEEE Transactions on Software Engineering 47(2), 332-347, 2021 (online 2019) | 10.1109/TSE.2019.2892102; arXiv:1803.09939v2 | Ernst's publication page gives volume and pages; arXiv says accepted by TSE in December 2018. The IEEE Xplore page itself was not opened | arXiv PDF (v2) |
| 5 | Rezaalipour, Furia. An Empirical Study of Fault Localization in Python Programs | Empirical Software Engineering 29(4), article 92, 2024 | arXiv:2305.19834v3; **publisher DOI not confirmed** | DBLP entry and the project's citation file | arXiv PDF (v3) |
| 6 | Lin, Koppel, Chen, Solar-Lezama. QuixBugs: A Multi-Lingual Program Repair Benchmark Set Based on the Quixey Challenge | SPLASH Companion 2017, 2 pages | 10.1145/3135932.3135941 | ACM reference block printed in the paper | PDF from the benchmark's site |
| 7 | Spiess, Gros, Pai, Pradel, Rabin, Alipour, Jha, Devanbu, Ahmed. Calibration and Correctness of Language Models for Code | 47th International Conference on Software Engineering (ICSE), 2025 | arXiv:2402.02047v4; publisher DOI not checked | ICSE 2025 research-track programme page | arXiv HTML (v4); the last 10% of the page (appendix) was not read |
| 8 | Kang, An, Yoo. A Quantitative and Qualitative Evaluation of LLM-Based Explainable Fault Localization | ACM International Conference on the Foundations of Software Engineering (FSE), 2024 | 10.1145/3660771 (as listed by arXiv; ACM page not opened); arXiv:2308.05487v3 | arXiv record states acceptance at FSE 2024; FSE 2024 site lists the paper | arXiv PDF (v3) |
| 9 | Guo, Pleiss, Sun, Weinberger. On Calibration of Modern Neural Networks | 34th International Conference on Machine Learning (ICML), PMLR 70, 2017 | arXiv:1706.04599v2 | Proceedings line printed in the paper | arXiv PDF (v2) |

## Works cited from records only

| Reference | Venue and year | Identifier | Verified through | Not verified |
|---|---|---|---|---|
| Zeng, Wu, Ye, Xiong, Zhang, Zhang. Fault Localization via Efficient Probabilistic Modeling of Program Semantics | ICSE 2022 | not checked | ICSE 2022 programme page; Peking University lab page | Full text; reported numbers are from abstract-level sources |
| SmartFL: Semantics Based Probabilistic Fault Localization (extended version) | IEEE TSE 2025 | 10.1109/TSE.2025.3574487; arXiv:2503.23224 | OpenAlex, arXiv | Full text |
| Baah, Podgurski, Harrold. The Probabilistic Program Dependence Graph and Its Application to Fault Diagnosis | ISSTA 2008, pp. 189-200; IEEE TSE 36(4), 528-545, 2010 | 10.1145/1390630.1390654 (ISSTA) | DBLP | Full text; that the TSE article extends the ISSTA paper is assumed, not checked |
| Nath, Domingos. Learning Tractable Probabilistic Models for Fault Localization | AAAI 2016 | 10.1609/aaai.v30i1.10175 | AAAI proceedings page | Full text |
| Landsberg, Barr. Doric: Foundations for Statistical Fault Localisation | arXiv 2018 | arXiv:1810.00798 | arXiv | Whether a peer-reviewed version exists |
| Papadakis, Le Traon. Metallaxis-FL: mutation-based fault localization | Software Testing, Verification and Reliability 25, 605-628, 2015 | 10.1002/stvr.1509 | University of Luxembourg repository record | Full text (the download failed); the definition used in this project is the one in Pearson et al., §III-A |
| Moon, Kim, Kim, Yoo. Ask the Mutants: Mutating Faulty Programs for Fault Localization (MUSE) | ICST 2014 | not checked | Cited as reference [30] in Pearson et al. | Record and full text; definition taken from Pearson et al. |
| Xie, Chen, Kuo, Xu. A Theoretical Analysis of the Risk Evaluation Formulas for Spectrum-Based Fault Localization | ACM TOSEM 22(4), article 31, 2013 | 10.1145/2522920.2522924 | Crossref and OpenAlex records | Full text (repository unreachable) |

References already listed in `docs/REPORT.md` of version 2.0.0 keep the status given there.

## Benchmark verification

| Benchmark | Source | Version used | Licence | Suitability decision |
|---|---|---|---|---|
| QuixBugs | github.com/jkoppel/QuixBugs | commit `4257f44b0ff1181dedaedee6a447e133219fcebf` (29 August 2022), shallow clone, 2.3 MB | MIT (file `LICENSE`, copyright James Koppel 2017-2019) | **Used.** Python, single-function programs of 3 to 18 statements, one human-written single-line bug each, correct versions included. 31 of 40 programs have JSON test cases; the other 9 need object graphs and are excluded |
| BugsInPy | github.com/soarsmu/BugsInPy | not downloaded | not checked | **Not used.** Real project bugs need per-project environments, multi-file coverage and thousands of statements per fault, beyond exact inference and beyond the time available. Recorded as future work |
| Defects4J | github.com/rjust/defects4j | not downloaded | not checked | **Not used.** Java; the project analyses Python |

## Values quoted from papers

Every number attributed to a paper in `LITERATURE_REVIEW.md` was read in the paper's own text or
tables, with two caveats:

* Guo et al.: the range "4 to 10%" is from the text of the results section; no figure-panel values
  are quoted.
* Zeng et al. (SmartFL): no numbers are quoted, because the paper was not read.

## Sources

* https://pldi25.sigplan.org/details/pldi-2025-papers/25/Type-Aware-Constraining-for-LLM-Code-Generation
* https://arxiv.org/abs/2504.09246
* https://webarchive.di.uminho.pt/haslab.uminho.pt/ruimaranhao/files/ase09-1.pdf
* https://homes.cs.washington.edu/~rjust/publ/fault_localization_effectiveness_icse_2017.pdf
* https://arxiv.org/abs/1803.09939 and https://homes.cs.washington.edu/~mernst/pubs/fl-families-tse2019-abstract.html
* https://arxiv.org/abs/2305.19834 and https://dblp.org/pid/247/9795
* https://jkoppel.github.io/QuixBugs/quixbugs.pdf
* https://arxiv.org/html/2402.02047v4 and https://conf.researchr.org/details/icse-2025/icse-2025-research-track/8/Calibration-and-Correctness-of-Language-Models-for-Code
* https://arxiv.org/abs/2308.05487 and https://2024.esec-fse.org/details/fse-2024-posters/19/A-Quantitative-and-Qualitative-Evaluation-of-LLM-based-Explainable-Fault-Localization
* https://arxiv.org/abs/1706.04599
* https://conf.researchr.org/details/icse-2022/icse-2022-papers/37/Fault-Localization-via-Efficient-Probabilistic-Modeling-of-Program-Semantics
* https://arxiv.org/abs/2503.23224
* https://www.doi.org/10.1145/1390630.1390654
* https://ojs.aaai.org/index.php/AAAI/article/view/10175
* https://arxiv.org/abs/1810.00798
* https://orbilu.uni.lu/handle/10993/15363
* https://api.crossref.org/works/10.1145%2F2522920.2522924
