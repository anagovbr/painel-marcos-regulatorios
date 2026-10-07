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


# ---------------------------------------------------------------- montagem do painel.json
def M(dia, pct=50.0):
    return {"data": dia, "volume_pct": pct, "volume_hm3": 1.0, "capacidade_hm3": 2.0, "cota_m": 3.0}


@pytest.mark.parametrize("m,esperado", [
    (None, ["sem_informacao"]),
    ({**M(None)}, ["sem_informacao"]),
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
        assert r["lat"] and r["lon"] and r["nome_sar"] and r["nome_boletim"], r
    for s in sis.values():
        assert s["pagina_comar"].startswith(config.PAGINA_COMAR + "/alocacao-de-agua/"), s["sistema"]


def test_regra_dos_30_dias_do_sar(monkeypatch):
    assert atualiza.na_janela(M(date(2026, 9, 7)), HOJE) is not None      # 30 dias: ainda vale
    assert atualiza.na_janela(M(date(2026, 9, 6)), HOJE) is None          # 31 dias: sem informação
    monkeypatch.setattr(config, "BUSCA_MEDICAO_ANTERIOR_DIAS", 365)
    assert atualiza.na_janela(M(date(2026, 8, 22)), HOJE) is not None     # com a busca ligada, mostra com aviso
    assert atualiza.alertas(M(date(2026, 8, 22)), HOJE) == ["medicao_antiga"]


def test_busca_anterior_recua_30_dias_so_para_quem_falta():
    linha = lambda nome, data: {"reservatorio": nome, "data": data, "volumeUtil": "50", "volume": "1", "capacidade": "2", "cota": "3"}
    pedidos = []

    def ler(uf, d, s):
        pedidos.append(d)
        if d == HOJE:
            return [linha("TREMEDAL", "-"), linha("TRUVISCO", "06/10/2026")]
        if d == date(2026, 9, 7):
            return [linha("TREMEDAL", "-"), linha("TRUVISCO", "06/10/2026")]
        return [linha("TREMEDAL", "22/08/2026"), linha("TRUVISCO", "06/09/2026")]

    res = [{"res_id": 1, "nome_sar": "TREMEDAL", "uf": "BA"}, {"res_id": 2, "nome_sar": "TRUVISCO", "uf": "BA"}]
    sem = sar_portal.ultimas_medicoes(res, HOJE, 0, ler)
    assert sem[1]["data"] is None and pedidos == [HOJE]
    pedidos.clear()
    com = sar_portal.ultimas_medicoes(res, HOJE, 365, ler)
    assert com[1]["data"] == date(2026, 8, 22) and com[2]["data"] == date(2026, 10, 6)
    assert pedidos == [HOJE, date(2026, 9, 7), date(2026, 8, 8)]
