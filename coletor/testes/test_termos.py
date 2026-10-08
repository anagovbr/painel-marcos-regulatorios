# -*- coding: utf-8 -*-
"""Termos de alocação na página da COMAR: campanha atual, termo publicado (link) e nome do sistema no cadastro.

    py -m pytest coletor/testes
"""
from datetime import date

import pytest
import requests

from coletor import cadastro, termos as T

BASE = T.ALOCACAO


def aba(*sistemas):
    """HTML de uma aba de campanha como o da página: título do sistema e a lista de itens, com ou sem link."""
    corpo = ["<p>Bacia do Rio Teste</p>"]
    for nome, itens in sistemas:
        corpo.append(f"<p>{nome}</p><ul>")
        for rot, url in itens:
            corpo.append(f'<li><a href="{url}">- {rot}</a></li>' if url else f"<li>- {rot}</li>")
        corpo.append("</ul>")
    return '<div id="content-core">' + "".join(corpo) + '</div><div id="viewlet-below-content"></div>'


@pytest.mark.parametrize("url,ano", [(BASE + "pb/2026-2027", 2026), (BASE + "rn/2022-2023-1", 2022),
                                     (BASE + "ba/2016 - 2017", 2016), (BASE + "ba/arquivo", None)])
def test_inicio_da_campanha_pela_url_da_aba(url, ano):
    assert T.inicio_campanha(url) == ano


@pytest.mark.parametrize("hoje,minimo", [(date(2026, 10, 8), 2026), (date(2027, 3, 1), 2026), (date(2027, 6, 30), 2026),
                                         (date(2027, 7, 1), 2027)])
def test_campanha_atual_vira_em_julho(hoje, minimo):
    assert T.ano_minimo(hoje) == minimo


def test_so_conta_termo_com_pdf_linkado():
    h = aba(("Mirorós", [("Boletim de Acompanhamento da Alocação - Agosto/2026", BASE + "miroros_08-2026.pdf"),
                         ("Termo de Alocação de Água 2026 - 2027", BASE + "TermoMiroros.pdf"),
                         ("Convite", BASE + "ConviteMiroros.pdf")]),
            ("Ceraíma", [("Boletim de Acompanhamento da Alocação - Agosto/2026", BASE + "ceraima_08-2026.pdf"),
                         ("Termo de Alocação de Água 2026 - 2027", None)]),          # só o modelo da página
            ("UHE - Pedra", [("Aguardando reunião de alocação 2026-2027", None)]),
            ("Santa Inês", [("Termo de Alocação de Água 2026 - 2027", BASE + "TermoSantaInes.pdf"),
                            ("1º ADITIVO Termo de Alocação de Água 2026 - 2027", BASE + "aditivo.pdf")]),
            ("Rio Javaés", [("Apresentação 2026 - 2027", BASE + "javaes.pdf")]),
            ("Outro", [("Termo de Alocação de Água 2026 - 2027", BASE + "pagina-do-termo")]))  # não é PDF
    assert T.termos_publicados(h) == {"Mirorós": BASE + "TermoMiroros.pdf", "Santa Inês": BASE + "TermoSantaInes.pdf"}


SIS = {"brumado-riacho-do-paulo": {"nome": "Brumado–Riacho do Paulo", "nomes_comar": ""},
       "curema-mae-dagua": {"nome": "Curema–Mãe d'Água", "nomes_comar": ""},
       "sabugi": {"nome": "Sabugi", "nomes_comar": ""},
       "arg-mendubim": {"nome": "Armando Ribeiro Gonçalves–Mendubim", "nomes_comar": "Armando Ribeiro Gonçalves"},
       "pocoes-epitacio-pessoa": {"nome": "Poções–Epitácio Pessoa", "nomes_comar": ""},
       "andorinha-ii": {"nome": "Andorinha II", "nomes_comar": ""}}


