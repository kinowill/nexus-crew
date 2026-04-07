# NEXUS — Autonomous Multi-Agent Coding System

> A Brain + Workers architecture for AI-assisted development, powered by free NVIDIA NIM models.  
> Claude Sonnet / Opus are used only as fallback or for critical decisions.

---

## How it works

One intelligent **Brain** (Qwen 3.5 397B) centralizes all routing decisions.  
Specialized **Workers** execute tasks and return results — they never decide what happens next.

```
Brain (Qwen 3.5 397B)
  │
  ├─► Kimi K2 Instruct      — code generation, refactoring, tests
  ├─► Nemotron 3 Super 120B — code review, debugging, validation
  └─► GPT-OSS 120B          — documentation, synthesis, explanation
```

**Example flow — "implement JWT authentication":**
```
Brain → Kimi     [generates JWT code]
Brain → Nemotron [reviews the code]
Brain → Kimi     [fixes 2 bugs found]
Brain → FINAL    [validated code returned]
```

The order is never fixed in advance. The Brain decides each step based on results.

---

## Models used

All models are free via [NVIDIA NIM](https://build.nvidia.com/) (40 req/min limit).

| Role | Model | Purpose |
|------|-------|---------|
| Brain | `qwen/qwen3.5-397b-a17b` | Orchestration, routing, all decisions |
| Coder | `moonshotai/kimi-k2-instruct-0905` | Code generation & modification |
| Reviewer | `nvidia/nemotron-3-super-120b-a12b` | Code review, bug detection |
| Synthesizer | `openai/gpt-oss-120b` | Documentation, summaries |
| Long context | `minimaxai/minimax-m2.5` | Large context compression |
| Fallback | `z-ai/glm5` | Backup for all roles |

**Fallback chain:**  
Brain Qwen fails → Claude Sonnet (Claude Code CLI, OAuth)  
Worker fails → Qwen → GLM-5

---

## Requirements

- Python 3.11+
- [NVIDIA NIM account](https://build.nvidia.com/) + API key (free tier)
- [Claude Code](https://claude.ai/code) (optional — for Brain fallback via CLI)

```bash
pip install mcp httpx
```

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/kinowill/Claude-agentic-autonomous-agents.git
cd Claude-agentic-autonomous-agents

# 2. Set up your API key
cp .env.example .env
# Edit .env and fill in your NVIDIA_API_KEY

# 3. Discover available models on your account
python -X utf8 scripts/discover_models.py

# 4. Update models.json with confirmed IDs if needed

# 5. Test the connection
python -X utf8 scripts/test_connection.py

# 6. (Optional) Register the MCP server in Claude Code
claude mcp add -s user -e "NVIDIA_API_KEY=<your-key>" nexus -- python mcp-servers/nexus/server.py
```

**Windows:** After filling in `.env`, run `scripts/install.bat`.

---

## Usage

### Interactive chat (main interface)

```bash
# Basic — uses current directory as project
python nexus_chat.py

# With a project
python nexus_chat.py --project /path/to/your/project

# Write generated files directly
python nexus_chat.py --project /path/to/your/project --write

# Force Claude Sonnet as Brain (if Qwen unavailable)
python nexus_chat.py --brain claude
```

Chat commands: `/quit` `/context` `/files` `/clear` `/write` `/brain` `/help`

### One-shot batch mode

```bash
# Plan and show (no file writing)
python nexus.py "add unit tests for auth.py" --project /path/to/project

# Execute and write files
python nexus.py "implement JWT auth" --project /path/to/project --write

# Dry run — show plan only
python nexus.py "refactor the cache module" --dry
```

### MCP integration with Claude Code

Once the MCP server is registered, Claude Code can delegate tasks to NEXUS agents.  
Available tools: `plan_task`, `implement_code`, `review_code`, `compress_context`, `batch_implement`.

---

## Project structure

```
.
├── nexus_chat.py          # Main interactive interface (Brain + Workers loop)
├── nexus.py               # One-shot batch orchestrator
├── nexus.bat              # Windows launcher
├── .env.example           # API key template (copy to .env)
├── MASTER.md              # Architecture decisions & changelog
│
├── mcp-servers/nexus/
│   ├── server.py          # MCP server for Claude Code integration
│   ├── models.json        # Model configuration (update after discover_models.py)
│   └── requirements.txt
│
└── scripts/
    ├── discover_models.py  # Lists all models available on your NIM account
    ├── test_connection.py  # Health check for all configured models
    └── install.bat         # Windows one-click installer
```

---

## Two working modes

| Mode | When to use | How |
|------|-------------|-----|
| **Normal** | Interactive dev, questions, debugging | Just use Claude Code as usual |
| **NEXUS** | Defined implementation tasks, reviews, audits | `python nexus_chat.py --project .` |

---

## Security

- **Never commit `.env`** — it's gitignored by default
- The API key is read from `.env` or the `NVIDIA_API_KEY` environment variable
- `.nexus/` directories (local project context) are gitignored
- No personal data is stored in the repository

---

## Bonus models (available but not active by default)

Update `mcp-servers/nexus/models.json` to activate:

| Model | Best for |
|-------|----------|
| `qwen/qwen3-coder-480b-a35b-instruct` | Very complex code tasks |
| `nvidia/llama-3.1-nemotron-ultra-253b-v1` | Deep reasoning, Opus alternative |
| `moonshotai/kimi-k2-thinking` | Hard bugs, thinking mode |
| `deepseek-ai/deepseek-v3.2` | Strong generalist alternative |

---

## License

MIT
