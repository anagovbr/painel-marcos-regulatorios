# -*- coding: utf-8 -*-
"""Termos de alocação na página da COMAR: aba de campanha mais recente de cada UF e os termos linkados nela.

O vigia usa isto para avisar quando sai termo novo ou aba de campanha nova. O cadastro (estado hidrológico, vigência,
link do termo) não é atualizado sozinho: o estado é ato oficial e os termos trazem erros de digitação (vigência e
datas de reunião trocadas, em 07/10/2026), então alguém lê o termo antes.
"""
import html
import re

import requests

from . import config
from .boletins import UA

ALOCACAO = config.PAGINA_COMAR + "/alocacao-de-agua/"


def baixar(url, sessao=None):
    r = (sessao or requests).get(url, headers=UA, timeout=120)
    r.raise_for_status()
    return r.text


def abas(html_uf):
    """URLs das abas de campanha de uma página de UF, da mais recente para a mais antiga (ordem da página)."""
    return [u.replace("%20", " ") for u in re.findall(r'data-url="([^"]+)"', html_uf)]


def termos(html_aba):
    """[(sistema, rótulo, url)] dos termos de alocação (PDF) linkados numa aba de campanha."""
    m = re.search(r'id="content-core"(.*?)(<div id="viewlet-below-content"|<footer)', html_aba, re.S)
    c = m.group(1) if m else html_aba
    c = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>',
               lambda x: "\x01" + re.sub("<[^>]+>", "", x.group(2)).strip() + "\x02" + x.group(1) + "\x03", c, flags=re.S)
    c = re.sub(r"<(br|p|li|h\d|tr|div|td)[^>]*>", "\n", c)
    c = html.unescape(re.sub(r"<[^>]+>", "", c)).replace("\xa0", " ")
    sistema, saida = None, []
    for linha in c.split("\n"):
        s = linha.strip()
        links = re.findall(r"\x01([^\x02]*)\x02([^\x03]*)\x03", s)
        if not s or s == ">":
            continue
        if not links and not s.startswith("-") and not s.lower().startswith("bacia") and len(s) < 80:
            sistema = s
        for rot, url in links:
            if re.search(r"termo", rot, re.I) and url.lower().endswith(".pdf"):
                saida.append((sistema, rot.strip(" -"), url))
    return saida
