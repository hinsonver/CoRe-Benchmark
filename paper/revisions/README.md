# Historical source and display provenance

Verbatim excerpts from the preceding technical-report source. These describe historical displays and are not instructions for interpreting the present figure. The complete preceding source is preserved locally.

```latex
\textbf{Uniform scoring and results.} Current results apply the complete screen uniformly to the saved replies. Twelve early DeepSeek summaries are compatible with a different counting behavior, without target-vote subtraction or the arithmetic rule; the old source revision was not recovered. Those summaries remain historical records, while the uniform integer counts are stored separately in \href{https://github.com/hinsonver/CoRe-Benchmark/blob/main/results/derived/uniform_continuation.json}{\nolinkurl{results/derived/uniform_continuation.json}}. The current \href{https://github.com/hinsonver/CoRe-Benchmark/blob/main/code/src/uniform_continuation.py}{\nolinkurl{code/src/uniform_continuation.py}} selects maxima and pools leakage from those integers. On Hospital, DeepSeek scores 221/468 (47\%) on context-absent cells and 3/144 (2.1\%) on hard cells. Across tested settings, the largest hard-cell accuracy is 32/375 (0.085 after rounding). OLMo-2 base reaches a displayed maximum of 0.011. Hard clean-value leakage is 3/601 cell-trials for DeepSeek and 1/2,008 for the four open instruction cleaners.
```

```latex
Saved records include query titles, PMIDs, compared field values and outcomes, the publication year for dates, and a text prefix for encoding. Complete candidate responses, returned titles and similarity scores are not retained. A provenance search recovered matching early JSON, logs and programs, but no additional complete candidate-response chain. \href{https://github.com/hinsonver/CoRe-Benchmark/blob/main/code/src/rayyan_audit.py}{\nolinkurl{code/src/rayyan_audit.py}} describes the historical query/check logic; the public replay uses saved matches and outcomes rather than issuing fresh searches.
```

```latex
This guide maps the manuscript's analyses to the included evidence and executable replay routes. It distinguishes the current manuscript presentation from the earlier fixed statistical ZIP.
```

```latex
The current repository presentation produces 19 table sources (17 full sources and two compact views) and eleven CSV files. It includes the focused recovery comparison and Hospital construction example. The earlier fixed statistical package, {\ttfamily\small CoRe-public-core-statistical.zip}, retains 16 table sources and nine CSV files. Its SHA-256 is {\ttfamily\small 9a4e03a3\allowbreak{}af74696f\allowbreak{}2e100fc1\allowbreak{}a12b0831\allowbreak{}f718cf67\allowbreak{}6a5a5b5d\allowbreak{}e7d4e054\allowbreak{}c86542d0}, and its manifest SHA-256 is {\ttfamily\small 3162d8b7\allowbreak{}e9433728\allowbreak{}40c1960a\allowbreak{}5f7fc2c2\allowbreak{}57c7f376\allowbreak{}8e6baa9c\allowbreak{}75e47cdb\allowbreak{}5fa32f38}. These historical bindings are not replaced by the current presentation. The current first figure contrasts saved Movies identifier-mapping counts with retained year candidates; the original three-dataset overview and intervals remain in the extended displays.
```

```latex
The \href{https://github.com/hinsonver/CoRe-Benchmark/blob/main/scripts/verify.sh}{\nolinkurl{scripts/verify.sh}} and \href{https://github.com/hinsonver/CoRe-Benchmark/blob/main/scripts/reproduce.sh}{\nolinkurl{scripts/reproduce.sh}} wrappers use the selected {\ttfamily\small PYTHON} interpreter. Public replay requires no GPU, model key or network. The current presentation regenerates 19 table sources and eleven CSV files, using uniform continuation counts and exact sign-test probabilities before Holm correction. Adding {\ttfamily\small --presentation frozen} selects the original archived scores and formatting. The fixed ZIP's 16-table/nine-CSV inventory describes that historical archive, not the current presentation. Explanatory verification and diagram views are not additional experimental observations.
```

```latex
\subsection{Current manuscript display projections}
```

```latex
The checked table-display entry is \href{https://github.com/hinsonver/CoRe-Benchmark/blob/main/code/src/paper_presentation.py}{\nolinkurl{code/src/paper_presentation.py}}. The current repository replay invokes this projection, checks all 17 full source bodies, overlays current captions and adds two compact sources. The projection does not retroactively alter the earlier fixed ZIP.
```

