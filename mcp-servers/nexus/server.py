"""
NEXUS MCP Server v1.0
=====================
Orchestration multi-agents pour Claude Code via NVIDIA NIM (gratuit).

Modèles :
  - Qwen 3.5 397B  → planification, raisonnement (plan_task)
  - Kimi K2.5      → génération de code (implement_code, batch_implement)
  - Nemotron Super → review de code (review_code)
  - GPT-OSS / GLM  → compression de contexte (compress_context)

Escalade vers Claude Opus 4.5 uniquement via escalate_to_opus.

Configuration des modèles : models.json (même répertoire)
Clé API injectée via variable d'environnement NVIDIA_API_KEY.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# ─── Configuration ────────────────────────────────────────────────────────────

HERE = Path(__file__).parent
MODELS_FILE = HERE / "models.json"

NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"


def load_models() -> dict:
    if MODELS_FILE.exists():
        data = json.loads(MODELS_FILE.read_text(encoding="utf-8"))
        # Aplatir : exclure les clés de métadonnées et les sous-objets _bonus_models
        flat = {}
        for k, v in data.items():
            if k.startswith("_"):
                continue
            if isinstance(v, dict) and "id" in v:
                flat[k] = v
        return flat
    # Fallback sur les modèles confirmés (IDs vérifiés le 2026-04-07)
    return {
        "qwen":     {"id": "qwen/qwen3.5-397b-a17b",           "max_tokens": 8192, "temperature": 0.2},
        "kimi":     {"id": "moonshotai/kimi-k2.5",             "max_tokens": 8192, "temperature": 0.05},
        "nemotron": {"id": "nvidia/nemotron-3-super-120b-a12b", "max_tokens": 4096, "temperature": 0.1},
        "gpt_oss":  {"id": "openai/gpt-oss-120b",              "max_tokens": 4096, "temperature": 0.3},
        "minimax":  {"id": "minimaxai/minimax-m2.5",            "max_tokens": 8192, "temperature": 0.1},
        "glm":      {"id": "z-ai/glm5",                        "max_tokens": 4096, "temperature": 0.2},
    }


# ─── Gestion d'état projet ────────────────────────────────────────────────────

def get_nexus_dir() -> Path:
    """Répertoire .nexus/ dans le dossier de travail courant."""
    nexus = Path.cwd() / ".nexus"
    nexus.mkdir(exist_ok=True)
    return nexus


def read_project_context() -> str:
    ctx = get_nexus_dir() / "context.md"
    if ctx.exists():
        return ctx.read_text(encoding="utf-8")
    return "(Aucun contexte projet enregistré — nouveau projet ou première session.)"


def write_project_context(content: str):
    (get_nexus_dir() / "context.md").write_text(content, encoding="utf-8")


def log_decision(text: str, agent: str):
    dec = get_nexus_dir() / "decisions.md"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(dec, "a", encoding="utf-8") as f:
        f.write(f"\n## [{ts}] {agent}\n{text}\n")


def log_api_call(model_key: str, prompt_tokens: int, completion_tokens: int):
    log = get_nexus_dir() / "usage.jsonl"
    entry = {
        "ts": datetime.now().isoformat(),
        "model": model_key,
        "tok_in": prompt_tokens,
        "tok_out": completion_tokens,
        "cost": 0  # NVIDIA NIM gratuit
    }
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ─── Appel NVIDIA NIM ─────────────────────────────────────────────────────────

async def call_nvidia(model_key: str, messages: list, max_tokens: int | None = None) -> str:
    if not NVIDIA_KEY:
        return "ERREUR : NVIDIA_API_KEY non définie. Vérifier la configuration MCP."

    models = load_models()
    if model_key not in models:
        return f"ERREUR : modèle '{model_key}' inconnu. Vérifier models.json."

    cfg = models[model_key]
    model_id = cfg["id"]
    tok = max_tokens or cfg.get("max_tokens", 4096)
    temp = cfg.get("temperature", 0.1)

    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(
            NVIDIA_URL,
            headers={
                "Authorization": f"Bearer {NVIDIA_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_id,
                "messages": messages,
                "max_tokens": tok,
                "temperature": temp,
            },
        )

        if resp.status_code != 200:
            return f"ERREUR NIM [{resp.status_code}] : {resp.text[:300]}"

        data = resp.json()
        usage = data.get("usage", {})
        log_api_call(model_key, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))

        msg = data["choices"][0]["message"]
        # Certains modèles (thinking, GPT-OSS) retournent le contenu dans
        # reasoning_content quand content est null
        content = msg.get("content") or msg.get("reasoning_content") or ""
        if not content:
            # Dernier recours : sérialiser le message entier pour debug
            content = f"[réponse vide — message brut : {json.dumps(msg)[:500]}]"
        return content


# ─── Serveur MCP ──────────────────────────────────────────────────────────────

app = Server("nexus-orchestrator")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [

        types.Tool(
            name="plan_task",
            description=(
                "Décompose une tâche complexe en sous-tâches atomiques via Qwen 3.5 397B. "
                "À appeler EN PREMIER pour toute demande complexe, multi-fichiers ou ambiguë. "
                "Retourne un plan structuré avec l'agent recommandé pour chaque étape."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "La tâche à planifier et décomposer"
                    },
                    "project_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Chemins des fichiers déjà lus et pertinents pour la tâche"
                    }
                },
                "required": ["task"]
            }
        ),

        types.Tool(
            name="implement_code",
            description=(
                "Génère du code précis via Kimi K2.5 (spécialiste code). "
                "Idéal pour : nouvelles fonctions, composants, endpoints, tests, migrations. "
                "Scope PRÉCIS requis — une fonction ou un fichier à la fois, pas tout le projet."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Description précise de ce que le code doit faire"
                    },
                    "language": {
                        "type": "string",
                        "description": "Langage : python | typescript | rust | go | java | etc."
                    },
                    "context": {
                        "type": "string",
                        "description": "Code existant pertinent (interfaces, types, fonctions voisines) — max 3000 tokens"
                    },
                    "constraints": {
                        "type": "string",
                        "description": "Contraintes spécifiques : style, performance, compatibilité, conventions"
                    }
                },
                "required": ["task", "language"]
            }
        ),

        types.Tool(
            name="review_code",
            description=(
                "Revue de code approfondie via Nemotron Super. "
                "Détecte bugs, sécurité, style, régressions. "
                "À appeler avant tout commit ou merge important."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Le code à reviewer (max 200 lignes pour une review de qualité)"
                    },
                    "language": {
                        "type": "string",
                        "description": "Langage du code"
                    },
                    "focus": {
                        "type": "string",
                        "description": "Axes prioritaires : security | performance | correctness | style (séparés par virgules)"
                    }
                },
                "required": ["code", "language"]
            }
        ),

        types.Tool(
            name="compress_context",
            description=(
                "Compresse le contexte de session pour économiser des tokens. "
                "À appeler quand la session devient longue (> 40-50 messages) ou avant une nouvelle phase. "
                "Sauvegarde dans .nexus/context.md du projet courant."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Contenu à compresser : historique de session, notes, contexte accumulé"
                    },
                    "preserve": {
                        "type": "string",
                        "description": "Points critiques à conserver absolument dans le résumé"
                    }
                },
                "required": ["content"]
            }
        ),

        types.Tool(
            name="batch_implement",
            description=(
                "Implémente plusieurs fonctions ou modules indépendants en parallèle via Kimi K2.5. "
                "Économise du temps pour les tâches répétitives : CRUD, tests multiples, composants similaires."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "description": "Identifiant court de la tâche"},
                                "task": {"type": "string", "description": "Description de la tâche"},
                                "context": {"type": "string", "description": "Contexte spécifique à cette tâche (optionnel)"}
                            },
                            "required": ["id", "task"]
                        },
                        "description": "Liste de tâches d'implémentation indépendantes"
                    },
                    "language": {"type": "string"}
                },
                "required": ["tasks", "language"]
            }
        ),

        types.Tool(
            name="escalate_to_opus",
            description=(
                "ESCALADE vers Claude Opus 4.5 — Coût élevé, usage exceptionnel uniquement. "
                "Conditions strictes : (1) agents gratuits ont échoué 2+ fois, "
                "(2) décision architecturale fondamentale irréversible, "
                "(3) bug critique impossible à résoudre autrement. "
                "NE PAS utiliser pour du code standard ou des questions simples."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "problem": {
                        "type": "string",
                        "description": "Le problème précis nécessitant Opus"
                    },
                    "already_tried": {
                        "type": "string",
                        "description": "Ce qui a déjà été tenté avec les agents gratuits"
                    },
                    "why_opus": {
                        "type": "string",
                        "description": "Justification de l'escalade"
                    }
                },
                "required": ["problem", "why_opus"]
            }
        ),

        types.Tool(
            name="get_project_state",
            description=(
                "Lit l'état courant du projet depuis .nexus/ (contexte compressé, statistiques d'usage). "
                "À appeler en début de session pour reprendre là où on s'est arrêté."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),

        types.Tool(
            name="save_decision",
            description=(
                "Sauvegarde une décision architecturale ou technique importante dans .nexus/decisions.md. "
                "Utiliser pour toute décision qui impacte la structure du projet."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "decision": {"type": "string", "description": "La décision prise"},
                    "rationale": {"type": "string", "description": "Pourquoi cette décision (contexte, alternatives rejetées)"}
                },
                "required": ["decision"]
            }
        ),

    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    # ── plan_task ──────────────────────────────────────────────────────────────
    if name == "plan_task":
        context = read_project_context()
        files_hint = ""
        if arguments.get("project_files"):
            files_hint = f"\nFichiers du projet déjà lus : {', '.join(arguments['project_files'])}"

        messages = [
            {
                "role": "system",
                "content": (
                    "Tu es un architecte senior. Décompose la tâche en sous-tâches atomiques et actionnables.\n"
                    "Pour chaque sous-tâche, indique :\n"
                    "- Description précise (scope minimal, une seule responsabilité)\n"
                    "- Agent recommandé : kimi (génération code) | nemotron (review/debug) | qwen (analyse/plan)\n"
                    "- Inputs requis\n"
                    "- Outputs attendus\n"
                    "- Dépendances avec les autres sous-tâches\n"
                    "Sois précis et atomique. Pas de sous-tâches floues."
                ),
            },
            {
                "role": "user",
                "content": f"Contexte projet :\n{context}{files_hint}\n\nTâche à décomposer :\n{arguments['task']}",
            },
        ]

        result = await call_nvidia("qwen", messages)
        return [types.TextContent(type="text", text=f"**Plan NEXUS (Qwen 3.5 397B)**\n\n{result}")]

    # ── implement_code ─────────────────────────────────────────────────────────
    elif name == "implement_code":
        lang = arguments["language"]
        system = (
            f"Tu es un expert {lang} qui écrit du code production-ready.\n"
            "Règles absolues :\n"
            "- Code fonctionnel, propre, sans TODO ni placeholder\n"
            "- Gestion d'erreurs appropriée au contexte\n"
            "- Pas de commentaires inutiles (uniquement si logique non évidente)\n"
            "- Retourne UNIQUEMENT le code\n"
            "- Si plusieurs fichiers, sépare avec : // === FICHIER: chemin/fichier.ext ==="
        )

        user_content = arguments["task"]
        if arguments.get("context"):
            user_content = f"Code existant pertinent :\n```{lang}\n{arguments['context']}\n```\n\nTâche : {user_content}"
        if arguments.get("constraints"):
            user_content += f"\n\nContraintes : {arguments['constraints']}"

        result = await call_nvidia("kimi", [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ])
        return [types.TextContent(type="text", text=f"**Code généré (Kimi K2.5)**\n\n{result}")]

    # ── review_code ────────────────────────────────────────────────────────────
    elif name == "review_code":
        lang = arguments["language"]
        focus = arguments.get("focus", "correctness, security, style")

        messages = [
            {
                "role": "system",
                "content": (
                    f"Tu es un reviewer expert en {lang}. Focus demandé : {focus}.\n"
                    "Format de sortie :\n"
                    "## Issues critiques (bloquants)\n"
                    "## Issues majeures (important)\n"
                    "## Suggestions (mineur)\n"
                    "## Verdict : APPROVED | CHANGES_REQUIRED | BLOCKED\n\n"
                    "Pour chaque issue : numéro de ligne, description, exemple de correction."
                ),
            },
            {
                "role": "user",
                "content": f"Code à reviewer :\n```{lang}\n{arguments['code']}\n```",
            },
        ]

        result = await call_nvidia("nemotron", messages)
        return [types.TextContent(type="text", text=f"**Review (Nemotron Super)**\n\n{result}")]

    # ── compress_context ───────────────────────────────────────────────────────
    elif name == "compress_context":
        preserve = arguments.get("preserve", "")

        messages = [
            {
                "role": "system",
                "content": (
                    "Tu es un assistant de compression de contexte projet.\n"
                    "Produis un résumé DENSE en Markdown (max 800 mots) avec ce format :\n"
                    "## État du projet\n"
                    "## Décisions prises\n"
                    "## Travail réalisé (liste bullet)\n"
                    "## Prochaines étapes\n"
                    "## Points d'attention\n"
                    "Préserve les faits techniques exacts. Supprime tout ce qui est redondant."
                ),
            },
            {
                "role": "user",
                "content": f"À compresser :\n{arguments['content']}\n\nÀ préserver absolument :\n{preserve}",
            },
        ]

        # Essaie gpt_oss, fallback sur qwen si indisponible
        result = await call_nvidia("gpt_oss", messages, max_tokens=1500)
        if result.startswith("ERREUR"):
            result = await call_nvidia("qwen", messages, max_tokens=1500)

        write_project_context(result)
        return [types.TextContent(
            type="text",
            text=f"**Contexte compressé et sauvegardé (.nexus/context.md)**\n\n{result}"
        )]

    # ── batch_implement ────────────────────────────────────────────────────────
    elif name == "batch_implement":
        lang = arguments["language"]
        tasks = arguments["tasks"]

        async def implement_one(item: dict) -> str:
            msgs = [
                {"role": "system", "content": f"Expert {lang}. Code production-ready uniquement."},
                {"role": "user", "content": f"{item.get('context', '')}\n\nTâche [{item['id']}] : {item['task']}"},
            ]
            res = await call_nvidia("kimi", msgs, max_tokens=2048)
            return f"### [{item['id']}]\n{res}"

        results = await asyncio.gather(*[implement_one(t) for t in tasks])
        combined = "\n\n---\n\n".join(results)

        return [types.TextContent(
            type="text",
            text=f"**Batch implémentation (Kimi K2.5) — {len(tasks)} tâches**\n\n{combined}"
        )]

    # ── escalate_to_opus ───────────────────────────────────────────────────────
    elif name == "escalate_to_opus":
        log_decision(
            f"ESCALADE OPUS demandée\nProblème : {arguments['problem']}\nJustification : {arguments['why_opus']}",
            "nexus-escalation"
        )
        already = arguments.get("already_tried", "non précisé")

        return [types.TextContent(
            type="text",
            text=(
                "**ESCALADE VERS CLAUDE OPUS 4.5**\n\n"
                f"**Problème :** {arguments['problem']}\n\n"
                f"**Déjà tenté :** {already}\n\n"
                f"**Justification :** {arguments['why_opus']}\n\n"
                "---\n"
                "Pour activer Opus dans Claude Code :\n"
                "1. Tape `/model opus` dans le prompt\n"
                "2. Pose ta question directement\n"
                "3. Une fois résolu, reviens à Sonnet avec `/model sonnet`\n\n"
                "*Décision tracée dans .nexus/decisions.md*"
            )
        )]

    # ── get_project_state ──────────────────────────────────────────────────────
    elif name == "get_project_state":
        nexus = get_nexus_dir()
        context = read_project_context()

        # Statistiques d'usage
        usage_stats = {}
        usage_log = nexus / "usage.jsonl"
        if usage_log.exists():
            for line in usage_log.read_text(encoding="utf-8").strip().split("\n"):
                if line:
                    try:
                        e = json.loads(line)
                        m = e.get("model", "?")
                        usage_stats[m] = usage_stats.get(m, 0) + 1
                    except json.JSONDecodeError:
                        pass

        decisions_count = 0
        dec_file = nexus / "decisions.md"
        if dec_file.exists():
            decisions_count = dec_file.read_text(encoding="utf-8").count("## [")

        report = (
            f"**État du projet NEXUS**\n\n"
            f"**Répertoire :** `{Path.cwd()}`\n"
            f"**Décisions tracées :** {decisions_count}\n"
            f"**Appels agents (session) :** {json.dumps(usage_stats, ensure_ascii=False)}\n\n"
            f"**Contexte projet :**\n{context}"
        )

        return [types.TextContent(type="text", text=report)]

    # ── save_decision ──────────────────────────────────────────────────────────
    elif name == "save_decision":
        text = arguments["decision"]
        if arguments.get("rationale"):
            text += f"\n\n**Rationale :** {arguments['rationale']}"
        log_decision(text, "claude-code")

        return [types.TextContent(
            type="text",
            text=f"Décision sauvegardée dans `.nexus/decisions.md`\n\n> {arguments['decision'][:200]}"
        )]

    return [types.TextContent(type="text", text=f"Outil inconnu : {name}")]


# ─── Entrée ───────────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
