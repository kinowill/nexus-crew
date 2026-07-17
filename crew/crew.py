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

Permissions (Phase 0) :
  - read         : toujours ON, borne par _safe_path() au projet + --allow
  - write_file   : OFF par defaut, ON avec --write (Coder uniquement)
  - run_shell    : OFF par defaut, ON avec --allow-shell (Coder uniquement).
                   shell=False, allowlist stricte de binaires, pas de chainage.
                   Critic est toujours en lecture seule.
"""

import argparse
import json
import os
import subprocess
import sys
import time
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

# Tracing CrewAI = cloud (envoie prompts + outputs vers leur plateforme).
# Force OFF pour éviter tout leak de code/secrets projet.
os.environ["CREWAI_TRACING_ENABLED"] = "false"
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"

# ─── Imports CrewAI (après config env) ────────────────────────────────────────

from crewai import Agent, Task, Crew, LLM, BaseLLM, Process  # noqa: E402
from crewai.tools import tool  # noqa: E402
from pydantic import ConfigDict  # noqa: E402

from contracts import ContractTracker  # noqa: E402

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
        "openai/openai/gpt-oss-120b",
        "openai/nvidia/llama-3.3-nemotron-super-49b-v1.5",
    ],
    "architect": [
        # 2026-07-09 : DeepSeek V3.2 et Llama 3.3 70B retires de cette chaine.
        # DeepSeek retourne 404/timeout cote NIM; Llama 70B casse en runtime
        # multi-outils (single tool-calls only). GPT-OSS et Nemotron valides
        # en appel direct avec plusieurs outils disponibles.
        "openai/qwen/qwen3.5-397b-a17b",
        "openai/openai/gpt-oss-120b",
        "openai/nvidia/llama-3.3-nemotron-super-49b-v1.5",
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


def _strip_strict_tools(tools: list) -> list:
    """Normalise les schemas d'outils CrewAI pour compatibilité NVIDIA NIM.

    CrewAI génère des schemas avec strict:true, additionalProperties:false,
    et TOUS les params dans required (même ceux avec default Python).
    Certains modèles NIM (Qwen Coder, Kimi K2) basculent en XML Hermes cassé
    quand required contient des params à default.

    Fix : retire strict + additionalProperties, et sort du required les params
    qui ont un "default" dans le schema. Confirmé par test_crewai_schema.py
    (2026-04-10, Phase 1 §0.c) : required=["path"] → NATIVE, required=all → MALFORMED.
    """
    import copy
    cleaned = copy.deepcopy(tools)
    for t in cleaned:
        if not isinstance(t, dict):
            continue
        func = t.get("function", {})
        func.pop("strict", None)
        params = func.get("parameters", {})
        params.pop("additionalProperties", None)
        # Retire du required les params qui ont un default dans le schema
        props = params.get("properties", {})
        required = params.get("required", [])
        if required and props:
            truly_required = [r for r in required if "default" not in props.get(r, {})]
            params["required"] = truly_required
    return cleaned


# Phase 1 §3 — Resilience NIM : backoff 429 + retry sur sortie XML Hermes cassee.
# Mesure contre : rate limit NIM free tier (~40 req/min, Coder 480B cap plus tot
# en bursts) et variance intrinseque Kimi K2 Thinking (~10% de reponses texte
# sans tool_calls quand des tools sont fournis). Voir journal 2026-04-19.
RATE_LIMIT_BACKOFFS = [1.0, 2.0, 4.0]  # attentes apres 429 avant fallback chain
LLM_TIMEOUT_SECONDS = 90  # defaut; surcharge possible via NEXUS_LLM_TIMEOUT_SECONDS


def _resolve_llm_timeout_seconds() -> int:
    """Retourne le timeout d'un appel modele, configurable par environnement."""
    raw = os.environ.get("NEXUS_LLM_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return LLM_TIMEOUT_SECONDS
    try:
        timeout = int(raw)
    except ValueError:
        return LLM_TIMEOUT_SECONDS
    return max(10, timeout)

# Phase 1 §3bis (journal 2026-04-20) — Variance "0 tools au tour 1" : un modele
# peut renvoyer une intention en texte nu sans emettre de tool_call alors que
# des outils sont disponibles. Symptome observe Researcher Qwen 3.5 397B :
# 132 chars du type "Je vais lire le README pour comprendre le projet...".
# On flagge les sorties courtes qui contiennent un marqueur d'intention typique.
MALFORMED_SHORT_TEXT_MAX = 300  # seuil de "reponse courte"
_INTENTION_PATTERNS = (
    # FR
    "je vais", "je dois", "d'abord", "pour repondre", "pour répondre",
    "je commence", "commencons", "commençons",
    # EN (CrewAI prompts sont en anglais par defaut)
    "let me ", "i'll ", "i will ", "i need to ", "i should ",
    "first, i", "first i", "to answer", "to solve",
    # ReAct markers CrewAI : "Thought:" sans action reelle
    "thought:",
)


def _is_rate_limit_error(err: Exception) -> bool:
    """Detecte 429 / rate limit via nom de classe ou message."""
    tname = type(err).__name__.lower()
    if "ratelimit" in tname:
        return True
    msg = str(err).lower()
    return "429" in msg or "rate limit" in msg or "too many requests" in msg


def _malformed_output_kind(out, had_tools: bool) -> str | None:
    """Return the malformed output kind when tools were provided."""
    if not had_tools or not isinstance(out, str):
        return None
    if "<tool_call>" in out or "<function=" in out:
        return "xml_hermes"
    if len(out) < MALFORMED_SHORT_TEXT_MAX:
        low = out.lower()
        if any(p in low for p in _INTENTION_PATTERNS):
            return "intention_0_tools"
    return None


def _output_looks_malformed(out, had_tools: bool) -> bool:
    """Detecte une sortie cassee quand des tools etaient fournis.

    Deux modes de defaillance couverts :

    1. XML Hermes (journal 2026-04-19) - le modele emet <tool_call>... ou
       <function=... au lieu du format tool_calls natif OpenAI.
    2. Intention 0-tools courte (journal 2026-04-20) - le modele repond en
       texte narratif court sans appeler d'outil alors que des outils sont
       disponibles.
    """
    return _malformed_output_kind(out, had_tools) is not None


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
            LLM(
                model=m,
                api_key=API_KEY,
                base_url=NVIDIA_BASE,
                temperature=temperature,
                timeout=_resolve_llm_timeout_seconds(),
                # NIM Llama ne supporte pas les tool calls parallèles
                parallel_tool_calls=False,
            )
            for m in chain
        ]
        object.__setattr__(self, "_chain", chain)
        object.__setattr__(self, "_llms", llms)
        object.__setattr__(self, "_disabled_model_indices", set())

    def call(self, messages, tools=None, callbacks=None, available_functions=None,
             from_task=None, from_agent=None, response_model=None):
        # --- Normalisation messages pour NVIDIA NIM ---
        # Qwen et co exigent que TOUT system message soit en position 0.
        # CrewAI (delegation, memory, planning) en injecte parfois au milieu.
        # On fusionne tous les system messages en un seul au début.
        if isinstance(messages, list) and messages and isinstance(messages[0], dict):
            sys_parts = [m.get("content", "") for m in messages if m.get("role") == "system"]
            others = [m for m in messages if m.get("role") != "system"]
            if sys_parts:
                merged_sys = {"role": "system", "content": "\n\n".join(s for s in sys_parts if s)}
                messages = [merged_sys] + others
            else:
                messages = others
        # NIM ne supporte pas response_format/grammar structuré sur la plupart des modèles
        response_model = None

        # --- Normalisation tools pour NVIDIA NIM (fix §0.c) ---
        # CrewAI génère des schemas avec strict:true + additionalProperties:false +
        # TOUS les params dans required (même ceux avec defaults Python).
        # Certains modèles NIM (Qwen Coder, Kimi K2) abandonnent le format
        # tool_calls natif et tentent du XML Hermes quand ils voient ce schema
        # strict. On retire strict + additionalProperties pour laisser les modèles
        # utiliser le tool calling "souple" qui marche chez tous.
        if tools:
            tools = _strip_strict_tools(tools)

        # Phase 1 §3 — Resilience NIM.
        # (a) Backoff 429 sur le meme modele avant fallback chain.
        # (b) Retry-1 si la reponse est XML Hermes (tools fournis mais pas parses).
        # (c) Logs payload opt-in via NEXUS_DEBUG_LLM=1.
        debug = os.environ.get("NEXUS_DEBUG_LLM") == "1"
        had_tools = bool(tools)
        last_err = None

        for idx, llm in enumerate(self._llms):
            model_name = self._chain[idx]
            if idx in self._disabled_model_indices:
                if debug:
                    print(f"  [LLM] model={model_name} ignore (desactive pour ce run)")
                continue
            rl_attempts = 0
            malformed_retries_used = set()

            while True:
                if debug:
                    if isinstance(messages, list):
                        nmsgs = len(messages)
                        nbytes = sum(len(str(m.get("content", ""))) for m in messages)
                        roles = ",".join(m.get("role", "?") for m in messages)
                    else:
                        nmsgs, nbytes, roles = 1, len(str(messages)), "?"
                    print(f"  [LLM] model={model_name} rl_try={rl_attempts} "
                          f"msgs={nmsgs} bytes={nbytes} tools={len(tools) if tools else 0} "
                          f"roles=[{roles}]")
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
                except Exception as e:
                    last_err = e
                    if _is_rate_limit_error(e) and rl_attempts < len(RATE_LIMIT_BACKOFFS):
                        wait = RATE_LIMIT_BACKOFFS[rl_attempts]
                        rl_attempts += 1
                        print(f"  [429 {model_name} : backoff {wait}s, "
                              f"retry {rl_attempts}/{len(RATE_LIMIT_BACKOFFS)}]")
                        time.sleep(wait)
                        continue
                    self._disabled_model_indices.add(idx)
                    print(f"  [modèle {model_name} a échoué : {str(e)[:100]}]")
                    break  # passe au LLM suivant de la chaine

                # (b) 1 retry par type de sortie cassee sur le meme modele.
                malformed_kind = _malformed_output_kind(out, had_tools)
                if malformed_kind and malformed_kind not in malformed_retries_used:
                    malformed_retries_used.add(malformed_kind)
                    print(f"  [sortie malformed {malformed_kind} {model_name} : "
                          f"retry-{len(malformed_retries_used)} sur meme modele]")
                    continue

                if idx > 0:
                    print(f"  [fallback actif : {model_name}]")
                if debug and (malformed_retries_used or rl_attempts > 0):
                    print(f"  [LLM] {model_name} OK apres "
                          f"rl_retries={rl_attempts} malformed_retries={len(malformed_retries_used)}")
                return out

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
    """Cherche un pattern regex dans les fichiers du projet. glob optionnel (ex: *.py).
    Utilise le binaire grep si dispo, sinon fallback Python pur (re + fnmatch)."""
    import shutil as _sh
    # Chemin rapide : grep natif
    if _sh.which("grep"):
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
            return f"Erreur grep natif : {e}"

    # Fallback Python pur
    import re
    import fnmatch
    try:
        rx = re.compile(pattern)
    except re.error as e:
        return f"Regex invalide : {e}"
    hits = []
    total_chars = 0
    for root, dirs, files in os.walk(_project()):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            if not fnmatch.fnmatch(fname, glob):
                continue
            fpath = Path(root) / fname
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    for lineno, line in enumerate(f, 1):
                        if rx.search(line):
                            rel = fpath.relative_to(_project())
                            entry = f"{rel}:{lineno}:{line.rstrip()}"
                            hits.append(entry)
                            total_chars += len(entry) + 1
                            if total_chars >= 8000:
                                hits.append("... (tronque)")
                                return "\n".join(hits)
            except (OSError, UnicodeDecodeError):
                continue
    return "\n".join(hits) or f"(aucun match pour '{pattern}')"


