#!/usr/bin/env python3
"""
NEXUS Chat v3.0 — Architecture Brain + Workers
===============================================

Un seul agent intelligent centralise TOUTES les décisions de routage.
Les workers (Kimi, Nemotron, GPT-OSS) exécutent et retournent, sans réfléchir au flux.

Brain par défaut : Qwen 3.5 397B (gratuit, raisonnement fort)
Fallback Brain   : Claude Sonnet (Pro, si Qwen échoue)
Dernier recours  : Claude Opus   (si tâche critique et Sonnet insuffisant)

Workers :
  kimi     — écrire / modifier du code
  nemotron — review, debug, validation
  gpt_oss  — documentation, synthèse, explication

Usage :
  python nexus_chat.py
  python nexus_chat.py --project C:/mon-projet --write
  python nexus_chat.py --brain claude   (force Claude comme brain)

Commandes : /quit /context /files /clear /write /help
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import httpx

# ─── Config ───────────────────────────────────────────────────────────────────

HERE        = Path(__file__).parent
ENV_FILE    = HERE / ".env"
MODELS_FILE = HERE / "mcp-servers" / "nexus" / "models.json"
NVIDIA_URL  = "https://integrate.api.nvidia.com/v1/chat/completions"

MAX_ITERATIONS = 8

def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

load_env()
API_KEY = os.environ.get("NVIDIA_API_KEY", "")

NVIDIA_MODELS = {
    "qwen":     "qwen/qwen3.5-397b-a17b",
    "kimi":     "moonshotai/kimi-k2-instruct-0905",
    "nemotron": "nvidia/nemotron-3-super-120b-a12b",
    "gpt_oss":  "openai/gpt-oss-120b",
    "minimax":  "minimaxai/minimax-m2.5",
    "glm":      "z-ai/glm5",
}

def get_model_id(key: str) -> str:
    try:
        if MODELS_FILE.exists():
            raw = json.loads(MODELS_FILE.read_text(encoding="utf-8"))
            for k, v in raw.items():
                if k == key and isinstance(v, dict) and "id" in v:
                    return v["id"]
    except Exception:
        pass
    return NVIDIA_MODELS.get(key, NVIDIA_MODELS["qwen"])

# ─── Couleurs ─────────────────────────────────────────────────────────────────

R  = "\033[0m"
B  = "\033[1m"
DIM= "\033[2m"
CY = "\033[96m"
GR = "\033[92m"
YL = "\033[93m"
RE = "\033[91m"
BL = "\033[94m"
MG = "\033[95m"

AGENT_COLORS = {
    "qwen":     BL,
    "kimi":     GR,
    "nemotron": YL,
    "gpt_oss":  CY,
    "minimax":  MG,
    "glm":      DIM,
    "claude":   MG,
}
AGENT_NAMES = {
    "qwen":     "Qwen 3.5 397B",
    "kimi":     "Kimi K2",
    "nemotron": "Nemotron Super",
    "gpt_oss":  "GPT-OSS 120B",
    "minimax":  "MiniMax M2.5",
    "glm":      "GLM-5",
    "claude":   "Claude Sonnet",
}

def label(key: str) -> str:
    col  = AGENT_COLORS.get(key, "")
    name = AGENT_NAMES.get(key, key.upper())
    return f"{col}{B}[{name}]{R}"

# ─── Appels API ───────────────────────────────────────────────────────────────

async def call_nvidia(key: str, messages: list,
                      max_tokens: int = 6000, temperature: float = 0.1) -> str | None:
    model_id = get_model_id(key)
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                NVIDIA_URL,
                headers={"Authorization": f"Bearer {API_KEY}"},
                json={"model": model_id, "messages": messages,
                      "max_tokens": max_tokens, "temperature": temperature}
            )
            if resp.status_code == 429:
                print(f" {YL}[rate limit — 15s]{R}", end="", flush=True)
                await asyncio.sleep(15)
                return await call_nvidia(key, messages, max_tokens, temperature)
            if resp.status_code != 200:
                return None
            msg = resp.json()["choices"][0]["message"]
            return msg.get("content") or msg.get("reasoning_content") or None
    except Exception:
        return None

def call_claude_cli(prompt: str, model: str = "sonnet") -> str | None:
    """Appel Claude via CLI (authentification OAuth — pas besoin de clé API)."""
    model_flag = f"claude-{model}-4-6" if model in ("sonnet", "opus") else model
    try:
        result = subprocess.run(
            ["claude", "--model", model_flag, "--print", prompt],
            capture_output=True, text=True, timeout=120, encoding="utf-8"
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None

# ─── BRAIN — l'agent qui décide de tout ──────────────────────────────────────

BRAIN_SYSTEM = """Tu es le Brain de NEXUS, l'orchestrateur central. TU SEUL décides du flux.

