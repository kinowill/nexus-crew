#!/usr/bin/env python3
"""
NEXUS — Orchestrateur agentique autonome v2.0
==============================================
Mode d'emploi :
  python nexus.py "implémente l'authentification JWT dans mon projet"
  python nexus.py "ajoute des tests pour le module users" --write
  python nexus.py "refactore auth.py pour séparer les concerns" --project C:/monprojet

Modes :
  Sans --write  → affiche le plan + le code généré, rien n'est écrit
  Avec  --write → écrit les fichiers directement dans le projet
  Avec  --dry   → affiche uniquement le plan, sans exécuter

Escalade automatique :
  Agent échoue 2x → fallback sur Qwen
  Qwen échoue    → escalade vers Claude Code CLI
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

# ─── Configuration ────────────────────────────────────────────────────────────

HERE = Path(__file__).parent
ENV_FILE = HERE / ".env"
MODELS_FILE = HERE / "mcp-servers" / "nexus" / "models.json"

NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# Charger la clé depuis .env
def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

load_env()
API_KEY = os.environ.get("NVIDIA_API_KEY", "")

# Modèles (fallback si models.json absent)
MODELS = {
    "qwen":     "qwen/qwen3.5-397b-a17b",
    "kimi":     "moonshotai/kimi-k2-instruct-0905",
    "nemotron": "nvidia/nemotron-3-super-120b-a12b",
    "gpt_oss":  "openai/gpt-oss-120b",
    "minimax":  "minimaxai/minimax-m2.5",
    "glm":      "z-ai/glm5",
}

def load_models():
    if MODELS_FILE.exists():
        raw = json.loads(MODELS_FILE.read_text(encoding="utf-8"))
        return {k: v["id"] for k, v in raw.items()
                if isinstance(v, dict) and "id" in v and not k.startswith("_")}
    return MODELS

# ─── Affichage ────────────────────────────────────────────────────────────────

def p(msg: str, indent: int = 0):
    prefix = "  " * indent
    print(f"{prefix}{msg}")

def header(title: str):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)

def step_log(n: int, total: int, agent: str, desc: str):
    print(f"\n  [{n}/{total}] {agent.upper()} -- {desc[:55]}")

# ─── Appel NVIDIA NIM ─────────────────────────────────────────────────────────

async def call_model(model_key: str, messages: list,
                     max_tokens: int = 4096, temperature: float = 0.1,
                     retries: int = 2) -> str | None:
    models = load_models()
    model_id = models.get(model_key)
    if not model_id:
        p(f"    Modele inconnu : {model_key}")
        return None

    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    NVIDIA_URL,
                    headers={"Authorization": f"Bearer {API_KEY}"},
                    json={
                        "model": model_id,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    }
                )
                if resp.status_code == 429:
                    wait = 15 * (attempt + 1)
                    p(f"    Rate limit -- attente {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                if resp.status_code != 200:
                    p(f"    Erreur HTTP {resp.status_code}")
                    return None

                msg = resp.json()["choices"][0]["message"]
                content = msg.get("content") or msg.get("reasoning_content") or ""
                if content:
                    return content

                p(f"    Reponse vide (tentative {attempt+1}/{retries})")
                await asyncio.sleep(3)

        except httpx.TimeoutException:
            p(f"    Timeout (tentative {attempt+1}/{retries})")
            if attempt < retries - 1:
                await asyncio.sleep(5)
        except Exception as e:
            p(f"    Erreur : {e}")
            return None

    return None

# ─── Escalade vers Claude Code CLI ────────────────────────────────────────────

def escalate_to_claude(task: str, context: str = "") -> str:
    p("\n  [ESCALADE] Appel Claude Code CLI...")
    prompt = f"{context}\n\n{task}" if context else task
    try:
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        p(f"    Claude CLI erreur : {result.stderr[:100]}")
    except FileNotFoundError:
        p("    Claude Code CLI non trouve dans le PATH.")
    except subprocess.TimeoutExpired:
        p("    Claude CLI timeout.")
    return ""

# ─── Phase 1 : Orchestration (Qwen planifie) ──────────────────────────────────

ORCHESTRATOR_SYSTEM = """Tu es un orchestrateur d'agents IA expert.
Ta mission : analyser une tâche et produire un plan d'exécution JSON strict.

