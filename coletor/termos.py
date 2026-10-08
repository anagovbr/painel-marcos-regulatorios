# -*- coding: utf-8 -*-
"""Termos de alocação publicados na página da COMAR: quais sistemas do cadastro têm o termo da campanha atual.

A COMAR quer no painel todo sistema com termo atual, mesmo com o boletim atrasado (08/10/2026). Conta como termo atual
o PDF linkado na aba de uma campanha atual da página da UF (`.../alocacao-de-agua/<uf>/<AAAA-AAAA>`). A página lista
para cada sistema "Boletim / Termo / Apresentação / Convite" e só vira link o que já foi publicado; o item sem link é
só o modelo da página e não conta (Diego, 08/10/2026: entra quando a COMAR publicar o PDF).

Campanha atual: a que começa no ano de `ano_minimo` ou depois. As campanhas levam o nome do ano em que começam (abril a
outubro) e terminam no ano seguinte (março a julho); a partir de julho (`config.VIRADA_CAMPANHA_MES`) só vale a que
começa no próprio ano. O sistema que não renovou o termo continua no painel enquanto tiver boletim recente (regra dos
boletins, `config.JANELA_BOLETIM_MESES`).

O nome do sistema na página liga-se ao cadastro só por igualdade depois de normalizar (sem acento, sem pontuação, sem
"e", "de", "do"..., e também sem o trecho entre parênteses: "Sabugi (Santo Antônio)"). Nome que não bate vai para o
aviso, nunca para um palpite: `nomes_comar` em cadastro/sistemas.csv guarda os outros nomes de um sistema, e
cadastro/sistemas_ignorados.csv os sistemas da página que não entram no painel (sem açude no SAR).
"""
import csv
import html
import re

import requests

from . import config
from .boletins import UA, sem_acento

ALOCACAO = config.PAGINA_COMAR + "/alocacao-de-agua/"
VAZIAS = {"e", "de", "do", "da", "dos", "das", "d", "acude", "acudes", "sistema", "hidrico"}


def baixar(url, sessao=None):
    r = (sessao or requests).get(url.replace(" ", "%20"), headers=UA, timeout=120)
    r.raise_for_status()
    return r.text


def ufs_da_pagina(html_raiz):
    """Páginas de UF listadas na página da alocação de água."""
    return sorted(set(re.findall(r'/alocacao-de-agua/([a-z]{2})"', html_raiz)))


def abas(html_uf):
    """URLs das abas de campanha de uma página de UF, na ordem da página."""
    return [html.unescape(u).replace("%20", " ") for u in re.findall(r'data-url="([^"]+)"', html_uf)]


def inicio_campanha(aba):
    """Ano de início da campanha pelo fim da URL da aba ("2026-2027", "2022-2023-1", "2016 - 2017")."""
    m = re.search(r"(\d{4})\s*-\s*\d{4}", aba.rsplit("/", 1)[-1])
    return int(m.group(1)) if m else None


def ano_minimo(hoje):
    return hoje.year if hoje.month >= config.VIRADA_CAMPANHA_MES else hoje.year - 1


def blocos(html_aba):
    """[(sistema, [(rótulo, url)])] na ordem da aba: cada título de sistema e os links que vêm abaixo dele."""
    m = re.search(r'id="content-core"(.*?)(<div id="viewlet-below-content"|<footer)', html_aba, re.S)
    c = m.group(1) if m else html_aba
    c = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>',
               lambda x: "\x01" + re.sub("<[^>]+>", "", x.group(2)) + "\x02" + x.group(1) + "\x03", c, flags=re.S)
    c = re.sub(r"<(br|p|li|h\d|tr|div|td)[^>]*>", "\n", c)
    c = html.unescape(re.sub(r"<[^>]+>", "", c)).replace("\xa0", " ")
    saida = []
    for linha in c.split("\n"):
        s = re.sub(r"\s+", " ", linha).strip()
        if not s or s == ">":
            continue
        links = [(re.sub(r"\s+", " ", r).strip(" -"), u.strip()) for r, u in re.findall(r"\x01([^\x02]*)\x02([^\x03]*)\x03", s)]
        if links:
            if saida:
                saida[-1][1].extend(links)
        elif not s.startswith("-") and not s.lower().startswith("bacia") and len(s) < 80:
            saida.append((s, []))
    return saida