Ton rôle :
  1. Analyser la tâche et les résultats déjà produits
  2. Décider de la prochaine action

Workers à ta disposition (ils exécutent et te retournent le résultat) :
  "kimi"     → écrire ou modifier du code (fonctions, classes, tests, fichiers)
  "nemotron" → review de code, debug, identification de bugs et corrections
  "gpt_oss"  → documentation, explication, résumé, synthèse finale

Règles de décision :
  - Toute génération de code non triviale → kimi
  - Après génération de code → nemotron (review systématique si code > 20 lignes)
  - Nemotron a trouvé des bugs → kimi (correction)
  - Réponse prête mais brute → gpt_oss (mise en forme) OU réponse finale directe
  - Si tu peux répondre seul (question, analyse, explication) → réponds directement

PROTOCOLE DE TRAVAIL (non négociable) :
  - Ne jamais inventer un nom de fichier, de fonction ou de variable — lire d'abord.
  - Ne jamais présenter comme "fini" ce qui n'a pas été validé en vrai.
  - Distinguer explicitement : code local modifié / déployé en prod / validé réellement.
  - Si une information vient d'un résumé ou d'une mémoire : la vérifier avant d'agir.
  - Quand un choix architectural est nécessaire : présenter les options, ne pas trancher seul.
  - Mettre à jour le document maître (.nexus/context.md) après chaque action significative.

FORMAT DE SORTIE — choisis exactement un des deux formats :

Format 1 — Déléguer à un worker :
DELEGATE: {"to": "kimi", "task": "description précise de la tâche", "reason": "pourquoi ce worker"}

Format 2 — Réponse finale (tout ce qui suit est la réponse) :
FINAL:
[ta réponse complète ici, peut contenir du code, du markdown, etc.]

⚠ Ne mélange pas les deux. Ne produis QUE l'un ou l'autre."""

BRAIN_SYSTEM_WITH_RESULTS = """Tu es le Brain de NEXUS. Tu viens de recevoir le résultat d'un worker.

Évalue ce résultat :
  - Est-il complet et correct ? → FINAL
  - Nécessite-t-il une review ? → DELEGATE nemotron
  - Contient-il des bugs identifiés ? → DELEGATE kimi pour correction
  - Est-il trop brut ? → DELEGATE gpt_oss pour synthèse
  - Autre chose manque-t-il ? → DELEGATE le bon worker

Workers : "kimi" (code), "nemotron" (review/debug), "gpt_oss" (doc/synthèse)

