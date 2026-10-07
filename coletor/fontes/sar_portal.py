# -*- coding: utf-8 -*-
"""API do portal do SAR (www.ana.gov.br/sar/restportal/api/), em uso até a chegada do novo SAR.

retornaMedicoes devolve, para cada reservatório da UF, a ÚLTIMA medição com a sua data (não o valor do dia pedido);
o campo `codigo` vem nulo, então o casamento é pelo nome dentro da UF (coluna nome_sar do cadastro). Valor ausente
vem como "-", "" ou "null". Para o tipoSistema 1 (Nordeste e Semiárido) a API pede siglaUf.
"""
import re
import unicodedata
from datetime import datetime

import requests

API = "https://www.ana.gov.br/sar/restportal/api/"
NOME = "SAR – Sistema de Acompanhamento de Reservatórios (ANA)"
URL_PUBLICA = "https://www.ana.gov.br/sar/"


class CasamentoFalhou(Exception):
    """Nome do cadastro que não casa com exatamente uma linha da API."""


def chave(nome):
    s = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]+", " ", s).strip()


def data_api(d):
    """A API espera a data no formato do Date.toString() do JavaScript."""
    return datetime(d.year, d.month, d.day).strftime("%a %b %d %Y 00:00:00 GMT-0300")


def num(v):
    if v in (None, "-", "", "null", "NULL"):
        return None
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def data_br(v):
    if v in (None, "-", ""):
        return None
    try:
        return datetime.strptime(v, "%d/%m/%Y").date()
    except ValueError:
        return None


def linhas_uf(uf, hoje, sessao=None):
    s = sessao or requests
    r = s.get(API + "retornaMedicoes", params={"tipoSistema": 1, "siglaUf": uf, "data": data_api(hoje)}, timeout=120)
    r.raise_for_status()
    return [x for x in r.json() if x.get("reservatorio")]


def medicao(x):
    return {"data": data_br(x.get("data")), "volume_pct": num(x.get("volumeUtil")), "volume_hm3": num(x.get("volume")),
            "capacidade_hm3": num(x.get("capacidade")), "cota_m": num(x.get("cota"))}


def casar(reservatorios, linhas_por_uf):
    """res_id -> linha da API; falha se algum nome não casar com exatamente uma linha da sua UF."""
    saida, erros = {}, []
    for r in reservatorios:
        achadas = [x for x in linhas_por_uf.get(r["uf"], []) if chave(x["reservatorio"]) == chave(r["nome_sar"])]
        if len(achadas) != 1:
            erros.append(f"{r['res_id']} '{r['nome_sar']}' ({r['uf']}): {len(achadas)} linhas na API")
        else:
            saida[int(r["res_id"])] = achadas[0]
    if erros:
        raise CasamentoFalhou("; ".join(erros))
    return saida


def ultimas_medicoes(reservatorios, hoje, busca_anterior_dias=0, ler=linhas_uf):
    """Última medição de cada açude. A API devolve a medição mais próxima da data pedida dentro de 30 dias (regra do
    SAR) e "-" fora disso. Com busca_anterior_dias > 0, o açude sem medição é procurado de novo recuando 30 dias por
    vez: como a janela anterior veio vazia, o que a API devolve é a última medição (conferido com Tremedal, 07/10/2026:
    "-" pedindo 07/10 e 22/08/2026 pedindo 20/09)."""
    from datetime import timedelta

    with requests.Session() as s:
        s.headers["User-Agent"] = "painel-marcos-regulatorios (github.com/dlpena/painel-marcos-regulatorios)"
        por_uf = {uf: ler(uf, hoje, s) for uf in sorted({r["uf"] for r in reservatorios})}
        saida = {rid: medicao(x) for rid, x in casar(reservatorios, por_uf).items()}
        recuo = 30
        while recuo <= busca_anterior_dias:
            faltam = [r for r in reservatorios if saida[int(r["res_id"])]["data"] is None]
            if not faltam:
                break
            antes = {uf: ler(uf, hoje - timedelta(days=recuo), s) for uf in sorted({r["uf"] for r in faltam})}
            for rid, x in casar(faltam, antes).items():
                if data_br(x.get("data")):
                    saida[rid] = medicao(x)
            recuo += 30
    return saida
