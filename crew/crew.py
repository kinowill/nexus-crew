#!/usr/bin/env python3
"""
NEXUS Crew v1 — Multi-agent system with real tool access
=========================================================

4 agents (5 en mode --deep) tournant sur NVIDIA NIM gratuits, chacun avec
un vrai accès fichiers + shell via les tools CrewAI et LiteLLM.

Roles :
  Researcher (Qwen 3.5 397B)     — lit, explore, produit une carte mentale
  Architect  (DeepSeek V3.2)     — planifie l'intervention
  Coder      (Qwen 3 Coder 480B) — implémente
  Critic     (Kimi K2 Thinking)  — review, bugs, sécurité
  Scanner    (Llama 3.3 70B)     — wide scan rapide (mode --deep uniquement)

Usage :
  python crew.py "ta tâche" --project C:/chemin/du/projet
  python crew.py "refactore l'auth" --project C:/mon-projet --write
  python crew.py "audit complet" --project C:/gros-projet --deep --write
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# ─── Chargement .env ──────────────────────────────────────────────────────────

ENV_FILE = Path(__file__).parent.parent / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

API_KEY     = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"

if not API_KEY:
    print("ERREUR : NVIDIA_API_KEY manquante dans AGENTIQUE/.env")
    sys.exit(1)

# LiteLLM lit ces variables pour le provider openai-compatible
os.environ["OPENAI_API_KEY"]  = API_KEY
os.environ["OPENAI_API_BASE"] = NVIDIA_BASE

# ─── Imports CrewAI (après config env) ────────────────────────────────────────

from crewai import Agent, Task, Crew, LLM, BaseLLM, Process
from crewai.tools import tool
from pydantic import ConfigDict

# ─── Cache LiteLLM disk (scope = session courante uniquement) ─────────────────
# Le cache est vidé à chaque démarrage pour éviter des réponses obsolètes
# quand le code du projet a changé entre deux runs. Pendant la session, il
# accélère les retries, les fallbacks et les questions reposées par délégation.
try:
    import litellm
    import shutil
    from litellm.caching.caching import Cache
    CACHE_DIR = Path(__file__).parent.parent / ".crew_cache"
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR, ignore_errors=True)
    CACHE_DIR.mkdir(exist_ok=True)
    litellm.cache = Cache(type="disk", disk_cache_dir=str(CACHE_DIR))
    litellm.enable_cache()
    print(f"  [cache LiteLLM actif — session uniquement : {CACHE_DIR}]")
except Exception as _e:
    print(f"  [cache LiteLLM désactivé : {_e}]")

# ─── Config embedder NVIDIA NIM (pour la mémoire CrewAI) ──────────────────────
# Modèle retenu : nvidia/nv-embed-v1 (symétrique, OpenAI-compat sans champ extra).
# Les modèles *nv-embedqa-* exigent input_type="query"/"passage", non-standard
# OpenAI — CrewAI/chromadb ne l'envoient pas, donc ils crashent. Vérifié via
# curl direct sur /v1/embeddings avant de committer.
NVIDIA_EMBEDDER = {
    "provider": "openai",
    "config": {
        "api_key": API_KEY,
        "api_base": NVIDIA_BASE,
        "model": "nvidia/nv-embed-v1",
    },
}

# ─── Config des modèles + fallbacks ───────────────────────────────────────────
# Clé = rôle, valeur = [primaire, fallback_1, fallback_2]
# LiteLLM accepte "openai/<model-id>" pour router vers notre base openai-compatible.

MODEL_CHAINS = {
    "researcher": [
        "openai/qwen/qwen3.5-397b-a17b",
        "openai/deepseek-ai/deepseek-v3.2",
        "openai/meta/llama-3.3-70b-instruct",
    ],
    "architect": [
        "openai/deepseek-ai/deepseek-v3.2",
        "openai/qwen/qwen3.5-397b-a17b",
        "openai/meta/llama-3.3-70b-instruct",
    ],
    "coder": [
        "openai/qwen/qwen3-coder-480b-a35b-instruct",
        "openai/mistralai/devstral-2-123b-instruct-2512",
        "openai/moonshotai/kimi-k2-instruct-0905",
    ],
    "critic": [
        "openai/moonshotai/kimi-k2-thinking",
        "openai/qwen/qwen3-next-80b-a3b-thinking",
        "openai/nvidia/llama-3.3-nemotron-super-49b-v1.5",
    ],
    "scanner": [
        "openai/meta/llama-3.3-70b-instruct",
        "openai/openai/gpt-oss-120b",
        "openai/google/gemma-3-27b-it",
    ],
}


class FallbackLLM(BaseLLM):
    """LLM CrewAI qui cascade sur une liste de modèles en cas d'erreur.

    Hérite de BaseLLM (pydantic). Les LLM internes sont stockés hors pydantic via
    object.__setattr__ pour éviter les conflits de validation.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    def __init__(self, chain: list[str], temperature: float = 0.1):
        # BaseLLM attend un "model" — on lui donne le premier de la chaîne
        super().__init__(model=chain[0], temperature=temperature)
        llms = [
            LLM(model=m, api_key=API_KEY, base_url=NVIDIA_BASE, temperature=temperature)
            for m in chain
        ]
        object.__setattr__(self, "_chain", chain)
        object.__setattr__(self, "_llms", llms)

    def call(self, messages, tools=None, callbacks=None, available_functions=None,
             from_task=None, from_agent=None, response_model=None):
        last_err = None
        for idx, llm in enumerate(self._llms):
            try:
                out = llm.call(
                    messages=messages,
                    tools=tools,
                    callbacks=callbacks,
                    available_functions=available_functions,
                    from_task=from_task,
                    from_agent=from_agent,
                    response_model=response_model,
                )
                if idx > 0:
                    print(f"  [fallback actif : {self._chain[idx]}]")
                return out
            except Exception as e:
                last_err = e
                print(f"  [modèle {self._chain[idx]} a échoué : {str(e)[:100]}]")
                continue
        raise RuntimeError(f"Tous les fallbacks ont échoué pour {self._chain[0]} : {last_err}")

    def supports_function_calling(self) -> bool:
        return True

    def supports_stop_words(self) -> bool:
        return True

    def get_context_window_size(self) -> int:
        return 120000