Règles absolues :
- Chaque étape est atomique (une seule responsabilité)
- Les étapes sont ordonnées par dépendances
- Assigne chaque étape à l'agent optimal

Agents disponibles :
  "kimi"     — génération de code (fonctions, classes, composants, tests, migrations)
  "nemotron" — review de code, debug, analyse de qualité
  "gpt_oss"  — documentation, explications, tâches générales
  "qwen"     — raisonnement complexe, architecture, décomposition

Réponds UNIQUEMENT avec du JSON valide, sans markdown ni texte autour :
{
  "goal": "description concise de l'objectif",
  "steps": [
    {
      "id": "step_1",
      "agent": "kimi",
      "description": "description courte de cette étape",
      "task": "prompt exact à envoyer à l'agent",
      "language": "python",
      "output_file": "src/auth.py",
      "depends_on": []
    }
  ]
}

Champs optionnels : "language" (si code), "output_file" (si fichier à créer/modifier).
"depends_on" : liste des IDs d'étapes dont cette étape dépend."""

async def orchestrate(task: str, context: str, project_files: list[str]) -> dict | None:
    p("  Qwen 3.5 planifie la tache...", indent=1)

    files_hint = ""
    if project_files:
        files_hint = f"\n\nFichiers du projet disponibles :\n" + "\n".join(f"  - {f}" for f in project_files[:20])

    messages = [
        {"role": "system", "content": ORCHESTRATOR_SYSTEM},
        {"role": "user", "content": f"Contexte projet :\n{context}{files_hint}\n\nTâche : {task}"}
    ]

    result = await call_model("qwen", messages, max_tokens=3000, temperature=0.1)
    if not result:
        return None

    # Extraire le JSON
    try:
        start = result.find("{")
        end = result.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(result[start:end])
    except json.JSONDecodeError as e:
        p(f"    JSON invalide : {e}")

    # Fallback : plan minimal
    return {
        "goal": task,
        "steps": [{
            "id": "step_1",
            "agent": "kimi",
            "description": "Implémentation directe",
            "task": task,
            "depends_on": []
        }]
    }

# ─── Phase 2 : Exécution des étapes ──────────────────────────────────────────

async def execute_step(step: dict, context: str, previous_results: dict,
                       project_path: Path) -> str | None:
    agent = step.get("agent", "kimi")
    task = step["task"]
    lang = step.get("language", "")

    # Injecter les résultats des étapes précédentes
    dep_context = ""
    for dep_id in step.get("depends_on", []):
        if dep_id in previous_results:
            dep_context += f"\n\n=== Résultat de {dep_id} ===\n{previous_results[dep_id][:2000]}"

    # Contexte fichier si output_file existe déjà
    file_context = ""
    output_file = step.get("output_file")
    if output_file and project_path:
        fp = project_path / output_file
        if fp.exists():
            content = fp.read_text(encoding="utf-8")
            file_context = f"\n\nFichier existant ({output_file}) :\n```{lang}\n{content[:3000]}\n```"

    system = build_system_prompt(agent, lang)
    user_content = f"Contexte projet :\n{context[:1500]}{dep_context}{file_context}\n\nTâche : {task}"

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content}
    ]

    result = await call_model(agent, messages, max_tokens=5000, temperature=0.05)

    # Fallback sur Qwen si l'agent primaire échoue
    if not result:
        p(f"    Fallback sur Qwen...", indent=3)
        result = await call_model("qwen", messages, max_tokens=5000, temperature=0.1)

    # Dernier recours : Claude CLI
    if not result:
        result = escalate_to_claude(task, context[:1000])

    return result

