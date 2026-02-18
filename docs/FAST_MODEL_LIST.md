# Fast Model List

Last updated: 2026-02-18 (via Firecrawl + official provider docs)

This list is tuned for low latency / cost-efficient usage in this project.

| Provider | Recommended fast model | Notes |
| --- | --- | --- |
| OpenAI | `openai/gpt-5-nano` | OpenAI describes GPT-5 nano as the fastest, most cost-efficient GPT-5 variant. |
| OpenAI | `openai/gpt-5-mini` | Faster, cost-efficient GPT-5 variant for well-defined tasks. |
| Anthropic | `anthropic/claude-haiku-4-5` | Anthropic describes Haiku 4.5 as their fastest model. |
| Google | `google/gemini-2.5-flash-lite` | Google labels 2.5 Flash-Lite as ULTRA FAST and optimized for cost-efficiency/high throughput. |
| Google | `google/gemini-3-flash-preview` | Google positions Gemini 3 Flash for speed/scale with stronger frontier capability (preview model). |
| Groq | `groq/openai/gpt-oss-20b` | Groq production list shows this at ~1000 tokens/sec, higher than `llama-3.1-8b-instant` (~560 tps). |
| Groq | `groq/llama-3.1-8b-instant` | Strong fallback fast model with low cost and broad compatibility on Groq. |
| Mistral | `mistral/ministral-3b-2512` | Ministral 3 3B is described as smallest/most efficient in the Ministral 3 family. |

## Sources

- OpenAI models page: https://developers.openai.com/api/docs/models
- OpenAI GPT-5 mini: https://developers.openai.com/api/docs/models/gpt-5-mini
- OpenAI GPT-5 nano: https://developers.openai.com/api/docs/models/gpt-5-nano
- Anthropic models overview: https://docs.anthropic.com/en/docs/about-claude/models/overview
- Anthropic choosing a model: https://docs.anthropic.com/en/docs/about-claude/models/choosing-a-model
- Google Gemini models: https://ai.google.dev/gemini-api/docs/models
- Groq supported models: https://console.groq.com/docs/models
- Mistral models catalog: https://docs.mistral.ai/getting-started/models
- Mistral model page (Ministral 3 3B): https://docs.mistral.ai/models/ministral-3-3b-25-12

## Notes

- Model availability can vary by account/region/tier.
- For Mistral specifically, confirm active IDs in your account via `GET /v1/models`.
- For Groq specifically, confirm active IDs in your account via `GET https://api.groq.com/openai/v1/models`.
- For Google specifically, `gemini-3-flash-preview` is preview; use `gemini-2.5-flash-lite` as stable fast default.
- If a model is unavailable, pick the next entry in the same provider row.
