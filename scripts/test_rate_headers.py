#!/usr/bin/env python3
"""
Inspecte les headers de l'API NVIDIA NIM pour trouver les infos rate limit.

Fait un seul appel chat.completions (tout petit) et imprime TOUS les headers
de la reponse. On cherche specifiquement x-ratelimit-* mais on affiche tout
pour ne rien rater (retry-after, x-request-id, etc.).

Usage :
  python scripts/test_rate_headers.py
  python scripts/test_rate_headers.py --model openai/qwen/qwen3.5-397b-a17b
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("ERREUR : httpx non installe.")
    sys.exit(1)

ROOT = Path(__file__).parent.parent
ENV_FILE = ROOT / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get("NVIDIA_API_KEY", "")
if not API_KEY:
    print("ERREUR : NVIDIA_API_KEY manquante")
    sys.exit(1)

NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen/qwen3.5-397b-a17b",
                        help="ID du modele NIM (sans prefixe openai/)")
    args = parser.parse_args()

    # Mini payload : juste assez pour obtenir une reponse
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": "Say 'ok' and nothing else."}],
        "max_tokens": 5,
        "temperature": 0,
    }

    url = f"{NVIDIA_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    print()
    print("=" * 70)
    print("  Probe headers NIM")
    print(f"  Modele : {args.model}")
    print(f"  URL    : {url}")
    print("=" * 70)
    print()

    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=30.0)
    except Exception as e:
        print(f"ERREUR transport : {e}")
        sys.exit(2)

    print(f"  Status : {r.status_code}")
    print()
    print("  --- TOUS les headers de reponse ---")
    # Tri alphabetique pour rendre le diff session-a-session facile
    for k in sorted(r.headers.keys()):
        v = r.headers[k]
        # Troncature si valeur trop longue
        if len(v) > 200:
            v = v[:200] + "..."
        print(f"  {k:30s} : {v}")
    print()

    # Mise en avant ciblee
    print("  --- Headers rate limit detectes ---")
    rate_keys = [k for k in r.headers.keys()
                 if "ratelimit" in k.lower()
                 or "retry" in k.lower()
                 or "x-rate" in k.lower()
                 or k.lower() == "x-requests-remaining"]
    if not rate_keys:
        print("  AUCUN header rate limit expose par NIM.")
        print("  -> Il faudra se rabattre sur : doc officielle + backoff 429 defensif.")
    else:
        for k in sorted(rate_keys):
            print(f"  {k} = {r.headers[k]}")

    print()

    # Resume corps (debug)
    try:
        body = r.json()
        if "usage" in body:
            print(f"  Usage : {body['usage']}")
        if "id" in body:
            print(f"  Request ID : {body['id']}")
        if r.status_code >= 400:
            print(f"  Body (erreur) : {json.dumps(body, indent=2)[:500]}")
    except Exception:
        print(f"  Body brut : {r.text[:300]}")
    print()


if __name__ == "__main__":
    main()
