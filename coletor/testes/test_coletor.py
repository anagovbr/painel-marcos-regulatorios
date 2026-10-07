# -*- coding: utf-8 -*-
"""Testes do coletor: casos sintéticos das regras e conferência do cadastro real.

    py -m pytest coletor/testes
"""
import csv
from datetime import date, datetime

import pytest

from coletor import atualiza, boletins, cadastro, config
from coletor.fontes import MEDICAO, sar_portal

HOJE = date(2026, 10, 7)


# ---------------------------------------------------------------- fonte: API do portal do SAR
def test_num_trata_ausentes_da_api():
    assert [sar_portal.num(v) for v in ("-", "", "null", None, "45.10", "1.034,5")] == [None, None, None, None, 45.1, None]


def test_data_no_formato_que_a_api_aceita():
    assert sar_portal.data_api(HOJE) == "Wed Oct 07 2026 00:00:00 GMT-0300"


def test_casar_por_nome_dentro_da_uf():
    linhas = {"PB": [{"reservatorio": "EPITÁCIO PESSOA"}, {"reservatorio": "SUMÉ"}],
              "PE": [{"reservatorio": "MÃE D'ÁGUA"}]}
    res = [{"res_id": "12172", "nome_sar": "Epitacio Pessoa", "uf": "PB"}]
    assert sar_portal.casar(res, linhas) == {12172: {"reservatorio": "EPITÁCIO PESSOA"}}


def test_casar_falha_quando_nome_nao_existe_ou_repete():
    linhas = {"PB": [{"reservatorio": "SANTO ANTÔNIO"}, {"reservatorio": "SANTO ANTONIO"}]}
    with pytest.raises(sar_portal.CasamentoFalhou):
        sar_portal.casar([{"res_id": 1, "nome_sar": "SANTO ANTÔNIO", "uf": "PB"}], linhas)
    with pytest.raises(sar_portal.CasamentoFalhou):
        sar_portal.casar([{"res_id": 2, "nome_sar": "INEXISTENTE", "uf": "PB"}], linhas)


def test_medicao_tem_as_chaves_do_contrato():
    m = sar_portal.medicao({"data": "07/10/2026", "volumeUtil": "45.10", "volume": "210.41", "capacidade": "466.53",
                            "cota": "370.68"})
    assert tuple(m) == MEDICAO and m["data"] == HOJE and m["volume_pct"] == 45.1
    assert sar_portal.medicao({"data": "-", "volumeUtil": "-"})["data"] is None


# ---------------------------------------------------------------- boletins da COMAR
ARQ = [{"url": f"https://x/alocacao-de-agua/{n}", "modificado": "16/09/2026 16h00"} for n in
       ("pocoes-epitacio_12-2025.pdf", "pocoes-epitacio-pessoa_08-2026.pdf", "sume_08-2026.pdf", "itans_05-2026.pdf",
        "sume_12-2026.pdf", "TermoQualquer.pdf")]


def test_boletins_por_slug_ignora_mes_futuro_e_outros_arquivos():
    p = boletins.boletins_por_slug(ARQ, HOJE)
    assert set(p) == {"pocoes-epitacio", "pocoes-epitacio-pessoa", "sume", "itans"}
    assert [m for m, _, _ in p["sume"]] == ["2026-08"]


def test_ultimo_boletim_junta_os_slugs_do_sistema():
    p = boletins.boletins_por_slug(ARQ, HOJE)
    s = {"epitacio": {"slugs": ["pocoes-epitacio-pessoa", "pocoes-epitacio"]}, "itans": {"slugs": ["itans"]}}
    u = boletins.ultimo_por_sistema(s, p)
    assert u["epitacio"]["mes"] == "2026-08" and u["epitacio"]["slug"] == "pocoes-epitacio-pessoa"


def test_janela_do_painel():
    u = {"a": {"mes": "2026-08"}, "b": {"mes": "2026-06"}, "c": {"mes": "2026-05"}}
    assert boletins.meses_entre("2025-12", "2026-02") == 2
    assert boletins.no_painel(u, "2026-08", janela=2) == {"a", "b"}
    assert boletins.no_painel(u, "2026-08", janela=0) == {"a"}


def test_rotulo_do_mes():
    assert boletins.rotulo_mes("2026-03") == "março de 2026"