@pytest.mark.parametrize("nome,sid", [
    ("Brumado e Riacho do Paulo", "brumado-riacho-do-paulo"),     # travessão no cadastro, "e" na página
    ("Curema e Mãe D'água", "curema-mae-dagua"),
    ("Sabugi (Santo Antônio)", "sabugi"),                         # trecho entre parênteses
    ("Armando Ribeiro Gonçalves", "arg-mendubim"),                # nomes_comar
    ("Poções-Epitácio Pessoa", "pocoes-epitacio-pessoa"),
    ("Andorinha II", "andorinha-ii"),
    ("Andorinha", None),                                          # nome parecido não basta
    ("Andorinha III", None),
    ("Riacho do Paulo", None),
    ("Santo Antônio", None),
])
def test_nome_da_pagina_so_casa_por_igualdade(nome, sid):
    assert T.casar(nome, T.indice_de_nomes(SIS)) == sid


def test_nome_que_casa_com_dois_sistemas_nao_vale():
    sis = {"a": {"nome": "Santa Cruz", "nomes_comar": ""}, "b": {"nome": "Santa Cruz (BA)", "nomes_comar": ""}}
    assert T.casar("Santa Cruz", T.indice_de_nomes(sis)) is None


def fake(paginas, falha=()):
    def baixar(url, sessao=None):
        if any(url.endswith(f) for f in falha):
            raise requests.ConnectionError(url)
        return paginas[url]
    return baixar


def test_ler_usa_so_campanha_atual_avisa_sem_cadastro_e_ignora_os_sem_sar():
    abas = '<a data-url="{0}/2026-2027">2026-2027</a><a data-url="{0}/2025-2026">2025-2026</a>'
    paginas = {
        BASE.rstrip("/"): f'<a href="{BASE}pb">PB</a><a href="{BASE}mg">MG</a>',
        BASE + "pb": abas.format(BASE + "pb"),
        BASE + "pb/2026-2027": aba(("Curema e Mãe d'Água", [("Termo de Alocação de Água 2026 - 2027", BASE + "t1.pdf")]),
                                   ("Condado Novo", [("Termo de Alocação de Água 2026 - 2027", BASE + "t2.pdf")])),
        BASE + "pb/2025-2026": aba(("Sabugi", [("Termo de Alocação de Água 2025 - 2026", BASE + "velho.pdf")])),
        BASE + "mg": abas.format(BASE + "mg"),
        BASE + "mg/2026-2027": aba(("Médio Pardo (machado Mineiro)", [("Termo de Alocação de Água 2026 - 2027",
                                                                        BASE + "t3.pdf")])),
        BASE + "mg/2025-2026": aba(),
    }
    termos, sem_cadastro, notas = T.ler(SIS, date(2026, 10, 8), baixar=fake(paginas))
    assert termos == {"curema-mae-dagua": {"campanha": "2026-2027", "url": BASE + "t1.pdf", "uf": "pb"}}
    assert sem_cadastro == ["Condado Novo"]           # Médio Pardo está em cadastro/sistemas_ignorados.csv
    assert notas == []
    # antes da virada de julho, a campanha que começou no ano anterior ainda vale
    assert "sabugi" in T.ler(SIS, date(2026, 6, 1), baixar=fake(paginas))[0]


def test_uf_que_nao_abre_fica_com_a_leitura_anterior():
    paginas = {BASE.rstrip("/"): f'<a href="{BASE}pb">PB</a>'}
    anterior = {"sabugi": {"campanha": "2026-2027", "url": BASE + "t.pdf", "uf": "pb"},
                "andorinha-ii": {"campanha": "2026-2027", "url": BASE + "a.pdf", "uf": "ba"}}
    termos, _, notas = T.ler(SIS, date(2026, 10, 8), baixar=fake(paginas, falha=("/pb",)), anterior=anterior)
    assert termos == {"sabugi": anterior["sabugi"]} and "PB" in notas[0]


def test_cadastro_real_sem_nome_repetido_entre_sistemas():
    sis = cadastro.sistemas()
    idx = T.indice_de_nomes(sis)
    for sid, s in sis.items():
        assert T.casar(s["nome"], idx) == sid, s["nome"]
