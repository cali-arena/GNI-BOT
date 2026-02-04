#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simulate news flow: validate correct format and workflow.
On Windows, run with: set PYTHONIOENCODING=utf-8  (or chcp 65001)
Uses fixture payloads (no Ollama/DB required) to test:
- Template A (ANALISE_INTEL) and Template B (FLASH_SETORIAL) render format
- Make webhook payload spec
- Full pipeline can be run with --live (requires docker compose up)
"""
import json
import sys
from pathlib import Path

repo = Path(__file__).resolve().parent.parent
if str(repo) not in sys.path:
    sys.path.insert(0, str(repo))

from apps.worker.render import render, render_intelligence, render_sector_flash
from apps.publisher.whatsapp_make import MakePayload


# Fixture: Template A (ANALISE_INTEL) payload
FIXTURE_TEMPLATE_A = {
    "tema": "Acordo regulatório em apuração",
    "status_confirmacao": "em apuração",
    "leitura_rapida": [
        "Fontes indicam negociação avançada",
        "SEC e empresa em diálogo",
        "Anúncio esperado em breve",
    ],
    "por_que_importa": [
        "Impacto no preço do ativo",
        "Precedente para o setor",
    ],
    "checklist_osint": [
        "Verificar comunicados oficiais",
        "Cruzar com fontes primárias",
        "Aguardar confirmação",
    ],
    "insight_central": "Possível acordo em fase final; monitorar canais oficiais.",
}

# Fixture: Template B (FLASH_SETORIAL) payload
FIXTURE_TEMPLATE_B = {
    "setor": "Crypto",
    "flag_emoji": "🇺🇸",
    "linha_1": "Bitcoin atinge nova máxima institucional.",
    "em_destaque": [
        "ETF aprovado e em alta",
        "Fluxo institucional positivo",
        "Correlação com ações tech",
    ],
    "insight": "Momentum mantém; suporte em 95k.",
}


def test_template_a_format() -> bool:
    """Validate Template A render output."""
    out = render_intelligence(FIXTURE_TEMPLATE_A)
    checks = [
        ("Header", "🚨 GNI — Análise de Inteligência" in out),
        ("Tema:", "Tema:" in out),
        ("Leitura rápida", "Leitura rápida" in out),
        ("Por que isso importa", "Por que isso importa" in out),
        ("checklist OSINT", "Como validar (checklist OSINT)" in out),
        ("Insight central", "Insight central" in out),
        ("Bullets", "\t• " in out),
        ("Checklist prefix", "\t• ✅ " in out),
        ("Separator", out.strip().endswith("⸻")),
    ]
    ok = all(c[1] for c in checks)
    for name, passed in checks:
        print(f"  {'[OK]' if passed else '[FAIL]'} {name}")
    return ok


def test_template_b_format() -> bool:
    """Validate Template B render output."""
    out = render_sector_flash("Crypto", "🇺🇸", FIXTURE_TEMPLATE_B)
    checks = [
        ("Header GNI | Setor", "🚨 GNI |" in out and "Crypto" in out),
        ("Em destaque", "Em destaque:" in out),
        ("Insight", "📌 Insight:" in out),
        ("Bullets", "\t• " in out),
        ("Separator", out.strip().endswith("⸻")),
    ]
    ok = all(c[1] for c in checks)
    for name, passed in checks:
        print(f"  {'[OK]' if passed else '[FAIL]'} {name}")
    return ok


def test_make_payload_format() -> bool:
    """Validate Make webhook payload spec."""
    p = MakePayload(
        text="Test message",
        template="ANALISE_INTEL",
        priority="P1",
        source="CoinDesk",
        url="https://example.com/1",
        item_id=42,
    )
    j = p.to_json()
    checks = [
        ("channel=whatsapp", j.get("channel") == "whatsapp"),
        ("text", "text" in j),
        ("template", j.get("template") == "ANALISE_INTEL"),
        ("priority", j.get("priority") == "P1"),
        ("meta object", isinstance(j.get("meta"), dict)),
        ("meta.source", j.get("meta", {}).get("source") == "CoinDesk"),
        ("meta.url", j.get("meta", {}).get("url") == "https://example.com/1"),
        ("meta.item_id", j.get("meta", {}).get("item_id") == 42),
    ]
    ok = all(c[1] for c in checks)
    for name, passed in checks:
        print(f"  {'[OK]' if passed else '[FAIL]'} {name}")
    return ok


def test_render_function() -> bool:
    """Validate render() dispatches correctly."""
    msgs_a = render(template="ANALISE_INTEL", payload=FIXTURE_TEMPLATE_A, sector="", flag="")
    msgs_b = render(template="FLASH_SETORIAL", payload=FIXTURE_TEMPLATE_B, sector="Crypto", flag="🇺🇸")
    ok = bool(msgs_a) and bool(msgs_b)
    print(f"  {'[OK]' if ok else '[FAIL]'} Template A returns messages: {len(msgs_a)}")
    print(f"  {'[OK]' if ok else '[FAIL]'} Template B returns messages: {len(msgs_b)}")
    return ok


def main() -> int:
    print("=== Simulating news flow ===\n")

    all_ok = True

    print("1. Template A (ANALISE_INTEL) format:")
    all_ok &= test_template_a_format()
    print()

    print("2. Template B (FLASH_SETORIAL) format:")
    all_ok &= test_template_b_format()
    print()

    print("3. Make webhook payload spec:")
    all_ok &= test_make_payload_format()
    print()

    print("4. Render dispatcher:")
    all_ok &= test_render_function()
    print()

    print("--- Rendered outputs ---\n")
    print("Template A (ANALISE_INTEL):")
    print(render_intelligence(FIXTURE_TEMPLATE_A))
    print("\n" + "─" * 40 + "\n")
    print("Template B (FLASH_SETORIAL):")
    print(render_sector_flash("Crypto", "🇺🇸", FIXTURE_TEMPLATE_B))
    print("\n" + "─" * 40 + "\n")
    print("Make payload (sample):")
    p = MakePayload(
        text=render_intelligence(FIXTURE_TEMPLATE_A)[:200] + "...",
        template="ANALISE_INTEL",
        priority="P1",
        source="CoinDesk",
        url="https://coindesk.com/1",
        item_id=1,
    )
    print(json.dumps(p.to_json(), indent=2, ensure_ascii=False))

    if all_ok:
        print("\n=== ALL FORMAT CHECKS PASSED ===")
        return 0
    print("\n=== SOME CHECKS FAILED ===")
    return 1


if __name__ == "__main__":
    sys.exit(main())
