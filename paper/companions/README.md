# CoRe manuscript companion materials

These companions carry the adopted manuscript's technical details, extended displays and archived diagnostics. They preserve the frozen experimental scope and refer to saved inputs and replies; they do not add experiments or replace any previous fixed archive.

| Manuscript topic and stable label | Companion |
| --- | --- |
| Controlled-table construction and acceptance, `sec:construction` | [Construction and acceptance](01-构造与验收细则.md) |
| Models, prompts, budgets and scoring, `sec:scoring`, `sec:setup`, `sec:memorization`, `sec:conflictmetric` | [Run and scoring specification](02-运行与评分规格.md) |
| Title retrieval, field checks and versioned scoring, `sec:rayyan-audit`, `sec:rayyan-rewards` | [Rayyan retrieval and scoring details](03-Rayyan检索与评分材料说明.md) |
| Adapting the design, `sec:apply` | [Applying CoRe](04-新基准应用指南.md) |
| C1–C3 executable evidence and public/local modes, `sec:artifact` | [Public verification guide](05-Public-Verification-Guide.md) |
| Complete Hospital row example; original three-dataset condition plot and intervals; full aligned matrix; acceptance and Rayyan/scale displays | [Extended displays and result details](06-扩展图表与结果明细.md) |
| Passing-seed contrasts, incomplete-reply sensitivity, count-formatting outputs, exact cleaning prompt and recorded usage | [Archived sensitivity and output checks](07-归档敏感性与输出核验.md) |

The [revision binding](../revision-binding.json) records the adopted source/PDF and current packaged materials; `MANIFEST.sha256` at the repository root covers all current members. Earlier fixed archives retain their original hashes. The repository remains private.

## Reading the evidence

| Question | Main-paper entry | What to inspect |
| --- | --- | --- |
| Does renaming remove a mapping or leave useful candidates? | `fig:decomposition`, `fig:year`, `tab:recoverability`, `tab:main`; Findings 2–4 | Compare missing identifier mappings with retained year candidates. Keep paired O/W/S contrasts separate from fresh comparisons. |
| Do labels or repeated records change the available evidence? | `fig:aligned`, `tab:aligned`; Finding 5 | Compare aligned inputs first, then whole-table access. [Extended displays](06-扩展图表与结果明细.md) also bind the archived TabClean output example. |
| Does a familiar fact override the assigned target? | `fig:near`, `fig:nearmodels`, `tab:conflictcounts`; Finding 6 | Use each model's known subset and distinguish directed factual rewrites from other edits or name restoration. |
| What does reference matching reward? | `tab:rayyan`, `sec:rayyan-rewards`; Finding 7 | Separate title-matched field checks, the weighted failure estimate and TabClean's credited-repair denominator. |

The [verification guide](05-Public-Verification-Guide.md) supplies executable entries. This index adds evidence navigation, not another effect-size aggregate or a second set of experimental results.

The [archived checks](07-归档敏感性与输出核验.md) address construction and reply-completeness sensitivity using saved data and outputs. Their diagnostics are separate from the frozen main tables and have not been inserted into historical package archives. The companion distinguishes package-side numerical recomputation from author-side raw-output auditing.
