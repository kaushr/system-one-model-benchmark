# Methodology

## Frozen corpus

System One Model Benchmark v1.0 contains 160 public cases and is frozen by the SHA-256 recorded in `benchmark-manifest.json`. Labels were established before model evaluation. The benchmark contains 150 semantic decisions and 10 deterministic controls; results keep these groups separate.

## Jev evaluation

The first evaluation used TypeSafe's direct System One endpoint with requested alias `jev-latest`, which reported resolved model `jev-1.13.0`. Each case received one Choice request. The request carried the public state, question, allowed choices, and the same short criterion for each choice. The expected answer and label status were not sent to the model.

Raw request/response events are retained in `results/jev-1.13.0/raw-responses.jsonl`. A valid model response was never retried. The run had no provider failures and no retries. Input-token usage was priced at the published TypeSafe rate in effect for the run; output was listed as free. The run manifest records request counts, model, timing, token use, pricing, and the frozen corpus hash.

## Scoring

A response is correct when its selected choice exactly matches `expected_answer`. Provider failures are reported separately from incorrect model choices. Aggregate metrics are reported for all cases, semantic decisions, deterministic controls, and intentional-ambiguity cases. Semantic-only accuracy is also broken down by task family.

## Uncertainty analysis

Top probability, top-two probability margin, and entropy are computed from returned Choice probabilities. AUC and least-certain-case capture are retrospective analyses of this one run. They do not validate a production threshold. No fallback model, cohort, or production routing policy was evaluated.
