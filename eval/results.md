# Eval results
> split=test, n=27
> ⚠ Numbers from MockDecider — replace after Stage 0 spike with RealDecider.

| Approach | Accuracy | False-block | Missed-block | p50 ms | p95 ms |
|---|---|---|---|---|---|
| none | 40.7% | 0.0% | 48.1% | 0.0 | 0.0 |
| regex | 37.0% | 40.7% | 22.2% | 0.0 | 1.2 |
| embedding | 48.1% | 44.4% | 3.7% | 0.0 | 0.0 |
| llm_judge | 37.0% | 40.7% | 22.2% | 0.0 | 0.0 |
| grounded | 37.0% | 51.9% | 0.0% | 0.1 | 0.4 |