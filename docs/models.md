# Models and execution settings

The archive contains outputs for four open-weight instruction models
(Qwen2.5-7B, Llama-3.1-8B, Qwen2.5-14B, and Qwen2.5-32B), the OLMo-2-7B base
model used by the P1 probe, and four hosted models recorded in the result files
as DeepSeek-V4-Pro, Qwen3.8-Max, GLM-5.3, and GPT-6.1-Sol.

These names are experimental identifiers, not a promise that the same endpoint
or checkpoint remains available. `results/derived/output-inventory.json`
enumerates the actual archived files consumed by the analyses.

Model specifications use `provider:model`. Supported providers and variables:

| Provider | Variables | Notes |
|---|---|---|
| `mock` | none | Offline plumbing check; does not measure quality. |
| `local` / `localbase` | `LOCAL_BASE_URL`, optional `LOCAL_API_KEY` | OpenAI-compatible local server; `localbase` uses text completion. |
| `openai` | `OPENAI_API_KEY` | Hosted API. |
| `deepseek` | `DEEPSEEK_API_KEY` | Hosted OpenAI-compatible API. |
| `qwen` | `DASHSCOPE_API_KEY` | Hosted OpenAI-compatible API. |
| `custom` | `CUSTOM_BASE_URL`, `CUSTOM_API_KEY` | Generic relay. |
| `gemini` | `GEMINI_API_KEY` | Google's OpenAI-compatible endpoint. |
| `anthropic` | `EXP_ANTHROPIC_API_KEY` | Requires the optional `anthropic` package. |

The client uses temperature 0 where the API permits it, caches responses, and
retries truncated JSON for hosted providers at larger token budgets. The GPT
identifier in the archive accepted only its default temperature and therefore
used sampled decoding with low reasoning effort. GLM thinking could not be
disabled and was run at its lowest offered reasoning effort. Those differences
limit direct cross-model interpretation.

No API key, endpoint credential, response cache, or model weight is distributed
in this package. Provider runs require `--allow-paid-api`; this guard covers
both possible monetary cost and transmission of table data to a third party.