def build_system_prompt(agent: str, language: str) -> str:
    if agent == "kimi":
        lang_hint = f" en {language}" if language else ""
        return (
            f"Tu es un expert en développement logiciel{lang_hint}. "
            "Écris du code production-ready, propre, sans TODO ni placeholder. "
            "Si plusieurs fichiers, sépare avec : // === FICHIER: chemin/fichier ==="
        )
    elif agent == "nemotron":
        return (
            "Tu es un expert en review de code et débogage. "
            "Analyse le code, identifie les problèmes (bugs, sécurité, performance), "
            "et fournis des corrections précises avec le code corrigé."
        )
    elif agent == "gpt_oss":
        return "Tu es un assistant technique expert. Réponds de façon précise et structurée."
    else:
        return "Tu es un expert en architecture logicielle et raisonnement technique."

# ─── Phase 3 : Écriture des fichiers ─────────────────────────────────────────

def extract_code_blocks(content: str) -> list[tuple[str, str]]:
    """Extrait les blocs de code avec leur langage."""
    import re
    blocks = re.findall(r"```(?:\w+)?\n(.*?)```", content, re.DOTALL)
    return blocks

def write_output(step: dict, result: str, project_path: Path) -> bool:
    """Écrit le résultat dans le fichier de sortie si spécifié."""
    output_file = step.get("output_file")
    if not output_file or not project_path:
        return False

    # Chercher un marqueur de fichier multi-fichiers
    if "=== FICHIER:" in result:
        import re
        parts = re.split(r"//\s*===\s*FICHIER:\s*(.+?)\s*===", result)
        for i in range(1, len(parts), 2):
            fname = parts[i].strip()
            fcode = parts[i+1].strip() if i+1 < len(parts) else ""
            # Enlever les balises de code markdown
            fcode = re.sub(r"^```\w*\n?", "", fcode)
            fcode = re.sub(r"\n?```$", "", fcode)
            if fcode:
                fp = project_path / fname
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_text(fcode, encoding="utf-8")
                p(f"    Ecrit : {fname}")
        return True

    # Fichier unique : extraire le premier bloc de code
    import re
    code_match = re.search(r"```(?:\w+)?\n(.*?)```", result, re.DOTALL)
    raw = code_match.group(1).strip() if code_match else result.strip()

    fp = project_path / output_file
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(raw, encoding="utf-8")
    p(f"    Ecrit : {output_file}")
    return True

# ─── Contexte projet ──────────────────────────────────────────────────────────

def load_project_context(project_path: Path) -> str:
    nexus_ctx = project_path / ".nexus" / "context.md"
    if nexus_ctx.exists():
        return nexus_ctx.read_text(encoding="utf-8")
    return ""

def save_project_context(project_path: Path, summary: str):
    nexus_dir = project_path / ".nexus"
    nexus_dir.mkdir(exist_ok=True)
    ctx_file = nexus_dir / "context.md"
    existing = ctx_file.read_text(encoding="utf-8") if ctx_file.exists() else ""
    # Garder seulement les 3000 derniers chars + nouveau résumé
    combined = (existing[-2000:] + "\n\n" + summary) if existing else summary
    ctx_file.write_text(combined, encoding="utf-8")

def scan_project_files(project_path: Path) -> list[str]:
    """Liste les fichiers de code du projet (heuristique)."""
    extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go",
                  ".java", ".cs", ".cpp", ".c", ".h", ".json", ".yaml", ".yml"}
    exclude = {"node_modules", ".git", "__pycache__", ".venv", "dist", "build", ".nexus"}

    files = []
    try:
        for p in project_path.rglob("*"):
            if any(ex in p.parts for ex in exclude):
                continue
            if p.is_file() and p.suffix in extensions:
                files.append(str(p.relative_to(project_path)))
    except PermissionError:
        pass
    return files[:50]

# ─── Résumé post-exécution ────────────────────────────────────────────────────

async def summarize_run(goal: str, steps_results: dict) -> str:
    """Produit un résumé compact de ce qui a été accompli."""
    content = "\n\n".join(f"Étape {k} : {v[:500]}" for k, v in steps_results.items())
    messages = [
        {"role": "system", "content": "Résume en 5 bullet points max ce qui a été accompli. Sois factuel et concis."},
        {"role": "user", "content": f"Objectif : {goal}\n\nRésultats :\n{content[:3000]}"}
    ]
    summary = await call_model("glm", messages, max_tokens=500, temperature=0.1)
    return summary or f"Objectif accompli : {goal}"

