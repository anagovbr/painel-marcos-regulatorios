# -*- coding: utf-8 -*-
"""Boletins de acompanhamento da alocação publicados pela COMAR: listagem da pasta, último boletim de cada sistema e
regra de entrada no painel.

A pasta não tem API: a listagem `folder_listing` do Plone traz cada arquivo com o título e a data da última
modificação. Os boletins seguem o padrão `<slug>_<MM>-<AAAA>.pdf`; o mesmo sistema já mudou de slug ao longo do tempo,
por isso o cadastro guarda todos os slugs de cada sistema.
"""
import html
import io
import re

import requests

from . import config

PADRAO = re.compile(r"/([a-z0-9-]+)_(\d{2})-(\d{4})\.pdf$")
UA = {"User-Agent": "Mozilla/5.0 (painel-marcos-regulatorios)"}
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]


def listar_pasta(sessao=None):
    """Todos os arquivos da pasta: url, título e 'dd/mm/aaaa hhhmm' da última modificação."""
    s = sessao or requests
    arquivos, inicio = [], 0
    while True:
        r = s.get(config.PASTA_COMAR + f"folder_listing?b_size:int=1000&b_start:int={inicio}", headers=UA, timeout=180)
        r.raise_for_status()
        blocos = re.findall(r'<article class="entry">(.*?)</article>', r.text, re.S)
        for b in blocos:
            m = re.search(r'<a href="([^"]+?)(?:/view)?" class="contenttype-[^"]*"[^>]*>([^<]*)</a>', b)
            d = re.search(r"última modificação\s*(\d{2}/\d{2}/\d{4} \d{2}h\d{2})", b)
            if m:
                arquivos.append({"url": m.group(1), "titulo": html.unescape(m.group(2)).strip(),
                                 "modificado": d.group(1) if d else None})
        if len(blocos) < 1000:
            return arquivos
        inicio += 1000


def boletins_por_slug(arquivos, hoje):
    """slug -> lista de (AAAA-MM, url, modificado), ignorando mês de referência no futuro (erro de nome)."""
    saida = {}
    for a in arquivos:
        m = PADRAO.search(a["url"])
        if m:
            mes = f"{m.group(3)}-{m.group(2)}"
            if mes <= hoje.strftime("%Y-%m"):
                saida.setdefault(m.group(1), []).append((mes, a["url"], a["modificado"]))
    return saida


def ultimo_por_sistema(sistemas, por_slug):
    """sistema -> {mes, url, publicado_em, slug} do boletim mais recente entre todos os slugs do sistema."""
    saida = {}
    for sid, s in sistemas.items():
        todos = [(mes, url, mod, slug) for slug in s["slugs"] for (mes, url, mod) in por_slug.get(slug, [])]
        if todos:
            mes, url, mod, slug = max(todos)
            saida[sid] = {"mes": mes, "url": url, "publicado_em": mod, "slug": slug}
    return saida


def meses_entre(a, b):
    """Meses de 'AAAA-MM' a até 'AAAA-MM' b."""
    return (int(b[:4]) - int(a[:4])) * 12 + int(b[5:]) - int(a[5:])


def no_painel(ultimos, mais_recente, janela=None):
    """Sistemas cujo último boletim está dentro da janela, contada do boletim mais recente da pasta."""
    janela = config.JANELA_BOLETIM_MESES if janela is None else janela
    return {sid for sid, b in ultimos.items() if meses_entre(b["mes"], mais_recente) <= janela}


def rotulo_mes(mes):
    return f"{MESES[int(mes[5:]) - 1]} de {mes[:4]}"


def ler_pdf(url, sessao=None):
    """Campanha (AAAA-AAAA) e açudes com página própria ('AÇUDE X') no boletim."""
    from pypdf import PdfReader

    s = sessao or requests
    r = s.get(url, headers=UA, timeout=180)
    r.raise_for_status()
    texto = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(r.content)).pages)
    acudes = sorted(set(a.strip() for a in re.findall(r"AÇUDE ([A-ZÀ-Ú' ().-]+?)\s*(?:\n|Data|$)", texto)))
    campanha = re.search(r"\b(20\d{2}-20\d{2})\b", texto)
    return {"campanha": campanha.group(1) if campanha else None, "acudes": acudes}


def hoje_brasilia():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo(config.FUSO))