# Allowlist de binaires exécutables par run_shell_tool (Phase 0 #1).
# Tout ce qui n'est pas la-dedans est refuse, point. Plus de blacklist naive.
# Les builtins cmd.exe (dir, type) sont exclus : shell=False ne les execute pas,
# le Coder utilise list_files_tool et read_file_tool a la place.
SHELL_ALLOWLIST = {
    "python", "python3", "py",
    "pytest",
    "node", "npm", "npx", "pnpm", "yarn",
    "git",
    "grep", "rg", "find", "where",
    "ls", "cat", "head", "tail",
    "cargo", "go", "make",
    "echo",
}

# Metacaracteres shell refuses : un appel = une commande, pas de chainage.
# Le shell=False ne les interprete pas, mais on les rejette explicitement
# pour donner un message clair a l'agent plutot que des erreurs obscures.
SHELL_FORBIDDEN_META = ["|", ";", "&&", "||", ">", "<", "`", "$(", ">>", "<<"]


def _split_shell_command(command: str) -> list[str]:
    """Split a single command while preserving native Windows paths."""
    if not command.strip():
        return []
    if os.name == "nt":
        import ctypes

        argc = ctypes.c_int()
        shell32 = ctypes.windll.shell32
        kernel32 = ctypes.windll.kernel32
        shell32.CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
        shell32.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p

        argv_ptr = shell32.CommandLineToArgvW(command, ctypes.byref(argc))
        if not argv_ptr:
            raise ValueError("CommandLineToArgvW failed")
        try:
            return [argv_ptr[i] for i in range(argc.value)]
        finally:
            kernel32.LocalFree(argv_ptr)

    import shlex
    return shlex.split(command, posix=True)


