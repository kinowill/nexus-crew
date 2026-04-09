# Matrice tool use NIM

Genere le 2026-04-09 par `scripts/test_tool_use.py`.

Le critere `NATIVE` est le SEUL utilisable par CrewAI/LiteLLM : c'est
le format OpenAI `tool_calls` standard. Les autres categories revelent
un modele qui ne sait pas appeler un outil de maniere parsable.

## Resultats par modele

| Modele | Statut | Note |
|---|---|---|
| `openai/qwen/qwen3.5-397b-a17b` | **NATIVE** | tool_call=get_weather |
| `openai/deepseek-ai/deepseek-v3.2` | **ERROR** | litellm.Timeout: APITimeoutError - Request timed out. Error_str: Request timed out. |
| `openai/meta/llama-3.3-70b-instruct` | **NATIVE** | tool_call=get_weather |
| `openai/qwen/qwen3-coder-480b-a35b-instruct` | **NATIVE** | tool_call=get_weather |
| `openai/mistralai/devstral-2-123b-instruct-2512` | **NATIVE** | tool_call=get_weather |
| `openai/moonshotai/kimi-k2-instruct-0905` | **NATIVE** | tool_call=get_weather |
| `openai/moonshotai/kimi-k2-thinking` | **NATIVE** | tool_call=get_weather |
| `openai/qwen/qwen3-next-80b-a3b-thinking` | **NATIVE** | tool_call=get_weather |
| `openai/nvidia/llama-3.3-nemotron-super-49b-v1.5` | **NATIVE** | tool_call=get_weather |
| `openai/openai/gpt-oss-120b` | **NATIVE** | tool_call=get_weather |
| `openai/google/gemma-3-27b-it` | **ERROR** | litellm.BadRequestError: OpenAIException - "auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set |

## Diagnostic par role

| Role | Primaire | Statut | Action |
|---|---|---|---|
| researcher | `openai/qwen/qwen3.5-397b-a17b` | NATIVE | rien a faire |
| architect | `openai/deepseek-ai/deepseek-v3.2` | ERROR | basculer vers `openai/qwen/qwen3.5-397b-a17b` |
| coder | `openai/qwen/qwen3-coder-480b-a35b-instruct` | NATIVE | rien a faire |
| critic | `openai/moonshotai/kimi-k2-thinking` | NATIVE | rien a faire |
| scanner | `openai/meta/llama-3.3-70b-instruct` | NATIVE | rien a faire |

## Chaines completes

### researcher

- `openai/qwen/qwen3.5-397b-a17b` — **NATIVE**
- `openai/deepseek-ai/deepseek-v3.2` — **ERROR**
- `openai/meta/llama-3.3-70b-instruct` — **NATIVE**

### architect

- `openai/deepseek-ai/deepseek-v3.2` — **ERROR**
- `openai/qwen/qwen3.5-397b-a17b` — **NATIVE**
- `openai/meta/llama-3.3-70b-instruct` — **NATIVE**

### coder

- `openai/qwen/qwen3-coder-480b-a35b-instruct` — **NATIVE**
- `openai/mistralai/devstral-2-123b-instruct-2512` — **NATIVE**
- `openai/moonshotai/kimi-k2-instruct-0905` — **NATIVE**

### critic

- `openai/moonshotai/kimi-k2-thinking` — **NATIVE**
- `openai/qwen/qwen3-next-80b-a3b-thinking` — **NATIVE**
- `openai/nvidia/llama-3.3-nemotron-super-49b-v1.5` — **NATIVE**

### scanner

- `openai/meta/llama-3.3-70b-instruct` — **NATIVE**
- `openai/openai/gpt-oss-120b` — **NATIVE**
- `openai/google/gemma-3-27b-it` — **ERROR**