# ---------------------------------------------------------------- montagem do painel.json
def M(dia, pct=50.0):
    return {"data": dia, "volume_pct": pct, "volume_hm3": 1.0, "capacidade_hm3": 2.0, "cota_m": 3.0}


@pytest.mark.parametrize("m,esperado", [
    (None, ["sem_medicao"]),
    ({**M(None)}, ["sem_medicao"]),
    (M(date(2026, 10, 8)), ["data_futura"]),
    (M(date(2026, 9, 1)), ["medicao_antiga"]),
    (M(date(2026, 10, 7), 130.0), ["volume_fora_da_faixa"]),
    (M(date(2026, 10, 7), 103.1), []),
])
def test_alertas(m, esperado):
    assert atualiza.alertas(m, HOJE) == esperado


def test_montar_so_publica_sistemas_no_painel_e_nao_altera_valores():
    sistemas = {s: {k: "" for k in atualiza.CAMPOS_SISTEMA} for s in ("dentro", "fora")}
    res = [{k: "" for k in atualiza.CAMPOS_RESERVATORIO} | {"res_id": i, "sistema": s} for i, s in ((1, "dentro"), (2, "fora"))]
    bol = {"lido_em": "x", "mais_recente": "2026-08", "janela_meses": 2,
           "sistemas": {"dentro": {"no_painel": True, "mes": "2026-08"}, "fora": {"no_painel": False}}}

    class Fonte:
        NOME, URL_PUBLICA = "SAR", "https://www.ana.gov.br/sar/"

    p = atualiza.montar(sistemas, res, bol, {1: M(date(2026, 10, 6), 130.0)}, Fonte, datetime(2026, 10, 7, 12))
    assert [s["id"] for s in p["sistemas"]] == ["dentro"]
    assert len(p["reservatorios"]) == 1
    r = p["reservatorios"][0]
    assert r["medicao"]["volume_pct"] == 130.0 and r["medicao"]["dias"] == 1 and r["alertas"] == ["volume_fora_da_faixa"]


# ---------------------------------------------------------------- cadastro real
def test_cadastro_consistente():
    sis, res = cadastro.sistemas(), cadastro.reservatorios()
    assert len({r["res_id"] for r in res}) == len(res), "código SAR repetido"
    assert {r["sistema"] for r in res} == set(sis), "sistema sem açude ou açude sem sistema"
    slugs = [x for s in sis.values() for x in s["slugs"]]
    assert len(slugs) == len(set(slugs)), "slug em mais de um sistema"
    with open(config.RAIZ / "cadastro" / "slugs_ignorados.csv", encoding="utf-8-sig") as f:
        assert not set(slugs) & {l["slug"] for l in csv.DictReader(f, delimiter=";")}
    for r in res:
        assert r["estado"] in ("", "AZUL", "VERDE", "AMARELO", "VERMELHO"), r
        assert r["lat"] and r["lon"], r
        assert not r["estado"] or (r["estado_fonte"] and r["estado_data_ref"]), r
    for s in sis.values():
        assert s["pagina_comar"].startswith(config.PAGINA_COMAR)
        assert not s["termo_link"] or s["vigencia"], s["sistema"]


# ---------------------------------------------------------------- termos na página da COMAR
from coletor import termos  # noqa: E402

ABA = """<div id="content-core"><p>Bacia do rio Paraíba</p><p>Sumé</p>
<p><a href="https://x/sume_08-2026.pdf">- Boletim de Acompanhamento da Alocação - Agosto/2026</a></p>
<p><a href="https://x/TermodeAlocaodeguaSum20262027assinado.pdf">- Termo de Alocação de Água 2026 - 2027</a></p>
<p>Condado</p><p>- Termo de Alocação de Água 2023 - 2024</p></div><footer>"""


def test_termos_da_aba():
    assert termos.termos(ABA) == [("Sumé", "Termo de Alocação de Água 2026 - 2027", "https://x/TermodeAlocaodeguaSum20262027assinado.pdf")]


def test_abas_da_uf_na_ordem_da_pagina():
    h = '<a data-url="https://x/pb/2026-2027"></a><a data-url="https://x/ba/2016%20-%202017"></a>'
    assert termos.abas(h) == ["https://x/pb/2026-2027", "https://x/ba/2016 - 2017"]