FORMAT — exactement un des deux :
DELEGATE: {"to": "...", "task": "...", "reason": "..."}
FINAL:
[réponse complète]"""


def parse_brain_output(raw: str) -> dict:
    """
    Retourne {"action": "delegate"|"final", ...}
    """
    raw = raw.strip()

    # Chercher DELEGATE:
    if raw.startswith("DELEGATE:"):
        json_part = raw[len("DELEGATE:"):].strip()
        try:
            start = json_part.find("{")
            end   = json_part.rfind("}") + 1
            data  = json.loads(json_part[start:end])
            return {"action": "delegate", "to": data.get("to", "kimi"),
                    "task": data.get("task", ""), "reason": data.get("reason", "")}
        except Exception:
            pass  # JSON malformé → traité comme FINAL

    # Chercher FINAL:
    if "FINAL:" in raw:
        idx = raw.index("FINAL:")
        response = raw[idx + len("FINAL:"):].strip()
        return {"action": "final", "response": response}

    # Fallback : si aucun marqueur, c'est une réponse finale directe
    return {"action": "final", "response": raw}


async def call_brain(task: str, results: list[dict],
                     project_context: str, conv_history: list,
                     brain_mode: str = "qwen") -> dict:
    """
    Appelle le Brain (Qwen ou Claude).
    results = liste de {"worker": str, "task": str, "output": str}
    """

    # Construire le contexte des résultats précédents
    results_text = ""
    if results:
        lines = []
        for r in results:
            w_name = AGENT_NAMES.get(r["worker"], r["worker"])
            snippet = r["output"][:1500]
            lines.append(f"── {w_name} ──\nTâche : {r['task'][:100]}\nRésultat :\n{snippet}")
        results_text = "\n\n".join(lines)

    system = BRAIN_SYSTEM if not results else BRAIN_SYSTEM_WITH_RESULTS
    if project_context:
        system += f"\n\nContexte projet :\n{project_context[:1500]}"

    user_content = f"Tâche originale : {task}"
    if results_text:
        user_content += f"\n\nRésultats des workers :\n{results_text}"

    messages = [
        {"role": "system", "content": system},
        *conv_history[-4:],
        {"role": "user", "content": user_content},
    ]

    raw = None

    # Brain principal : Qwen (gratuit)
    if brain_mode in ("qwen", "auto"):
        raw = await call_nvidia("qwen", messages, max_tokens=3000, temperature=0.1)

    # Fallback : Claude Sonnet
    if not raw or brain_mode == "claude":
        print(f" {MG}[brain→Claude]{R}", end="", flush=True)
        full_prompt = f"{system}\n\n{user_content}"
        raw = call_claude_cli(full_prompt, model="sonnet")

    # Dernier recours : GLM (simple, moins intelligent mais disponible)
    if not raw:
        print(f" {DIM}[brain→GLM fallback]{R}", end="", flush=True)
        raw = await call_nvidia("glm", messages, max_tokens=2000, temperature=0.2)

    if not raw:
        return {"action": "final", "response": "Impossible d'obtenir une réponse du Brain."}

    return parse_brain_output(raw)

# ─── Workers — exécutent sans réfléchir au flux ───────────────────────────────

WORKER_SYSTEMS = {
    "kimi": (
        "Tu es un expert développeur logiciel. "
        "Écris du code production-ready, propre, sans TODO ni placeholder. "
        "Pour plusieurs fichiers : // === FICHIER: chemin/vers/fichier.ext ===\n"
        "Retourne UNIQUEMENT le code demandé, pas d'explication superflue."
    ),
    "nemotron": (
        "Tu es un expert en review de code et debugging. "
        "Analyse le code fourni : bugs, sécurité, performance, style. "
        "Format de sortie :\n"
        "## Problèmes critiques\n## Problèmes majeurs\n## Suggestions\n## Verdict (APPROVED / CHANGES_NEEDED)\n"
        "Pour chaque problème : ligne, description, correction proposée."
    ),
    "gpt_oss": (
        "Tu es un expert en documentation et synthèse technique. "
        "Produis une réponse claire, structurée, complète. "
        "Conserve tout le code existant dans ta synthèse."
    ),
}

WORKER_FALLBACKS = {
    "kimi":     ["qwen", "glm"],
    "nemotron": ["qwen", "glm"],
    "gpt_oss":  ["qwen", "glm"],
}

async def call_worker(worker: str, task: str,
                      project_context: str, previous_output: str = "") -> str:
    """
    Appelle un worker spécialisé. Retourne son output brut.
    Ne prend aucune décision de routage.
    """
    system = WORKER_SYSTEMS.get(worker, WORKER_SYSTEMS["gpt_oss"])
    if project_context:
        system += f"\n\nContexte projet :\n{project_context[:1500]}"

    user_content = task
    if previous_output:
        user_content = f"Travail précédent à améliorer :\n{previous_output[:2000]}\n\nNouvelle tâche : {task}"

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]

    result = await call_nvidia(worker, messages, max_tokens=5000, temperature=0.08)
    if result:
        return result

    # Fallback chain
    for fallback in WORKER_FALLBACKS.get(worker, ["qwen"]):
        print(f" {YL}[fallback→{fallback}]{R}", end="", flush=True)
        result = await call_nvidia(fallback, messages, max_tokens=5000, temperature=0.15)
        if result:
            return result

    return "Worker n'a pas pu produire de résultat."

# ─── Boucle Brain + Workers ───────────────────────────────────────────────────

async def orchestrate(task: str, project_context: str,
                      conv_history: list, brain_mode: str) -> tuple[str, str]:
    """
    Boucle principale :
      Brain décide → Worker exécute → Brain évalue → ... → Brain: FINAL
    Retourne (réponse_finale, brain_utilisé).
    """

    results: list[dict] = []   # historique des passes worker
    brain_used = "qwen" if brain_mode != "claude" else "claude"

    for iteration in range(MAX_ITERATIONS):

        # ── Brain décide ─────────────────────────────────────────────────────
        arrow = "→" if iteration == 0 else "↻"
        b_name = "Brain/Claude" if brain_mode == "claude" else "Brain/Qwen"
        print(f"  {DIM}{arrow} {b_name}{R}", end="", flush=True)

        decision = await call_brain(task, results, project_context,
                                    conv_history, brain_mode)

        # ── Réponse finale ───────────────────────────────────────────────────
        if decision["action"] == "final":
            print(f" {GR}→ réponse finale{R}")
            return decision["response"], brain_used

        # ── Délégation à un worker ───────────────────────────────────────────
        worker      = decision["to"]
        worker_task = decision["task"]
        reason      = decision.get("reason", "")

        w_name = AGENT_NAMES.get(worker, worker)
        print(f" {GR}→ {w_name}{R}")
        if reason:
            print(f"    {DIM}raison : {reason}{R}")

        print(f"  {AGENT_COLORS.get(worker, '')}  [{w_name}]{R}", end=" ", flush=True)

        # Contexte du dernier output du même worker (pour les itérations)
        last_same_worker = next(
            (r["output"] for r in reversed(results) if r["worker"] == worker), ""
        )

        worker_output = await call_worker(
            worker, worker_task, project_context, last_same_worker
        )
        print(f"{GR}✓{R}")

        results.append({
            "worker": worker,
            "task":   worker_task,
            "output": worker_output,
        })

        await asyncio.sleep(1.0)   # respiration entre les appels

    # Max itérations atteint
    print(f"\n  {YL}[max itérations — réponse du dernier worker]{R}")
    return results[-1]["output"] if results else "Pas de réponse.", brain_used

# ─── Routage initial rapide ───────────────────────────────────────────────────

def needs_orchestration(message: str) -> bool:
    """
    Faux pour les messages très simples (question courte, explication) :
    le Brain répond directement sans passer par les workers.
    """
    m = message.lower().strip()
    # Trop court pour être une vraie tâche de dev
    if len(m) < 40 and not re.search(r"\b(implémente?|écris?|génère?|crée?|refactor|bug|test)\b", m):
        return False
    return True

# ─── Contexte projet ──────────────────────────────────────────────────────────

def load_context(path: Path) -> str:
    f = path / ".nexus" / "context.md"
    return f.read_text(encoding="utf-8") if f.exists() else ""

def save_context(path: Path, update: str):
    d = path / ".nexus"
    d.mkdir(exist_ok=True)
    f = d / "context.md"
    existing = f.read_text(encoding="utf-8") if f.exists() else ""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    f.write_text(existing[-3000:] + f"\n\n## [{ts}]\n{update}", encoding="utf-8")

def list_files(path: Path) -> list[str]:
    ext  = {".py",".ts",".tsx",".js",".jsx",".rs",".go",
            ".java",".cs",".cpp",".c",".h",".json",".yaml",".yml",".md"}
    skip = {"node_modules",".git","__pycache__",".venv","dist","build",".nexus"}
    files = []
    try:
        for p in path.rglob("*"):
            if any(s in p.parts for s in skip):
                continue
            if p.is_file() and p.suffix in ext:
                files.append(str(p.relative_to(path)))
    except PermissionError:
        pass
    return sorted(files)[:60]

# ─── Interface conversationnelle ──────────────────────────────────────────────

async def chat_loop(project_path: Path, write_files: bool, brain_mode: str):
    conv_history: list[dict] = []
    last_brain = brain_mode if brain_mode == "claude" else "qwen"

    brain_display = f"{MG}Claude Sonnet{R}" if brain_mode == "claude" else f"{BL}Qwen 3.5 397B{R} (fallback Claude)"
    print()
    print(f"{B}{CY}╔════════════════════════════════════════════════════╗{R}")
    print(f"{B}{CY}║  NEXUS Chat v3 — Brain + Workers                  ║{R}")
    print(f"{B}{CY}╚════════════════════════════════════════════════════╝{R}")
    print(f"  Brain    : {brain_display}")
    print(f"  Workers  : {GR}Kimi{R} · {YL}Nemotron{R} · {CY}GPT-OSS{R}  (gratuits, NVIDIA NIM)")
    print(f"  Projet   : {B}{project_path}{R}")
    print(f"  Écriture : {(GR+'OUI') if write_files else (YL+'NON (--write pour activer)')}{R}")
    print(f"  {DIM}Le Brain décide seul de l'ordre et des délégations.{R}")
    print(f"  {DIM}/help pour les commandes{R}\n")

    project_context = load_context(project_path)

    while True:
        try:
            user_input = input(f"{B}{CY}vous >{R} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}Au revoir.{R}")
            break

        if not user_input:
            continue

        # ── Commandes ────────────────────────────────────────────────────────
        if user_input.startswith("/"):
            cmd = user_input.split()[0].lower()
            if cmd == "/quit":
                print(f"{DIM}Au revoir.{R}")
                break
            elif cmd == "/help":
                print(f"""
  {B}Commandes :{R}
  {CY}/quit{R}    — quitter
  {CY}/context{R} — contexte projet mémorisé
  {CY}/files{R}   — fichiers du projet
  {CY}/clear{R}   — effacer l'historique de conversation
  {CY}/write{R}   — activer/désactiver l'écriture de fichiers
  {CY}/brain{R}   — voir quel Brain est actif
