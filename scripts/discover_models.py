"""
discover_models.py
==================
Liste tous les modèles disponibles sur ton compte NVIDIA NIM
et identifie lesquels correspondent aux rôles NEXUS.

Usage : python scripts/discover_models.py

Après l'exécution, mets à jour mcp-servers/nexus/models.json
avec les IDs exacts trouvés.
"""

import json
import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Erreur : httpx non installé. Lance : pip install httpx")
    sys.exit(1)

# Charger la clé API depuis .env ou variable d'environnement
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

API_KEY = os.environ.get("NVIDIA_API_KEY", "")
if not API_KEY:
    print("Erreur : NVIDIA_API_KEY non trouvée. Vérifie le fichier .env")
    sys.exit(1)

# Mots-clés pour identifier les modèles d'intérêt
KEYWORDS_OF_INTEREST = [
    "qwen", "kimi", "nemotron", "minimax", "glm", "moonshot",
    "llama", "mistral", "deepseek", "gpt", "nvdev"
]


def fetch_models():
    print("Connexion à NVIDIA NIM...")
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            "https://integrate.api.nvidia.com/v1/models",
            headers={"Authorization": f"Bearer {API_KEY}"}
        )
        if resp.status_code != 200:
            print(f"Erreur {resp.status_code} : {resp.text[:300]}")
            sys.exit(1)
        return resp.json()


def main():
    data = fetch_models()
    models = data.get("data", [])

    print(f"\n{len(models)} modèles disponibles sur ton compte.\n")
    print("=" * 70)

    # Filtrer les modèles d'intérêt
    relevant = []
    for m in models:
        model_id = m.get("id", "")
        if any(kw in model_id.lower() for kw in KEYWORDS_OF_INTEREST):
            relevant.append(model_id)

    print(f"\nModèles pertinents pour NEXUS ({len(relevant)}) :\n")
    for mid in sorted(relevant):
        print(f"  {mid}")

    print("\n" + "=" * 70)
    print("\nTous les modèles disponibles :")
    print()
    for m in sorted(models, key=lambda x: x.get("id", "")):
        print(f"  {m.get('id', '?')}")

    print("\n" + "=" * 70)
    print("\nRôles NEXUS suggérés :")
    print()

    # Suggestions intelligentes
    roles = {
        "qwen": next((m for m in relevant if "qwen" in m.lower()), None),
        "kimi": next((m for m in relevant if "kimi" in m.lower()), None),
        "nemotron": next((m for m in relevant if "nemotron" in m.lower()), None),
        "gpt_oss": next((m for m in relevant if "llama" in m.lower() and ("405" in m or "120" in m or "70" in m)), None),
        "minimax": next((m for m in relevant if "minimax" in m.lower()), None),
        "glm": next((m for m in relevant if "glm" in m.lower()), None),
    }

    for role, model_id in roles.items():
        status = "✅" if model_id else "❌ Non trouvé"
        print(f"  {role:12s} → {model_id or 'À chercher manuellement'} {status}")

    # Écrire un models.json mis à jour
    models_file = Path(__file__).parent.parent / "mcp-servers" / "nexus" / "models.json"
    if models_file.exists():
        current = json.loads(models_file.read_text(encoding="utf-8"))
        updated = False
        for role, model_id in roles.items():
            if model_id and role in current and not current[role].get("confirmed", False):
                current[role]["id"] = model_id
                current[role]["confirmed"] = True
                current[role].pop("note", None)
                updated = True

        if updated:
            current["_last_updated"] = "2026-04-07 (auto-discover)"
            models_file.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
            print("\n✅ models.json mis à jour automatiquement avec les IDs confirmés.")
        else:
            print("\n⚠ models.json non modifié (tous déjà confirmés ou non trouvés).")


if __name__ == "__main__":
    main()
