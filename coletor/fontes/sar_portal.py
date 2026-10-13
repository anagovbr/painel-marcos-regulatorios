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


def linhas_uf(uf, hoje, sessao=None, tentativas=4, espera=15):
    """Linhas da API para uma UF. Erro do servidor (5xx) ou de conexão tenta de novo, esperando 15, 30 e 45 s: a API
    devolve 504 de vez em quando e a rodada seguinte funciona (10 e 13/10/2026, BA)."""
    import time

    s = sessao or requests
    for i in range(tentativas):
        try:
            r = s.get(API + "retornaMedicoes", params={"tipoSistema": 1, "siglaUf": uf, "data": data_api(hoje)}, timeout=120)
            if r.status_code < 500:
                r.raise_for_status()
                return [x for x in r.json() if x.get("reservatorio")]
            erro = requests.HTTPError(f"{r.status_code} para {uf}", response=r)
        except (requests.ConnectionError, requests.Timeout) as e:
            erro = e
        if i < tentativas - 1:
            print(f"   API do SAR ({uf}): {erro}; nova tentativa em {espera * (i + 1)} s")
            time.sleep(espera * (i + 1))
    raise erro


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
    "-" pedindo 07/10 e 22/08/2026 pedindo 20/09).

    UF que a API não respondeu, mesmo depois das novas tentativas de linhas_uf, fica fora do resultado, e quem chama
    mantém a medição anterior dos açudes dela (a API cai por alguns minutos de vez em quando: 13/10/2026, MG, 504 por
    mais de 1,5 min). Só se nenhuma UF responder a falha sobe e a rodada falha."""
    from datetime import timedelta

    def tentar(uf, dia, s):
        try:
            return ler(uf, dia, s)
        except requests.RequestException as e:
            erros.append(e)
            print(f"   API do SAR sem resposta para {uf} ({e}); os açudes de {uf} ficam com a medição anterior")
            return None

    erros = []
    with requests.Session() as s:
        s.headers["User-Agent"] = "painel-marcos-regulatorios (github.com/anagovbr/painel-marcos-regulatorios)"
        por_uf = {}
        for uf in sorted({r["uf"] for r in reservatorios}):
            linhas = tentar(uf, hoje, s)
            if linhas is not None:
                por_uf[uf] = linhas
        if not por_uf:
            raise erros[-1]
        lidos = [r for r in reservatorios if r["uf"] in por_uf]
        saida = {rid: medicao(x) for rid, x in casar(lidos, por_uf).items()}
        recuo = 30
        while recuo <= busca_anterior_dias:
            faltam = [r for r in lidos if int(r["res_id"]) in saida and saida[int(r["res_id"])]["data"] is None]
            if not faltam:
                break
            for uf in sorted({r["uf"] for r in faltam}):
                da_uf = [r for r in faltam if r["uf"] == uf]
                linhas = tentar(uf, hoje - timedelta(days=recuo), s)
                if linhas is None:                       # sem resposta na busca: fica a medição anterior
                    for r in da_uf:
                        saida.pop(int(r["res_id"]), None)
                    continue
                for rid, x in casar(da_uf, {uf: linhas}).items():
                    if data_br(x.get("data")):
                        saida[rid] = medicao(x)
            recuo += 30
    return saida