# ─── Entrée principale ────────────────────────────────────────────────────────

async def run(task: str, project: str, write_files: bool, dry_run: bool):
    if not API_KEY:
        p("ERREUR : NVIDIA_API_KEY manquante. Verifie .env")
        sys.exit(1)

    project_path = Path(project).resolve() if project else Path.cwd()
    context = load_project_context(project_path)
    project_files = scan_project_files(project_path) if project else []

    header("NEXUS — Mode Agentique")
    p(f"Tache    : {task}")
    p(f"Projet   : {project_path}")
    p(f"Ecriture : {'OUI (--write)' if write_files else 'NON (mode simulation)'}")

    # ── Phase 1 : Orchestration ──────────────────────────────────────────────
    print()
    p("[1/3] PLANIFICATION (Qwen 3.5 397B)")
    plan = await orchestrate(task, context, project_files)

    if not plan:
        p("  Planification echouee. Escalade vers Claude...")
        result = escalate_to_claude(task, context)
        p(result)
        return

    steps = plan.get("steps", [])
    p(f"  Objectif : {plan.get('goal', task)}")
    p(f"  Etapes   : {len(steps)}")
    for s in steps:
        p(f"    [{s['id']}] {s.get('agent','?').upper()} -- {s.get('description', '')[:50]}")

    if dry_run:
        p("\n  Mode --dry : plan affiché, aucune exécution.")
        return

    # ── Phase 2 : Exécution ──────────────────────────────────────────────────
    print()
    p("[2/3] EXECUTION")
    results: dict[str, str] = {}

    for i, step in enumerate(steps, 1):
        step_log(i, len(steps), step.get("agent", "?"), step.get("description", ""))

        result = await execute_step(step, context, results, project_path)

        if result:
            results[step["id"]] = result

            # Affichage compact
            preview = result[:400].replace("\n", " ")
            p(f"    OK : {preview}...", indent=2)

            # Écriture fichiers si activée
            if write_files and step.get("output_file"):
                write_output(step, result, project_path)
        else:
            p(f"    ECHEC : etape {step['id']} -- continu...", indent=2)

        # Respect rate limit (40 req/min)
        if i < len(steps):
            await asyncio.sleep(1.5)

    # ── Phase 3 : Résumé ─────────────────────────────────────────────────────
    print()
    p("[3/3] RESUME")
    summary = await summarize_run(plan.get("goal", task), results)
    p(f"\n{summary}")

    # Mise à jour contexte projet
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    context_update = f"\n## [{ts}] Tâche accomplie\nObjectif : {task}\n{summary}"
    save_project_context(project_path, context_update)
    p(f"\n  Contexte projet mis a jour (.nexus/context.md)")

    header("NEXUS -- Termine")

    # Afficher les fichiers écrits
    if write_files:
        written = [s.get("output_file") for s in steps if s.get("output_file")]
        if written:
            p("Fichiers ecrits :")
            for f in written:
                p(f"  {f}")
    else:
        p("Mode simulation : relancer avec --write pour ecrire les fichiers.")


def main():
    parser = argparse.ArgumentParser(
        description="NEXUS — Orchestrateur agentique autonome",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python nexus.py "implémente l'auth JWT"
  python nexus.py "ajoute des tests pour src/users.py" --write
  python nexus.py "refactore le module cache" --project C:/monprojet --write
  python nexus.py "explique l'architecture" --dry
        """
    )
    parser.add_argument("task", help="Tâche à accomplir")
    parser.add_argument("--project", "-p", default="", help="Chemin du projet (défaut: répertoire courant)")
    parser.add_argument("--write", "-w", action="store_true", help="Écrire les fichiers générés")
    parser.add_argument("--dry", "-d", action="store_true", help="Afficher le plan sans exécuter")

    args = parser.parse_args()
    asyncio.run(run(args.task, args.project, args.write, args.dry))


if __name__ == "__main__":
    main()