def make_llm(role: str, temperature: float = 0.1) -> FallbackLLM:
    return FallbackLLM(MODEL_CHAINS[role], temperature=temperature)


# ─── Tools custom (exposés aux agents) ────────────────────────────────────────

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build", ".nexus", ".crew"}


def _project() -> Path:
    return Path(os.environ["CREW_PROJECT"])


def _allowed_roots() -> list[Path]:
    """Projet principal + dossiers supplémentaires autorisés via --allow."""
    roots = [_project()]
    extra = os.environ.get("CREW_ALLOWED_ROOTS", "")
    if extra:
        roots += [Path(r) for r in extra.split(os.pathsep) if r]
    return roots


def _safe_path(rel: str) -> Path:
    """Résout un chemin et vérifie qu'il est dans une racine autorisée.

    - Chemin relatif → résolu depuis le projet principal
    - Chemin absolu  → accepté s'il est dans une racine autorisée (--allow)
    """
    p = Path(rel)
    full = p.resolve() if p.is_absolute() else (_project() / p).resolve()
    for root in _allowed_roots():
        root_r = root.resolve()
        if full == root_r or root_r in full.parents:
            return full
    raise ValueError(
        f"Chemin hors des racines autorisées : {rel}. "
        f"Utilise --allow pour ajouter un dossier."
    )


@tool("read_file")
def read_file_tool(path: str, offset: int = 0, limit: int = 40000) -> str:
    """Lit un fichier. offset = position de départ en caractères, limit = taille max lue.
    Pour les gros fichiers, appeler plusieurs fois avec des offsets différents."""
    try:
        p = _safe_path(path)
        if not p.is_file():
            return f"Pas un fichier : {path}"
        content = p.read_text(encoding="utf-8", errors="replace")
        total = len(content)
        chunk = content[offset:offset + limit]
        header = f"[fichier {path} — taille totale {total} chars — lu {offset}..{offset+len(chunk)}]\n"
        if offset + len(chunk) < total:
            header += f"[reste {total - offset - len(chunk)} chars — rappelle read_file avec offset={offset+len(chunk)}]\n"
        return header + chunk
    except Exception as e:
        return f"Erreur lecture {path} : {e}"


@tool("write_file")
def write_file_tool(path: str, content: str) -> str:
    """Écrit du contenu dans un fichier du projet (crée les dossiers parents si besoin). Respecte le flag --write."""
    try:
        p = _safe_path(path)
        if not os.environ.get("CREW_WRITE_ENABLED"):
            return f"[DRY-RUN] Écrirait {len(content)} chars dans {path} (lance avec --write pour activer)"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"✓ Écrit {len(content)} chars dans {path}"
    except Exception as e:
        return f"Erreur écriture {path} : {e}"


