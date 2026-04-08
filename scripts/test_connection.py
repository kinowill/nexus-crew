"""
test_connection.py
==================
Vérifie que NEXUS Crew est prêt à tourner :
  1. Clé API NVIDIA présente
  2. Endpoint /v1/models joignable
  3. Les modèles primaires du crew existent dans le catalogue
  4. L'embedder répond en OpenAI-compat
  5. Fichiers clés du projet présents
  6. Dépendances Python critiques importables

Usage : python scripts/test_connection.py
"""

import json
import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("ERREUR : httpx non installé. Lance : pip install httpx")
    sys.exit(1)

ROOT = Path(__file__).parent.parent
ENV_FILE = ROOT / ".env"

# Charger .env
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"

# Modèles primaires utilisés par crew.py
PRIMARY_MODELS = [
    "qwen/qwen3.5-397b-a17b",
    "deepseek-ai/deepseek-v3.2",
    "qwen/qwen3-coder-480b-a35b-instruct",
    "moonshotai/kimi-k2-thinking",
    "meta/llama-3.3-70b-instruct",
]
EMBEDDER_MODEL = "nvidia/nv-embed-v1"

# Fichiers qui DOIVENT exister
REQUIRED_FILES = [
    ROOT / "crew" / "crew.py",
    ROOT / "nexus.bat",
    ROOT / "requirements.txt",
    ROOT / ".env.example",
    ROOT / ".env",
]

# Imports Python critiques
REQUIRED_IMPORTS = ["crewai", "litellm", "chromadb", "pydantic"]


def check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "OK  " if ok else "FAIL"
    line = f"  [{mark}] {label}"
    if detail:
        line += f"  -- {detail}"
    print(line)
    return ok


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print()
    print("=" * 60)
    print("  NEXUS Crew - Test de sante")
    print("=" * 60)
    print()

    results = []

    # 1. Clé API
    has_key = bool(API_KEY) and API_KEY.startswith("nvapi-") and "REMPLACE" not in API_KEY
    masked = f"{API_KEY[:10]}...{API_KEY[-4:]}" if has_key else "absente ou placeholder"
    results.append(check("Cle API NVIDIA", has_key, masked))
    if not has_key:
        print("\n  Edite .env et renseigne NVIDIA_API_KEY.\n")
        return 1

    # 2. Catalogue modèles
    print()
    print("  Catalogue NVIDIA NIM :")
    try:
        r = httpx.get(f"{NVIDIA_BASE}/models",
                      headers={"Authorization": f"Bearer {API_KEY}"},
                      timeout=15)
        if r.status_code != 200:
            results.append(check("GET /v1/models", False, f"HTTP {r.status_code}"))
            return 1
        catalog = {m["id"] for m in r.json().get("data", [])}
        results.append(check("GET /v1/models", True, f"{len(catalog)} modeles disponibles"))
    except Exception as e:
        results.append(check("GET /v1/models", False, str(e)[:80]))
        return 1

    # 3. Modèles primaires du crew
    print()
    print("  Modeles primaires du crew :")
    for m in PRIMARY_MODELS:
        results.append(check(m, m in catalog))

    # 4. Embedder
    print()
    print("  Embedder :")
    results.append(check(EMBEDDER_MODEL + " (catalogue)", EMBEDDER_MODEL in catalog))
    try:
        r = httpx.post(
            f"{NVIDIA_BASE}/embeddings",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"input": "health check", "model": EMBEDDER_MODEL},
            timeout=15,
        )
        ok = r.status_code == 200 and "data" in r.json()
        results.append(check(EMBEDDER_MODEL + " (endpoint)", ok,
                             "dim=" + str(len(r.json()["data"][0]["embedding"])) if ok else f"HTTP {r.status_code}"))
    except Exception as e:
        results.append(check(EMBEDDER_MODEL + " (endpoint)", False, str(e)[:80]))

    # 5. Fichiers
    print()
    print("  Fichiers :")
    for f in REQUIRED_FILES:
        results.append(check(f.relative_to(ROOT).as_posix(), f.exists()))

    # 6. Dépendances Python
    print()
    print("  Dependances Python :")
    for mod in REQUIRED_IMPORTS:
        try:
            __import__(mod)
            results.append(check(mod, True))
        except ImportError as e:
            results.append(check(mod, False, str(e)[:80]))

    # Bilan
    print()
    print("=" * 60)
    ok_count = sum(results)
    total = len(results)
    print(f"  {ok_count}/{total} checks OK")
    if ok_count == total:
        print("  NEXUS Crew pret a tourner.")
    else:
        print("  Corrige les [FAIL] avant de lancer le crew.")
    print("=" * 60)
    print()
    return 0 if ok_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
