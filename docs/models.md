# Models and execution settings

The archive contains outputs for four open-weight instruction models
(Qwen2.5-7B, Llama-3.1-8B, Qwen2.5-14B, and Qwen2.5-32B), the OLMo-2-7B instruction
and base variants used by the continuation probe, and four hosted cleaners recorded in the result files
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

DeepSeek-V4-Pro and Qwen3.8-Max run with thinking disabled and requested temperature 0.
GLM-5.3 retains thinking at low reasoning effort and requested temperature 0;
the GPT client uses low reasoning effort and leaves sampling parameters at API defaults.
Local instruction cleaners use greedy decoding. The continuation probe covers DeepSeek,
the four open-weight cleaners and both OLMo variants, not all eight cleaners.
Exact prompt, budgets and reply-completeness handling are in the
[run specification](../paper/companions/02-运行与评分规格.md) and
[archived diagnostics](../paper/companions/07-归档敏感性与输出核验.md).

No API key, endpoint credential, response cache, or model weight is distributed
in this package. Provider runs require `--allow-paid-api`; this guard covers
both possible monetary cost and transmission of table data to a third party.
