# First evaluation — Jev 1.13.0

Frozen cases SHA-256: `0a68ef2adbbb7c923a9dce8012987488dd4a291fe9697767854e0e01f6a221bf`.

| Slice | Correct | Accuracy | Provider failures | Cost | Mean / p50 / p95 latency |
|---|---:|---:|---:|---:|---:|
| All cases | 144/160 | 90.0% | 0 | $0.003010056 | 123.16 / 114.38 / 167.96 ms |
| Semantic decisions | 134/150 | 89.3% | 0 | $0.002858478 | 123.51 / 114.43 / 175.83 ms |
| Deterministic controls | 10/10 | 100.0% | 0 | $0.000151578 | 117.85 / 110.30 / 153.80 ms |
| Intentional ambiguity | 8/11 | 72.7% | 0 | $0.000201264 | 117.19 / 113.52 / 163.83 ms |

Task-family metrics are in `task-family-results.csv`. Run `python scripts/analyze_uncertainty.py` for exploratory error ranking.

## Exploratory uncertainty analysis

Top-two margin was the strongest error-ranking signal in this run (AUC 0.859 overall and 0.851 on semantic decisions). These are retrospective findings, not validated production thresholds.

| Population | Least-certain fraction | Errors captured / total |
|---|---:|---:|
| all_cases | 10% | 8/16 |
| all_cases | 20% | 12/16 |
| all_cases | 30% | 13/16 |
| semantic_decisions | 10% | 8/16 |
| semantic_decisions | 20% | 11/16 |
| semantic_decisions | 30% | 13/16 |

Three errors had selected-answer probability at least 0.90; one was effectively 1.00. See `high-confidence-errors.csv`. Model confidence should not be treated as truth without workload-specific validation.
