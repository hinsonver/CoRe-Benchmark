# Entity and reply clustering

Run the complete offline calculation with your selected Python interpreter:

```bash
python tools/core.py reproduce --output build/my-replay
```

For the statistical calculations alone, choose a new output path:

```bash
python tools/replay_cluster_statistics.py --output build/my-statistics.json
```

No model key, network or GPU is used. `data/witnesses/cluster_statistics.json` contains anonymous row/entity/reply indices, E/P/R/D count contributions, and known-target indicators. `data/manifests/CLUSTER_STATISTICS.json` binds its hash and evidence sources. It contains no movie titles, credits, assigned values or saved reply text. `tools/core.py verify` checks the package and witness bindings.

The current calculation uses 50,000 draws with seed 20261027. Hospital and Beers multiply independent Exp(1) entity and reply weights; Movies uses reply weights. O/W/S share corresponding weights. F replies are independent; Hospital's shared ProviderNumbers retain common entity weights without pairing different records. Weighted integers define micro-F1. The 40 Hospital/Movies and eight Beers O-S contrasts use centered two-sided bootstrap deviations and separate Holm families. These are approximate inferences conditional on the constructed tables and the entity/reply dependence model.

Conflict intervals resample complete replies and pool entity indicator means divided by sampled entity count. All target rows of an entity remain together. Known subsets and unusable-reply denominators are fixed. The `interval_available` flag is false for constant empirical distributions; displays report counts and rates rather than assigning those points a population-confidence interval. Beers F remains descriptive because its error and entity distributions differ from O/W/S. All archived replies have row-level count contributions; the three runs listed in `supplements/beers-f-input-provenance/run-input-map.json` use their hash-bound historical inputs for scoring.

`derived/cluster_statistics.json` includes the 40-comparison family, the eight-comparison Beers family, 240 known-subset conflict settings, aligned score intervals and comparisons, and the full-family GLM complete-reply sensitivity. The two sensitivity contrasts retain their paired/independent reply rules. Chunk wins/losses on Hospital and Beers are descriptive; the Movies sign test retains its separate eight-model family.

The raw numerical tables pass checked transformations in `tools/cluster_display.py` and `code/src/paper_presentation.py`; the four affected table bodies are hash-bound before and after the statistical transform. `code/src/figures.py` reads the calculated intervals. Figure centers, repaired-cell counts, construction ranges, continuation results and Rayyan results retain their original estimands.

To check the historical statistical calculation separately, use `tools/core.py reproduce --presentation frozen` or `tools/review_diagnostics.py --statistics frozen`. Current diagnostics default to the entity/reply calculation. No archived input, reply, summary or historical source code is overwritten.