def termos_publicados(html_aba):
    """{sistema: url do termo} dos sistemas com termo de alocação em PDF linkado na aba (o primeiro, se houver aditivo)."""
    saida = {}
    for nome, links in blocos(html_aba):
        for rot, url in links:
            if re.search(r"\btermo\b", sem_acento(rot), re.I) and url.lower().split("?")[0].endswith(".pdf"):
                saida.setdefault(nome, url)
    return saida


def chave(nome):
    # pontuação vira espaço antes de tirar o acento: "Brumado–Riacho" perderia o travessão e grudaria as palavras
    t = re.sub(r"[^a-z0-9]+", " ", sem_acento(re.sub(r"[^\w]+", " ", nome)).lower()).split()
    return " ".join(x for x in t if x not in VAZIAS)


def chaves(nome):
    """O nome inteiro e o nome sem o trecho entre parênteses."""
    sem_par = re.sub(r"\([^)]*\)", " ", nome)
    return {k for k in (chave(nome), chave(sem_par)) if k}


def indice_de_nomes(sistemas):
    """chave normalizada -> sistema do cadastro (nome e `nomes_comar`); chave repetida em dois sistemas não vale."""
    idx, repetidas = {}, set()
    for sid, s in sistemas.items():
        for nome in [s["nome"], *[x for x in (s.get("nomes_comar") or "").split("|") if x]]:
            for k in chaves(nome):
                if idx.get(k, sid) != sid:
                    repetidas.add(k)
                idx[k] = sid
    return {k: v for k, v in idx.items() if k not in repetidas}


def ignorados():
    with open(config.RAIZ / "cadastro" / "sistemas_ignorados.csv", encoding="utf-8-sig", newline="") as f:
        return {k for l in csv.DictReader(f, delimiter=";") for k in chaves(l["nome_comar"])}


def casar(nome, indice):
    achados = {indice[k] for k in chaves(nome) if k in indice}
    return achados.pop() if len(achados) == 1 else None


def ler(sistemas, hoje, sessao=None, anterior=None, baixar=baixar):
    """Lê as abas de campanha atual de todas as UFs.

    Devolve (termos, sem_cadastro, notas): termos = {sistema: {"campanha", "url", "uf"}}; sem_cadastro = nomes da página
    com termo atual que não batem com o cadastro nem com os ignorados. UF que não abriu fica com a leitura anterior
    (`anterior`, o "termos" do dados/boletins.json) e vai para as notas do log.
    """
    anterior = anterior or {}
    minimo = ano_minimo(hoje)
    indice, fora = indice_de_nomes(sistemas), ignorados()
    termos, sem_cadastro, notas = {}, set(), []
    for uf in ufs_da_pagina(baixar(ALOCACAO.rstrip("/"), sessao)):
        try:
            atuais = [a for a in abas(baixar(ALOCACAO + uf, sessao)) if (inicio_campanha(a) or 0) >= minimo]
            achados = {}
            for aba in atuais:
                for nome, url in termos_publicados(baixar(aba, sessao)).items():
                    achados.setdefault(nome, (aba, url))
        except requests.RequestException as e:
            notas.append(f"Termos de {uf.upper()} não lidos ({type(e).__name__}); fica a leitura anterior.")
            termos.update({sid: t for sid, t in anterior.items() if t.get("uf") == uf and sid not in termos})
            continue
        for nome, (aba, url) in achados.items():
            sid = casar(nome, indice)
            if sid:
                campanha = aba.rsplit("/", 1)[-1]
                if sid not in termos or campanha > termos[sid]["campanha"]:
                    termos[sid] = {"campanha": campanha, "url": url, "uf": uf}
            elif not chaves(nome) & fora:
                sem_cadastro.add(nome)
    return termos, sorted(sem_cadastro), notas
