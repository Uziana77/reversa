# AURA experiment summary

## Mean metrics per experiment

| exp | capture_rate | statement_bleu4 | statement_bertscore_f1 | docs_bleu4 | docs_bertscore_f1 | docs_glossary_recall | unit_coverage | traceability_density | valid_span_rate | ber | testable_share | gate_block_rate | llm_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0 | 0.4653 | 0.0 | 0.5 | 0.0107 | 0.8028 | 0.7245 | 0.75 | 1.0 | 1.0 | 0.2242 | 0.5272 | 0.0 | 19.0 |
| A1 | 0.4653 | 0.0 | 0.5 | 0.0105 | 0.795 | 0.7245 | 0.75 | 1.0 | 1.0 | 0.2535 | 1.0 | 0.0 | 18.0 |
| A2 | 0.0 | 0.0 | 0.0 | 0.0111 | 0.7433 | 0.6169 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 23.0 |
| A3 | 0.4653 | 0.0 | 0.5 | 0.0104 | 0.8058 | 0.7245 | 0.75 | 1.0 | 1.0 | 0.2242 | 0.5272 | 0.0 | 19.0 |
| B1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.4321 | 0.006 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.8333 |
| B2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.2475 | 0.0105 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 4.0 |
| B3 | 0.0 | 0.0 | 0.0 | 1.0 | 1.0 | 0.9425 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| S1 | 0.4653 | 0.0 | 0.5 | 0.0263 | 0.8641 | 0.8639 | 0.75 | 1.0 | 1.0 | 0.2242 | 0.2727 | 1.0 | 19.0 |

## Safety gate (S1: injected false rules)

- injected: 10.0 per unit (mean)
- labelled contradicted (blocked): 10.0
- survived: 0.0 — block rate 1.0

## A0 vs ... (Wilcoxon signed-rank, per unit)

- A0_vs_A1 on docs_bleu4: W=1.5, p=0.2012, rank-biserial=0.7, n=6
- A0_vs_A1 on docs_bertscore_f1: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_A1 on docs_glossary_recall: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_A1 on capture_rate: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_A1 on ber: W=0, p=0.1797, rank-biserial=-1.0, n=6
- A0_vs_A2 on docs_bleu4: W=4.0, p=0.715, rank-biserial=-0.2, n=6
- A0_vs_A2 on docs_bertscore_f1: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_A2 on docs_glossary_recall: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_A2 on capture_rate: W=0, p=0.0431, rank-biserial=1.0, n=6
- A0_vs_A2 on ber: W=0, p=0.1088, rank-biserial=1.0, n=6
- A0_vs_A3 on docs_bleu4: W=1.0, p=0.285, rank-biserial=0.667, n=6
- A0_vs_A3 on docs_bertscore_f1: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_A3 on docs_glossary_recall: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_A3 on capture_rate: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_A3 on ber: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_B1 on docs_bleu4: W=0, p=0.0679, rank-biserial=1.0, n=6
- A0_vs_B1 on docs_bertscore_f1: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_B1 on docs_glossary_recall: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_B1 on capture_rate: W=0, p=0.0431, rank-biserial=1.0, n=6
- A0_vs_B1 on ber: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_B2 on docs_bleu4: W=0, p=0.0679, rank-biserial=1.0, n=6
- A0_vs_B2 on docs_bertscore_f1: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_B2 on docs_glossary_recall: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_B2 on capture_rate: W=0, p=0.0431, rank-biserial=1.0, n=6
- A0_vs_B2 on ber: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_B3 on docs_bleu4: W=0, p=0.0277, rank-biserial=-1.0, n=6
- A0_vs_B3 on docs_bertscore_f1: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_B3 on docs_glossary_recall: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_B3 on capture_rate: W=0, p=0.0431, rank-biserial=1.0, n=6
- A0_vs_B3 on ber: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_S1 on docs_bleu4: W=0, p=0.0277, rank-biserial=-1.0, n=6
- A0_vs_S1 on docs_bertscore_f1: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_S1 on docs_glossary_recall: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_S1 on capture_rate: W=0.0, p=1.0, rank-biserial=0.0, n=6
- A0_vs_S1 on ber: W=0.0, p=1.0, rank-biserial=0.0, n=6
