# Environment notes

The release workflow targets Python 3.11 on macOS or Linux. It uses ordinary
CPU execution; the full offline reproduction generally finishes in under a
minute after Matplotlib's first-run font-cache setup.

The package was verified with Python 3.11.16, NumPy 2.4.6, pandas 3.0.6,
Matplotlib 3.11.2, and OpenAI 3.19.2. Lower compatible versions are allowed by
`requirements.txt` because the analysis uses stable public APIs.

`openai` is only needed for live OpenAI-compatible endpoints. An Anthropic run
additionally needs the separately installed `anthropic` package. GPU-backed
local experiments require an OpenAI-compatible serving layer such as vLLM;
model serving and model weights are intentionally outside this artifact.

All generated material belongs below `build/`. Environment variables used by
live runs are documented in `docs/models.md`; credentials must not be stored in
the repository.