```latex
The seven sections of the supplementary technical report give construction, execution, Rayyan criteria, adaptation guidance, replay routes, extended displays and diagnostic detail. Offline reproducibility does not imply redistribution of excluded historical movie records or access to model services. {\ttfamily\small verify --release} additionally checks citation metadata and an external approval record bound to the final manifest; these are release checks rather than statistical evidence.
\clearpage
\section{Extended displays and result details}
\hypertarget{companion-6}{}\label{report-6}
```

```latex
Main-paper Figure 6 displays Hospital/Movies zero-shot and aligned results with intervals, using all 24 rows of \href{https://github.com/hinsonver/CoRe-Benchmark/blob/main/results/figures/fig3_aligned.csv}{the plotted CSV}. Table 13 supplies exact scores across both information settings, including Beers. All three families use identity-column scoring here. For aligned Baran, each plotted whisker is the first run's 95\% chunk-bootstrap interval translated by the difference between the three-run mean and the first run's point estimate. It is neither a confidence interval for the three-run mean nor an interval over seeds. The implementation is \href{https://github.com/hinsonver/CoRe-Benchmark/blob/main/code/src/figures.py}{\nolinkurl{code/src/figures.py}} (\texttt{fig3}), and the CSV retains the exact plotted endpoints. The earlier six-row projection, \href{https://github.com/hinsonver/CoRe-Benchmark/blob/main/paper/latex/tables/whole_table.tex}{\nolinkurl{whole_table.tex}}, is retained as an unused generated view rather than an additional main-paper table.
```

```latex
The current presentation checks the non-caption content of its bound table sources, restores the manuscript captions, and adds {\ttfamily\small whole\_\allowbreak{}table.tex} and {\ttfamily\small rayyan\_\allowbreak{}checks.tex}. Its continuation table uses the uniform integer counts in Section 2.5, and its Beers city tests apply Holm to unrounded probabilities. The original archived scores remain available under {\ttfamily\small --presentation frozen}. Current replay produces 19 table sources and eleven CSV files:
```

```latex
The earlier fixed statistical ZIP retains its 16-table/nine-CSV inventory and original hashes. The current presentation and historical ZIP are distinct versioned deliverables, as described in \hyperlink{companion-5}{Public verification (Section~\ref{report-5})}.
```

```latex
The effective TabClean archive is \href{https://github.com/hinsonver/CoRe-Benchmark/blob/main/artifacts/raw_outputs/e4/}{\nolinkurl{artifacts/raw_outputs/e4/}}. Historical {\ttfamily\small \_\allowbreak{}failed\_\allowbreak{}1001}, {\ttfamily\small \_\allowbreak{}fresh\_\allowbreak{}v2}, {\ttfamily\small \_\allowbreak{}movies\_\allowbreak{}v2\_\allowbreak{}1002} and {\ttfamily\small \_\allowbreak{}beers\_\allowbreak{}v3\_\allowbreak{}1002} directories are not substituted for these final files. The effective archive retains the final condition outputs and execution evidence.
```