""")
            elif cmd == "/context":
                ctx = load_context(project_path)
                print(f"\n{DIM}{ctx[:2000] or 'Aucun contexte.'}{R}\n")
            elif cmd == "/files":
                files = list_files(project_path)
                if files:
                    print(f"\n  {B}{len(files)} fichiers :{R}")
                    for f in files[:30]:
                        print(f"    {DIM}{f}{R}")
                    if len(files) > 30:
                        print(f"    {DIM}... +{len(files)-30}{R}")
                else:
                    print(f"  {YL}Aucun fichier de code trouvé.{R}")
                print()
            elif cmd == "/clear":
                conv_history.clear()
                print(f"  {GR}Historique effacé.{R}")
            elif cmd == "/write":
                write_files = not write_files
                print(f"  Écriture : {(GR+'activée') if write_files else (YL+'désactivée')}{R}")
            elif cmd == "/brain":
                print(f"  Brain actif : {brain_display}")
            else:
                print(f"  {YL}Commande inconnue. /help{R}")
            continue

        # ── Message normal ───────────────────────────────────────────────────
        conv_history.append({"role": "user", "content": user_input})
        print()

        if needs_orchestration(user_input):
            # Boucle complète Brain + Workers
            response, last_brain = await orchestrate(
                user_input, project_context, conv_history, brain_mode
            )
        else:
            # Réponse directe du Brain (questions simples)
            b_name = "Brain/Claude" if brain_mode == "claude" else "Brain/Qwen"
            print(f"  {DIM}→ {b_name} (direct){R}", end=" ", flush=True)
            decision = await call_brain(user_input, [], project_context,
                                        conv_history, brain_mode)
            response = decision.get("response", "")
            last_brain = "claude" if brain_mode == "claude" else "qwen"
            print(f"{GR}✓{R}")

        # ── Affichage ────────────────────────────────────────────────────────
        if response:
            conv_history.append({"role": "assistant", "content": response})
            print(f"\n{label(last_brain)}\n{response}\n")

            # Compression de l'historique si trop long
            if len(conv_history) > 20:
                conv_history = conv_history[-8:]

            # Sauvegarde contexte projet
            if len(conv_history) % 8 == 0 and project_path:
                save_context(project_path,
                             f"Q: {user_input[:100]}\nR: {response[:300]}")
        else:
            print(f"\n  {RE}Pas de réponse.{R}\n")

# ─── Entrée ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="NEXUS Chat v3 — Brain + Workers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python nexus_chat.py
  python nexus_chat.py --project C:/mon-projet
  python nexus_chat.py --project C:/mon-projet --write
  python nexus_chat.py --brain claude   (Claude comme Brain)
        """
    )
    parser.add_argument("--project", "-p", default=".", help="Chemin du projet")
    parser.add_argument("--write",   "-w", action="store_true", help="Écrire les fichiers générés")
    parser.add_argument("--brain",   "-b", default="auto",
                        choices=["auto", "qwen", "claude"],
                        help="Brain principal : auto=Qwen+fallback, claude=Claude seul")
    args = parser.parse_args()

    if not API_KEY:
        print("ERREUR : NVIDIA_API_KEY manquante — vérifie AGENTIQUE/.env")
        sys.exit(1)

    asyncio.run(chat_loop(Path(args.project).resolve(), args.write, args.brain))

if __name__ == "__main__":
    main()
