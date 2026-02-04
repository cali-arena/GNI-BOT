"""Snapshot tests for render.py: compare rendered output vs expected Portuguese templates."""
import pytest

from apps.worker.render import (
    WHATSAPP_MAX_CHARS,
    render_intelligence,
    render_intelligence_messages,
    render_sector_flash,
    render_sector_flash_messages,
    render,
)


# --- Snapshot: Template A (ANALISE_INTEL) - new generator JSON ---
SNAPSHOT_INTEL_NEW = """🚨 GNI — Análise de Inteligência

Tema:
Acordo regulatório em apuração

Leitura rápida
\t• Fontes indicam negociação avançada
\t• SEC e empresa em diálogo
\t• Anúncio esperado em breve

Por que isso importa
\t• Impacto no preço do ativo
\t• Precedente para o setor

Como validar (checklist OSINT)
\t• ✅ Verificar comunicados oficiais
\t• ✅ Cruzar com fontes primárias
\t• ✅ Aguardar confirmação

Insight central
Possível acordo em fase final; monitorar canais oficiais.

⸻"""


def test_render_intelligence_template_a_snapshot():
    """Snapshot: Template A exact format (new generator JSON)."""
    payload = {
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
    out = render_intelligence(payload)
    assert out == SNAPSHOT_INTEL_NEW


def test_render_intelligence_legacy_snapshot():
    """Snapshot: Template A legacy payload (headline/body)."""
    payload = {
        "headline": "Unconfirmed reports of SEC settlement",
        "body": "Rumor suggests deal close; sources say announcement expected soon.",
    }
    out = render_intelligence(payload)
    assert out.startswith("🚨 GNI — Análise de Inteligência")
    assert "Tema:" in out
    assert "\t• " in out
    assert out.strip().endswith("⸻")


def test_render_intelligence_bullets_only():
    """Template A with bullets list only (legacy)."""
    payload = {"bullets": ["Point one", "Point two"]}
    out = render_intelligence(payload)
    assert out.startswith("🚨 GNI — Análise de Inteligência")
    assert "\t• Point one" in out
    assert "\t• Point two" in out
    assert out.strip().endswith("⸻")


# --- Snapshot: Template B (FLASH_SETORIAL) - new generator JSON ---
SNAPSHOT_FLASH_NEW = """🚨 GNI | Crypto 📌

Parceria Bank X e Crypto Y anunciada

Em destaque:
\t• Nova capacidade para clientes institucionais
\t• Integração com sistemas tradicionais
\t• Lançamento previsto para Q2

📌 Insight: Movimento importante para adoção institucional do setor.

⸻"""


def test_render_sector_flash_template_b_snapshot():
    """Snapshot: Template B exact format (new generator JSON)."""
    payload = {
        "setor": "Crypto",
        "flag_emoji": "📌",
        "linha_1": "Parceria Bank X e Crypto Y anunciada",
        "em_destaque": [
            "Nova capacidade para clientes institucionais",
            "Integração com sistemas tradicionais",
            "Lançamento previsto para Q2",
        ],
        "insight": "Movimento importante para adoção institucional do setor.",
    }
    out = render_sector_flash("Crypto", "Alert", payload)
    assert out == SNAPSHOT_FLASH_NEW


def test_render_sector_flash_legacy_snapshot():
    """Snapshot: Template B legacy payload (headline/body)."""
    payload = {
        "headline": "Partnership announcement: Bank X and Crypto Y",
        "body": "New capability unveiled for institutional clients.",
    }
    out = render_sector_flash("Crypto", "Alert", payload)
    assert out.startswith("🚨 GNI | Crypto")
    assert "Em destaque:" in out
    assert "\t• " in out
    assert out.strip().endswith("⸻")


def test_render_sector_flash_flag_empty():
    """Template B with empty flag still shows sector."""
    payload = {"headline": "Market update"}
    out = render_sector_flash("Macro", "", payload)
    assert out.startswith("🚨 GNI | Macro")


def test_render_sector_flash_uses_payload_setor_flag():
    """Template B uses setor and flag_emoji from payload when present."""
    payload = {
        "setor": "Macro",
        "flag_emoji": "🔴",
        "linha_1": "Atualização",
        "em_destaque": ["A", "B", "C"],
        "insight": "Insight.",
    }
    out = render_sector_flash("Crypto", "Alert", payload)
    assert out.startswith("🚨 GNI | Macro 🔴")


# --- WhatsApp split: WHATSAPP_MAX_CHARS (default 3500) ---
def test_render_intelligence_messages_under_limit_returns_one():
    """Under WHATSAPP_MAX_CHARS: single message."""
    payload = {"headline": "Short", "body": "Brief."}
    msgs = render_intelligence_messages(payload, max_length=4096)
    assert len(msgs) == 1
    assert msgs[0] == render_intelligence(payload)


def test_render_intelligence_messages_over_limit_splits_two():
    """Over limit: split into multiple messages; header in first part only. Each part <= max_length."""
    long_body = "x" * 4100
    payload = {"headline": "Title", "body": long_body}
    msgs = render_intelligence_messages(payload, max_length=100)
    assert len(msgs) >= 2
    assert msgs[0].startswith("🚨 GNI — Análise de Inteligência")
    for m in msgs[1:]:
        assert "🚨 GNI — Análise de Inteligência" not in m
    for m in msgs:
        assert len(m) <= 100


def test_render_sector_flash_messages_over_limit_splits_two():
    """Template B over limit: split into multiple messages; header in first part only. Each part <= max_length."""
    long_body = "y" * 200
    payload = {"headline": "Flash", "body": long_body}
    msgs = render_sector_flash_messages("Crypto", "Alert", payload, max_length=80)
    assert len(msgs) >= 2
    assert msgs[0].startswith("🚨 GNI | Crypto Alert")
    for m in msgs[1:]:
        assert "🚨 GNI |" not in m
    for m in msgs:
        assert len(m) <= 80


# --- render() dispatch ---
def test_render_analise_intel_dispatches_to_template_a():
    """render(template=ANALISE_INTEL) uses Template A."""
    payload = {
        "tema": "T",
        "leitura_rapida": ["A", "B", "C"],
        "por_que_importa": ["X", "Y"],
        "checklist_osint": ["1", "2", "3"],
        "insight_central": "I",
    }
    msgs = render("ANALISE_INTEL", payload)
    assert len(msgs) == 1
    assert msgs[0].startswith("🚨 GNI — Análise de Inteligência")
    assert "Tema:" in msgs[0]
    assert "Leitura rápida" in msgs[0]
    assert "Como validar (checklist OSINT)" in msgs[0]


def test_render_flash_setorial_dispatches_to_template_b():
    """render(template=FLASH_SETORIAL) uses Template B."""
    payload = {
        "setor": "Crypto",
        "flag_emoji": "📌",
        "linha_1": "Linha",
        "em_destaque": ["A", "B", "C"],
        "insight": "Insight.",
    }
    msgs = render("FLASH_SETORIAL", payload, sector="Macro", flag="Alert")
    assert len(msgs) == 1
    assert msgs[0].startswith("🚨 GNI | Crypto 📌")
    assert "Em destaque:" in msgs[0]
    assert "📌 Insight:" in msgs[0]


def test_render_default_uses_intelligence():
    """render(template=DEFAULT) uses Template A."""
    payload = {"headline": "Default", "body": "Content"}
    msgs = render("DEFAULT", payload)
    assert len(msgs) == 1
    assert msgs[0].startswith("🚨 GNI — Análise de Inteligência")


def test_whatsapp_max_chars_configurable():
    """WHATSAPP_MAX_CHARS is configurable (default 3500 when env not set)."""
    assert isinstance(WHATSAPP_MAX_CHARS, int)
    assert WHATSAPP_MAX_CHARS > 0