```latex
For a Beers example outside the development rows, {\ttfamily\small San Francisco CA} in City and an empty State become {\ttfamily\small San Francisco} and {\ttfamily\small CA}, matching the reference. Both pieces of information are present in the dirty input. All 104 non-development city-error rows in Beers O have the correct city and state in the final output. The generated program bodies were not retained in this effective archive, so the example describes observed edits, not a recovered internal rule. The archived outputs and \href{https://github.com/hinsonver/CoRe-Benchmark/blob/main/code/src/e4.py}{\nolinkurl{code/src/e4.py}} specify the effective versions and development exclusions.
\subsection{Exact aligned-Baran plotting endpoints}
Table~\ref{report-table-6-4} gives the unmodified CSV endpoints for the Baran series in main-paper Figure 6. The center is a three-run mean. The whiskers retain the first run's chunk-bootstrap width after translation to that center.
\ensuretablespace{149pt}
\begingroup\setlength{\tabcolsep}{3pt}\renewcommand{\arraystretch}{1.18}
\small
\begin{longtable}{@{}>{\raggedright\arraybackslash}p{\dimexpr 0.2000\textwidth-4.90pt\relax}>{\raggedright\arraybackslash}p{\dimexpr 0.2000\textwidth-4.90pt\relax}>{\raggedright\arraybackslash}p{\dimexpr 0.2000\textwidth-4.90pt\relax}>{\raggedright\arraybackslash}p{\dimexpr 0.2000\textwidth-4.90pt\relax}>{\raggedright\arraybackslash}p{\dimexpr 0.2000\textwidth-4.90pt\relax}@{}}
\caption{Aligned-Baran points and translated first-run interval endpoints.}\label{report-table-6-4}\\
\toprule
Dataset & Condition & Mean F1 & Lower endpoint & Upper endpoint \\
\midrule
\endfirsthead
\multicolumn{5}{l}{\small Table \thetable\ (continued)}\\
\toprule
Dataset & Condition & Mean F1 & Lower endpoint & Upper endpoint \\
\midrule
\endhead
\midrule\multicolumn{5}{r}{\footnotesize Continued on next page}\\\endfoot
\bottomrule\endlastfoot
Hospital & Original & 0.288 & 0.209 & 0.365 \\
Hospital & Fresh & 0.319 & 0.25 & 0.39 \\
Hospital & Words surrogate & 0.272 & 0.2 & 0.344 \\
Hospital & Syllable surrogate & 0.278 & 0.203 & 0.352 \\
Movies & Original & 0.0 & 0.0 & 0.0 \\
Movies & Fresh & 0.0 & 0.0 & 0.0 \\
Movies & Words surrogate & 0.0 & 0.0 & 0.0 \\
Movies & Syllable surrogate & 0.0 & 0.0 & 0.0 \\
\end{longtable}\endgroup
\subsection{Original extended figures}
Figures~\ref{report-fig-fig1_decomposition}--\ref{report-fig-fig5_rayyan} reproduce the archived plots at readable width. They retain the original estimates and intervals.
\begin{figure}[!htbp]\centering
\includegraphics[width=\textwidth,height=.66\textheight,keepaspectratio]{../latex/figures/fig1_decomposition.pdf}
\caption{Four-condition DeepSeek-V4-Pro repair F1 on Hospital/Movies identity columns and all Beers columns, with original 95\% chunk-bootstrap intervals. F is unpaired; Beers F is descriptive.}
\label{report-fig-fig1_decomposition}
\end{figure}
\begin{figure}[!htbp]\centering
\includegraphics[width=\textwidth,height=.66\textheight,keepaspectratio]{../latex/figures/fig2_year_range.pdf}
\caption{Movies year candidates and repairs. Taking the middle candidate matches 167/190 references; the cleaner was not supplied this rule.}
\label{report-fig-fig2_year_range}
\end{figure}
\begin{figure}[!htbp]\centering
\includegraphics[width=\textwidth,height=.66\textheight,keepaspectratio]{../latex/figures/fig6_scale.pdf}
\caption{Full eight-model Hospital identity-column comparison with original 95\% chunk-bootstrap intervals. The scale trend is confined to the tested Qwen2.5 family on Hospital.}
\label{report-fig-fig6_scale}
\end{figure}
\begin{figure}[!htbp]\centering
\includegraphics[width=\textwidth,height=.66\textheight,keepaspectratio]{../latex/figures/fig3_aligned.pdf}
\caption{Zero-shot and aligned repair F1. For aligned Baran only, whiskers are the first-run 95\% chunk-bootstrap interval translated to the three-run mean, not confidence intervals for that mean or seed ranges.}
\label{report-fig-fig3_aligned}
\end{figure}
\begin{figure}[!htbp]\centering
\includegraphics[width=\textwidth,height=.66\textheight,keepaspectratio]{../latex/figures/fig5_rayyan.pdf}
\caption{Original Rayyan stratified field-check display. The dirty changed-word check is unassessed. The plot uses the same saved matches and criteria as Section 3, not another sample.}
\label{report-fig-fig5_rayyan}
\end{figure}
\clearpage
\clearpage
\section{Archived sensitivity checks and output patterns}
\hypertarget{companion-7}{}\label{report-7}
```

```latex
The diagnostic aggregate contains the diagnostics, exact prompt literals and SHA-256 bindings for 184 source files. Its SHA-256 is {\ttfamily\small f29316b0\allowbreak{}f90fd0e4\allowbreak{}3345f1ad\allowbreak{}80a4fbb3\allowbreak{}c9e48c95\allowbreak{}2748e95d\allowbreak{}42fcde33\allowbreak{}77192e34}. This historical source index records author-side provenance, not a claim that all 184 sources are redistributed. The repository's \href{https://github.com/hinsonver/CoRe-Benchmark/blob/main/tools/review_diagnostics.py}{\nolinkurl{tools/review_diagnostics.py}} and \href{https://github.com/hinsonver/CoRe-Benchmark/blob/main/docs/reproduction.md}{\nolinkurl{docs/reproduction.md}} distinguish replayable checks from aggregate-only output-pattern and usage evidence.
```

