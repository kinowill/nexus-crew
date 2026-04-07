"""
test_connection.py
==================
Vérifie que le système NEXUS est opérationnel :
- Connexion NVIDIA NIM
- Test des modèles confirmés (Qwen et Kimi)
- Test de lecture du contexte projet

Usage : python scripts/test_connection.py
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

import asyncio
import json
import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Erreur : httpx non installé. Lance : pip install httpx")
    sys.exit(1)

# Charger la clé depuis .env
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

MODELS_FILE = Path(__file__).parent.parent / "mcp-servers" / "nexus" / "models.json"


def load_models():
    if MODELS_FILE.exists():
        return json.loads(MODELS_FILE.read_text(encoding="utf-8"))
    return {}


async def test_model(model_id: str, label: str) -> bool:
    print(f"  Test {label} ({model_id[:50]})...", end=" ", flush=True)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                NVIDIA_URL,
                headers={"Authorization": f"Bearer {API_KEY}"},
                json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": "Reply with exactly: NEXUS_OK"}],
                    "max_tokens": 20,
                    "temperature": 0,
                }
            )
            if resp.status_code == 200:
                msg = resp.json()["choices"][0]["message"]
                content = msg.get("content") or msg.get("reasoning_content") or str(msg)[:80]
                print(f"OK ({content.strip()[:35]})")
                return True
            else:
                err = resp.json().get("detail") or resp.text[:80]
                print(f"ERREUR HTTP {resp.status_code}: {err[:60]}")
                return False
    except Exception as e:
        print(f"ERREUR {str(e)[:60]}")
        return False


async def main():
    print("\n" + "=" * 60)
    print("  NEXUS — Test de connexion système")
    print("=" * 60 + "\n")

    # 1. Clé API
    if not API_KEY:
        print("❌ NVIDIA_API_KEY manquante. Vérifie le fichier .env")
        sys.exit(1)
    print(f"✅ Clé API NVIDIA trouvée : {API_KEY[:12]}...{API_KEY[-4:]}\n")

    # 2. Test des modèles
    models = load_models()
    confirmed = {
        k: v for k, v in models.items()
        if isinstance(v, dict) and v.get("confirmed") and not k.startswith("_")
    }

    if not confirmed:
        print("⚠ Aucun modèle confirmé dans models.json.")
        print("  Lance d'abord : python scripts/discover_models.py\n")
    else:
        print(f"Test des {len(confirmed)} modèles confirmés :\n")
        results = []
        for role, cfg in confirmed.items():
            ok = await test_model(cfg["id"], f"{role} ({cfg.get('role', '?')})")
            results.append(ok)

        success = sum(results)
        print(f"\n  {success}/{len(results)} modèles opérationnels")

    # 3. Vérification fichiers NEXUS
    print("\nFichiers NEXUS :")
    files_to_check = [
        Path(__file__).parent.parent / "mcp-servers" / "nexus" / "server.py",
        Path(__file__).parent.parent / "mcp-servers" / "nexus" / "models.json",
        Path(__file__).parent.parent / "MASTER.md",
        Path(__file__).parent.parent / ".env",
    ]
    for f in files_to_check:
        status = "✅" if f.exists() else "❌ MANQUANT"
        print(f"  {status}  {f.name}")

    print("\n" + "=" * 60)
    print("  Si tout est ✅, NEXUS est prêt.")
    print("  Relance Claude Code pour activer le MCP.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