@tool("run_shell")
def run_shell_tool(command: str) -> str:
    """Exécute une commande dans le projet (shell=False, allowlist stricte, timeout 120s).

    Une seule commande par appel. Chaînage shell (| ; && > < etc.) refusé.
    Binaires autorisés : python, pytest, node, npm, pnpm, git, grep, rg,
    ls, cat, head, tail, cargo, go, make, echo, etc. (voir SHELL_ALLOWLIST).
    """

    # 1. Refuser tout metacaractere shell (chainage, redirection, subst).
    for meta in SHELL_FORBIDDEN_META:
        if meta in command:
            return (
                f"[REFUSE] Chainage ou redirection shell non autorise ('{meta}'). "
                f"Lance une seule commande a la fois, sans pipe ni redirection."
            )

    # 2. Parser proprement en argv.
    try:
        argv = _split_shell_command(command)
    except ValueError as e:
        return f"[REFUSE] Parsing commande invalide : {e}"
    if not argv:
        return "[REFUSE] Commande vide."

    # 3. Normaliser le binaire : basename + sans extension .exe, lowercase.
    binary = Path(argv[0]).name.lower()
    if binary.endswith(".exe"):
        binary = binary[:-4]
    if binary not in SHELL_ALLOWLIST:
        return (
            f"[REFUSE] Binaire '{binary}' hors allowlist. "
            f"Autorises : {', '.join(sorted(SHELL_ALLOWLIST))}"
        )

    # 4. Execution reelle, shell=False.
    try:
        result = subprocess.run(
            argv, shell=False, cwd=str(_project()),
            capture_output=True, text=True, timeout=120
        )
        out = (result.stdout or "")[-3000:]
        err = (result.stderr or "")[-1500:]
        return f"exit={result.returncode}\nstdout:\n{out}\nstderr:\n{err}"
    except subprocess.TimeoutExpired:
        return "Timeout (>120s)"
    except FileNotFoundError:
        return f"[REFUSE] Binaire '{argv[0]}' introuvable dans le PATH."
    except Exception as e:
        return f"Erreur shell : {e}"


READ_TOOLS = [read_file_tool, list_files_tool, grep_tool]


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
        allow_delegation=False,
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
        allow_delegation=False,
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
        # Le Coder a toujours read + write_file. run_shell n'est ajoute que
        # si --allow-shell est explicitement passe par l'utilisateur (#1 Shell).
        tools=(
            READ_TOOLS + [write_file_tool, run_shell_tool]
            if os.environ.get("CREW_SHELL_ENABLED")
            else READ_TOOLS + [write_file_tool]
        ),
        verbose=True,
        allow_delegation=False,
        max_iter=15,
    )


def make_critic() -> Agent:
    return Agent(
        role="Critic",
        goal="Traquer activement bugs, failles de sécurité, edge cases et régressions dans le travail du Coder",
        backstory=(
            "Tu es un reviewer méticuleux. Tu cherches des problèmes — tu ne te contentes pas d'approuver. "
            "Tu relis le code contre le plan, tu vérifies la sécurité, "
            "tu cherches les edge cases que le Coder a pu rater. "
            "Si un test devrait être lancé, tu le mentionnes explicitement dans ton feedback "
            "(tu es en lecture seule, tu ne le lances pas toi-même). "
            "Tu finis par APPROVED ou CHANGES_NEEDED avec des corrections précises. "
            "Tu ne corriges JAMAIS toi-même : tu relis et tu bloques. La correction revient au Coder. "
            "COLLABORATION : tu peux renvoyer une question au Coder pour qu'il corrige avant validation, "
            "ou demander au Researcher de vérifier un point du projet si tu as un doute."
        ),
        llm=make_llm("critic"),
        # Lecture seule : le Critic relit et bloque, il ne modifie rien.
        # Pas de run_shell non plus tant que le Validation Agent n'existe pas
        # (dette acceptée Phase 0 — voir DOCUMENT_MAITRE_PROJET §Journal 2026-04-08).
        tools=READ_TOOLS,
        verbose=True,
        allow_delegation=False,
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
        allow_delegation=False,
        max_iter=5,
    )


# ─── Construction du crew ─────────────────────────────────────────────────────

# Phase 1 §2 (journal 2026-04-20) — Modes d'usage v1. Cible produit §9 du
# maître. Chaque mode route un sous-ensemble de tasks pour eviter la
# sur-utilisation systematique du pipeline complet (dette §14 : "crew sequentiel
# qui lance presque toujours toute la chaine"). L'utilisateur choisit
# explicitement via --mode. Le mode auto reste deterministe et local : pas
# d'appel LLM dedie, pas de changement du defaut historique edit.
#
#  - auto   : heuristique locale vers read / review / debug / edit.
#  - read   : comprehension / audit sans modification (Researcher seul).
#  - edit   : modification propre avec validation (pipeline complet, defaut).
#  - review : relecture d'un etat existant, pas d'apres-Coder (Researcher +
#             review standalone + final).
#  - debug  : investigation + correction avec consignes diagnostic,
#             meme composition que edit.


def _resolve_governance_json_path(project_path: Path, target: str) -> Path:
    """Resolve a governance JSON output path inside the project root."""
    output_path = Path(target)
    full = (
        output_path.resolve()
        if output_path.is_absolute()
        else (project_path / output_path).resolve()
    )
    project_root = project_path.resolve()
    if full != project_root and project_root not in full.parents:
        raise ValueError("governance json path must stay inside --project")
    return full