```latex
The original author-side audit read archived inputs, extracted pure scoring definitions and literal templates, and checked masks, replies, pairing, the full Holm family and parity with the original scorer. The repository replay recomputes the checks supported by included tables, block-count witnesses and saved matches. It reports aggregate-only evidence separately, without reconstructing omitted Movies replies or the historical billing log. Neither route invokes model generation.
\end{document}

```

```latex
\subsection{Exact aligned-Baran plotting endpoints}
Table~\ref{report-table-6-4} gives the unmodified CSV endpoints for the Baran series in main-paper Figure 6. The center is a three-run mean. The whiskers retain the first run's chunk-bootstrap width after translation to that center.
\ensuretablespace{149pt}
\begingroup\setlength{\tabcolsep}{3pt}\renewcommand{\arraystretch}{1.18}
\small
\begin{longtable}{@{}>{\raggedright\arraybackslash}p{\dimexpr 0.2000\textwidth-4.90pt\relax}>{\raggedright\arraybackslash}p{\dimexpr 0.2000\textwidth-4.90pt\relax}>{\raggedright\arraybackslash}p{\dimexpr 0.2000\textwidth-4.90pt\relax}>{\raggedright\arraybackslash}p{\dimexpr 0.2000\textwidth-4.90pt\relax}>{\raggedright\arraybackslash}p{\dimexpr 0.2000\textwidth-4.90pt\relax}@{}}
\caption{Aligned-Baran points and translated first-run interval endpoints.}\label{report-table-6-4}\\
\toprule
Dataset & Condition & Mean F1 & Lower endpoint & Upper endpoint \\
\midrule
\endfirsthead
\multicolumn{5}{l}{\small Table \thetable\ (continued)}\\
\toprule
Dataset & Condition & Mean F1 & Lower endpoint & Upper endpoint \\
\midrule
\endhead
\midrule\multicolumn{5}{r}{\footnotesize Continued on next page}\\\endfoot
\bottomrule\endlastfoot
Hospital & Original & 0.288 & 0.209 & 0.365 \\
Hospital & Fresh & 0.319 & 0.25 & 0.39 \\
Hospital & Words surrogate & 0.272 & 0.2 & 0.344 \\
Hospital & Syllable surrogate & 0.278 & 0.203 & 0.352 \\
Movies & Original & 0.0 & 0.0 & 0.0 \\
Movies & Fresh & 0.0 & 0.0 & 0.0 \\
Movies & Words surrogate & 0.0 & 0.0 & 0.0 \\
Movies & Syllable surrogate & 0.0 & 0.0 & 0.0 \\
\end{longtable}\endgroup

```

## Preceding repository provenance

# Manuscript revision provenance

The current scholarly reading documents are the [2026-10-26 manuscript](../latex/main.pdf) and [supplementary technical report](../CoRe-Supplementary-Technical-Report.pdf). The [revision binding](../revision-binding.json) records their exact hashes and separates the earlier adoption from the current version. The [result map](../result-map.json) follows the current compiled labels, pages and numbers.

The manuscript has a twelve-page body and fourteen pages with references. The technical report has twenty-one pages, seven sections, fourteen tables and seven original figures. It replaces the former seven Markdown reports as the formal technical reading document; those former chapters remain in Git history. Current installation and execution routes are the [README](../../README.md), [data guide](../../docs/data.md), [reproduction guide](../../docs/reproduction.md), [claim map](../claim-map.md) and [report index](../CoRe-companion-index.md).

All pre-existing records in this directory other than this navigation README are byte-preserved historical snapshots. Records 34–38 (`.md.txt`), earlier seals and `current-main.aux` describe earlier versions; their internal task identifiers and workspace-relative references are historical provenance, not current reader instructions. The retained author-side frozen-claims snapshot likewise records scope decisions, not an additional scholarly attachment. No new internal review or closure document is added here. The current compiled navigation file is `paper/latex/main.aux`, outside this historical directory.

The fixed private tag `v0.1.0-a04-review-private-20261022`, its Release assets and old archives remain unchanged. `MANIFEST.sha256` covers current repository members; fixed archives retain their original manifests. Original input/reply bytes and historical estimates remain preserved. Current continuation values and two Beers adjusted p-values follow the [documented statistical corrections](../../docs/statistical-revisions.md); cleaning contrasts, intervals and significance are unchanged. No new model calls occurred. Repository access remains private; synchronization does not grant public or reviewer access.