@tool("list_files")
def list_files_tool(directory: str = ".") -> str:
    """Liste les fichiers d'un dossier (récursif, filtrage efficace des SKIP_DIRS, max 300 entrées)."""
    try:
        base = _safe_path(directory)
        if not base.is_dir():
            return f"Pas un dossier : {directory}"
        items = []

        def walk(d: Path):
            try:
                entries = sorted(d.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            except PermissionError:
                return
            for p in entries:
                if len(items) >= 300:
                    return
                if p.name in SKIP_DIRS:
                    continue
                rel = p.relative_to(_project()) if _project() in p.parents or p == _project() else p
                if p.is_dir():
                    items.append(f"DIR  {rel}")
                    walk(p)
                else:
                    items.append(f"FILE {rel}")

        walk(base)
        if len(items) >= 300:
            items.append("... (tronqué à 300 — utilise grep pour cibler)")
        return "\n".join(items) or "(dossier vide)"
    except Exception as e:
        return f"Erreur list {directory} : {e}"


@tool("grep")
def grep_tool(pattern: str, glob: str = "*") -> str:
    """Cherche un pattern regex dans les fichiers du projet. glob optionnel (ex: *.py)."""
    try:
        cmd = ["grep", "-rn", "-I", "--include", glob]
        for skip in SKIP_DIRS:
            cmd.extend(["--exclude-dir", skip])
        cmd.extend([pattern, "."])
        result = subprocess.run(
            cmd, cwd=str(_project()), capture_output=True, text=True, timeout=30
        )
        out = result.stdout[:8000]
        return out or f"(aucun match pour '{pattern}')"
    except Exception as e:
        return f"Erreur grep : {e}"


@tool("run_shell")
def run_shell_tool(command: str) -> str:
    """Exécute une commande shell dans le projet (timeout 120s). Respecte le flag --write pour les commandes destructives."""
    cl = command.lower()
    destructive = any(w in cl for w in [
        "rm ", "rm -", "rmdir", " rd ", "del ", "erase ", "format ", "drop ",
        "remove-item", "shutdown", "mkfs", " dd ", ":(){ :|:& };:",
    ])
    if destructive and not os.environ.get("CREW_WRITE_ENABLED"):
        return f"[DRY-RUN] Commande potentiellement destructive bloquée : {command}"
    try:
        result = subprocess.run(
            command, shell=True, cwd=str(_project()),
            capture_output=True, text=True, timeout=120
        )
        out = (result.stdout or "")[-3000:]
        err = (result.stderr or "")[-1500:]
        return f"exit={result.returncode}\nstdout:\n{out}\nstderr:\n{err}"
    except subprocess.TimeoutExpired:
        return "Timeout (>120s)"
    except Exception as e:
        return f"Erreur shell : {e}"


READ_TOOLS = [read_file_tool, list_files_tool, grep_tool]
FULL_TOOLS = READ_TOOLS + [write_file_tool, run_shell_tool]


# ─── Agents ───────────────────────────────────────────────────────────────────

def make_researcher() -> Agent:
    return Agent(
        role="Researcher",
        goal="Construire une carte mentale complète et exploitable du projet : structure, dépendances, fichiers clés, état courant",
        backstory=(
            "Tu es un expert en lecture rapide de bases de code complexes. Tu raisonnes pendant que tu lis. "
            "Tu commences par la structure globale, puis tu plonges dans les fichiers clés (entry points, config, core). "
            "Tu produis un rapport structuré qui permet à un architect de planifier sans relire le projet."
        ),
        llm=make_llm("researcher"),
        tools=READ_TOOLS,
        verbose=True,
        allow_delegation=True,
        max_iter=8,
    )


def make_architect() -> Agent:
    return Agent(
        role="Architect",
        goal="Produire un plan d'intervention précis et séquencé à partir de la carte du Researcher et de la tâche demandée",
        backstory=(
            "Tu es un architecte logiciel senior. Tu reçois une carte projet et un objectif. "
            "Tu produis un plan numéroté étape par étape, avec les fichiers exacts à toucher, "
            "l'ordre des opérations, et les risques à vérifier. Tu respectes les conventions existantes du projet. "
            "Tu ne codes pas : tu planifies pour que le Coder exécute."
        ),
        llm=make_llm("architect"),
        tools=READ_TOOLS,
        verbose=True,
        allow_delegation=True,
        max_iter=6,
    )


def make_coder() -> Agent:
    return Agent(
        role="Coder",
        goal="Exécuter le plan de l'Architect avec précision, en écrivant du code production-ready",
        backstory=(
            "Tu es un développeur senior. Tu reçois un plan et tu l'exécutes fidèlement. "
            "Tu lis les fichiers avant de les modifier. Tu utilises grep pour trouver les références. "
            "Tu écris du code propre, sans TODO ni placeholder, qui respecte les conventions du projet. "
            "Tu utilises write_file pour persister les changements. "
            "COLLABORATION : si tu as un doute sur le projet, tu peux interroger le Researcher. "
            "Si le plan est ambigu, tu peux demander clarification à l'Architect. Ne code jamais à l'aveugle."
        ),
        llm=make_llm("coder"),
        tools=FULL_TOOLS,
        verbose=True,
        allow_delegation=True,
        max_iter=15,
    )


def make_critic() -> Agent:
    return Agent(
        role="Critic",
        goal="Traquer activement bugs, failles de sécurité, edge cases et régressions dans le travail du Coder",
        backstory=(
            "Tu es un reviewer méticuleux. Tu cherches des problèmes — tu ne te contentes pas d'approuver. "
            "Tu relis le code contre le plan, tu lances les tests quand c'est pertinent, "
            "tu vérifies la sécurité, tu cherches les edge cases que le Coder a pu rater. "
            "Tu finis par APPROVED ou CHANGES_NEEDED avec des corrections précises. "
            "COLLABORATION : tu peux renvoyer une question au Coder pour qu'il corrige avant validation, "
            "ou demander au Researcher de vérifier un point du projet si tu as un doute."
        ),
        llm=make_llm("critic"),
        tools=FULL_TOOLS,
        verbose=True,
        allow_delegation=True,
        max_iter=8,
    )


def make_scanner() -> Agent:
    return Agent(
        role="Scanner",
        goal="Faire un inventaire structurel rapide et large du projet",
        backstory=(
            "Tu es un scanner rapide. Tu produis un inventaire plat du projet : "
            "arborescence, fichiers principaux, stack technique visible. Tu es rapide, pas profond."
        ),
        llm=make_llm("scanner"),
        tools=READ_TOOLS,
        verbose=True,
        allow_delegation=True,
        max_iter=5,
    )


# ─── Construction du crew ─────────────────────────────────────────────────────

def build_crew(task_text: str, project_path: Path, deep: bool) -> Crew:
    researcher = make_researcher()
    architect  = make_architect()
    coder      = make_coder()
    critic     = make_critic()

    research_task = Task(
        description=(
            f"Analyse le projet à {project_path}.\n"
            f"Tâche demandée par l'utilisateur : {task_text}\n\n"
            "Produis une carte structurée :\n"
            "1. Structure projet (arborescence des fichiers clés, modules)\n"
            "2. Stack technique et dépendances détectées\n"
            "3. Fichiers particulièrement pertinents pour la tâche\n"
            "4. Risques, contraintes ou conventions à respecter\n"
            "Utilise list_files, read_file, grep. Sois précis sur les chemins."
        ),
        expected_output="Un rapport markdown avec la carte du projet et les éléments pertinents pour la tâche",
        agent=researcher,
    )

    plan_task = Task(
        description=(
            f"À partir de la carte produite par le Researcher et de la tâche : {task_text}\n\n"
            "Produis un plan d'exécution étape par étape :\n"
            "- Numérote chaque étape\n"
            "- Indique les fichiers exacts à toucher\n"
            "- Précise l'ordre et les dépendances\n"
            "- Liste les points à vérifier par le Critic"
        ),
        expected_output="Un plan numéroté et actionnable pour le Coder",
        agent=architect,
        context=[research_task],
    )

    code_task = Task(
        description=(
            "Exécute fidèlement le plan de l'Architect.\n"
            "- Lis les fichiers avant de les modifier (read_file)\n"
            "- Utilise grep pour trouver les références impactées\n"
            "- Utilise write_file pour persister chaque changement\n"
            "- Ne fais AUCUN changement hors du plan\n"
            "- Retourne un résumé précis des fichiers touchés et ce qui a changé"
        ),
        expected_output="Un résumé structuré des changements, avec la liste des fichiers modifiés",
        agent=coder,
        context=[plan_task],
    )

    review_task = Task(
        description=(
            "Review le travail du Coder :\n"
            "- Confronte les changements au plan de l'Architect\n"
            "- Cherche bugs, failles de sécurité, edge cases\n"
            "- Vérifie les régressions potentielles (grep sur les symboles modifiés)\n"
            "- Lance les tests si tu en trouves (run_shell)\n"
            "Finis par APPROVED si tout est bon, ou CHANGES_NEEDED avec les corrections à apporter"
        ),
        expected_output="APPROVED ou CHANGES_NEEDED avec feedback détaillé",
        agent=critic,
        context=[plan_task, code_task],
    )

    rework_task = Task(
        description=(
            "Lis le verdict du Critic.\n"
            "- Si le Critic a conclu par APPROVED : réponds simplement 'APPROVED — aucun changement nécessaire'.\n"
            "- Si le Critic a conclu par CHANGES_NEEDED : applique chaque correction demandée "
            "  en utilisant read_file + write_file. Ne touche QUE ce que le Critic demande. "
            "  Liste les fichiers retouchés.\n"
            "Tu peux interroger le Critic si une correction est ambiguë."
        ),
        expected_output="Soit 'APPROVED — aucun changement', soit la liste des corrections appliquées",
        agent=coder,
        context=[plan_task, code_task, review_task],
    )

    final_task = Task(
        description=(
            f"Synthèse finale pour l'utilisateur.\n"
            f"Tâche originale : {task_text}\n\n"
            "Produis un rapport clair et concis :\n"
            "- Ce qui a été fait\n"
            "- Ce qui a été reviewé + corrections éventuelles appliquées\n"
            "- État final (succès / corrections demandées / bloqué)\n"
            "- Fichiers touchés avec leurs chemins\n"
            "- Points d'attention restants pour l'utilisateur"
        ),
        expected_output="Un rapport final markdown lisible par un humain non-développeur",
        agent=architect,
        context=[research_task, plan_task, code_task, review_task, rework_task],
    )

    tasks  = [research_task, plan_task, code_task, review_task, rework_task, final_task]
    agents = [researcher, architect, coder, critic]

    if deep:
        scanner = make_scanner()
        scan_task = Task(
            description=(
                f"Scan rapide et large du projet à {project_path}.\n"
                "Produis un inventaire plat : arborescence, fichiers principaux, stack visible. "
                "Rapide, pas profond. Le Researcher plongera ensuite."
            ),
            expected_output="Un inventaire structurel du projet",
            agent=scanner,
        )
        tasks = [scan_task] + tasks
        research_task.context = [scan_task]
        agents = [scanner] + agents

    return Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
        memory=True,
        embedder=NVIDIA_EMBEDDER,
        cache=True,
        planning=True,
        planning_llm=make_llm("architect"),
    )


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    # Force UTF-8 sur stdout/stderr (Windows cp1252 ne supporte pas les caractères unicode)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="NEXUS Crew — multi-agent avec accès fichiers réel via NVIDIA NIM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemples :\n"
            '  python crew.py "fais un point sur le projet" --project C:/mon-projet\n'
            '  python crew.py "refactore l\'auth" --project C:/mon-projet --write\n'
            '  python crew.py "audit complet" --project C:/gros-projet --deep --write\n'
        ),
    )
    parser.add_argument("task", help="La tâche à accomplir")
    parser.add_argument("--project", "-p", required=True, help="Chemin du projet")
    parser.add_argument("--write", "-w", action="store_true",
                        help="Active l'écriture réelle de fichiers (sinon dry-run)")
    parser.add_argument("--deep", "-d", action="store_true",
                        help="Active le mode Scanner + Researcher pour les gros projets")
    parser.add_argument("--allow", "-a", action="append", default=[],
                        help="Dossier supplémentaire accessible (répétable). "
                             "Ex : --allow C:/autres/libs --allow D:/data")
    args = parser.parse_args()

    project_path = Path(args.project).resolve()
    if not project_path.is_dir():
        print(f"ERREUR : {project_path} n'est pas un dossier.")
        sys.exit(1)

    os.environ["CREW_PROJECT"] = str(project_path)
    if args.write:
        os.environ["CREW_WRITE_ENABLED"] = "1"

    # Racines supplémentaires autorisées (--allow)
    extra_roots = []
    for r in args.allow:
        rp = Path(r).resolve()
        if not rp.is_dir():
            print(f"ATTENTION : --allow {r} n'est pas un dossier, ignoré.")
            continue
        extra_roots.append(str(rp))
    if extra_roots:
        os.environ["CREW_ALLOWED_ROOTS"] = os.pathsep.join(extra_roots)
        print(f"  Accès : {project_path} + {len(extra_roots)} dossier(s) supplémentaire(s)")

    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║  NEXUS Crew v1 — Multi-agent avec accès fichiers réel     ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"  Projet  : {project_path}")
    print(f"  Mode    : {'DEEP (5 agents)' if args.deep else 'NORMAL (4 agents)'}")
    print(f"  Écriture: {'ACTIVÉE' if args.write else 'DRY-RUN (utiliser --write pour activer)'}")
    print(f"  Tâche   : {args.task}")
    print()

    crew = build_crew(args.task, project_path, deep=args.deep)
    result = crew.kickoff()

    print()
    print("=" * 60)
    print("RÉSULTAT FINAL")
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    main()
