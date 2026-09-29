# System One Model Benchmark

System One Model Benchmark is a frozen public benchmark for evaluating models designed for fast, bounded semantic decisions rather than open-ended generation. The first published evaluation uses TypeSafe AI's Jev 1.13.0.

## What this benchmark tests

The cases test bounded decisions across classification, routing, evidence evaluation, claim verification, acceptance, outcome verification, risk classification, timing evidence, record identity, and review routing.

The benchmark primarily tests **application of bounded decision predicates across varied states**, rather than understanding 160 unrelated natural-language instructions. Repeated question templates are intentional: they hold a decision predicate steady while the evidence state varies.

## Benchmark composition

- **160** total cases
- **150** semantic decisions
- **10** deterministic controls
- **11** intentional-ambiguity cases
- **31** distinct question templates

Deterministic controls use explicit values or rules that code can evaluate exactly. They are retained as controls and reported separately; they are not evidence of semantic-decision quality. Intentional-ambiguity cases test whether ambiguity is the right bounded answer. They are not unresolved labels.

## Frozen benchmark

- Version: **v1.0**
- Cases: **160**
- Canonical `cases.jsonl` SHA-256: `0a68ef2adbbb7c923a9dce8012987488dd4a291fe9697767854e0e01f6a221bf`
- Expected answers were finalized before model evaluation.

The JSONL case file is immutable for v1. Changes to state, question, choices, expected answer, task family, or benchmark role require a new version.

## First evaluation: Jev 1.13.0

| Slice | Correct | Accuracy |
|---|---:|---:|
| All cases | 144/160 | 90.0% |
| Semantic decisions | 134/150 | 89.3% |
| Deterministic controls | 10/10 | 100% |
| Intentional ambiguity | 8/11 | 72.7% |

The run made **160 requests**, with **0 provider failures** and **0 retries**. Estimated cost was **$0.003010056**. Latency was **123.16 ms mean**, **114.38 ms p50**, and **167.96 ms p95**. Cost uses TypeSafe's published input rate of $0.042 per million tokens; output tokens were free at run time ([pricing source](https://typesafe.ai/blog/introducing-system-one-models-and-jev)).

The run artifacts and per-task-family results are in [`results/jev-1.13.0/`](results/jev-1.13.0/).

## Uncertainty findings

Top-two Choice margin was the strongest exploratory error-ranking signal in this run, with AUC **0.859 overall** and **0.851 for semantic decisions**. Ranking the least-certain cases by margin would have captured:

- 10%: **8/16** errors overall
- 20%: **12/16**
- 30%: **13/16**

These are retrospective findings from one benchmark, not validated production thresholds. No production routing threshold was selected.

## High-confidence errors

Three incorrect answers had selected-answer probability ≥0.90; one was effectively 1.00. Model confidence should not be interpreted as calibrated truth without workload-specific validation. Case-level details are in [`high-confidence-errors.csv`](results/jev-1.13.0/high-confidence-errors.csv).

## Reproducing the benchmark

Score the committed evaluation results and regenerate the analysis:

```sh
python scripts/score_results.py
python scripts/analyze_uncertainty.py
```

To run Jev against the frozen cases, copy `.env.example` to `.env`, set `JEV_API_KEY`, then run:

```sh
python scripts/run_jev.py
```

The runner verifies the frozen SHA before making requests. It sends the state, question, and choices; it does not send `expected_answer`. It records raw responses and run metadata without writing credentials. It makes one request per case, does not retry a valid response, and retries a transport failure only once for HTTP 503 with the same input.

## Data format

Each line in `cases.jsonl` contains `case_id`, `task_family`, `benchmark_role`, `state`, `question`, `choices`, `expected_answer`, and `label_status`.

`benchmark_role` is either `semantic_decision` or `deterministic_control`. `label_status` is `CLEAR` or `INTENTIONAL_AMBIGUITY`.

## Limitations

- The benchmark is synthetic-controlled and does not estimate production accuracy.
- Repeated question templates are intentional; the benchmark measures predicate application across varied states.
- Intentional ambiguity is a small subset (11 cases).
- Uncertainty thresholds are exploratory and have not been validated for routing.
- One model version has been evaluated so far.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).

## Citation

```text
Ruparel, Kaushik. System One Model Benchmark, version 1.0, 2026.
```