def _resolve_correction_ledger_json_path(project_path: Path, target: str) -> Path:
    """Resolve a correction ledger input path inside the project root."""
    ledger_path = Path(target)
    full = (
        ledger_path.resolve()
        if ledger_path.is_absolute()
        else (project_path / ledger_path).resolve()
    )
    project_root = project_path.resolve()
    if full != project_root and project_root not in full.parents:
        raise ValueError("correction ledger json path must stay inside --project")
    return full


def _resolve_correction_dispatch_json_path(project_path: Path, target: str) -> Path:
    """Resolve a correction dispatch manifest path inside the project root."""
    dispatch_path = Path(target)
    full = (
        dispatch_path.resolve()
        if dispatch_path.is_absolute()
        else (project_path / dispatch_path).resolve()
    )
    project_root = project_path.resolve()
    if full != project_root and project_root not in full.parents:
        raise ValueError("correction dispatch json path must stay inside --project")
    return full


def _validate_attempts_map(raw, field_name: str) -> dict[str, int]:
    """Validate a correction-attempt ledger map."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} must be an object")
    validated: dict[str, int] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key:
            raise ValueError(f"{field_name} keys must be non-empty strings")
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"{field_name}.{key} must be an integer >= 0")
        validated[key] = value
    return validated


def _validate_correction_ledger_schema_version(payload: dict) -> None:
    """Validate the optional correction ledger schema version."""
    if "schema_version" not in payload:
        return
    version = payload["schema_version"]
    if version != CORRECTION_LEDGER_SCHEMA_VERSION:
        raise ValueError(
            "correction ledger schema_version must be "
            f"{CORRECTION_LEDGER_SCHEMA_VERSION}"
        )


def _load_correction_attempt_ledger(project_path: Path, target: str) -> tuple[dict[str, int], dict[str, int]]:
    """Load correction attempts from a JSON file under the project root."""
    ledger_path = _resolve_correction_ledger_json_path(project_path, target)
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("correction ledger json must be an object")
    _validate_correction_ledger_schema_version(payload)
    attempts_used_by_task = _validate_attempts_map(
        payload.get("attempts_used_by_task"),
        "attempts_used_by_task",
    )
    attempts_used_by_interaction_id = _validate_attempts_map(
        payload.get("attempts_used_by_interaction_id"),
        "attempts_used_by_interaction_id",
    )
    return attempts_used_by_task, attempts_used_by_interaction_id


def _correction_attempt_ledger_payload(
    tracker: ContractTracker,
    correction_attempt_budget: int,
    attempts_used_by_task: dict[str, int] | None = None,
    attempts_used_by_interaction_id: dict[str, int] | None = None,
) -> dict:
    """Return the current correction ledger snapshot without consuming attempts."""
    attempts_used_by_task = attempts_used_by_task or {}
    attempts_used_by_interaction_id = attempts_used_by_interaction_id or {}
    interactions = tracker.corrective_interactions(
        attempts_budget=correction_attempt_budget,
        attempts_used_by_task=attempts_used_by_task,
        attempts_used_by_interaction_id=attempts_used_by_interaction_id,
    )
    pending_ids = sorted(
        interaction["interaction_id"]
        for interaction in interactions
        if interaction.get("should_dispatch")
    )
    blocked_ids = sorted(
        interaction["interaction_id"]
        for interaction in interactions
        if not interaction.get("should_dispatch")
    )
    return {
        "schema_version": CORRECTION_LEDGER_SCHEMA_VERSION,
        "attempts_used_by_task": dict(sorted(attempts_used_by_task.items())),
        "attempts_used_by_interaction_id": dict(sorted(attempts_used_by_interaction_id.items())),
        "correction_plan": tracker.correction_plan_payload(
            attempts_budget=correction_attempt_budget,
            attempts_used_by_task=attempts_used_by_task,
            attempts_used_by_interaction_id=attempts_used_by_interaction_id,
        ),
        "pending_interaction_ids": pending_ids,
        "blocked_interaction_ids": blocked_ids,
        "interactions_count": len(interactions),
    }


def _write_correction_attempt_ledger(
    project_path: Path,
    target: str,
    tracker: ContractTracker,
    correction_attempt_budget: int,
    attempts_used_by_task: dict[str, int] | None = None,
    attempts_used_by_interaction_id: dict[str, int] | None = None,
) -> Path:
    """Write the current correction ledger snapshot under the project root."""
    ledger_path = _resolve_correction_ledger_json_path(project_path, target)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _correction_attempt_ledger_payload(
        tracker=tracker,
        correction_attempt_budget=correction_attempt_budget,
        attempts_used_by_task=attempts_used_by_task,
        attempts_used_by_interaction_id=attempts_used_by_interaction_id,
    )
    ledger_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return ledger_path


def _correction_dispatch_payload(
    tracker: ContractTracker,
    correction_attempt_budget: int,
    attempts_used_by_task: dict[str, int] | None = None,
    attempts_used_by_interaction_id: dict[str, int] | None = None,
) -> dict:
    """Return a dry-run dispatch manifest and the ledger it would consume."""
    attempts_used_by_task = attempts_used_by_task or {}
    attempts_used_by_interaction_id = attempts_used_by_interaction_id or {}
    interactions = tracker.corrective_interactions(
        attempts_budget=correction_attempt_budget,
        attempts_used_by_task=attempts_used_by_task,
        attempts_used_by_interaction_id=attempts_used_by_interaction_id,
    )
    dispatchable = [
        interaction for interaction in interactions
        if interaction.get("should_dispatch")
    ]
    blocked_ids = sorted(
        interaction["interaction_id"]
        for interaction in interactions
        if not interaction.get("should_dispatch")
    )
    next_attempts_by_interaction_id = dict(attempts_used_by_interaction_id)
    for interaction in dispatchable:
        interaction_id = interaction["interaction_id"]
        next_attempts_by_interaction_id[interaction_id] = interaction["attempts_used"] + 1

    if dispatchable:
        status = CORRECTION_DISPATCH_AVAILABLE
    elif interactions:
        status = CORRECTION_DISPATCH_BLOCKED_BUDGET_EXHAUSTED
    else:
        status = CORRECTION_DISPATCH_NO_DISPATCH_NEEDED

    return {
        "schema_version": CORRECTION_DISPATCH_SCHEMA_VERSION,
        "ledger_schema_version": CORRECTION_LEDGER_SCHEMA_VERSION,
        "status": status,
        "dispatchable_count": len(dispatchable),
        "blocked_count": len(blocked_ids),
        "dispatchable_interactions": dispatchable,
        "blocked_interaction_ids": blocked_ids,
        "correction_plan": tracker.correction_plan_payload(
            attempts_budget=correction_attempt_budget,
            attempts_used_by_task=attempts_used_by_task,
            attempts_used_by_interaction_id=attempts_used_by_interaction_id,
        ),
        "next_ledger": {
            "schema_version": CORRECTION_LEDGER_SCHEMA_VERSION,
            "attempts_used_by_task": dict(sorted(attempts_used_by_task.items())),
            "attempts_used_by_interaction_id": dict(sorted(next_attempts_by_interaction_id.items())),
        },
    }


def _write_correction_dispatch_json(
    project_path: Path,
    target: str,
    tracker: ContractTracker,
    correction_attempt_budget: int,
    attempts_used_by_task: dict[str, int] | None = None,
    attempts_used_by_interaction_id: dict[str, int] | None = None,
    payload: dict | None = None,
) -> Path:
    """Write a dry-run correction dispatch manifest under the project root."""
    dispatch_path = _resolve_correction_dispatch_json_path(project_path, target)
    dispatch_path.parent.mkdir(parents=True, exist_ok=True)
    if payload is None:
        payload = _correction_dispatch_payload(
            tracker=tracker,
            correction_attempt_budget=correction_attempt_budget,
            attempts_used_by_task=attempts_used_by_task,
            attempts_used_by_interaction_id=attempts_used_by_interaction_id,
        )
    dispatch_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return dispatch_path


def _write_correction_next_ledger_json(
    project_path: Path,
    target: str,
    tracker: ContractTracker,
    correction_attempt_budget: int,
    attempts_used_by_task: dict[str, int] | None = None,
    attempts_used_by_interaction_id: dict[str, int] | None = None,
) -> Path:
    """Write the next correction ledger projected by the dry-run dispatch."""
    ledger_path = _resolve_correction_ledger_json_path(project_path, target)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _correction_dispatch_payload(
        tracker=tracker,
        correction_attempt_budget=correction_attempt_budget,
        attempts_used_by_task=attempts_used_by_task,
        attempts_used_by_interaction_id=attempts_used_by_interaction_id,
    )["next_ledger"]
    ledger_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return ledger_path


def _format_dispatch_ids(label: str, interaction_ids: list[str], limit: int = 5) -> str:
    """Return one compact summary line for dispatch interaction ids."""
    visible_ids = interaction_ids[:limit]
    suffix = f" (+{len(interaction_ids) - limit})" if len(interaction_ids) > limit else ""
    return f"[CORRECTION] {label} ids : {', '.join(visible_ids)}{suffix}"


def _correction_dispatch_summary(payload: dict, strict_correction_dispatch: bool = False) -> str:
    """Return a compact human-readable summary for corrective dispatch state."""
    status = payload.get("status", CORRECTION_DISPATCH_NO_DISPATCH_NEEDED)
    dispatchable_count = payload.get("dispatchable_count", 0)
    blocked_count = payload.get("blocked_count", 0)
    dispatchable_ids = [
        interaction["interaction_id"]
        for interaction in payload.get("dispatchable_interactions", [])
        if "interaction_id" in interaction
    ]
    blocked_ids = list(payload.get("blocked_interaction_ids", []))
    lines = [
        "[CORRECTION] dispatch dry-run : "
        f"{status} ({dispatchable_count} dispatchable, {blocked_count} bloquee(s))"
    ]
    if dispatchable_ids:
        lines.append(_format_dispatch_ids("dispatchable", dispatchable_ids))
    if blocked_ids:
        lines.append(_format_dispatch_ids("blocked", blocked_ids))
    if strict_correction_dispatch and status == CORRECTION_DISPATCH_AVAILABLE:
        lines.append(
            "[CORRECTION] strict dispatch : exit code "
            f"{CORRECTION_DISPATCH_AVAILABLE_EXIT_CODE}"
        )
    return "\n".join(lines)


def _correction_dispatch_exit_code(
    tracker: ContractTracker,
    strict_correction_dispatch: bool = False,
    correction_attempt_budget: int = 1,
    attempts_used_by_task: dict[str, int] | None = None,
    attempts_used_by_interaction_id: dict[str, int] | None = None,
) -> int:
    """Return the optional CLI exit code for available corrective dispatches."""
    if not strict_correction_dispatch:
        return 0
    payload = _correction_dispatch_payload(
        tracker=tracker,
        correction_attempt_budget=correction_attempt_budget,
        attempts_used_by_task=attempts_used_by_task,
        attempts_used_by_interaction_id=attempts_used_by_interaction_id,
    )
    if payload["status"] == CORRECTION_DISPATCH_AVAILABLE:
        return CORRECTION_DISPATCH_AVAILABLE_EXIT_CODE
    return 0


CORRECTION_LEDGER_SCHEMA_VERSION = 1
CORRECTION_DISPATCH_SCHEMA_VERSION = 1
CORRECTION_DISPATCH_AVAILABLE = "DISPATCH_AVAILABLE"
CORRECTION_DISPATCH_BLOCKED_BUDGET_EXHAUSTED = "DISPATCH_BLOCKED_BUDGET_EXHAUSTED"
CORRECTION_DISPATCH_NO_DISPATCH_NEEDED = "NO_DISPATCH_NEEDED"
CORRECTION_DISPATCH_AVAILABLE_EXIT_CODE = 3
AUTO_MODE = "auto"
ROUTING_MODES = ("read", "edit", "review", "debug")
VALID_MODES = (AUTO_MODE, *ROUTING_MODES)
DEFAULT_MODE = "edit"


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _classify_mode(task_text: str) -> str:
    """Classify a user task into a deterministic local execution mode."""
    normalized = task_text.casefold()
    no_write_markers = ("sans modifier", "ne modifie", "ne touche pas")
    review_markers = (
        "review", "relis", "relire", "revue", "relecture", "audit",
        "verifie", "vérifie", "inspecte", "cherche les risques",
    )
    read_markers = (
        "explique", "explique-moi", "resume", "résume", "decris", "décris",
        "comprends", "comprendre", "cartographie", "lis ", "que fait",
        "c'est quoi", "c est quoi", "etat general", "état général",
    )
    debug_markers = (
        "debug", "bug", "erreur", "traceback", "crash", "corrige l'erreur",
        "corrige erreur", "pourquoi ca plante", "pourquoi ça plante",
        "investigue", "diagnostic", "diagnostique",
    )
    edit_markers = (
        "corrige", "fix", "implemente", "implémente", "ajoute", "modifie",
        "refactor", "refactore", "supprime", "remplace", "mets a jour",
        "met à jour", "update", "change",
    )
    if _contains_any(normalized, no_write_markers):
        return "review"
    if _contains_any(normalized, edit_markers):
        return "debug" if _contains_any(normalized, debug_markers) else "edit"
    if _contains_any(normalized, debug_markers):
        return "debug"
    if _contains_any(normalized, review_markers):
        return "review"
    if _contains_any(normalized, read_markers):
        return "read"
    return DEFAULT_MODE


def _resolve_mode(task_text: str, mode: str) -> str:
    if mode not in VALID_MODES:
        raise ValueError(f"mode invalide : {mode!r} (attendu : {VALID_MODES})")
    if mode == AUTO_MODE:
        return _classify_mode(task_text)
    return mode


def _debug_mode_guidance(mode: str, section: str) -> str:
    """Return task-specific diagnostic guidance for debug mode."""
    if mode != "debug":
        return ""
    guidance = {
        "research": (
            "\n\nMode DEBUG : oriente la carte vers la reproduction du probleme, "
            "les symptomes observables, les zones de cause racine probable et "
            "les validations utiles."
        ),
        "plan": (
            "\n\nMode DEBUG : structure le plan autour de l'hypothese de cause racine, "
            "de la reproduction, du patch minimal et des validations ciblees."
        ),
        "code": (
            "\n\nMode DEBUG : applique uniquement les changements necessaires a la "
            "cause racine identifiee. Evite les refactors opportunistes et "
            "garde chaque modification justifiable par le diagnostic."
        ),
        "review": (
            "\n\nMode DEBUG : verifie la chaine symptome -> cause racine -> patch -> "
            "validation. Cherche les regressions liees au correctif plutot que "
            "des ameliorations hors scope."
        ),
        "rework": (
            "\n\nMode DEBUG : corrige seulement ce qui invalide le diagnostic, le patch "
            "minimal ou la validation ciblee demandes par le Critic."
        ),
        "final": (
            "\n\nMode DEBUG : organise la synthese autour de la cause racine probable, "
            "du correctif applique, des validations effectuees et des risques "
            "restants."
        ),
    }
    return guidance[section]


def build_crew(task_text: str, project_path: Path, deep: bool,
               tracker: ContractTracker | None = None,
               mode: str = DEFAULT_MODE) -> Crew:
    mode = _resolve_mode(task_text, mode)

    # Le Researcher est commun a tous les modes.
    researcher = make_researcher()

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
            + _debug_mode_guidance(mode, "research")
        ),
        expected_output="Un rapport markdown avec la carte du projet et les éléments pertinents pour la tâche",
        agent=researcher,
    )

    # On instancie les agents et tasks specifiques selon le mode. Les modes
    # "read" et "review" n'ont pas besoin du Coder — economie concrete NIM.
    if mode == "read":
        # Lecture seule economique : le Researcher produit directement le
        # rapport utilisateur. La synthese Architect etait qualitative, mais
        # trop couteuse en runtime NIM borne pour les validations Codex.
        tasks = [research_task]
        agents = [researcher]
    elif mode == "review":
        # Relecture d'un etat existant (pas d'output Coder a analyser).
        critic = make_critic()
        architect = make_architect()
        review_standalone_task = Task(
            description=(
                f"Review du code existant (mode REVIEW — pas de travail Coder à analyser).\n"
                f"Tâche originale : {task_text}\n\n"
                "À partir de la carte du Researcher, relis le code existant :\n"
                "- Cherche bugs, failles de sécurité, edge cases\n"
                "- Repère les risques de régression potentiels\n"
                "- Identifie les conventions non respectées\n"
                "- Tu es en LECTURE SEULE : pas d'écriture, pas de shell, pas de tests. "
                "Si un test devrait être lancé, mentionne-le dans ton feedback.\n"
                "Finis par APPROVED si le code est propre, ou CHANGES_NEEDED avec les "
                "corrections recommandées (que l'utilisateur appliquera lui-même ou "
                "en mode edit)."
            ),
            expected_output="APPROVED ou CHANGES_NEEDED avec feedback détaillé",
            agent=critic,
            context=[research_task],
        )
        final_task = Task(
            description=(
                f"Synthèse pour l'utilisateur (mode REVIEW — aucune modification appliquée).\n"
                f"Tâche originale : {task_text}\n\n"
                "Produis un rapport clair :\n"
                "- Verdict du Critic (APPROVED / CHANGES_NEEDED)\n"
                "- Liste des findings importants\n"
                "- Recommandations concrètes (fichiers, lignes, corrections suggérées)\n"
                "- Points d'attention restants pour l'utilisateur"
            ),
            expected_output="Un rapport final markdown lisible par un humain non-développeur",
            agent=architect,
            context=[research_task, review_standalone_task],
        )
        tasks = [research_task, review_standalone_task, final_task]
        agents = [researcher, critic, architect]

    else:
        # mode == "edit" ou mode == "debug" : meme pipeline; debug
        # ajoute des consignes diagnostic sans changer la composition.
        architect = make_architect()
        coder      = make_coder()
        critic     = make_critic()

        plan_task = Task(
            description=(
                f"À partir de la carte produite par le Researcher et de la tâche : {task_text}\n\n"
                "Produis un plan d'exécution étape par étape :\n"
                "- Numérote chaque étape\n"
                "- Indique les fichiers exacts à toucher\n"
                "- Précise l'ordre et les dépendances\n"
                "- Liste les points à vérifier par le Critic"
                + _debug_mode_guidance(mode, "plan")
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
                + _debug_mode_guidance(mode, "code")
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
                "- Tu es en LECTURE SEULE : pas d'écriture, pas de shell, pas de tests. "
                "Si tu penses qu'un test devrait être lancé, mentionne-le dans ton feedback.\n"
                "Finis par APPROVED si tout est bon, ou CHANGES_NEEDED avec les corrections à apporter"
                + _debug_mode_guidance(mode, "review")
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
                + _debug_mode_guidance(mode, "rework")
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
                + _debug_mode_guidance(mode, "final")
            ),
            expected_output="Un rapport final markdown lisible par un humain non-développeur",
            agent=architect,
            context=[research_task, plan_task, code_task, review_task, rework_task],
        )

        tasks  = [research_task, plan_task, code_task, review_task, rework_task, final_task]
        agents = [researcher, architect, coder, critic]

    # Scanner ajoute en tete si --deep, quel que soit le mode.
    scan_task = None
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

    # -- Contract tracking (Phase 1 §1) --
    # On enregistre chaque task effectivement presente dans le pipeline.
    # Le kind sert a selectionner le bon contrat (crew/contracts.py).
    if tracker:
        tracker.register(research_task.description, "research")
        if mode == "read":
            pass
        elif mode == "review":
            tracker.register(review_standalone_task.description, "review")
            tracker.register(final_task.description, "final")
        else:  # edit / debug
            tracker.register(plan_task.description, "plan")
            tracker.register(code_task.description, "code")
            tracker.register(review_task.description, "review")
            tracker.register(rework_task.description, "rework")
            tracker.register(final_task.description, "final")
        if scan_task is not None:
            tracker.register(scan_task.description, "scan")

    crew_kwargs: dict = dict(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
        cache=True,
    )
    if tracker:
        crew_kwargs["task_callback"] = tracker.on_task_done

    return Crew(
        **crew_kwargs,
        # memory=True et planning=True désactivés : tous deux cassent sur NVIDIA NIM.
        #  - planning utilise un response_format/JSON schema non supporté
        #    ("Invalid grammar request" sur DeepSeek, Qwen, etc.)
        #  - memory injecte du contexte qui place un system message hors début
        #    de conversation ("System message must be at the beginning" sur Qwen).
        # La coordination passe par : context=[...] explicite + délégation entre
        # agents + boucle rework. Suffisant pour le flow Researcher→...→Coder(rework).
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
            "Modes (--mode) :\n"
            "  auto    Classification locale deterministe vers read/review/debug/edit\n"
            "  read    Compréhension / audit sans modification (Researcher seul)\n"
            "  edit    Modification propre avec validation (pipeline complet, défaut)\n"
            "  review  Relecture d'un état existant (Researcher + Critic + synthèse)\n"
            "  debug   Investigation + correction avec consignes diagnostic\n\n"
            "Exemples :\n"
            '  python crew.py "explique ce projet" --project C:/mon-projet --mode auto\n'
            '  python crew.py "explique ce projet" --project C:/mon-projet --mode read\n'
            '  python crew.py "refactore l\'auth" --project C:/mon-projet --mode edit --write\n'
            '  python crew.py "relis mes derniers changements" --project C:/mon-projet --mode review\n'
            '  python crew.py "lance les tests" --project C:/mon-projet --allow-shell\n'
            '  python crew.py "audit complet" --project C:/gros-projet --deep --write\n'
        ),
    )
    parser.add_argument("task", help="La tâche à accomplir")
    parser.add_argument("--project", "-p", required=True, help="Chemin du projet")
    parser.add_argument("--mode", "-m", choices=VALID_MODES, default=DEFAULT_MODE,
                        help=f"Mode d'usage : {' / '.join(VALID_MODES)} (défaut : {DEFAULT_MODE})")
    parser.add_argument("--write", "-w", action="store_true",
                        help="Active l'écriture réelle de fichiers (sinon dry-run)")
    parser.add_argument("--allow-shell", "-s", action="store_true",
                        help="Donne au Coder l'outil run_shell (shell=False, allowlist stricte). "
                             "OFF par defaut.")
    parser.add_argument("--deep", "-d", action="store_true",
                        help="Active le mode Scanner + Researcher pour les gros projets")
    parser.add_argument("--strict-contracts", action="store_true",
                        help="Retourne exit code 2 si les contrats de sortie sont violés. "
                             "Par défaut, les violations sont imprimées sans changer l'exit code.")
    parser.add_argument("--strict-correction-dispatch", action="store_true",
                        help="Retourne exit code 3 si un dispatch correctif dry-run est disponible. "
                             "N'active pas de retry automatique.")
    parser.add_argument("--governance-json",
                        help="Ecrit le rapport de gouvernance JSON dans un chemin sous --project.")
    parser.add_argument("--correction-attempt-budget", type=int, default=1,
                        help="Budget de relance par task expose dans le plan correctif. "
                             "N'active pas de retry automatique. Defaut : 1.")
    parser.add_argument("--correction-ledger-json",
                        help="Lit un ledger JSON de tentatives correctives sous --project. "
                             "N'active pas de retry automatique.")
    parser.add_argument("--correction-ledger-out-json",
                        help="Ecrit un snapshot du ledger correctif sous --project. "
                             "N'incremente aucune tentative et n'active pas de retry automatique.")
    parser.add_argument("--correction-dispatch-json",
                        help="Ecrit un manifeste dry-run des interactions correctives dispatchables "
                             "et du prochain ledger sous --project, puis imprime son resume. "
                             "N'active pas de retry automatique.")
    parser.add_argument("--correction-next-ledger-json",
                        help="Ecrit directement le next_ledger projeté sous --project, reutilisable "
                             "avec --correction-ledger-json. N'active pas de retry automatique.")
    parser.add_argument("--allow", "-a", action="append", default=[],
                        help="Dossier supplémentaire accessible (répétable). "
                             "Ex : --allow C:/autres/libs --allow D:/data")
    args = parser.parse_args()

    if args.correction_attempt_budget < 0:
        print("ERREUR : --correction-attempt-budget doit etre >= 0.")
        sys.exit(1)

    effective_mode = _resolve_mode(args.task, args.mode)

    # Garde-fou : en mode read ou review, --write n'a aucun sens (pas de Coder
    # dans le pipeline). On avertit et on continue — l'argparse garde ne suffit
    # pas car write est aussi consomme par _resolve_project_rel / write_file_tool
    # pour la permission globale.
    if effective_mode in ("read", "review") and args.write:
        mode_label = f"{args.mode} -> {effective_mode}" if args.mode == AUTO_MODE else args.mode
        print(f"ATTENTION : --write ignoré en mode {mode_label} (pas de Coder dans ce pipeline).")
        args.write = False

    project_path = Path(args.project).resolve()
    if not project_path.is_dir():
        print(f"ERREUR : {project_path} n'est pas un dossier.")
        sys.exit(1)

    attempts_used_by_task: dict[str, int] = {}
    attempts_used_by_interaction_id: dict[str, int] = {}
    if args.correction_ledger_json:
        try:
            attempts_used_by_task, attempts_used_by_interaction_id = _load_correction_attempt_ledger(
                project_path,
                args.correction_ledger_json,
            )
        except Exception as e:
            print(f"ERREUR : impossible de lire le ledger correctif JSON : {e}")
            sys.exit(1)

    os.environ["CREW_PROJECT"] = str(project_path)
    if args.write:
        os.environ["CREW_WRITE_ENABLED"] = "1"
    if args.allow_shell:
        os.environ["CREW_SHELL_ENABLED"] = "1"

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
    mode_display = effective_mode.upper()
    if args.mode == AUTO_MODE:
        mode_display = f"AUTO -> {mode_display}"
    print(f"  Projet  : {project_path}")
    print(f"  Mode    : {mode_display}{' + DEEP (Scanner)' if args.deep else ''}")
    print(f"  Tâche   : {args.task}")
    print()
    # Permissions actives — rendu explicite pour que l'utilisateur voie
    # exactement ce que les agents sont autorisés à faire.
    write_on = bool(args.write)
    shell_on = bool(args.allow_shell)
    n_extra = len(extra_roots)
    roots_detail = f"projet + {n_extra} dossier(s) --allow" if n_extra else "projet uniquement"
    print("  Permissions actives :")
    print(f"    - read       : ON  ({roots_detail})")
    print(f"    - write_file : {'ON ' if write_on else 'OFF'} (dry-run si OFF)")
    if shell_on:
        print("    - run_shell  : ON  (Coder uniquement, shell=False, allowlist stricte)")
    else:
        print("    - run_shell  : OFF (activer avec --allow-shell)")
    print()

    tracker = ContractTracker()
    crew = build_crew(args.task, project_path, deep=args.deep,
                      tracker=tracker, mode=effective_mode)
    result = crew.kickoff()

    print()
    print("=" * 60)
    print("RÉSULTAT FINAL")
    print("=" * 60)
    print(result)

    # -- Contract validation report + governance state (Phase 1 -> Phase 2) --
    print()
    print(tracker.summary())
    print(tracker.governance_summary())
    if tracker.should_block():
        print(tracker.correction_summary(
            attempts_budget=args.correction_attempt_budget,
            attempts_used_by_task=attempts_used_by_task,
            attempts_used_by_interaction_id=attempts_used_by_interaction_id,
        ))
    if args.governance_json:
        try:
            governance_path = _resolve_governance_json_path(project_path, args.governance_json)
            tracker.write_governance_json(
                governance_path,
                strict_contracts=args.strict_contracts,
                correction_attempt_budget=args.correction_attempt_budget,
                attempts_used_by_task=attempts_used_by_task,
                attempts_used_by_interaction_id=attempts_used_by_interaction_id,
            )
            print(f"[GOUVERNANCE] rapport JSON ecrit : {governance_path}")
        except Exception as e:
            print(f"ERREUR : impossible d'ecrire le rapport de gouvernance JSON : {e}")
            sys.exit(1)
    if args.correction_ledger_out_json:
        try:
            ledger_path = _write_correction_attempt_ledger(
                project_path=project_path,
                target=args.correction_ledger_out_json,
                tracker=tracker,
                correction_attempt_budget=args.correction_attempt_budget,
                attempts_used_by_task=attempts_used_by_task,
                attempts_used_by_interaction_id=attempts_used_by_interaction_id,
            )
            print(f"[CORRECTION] ledger JSON ecrit : {ledger_path}")
        except Exception as e:
            print(f"ERREUR : impossible d'ecrire le ledger correctif JSON : {e}")
            sys.exit(1)
    dispatch_payload_for_summary: dict | None = None
    if args.correction_dispatch_json:
        try:
            dispatch_payload_for_summary = _correction_dispatch_payload(
                tracker=tracker,
                correction_attempt_budget=args.correction_attempt_budget,
                attempts_used_by_task=attempts_used_by_task,
                attempts_used_by_interaction_id=attempts_used_by_interaction_id,
            )
            dispatch_path = _write_correction_dispatch_json(
                project_path=project_path,
                target=args.correction_dispatch_json,
                tracker=tracker,
                correction_attempt_budget=args.correction_attempt_budget,
                attempts_used_by_task=attempts_used_by_task,
                attempts_used_by_interaction_id=attempts_used_by_interaction_id,
                payload=dispatch_payload_for_summary,
            )
            print(f"[CORRECTION] manifeste dispatch JSON ecrit : {dispatch_path}")
            print(_correction_dispatch_summary(
                dispatch_payload_for_summary,
                strict_correction_dispatch=args.strict_correction_dispatch,
            ))
        except Exception as e:
            print(f"ERREUR : impossible d'ecrire le manifeste dispatch correctif JSON : {e}")
            sys.exit(1)
    if args.correction_next_ledger_json:
        try:
            next_ledger_path = _write_correction_next_ledger_json(
                project_path=project_path,
                target=args.correction_next_ledger_json,
                tracker=tracker,
                correction_attempt_budget=args.correction_attempt_budget,
                attempts_used_by_task=attempts_used_by_task,
                attempts_used_by_interaction_id=attempts_used_by_interaction_id,
            )
            print(f"[CORRECTION] next ledger JSON ecrit : {next_ledger_path}")
        except Exception as e:
            print(f"ERREUR : impossible d'ecrire le next ledger correctif JSON : {e}")
            sys.exit(1)
    governance_exit_code = tracker.exit_code(strict_contracts=args.strict_contracts)
    if governance_exit_code:
        sys.exit(governance_exit_code)
    if args.strict_correction_dispatch and dispatch_payload_for_summary is None:
        dispatch_payload_for_summary = _correction_dispatch_payload(
            tracker=tracker,
            correction_attempt_budget=args.correction_attempt_budget,
            attempts_used_by_task=attempts_used_by_task,
            attempts_used_by_interaction_id=attempts_used_by_interaction_id,
        )
        print(_correction_dispatch_summary(
            dispatch_payload_for_summary,
            strict_correction_dispatch=True,
        ))
    dispatch_exit_code = _correction_dispatch_exit_code(
        tracker=tracker,
        strict_correction_dispatch=args.strict_correction_dispatch,
        correction_attempt_budget=args.correction_attempt_budget,
        attempts_used_by_task=attempts_used_by_task,
        attempts_used_by_interaction_id=attempts_used_by_interaction_id,
    )
    if dispatch_exit_code:
        sys.exit(dispatch_exit_code)


if __name__ == "__main__":
    main()
