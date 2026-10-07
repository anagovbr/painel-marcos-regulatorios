# -*- coding: utf-8 -*-
"""Reconhecimento dos boletins da COMAR: variações de nome de arquivo, leitura do cabeçalho, grafia diferente dentro do
PDF e, sobretudo, os falsos positivos que não podem acontecer (boletim de um sistema ligado a outro).

    py -m pytest coletor/testes
"""
from datetime import date

import pytest

from coletor import boletins

HOJE = date(2026, 10, 7)


@pytest.mark.parametrize("nome,esperado", [
    # o padrão de hoje e variações de separador, caixa e mês
    ("ceraima_08-2026.pdf", ("ceraima", "2026-08")),
    ("ceraima_08_2026.pdf", ("ceraima", "2026-08")),
    ("Ceraima-08-2026.pdf", ("ceraima", "2026-08")),
    ("CERAIMA_08-2026.PDF", ("ceraima", "2026-08")),
    ("ceraima 08 2026.pdf", ("ceraima", "2026-08")),
    ("ceraima_08.2026.pdf", ("ceraima", "2026-08")),
    ("ceraima_082026.pdf", ("ceraima", "2026-08")),
    ("ceraima_8-2026.pdf", ("ceraima", "2026-08")),
    ("ceraima_08-26.pdf", ("ceraima", "2026-08")),
    ("ceraima_2026-08.pdf", ("ceraima", "2026-08")),
    ("ceraima_ago-2026.pdf", ("ceraima", "2026-08")),
    ("ceraima_ago2026.pdf", ("ceraima", "2026-08")),
    ("ceraima_Agosto_2026.pdf", ("ceraima", "2026-08")),
    ("ceraima_SET-2026.pdf", ("ceraima", "2026-09")),
    ("ceraima_março-2026.pdf", ("ceraima", "2026-03")),
    ("ceraima_marco-2026.pdf", ("ceraima", "2026-03")),
    # o que o Plone e a carga manual acrescentam
    ("copy_of_ceraima_08-2026.pdf", ("ceraima", "2026-08")),
    ("copy2_of_ceraima_08-2026.pdf", ("ceraima", "2026-08")),
    ("ceraima_08-2026-1.pdf", ("ceraima", "2026-08")),
    ("ceraima_08-2026 (1).pdf", ("ceraima", "2026-08")),
    ("ceraima_08-2026_v2.pdf", ("ceraima", "2026-08")),
    ("ceraima_08-2026_retificado.pdf", ("ceraima", "2026-08")),
    ("ceraima_08-2026-final.pdf", ("ceraima", "2026-08")),
    ("boletim_ceraima_08-2026.pdf", ("ceraima", "2026-08")),
    ("boletim-de-acompanhamento-ceraima_08-2026.pdf", ("ceraima", "2026-08")),
    ("pocoes_epitacio_pessoa_08-2026.pdf", ("pocoes-epitacio-pessoa", "2026-08")),
    ("pocoes-epitacio-pessoa_08-2026.pdf", ("pocoes-epitacio-pessoa", "2026-08")),
    ("Blsamo_12.2021.pdf", ("blsamo", "2021-12")),
    ("cerama_08-2026.pdf", ("cerama", "2026-08")),  # letra faltando: o slug não casa e o conteúdo decide
    # não são boletins
    ("ceraima_13-2026.pdf", None),
    ("ceraima_agt-2026.pdf", None),
    ("TermodeAlocaodeguaSum20262027assinado.pdf", None),
    ("ApresentaoAASum2026.2027.pdf", None),
    ("ConviteSum_presencial_14jul2026.pdf", None),
    ("Resoluo492020MRCHAMPRO.pdf", None),
])
def test_nome_do_arquivo_tolerante(nome, esperado):
    assert boletins.nome_boletim("https://x/alocacao-de-agua/" + nome) == esperado


def cab(mes, sistema, uf, acudes=(), titulo="BOLETIM DE ACOMPANHAMENTO DE ALOCAÇÃO DE ÁGUA"):
    """Texto como o pypdf extrai de um boletim: uma página por açude, cada uma com o bloco do cabeçalho."""
    pags = [f"AÇUDE {a}\nVolumes Esperados e Observados / Estados Hidrológicos\n0,0\n" for a in acudes] or ["0,0\n"]
    bloco = f"{mes}\n{titulo}\n{sistema}\nSISTEMA HÍDRICO\n2026-2027\nALOCAÇÃO\nLocal\nLOCAL\n{uf}\nUF\n16/09/2026\n"
    return "\n".join(p + bloco for p in pags)


def test_cabecalho_do_boletim():
    t = boletins.ler_texto(cab("Agosto de 2026", "ESTREITO-COVA DA…", "BA-MG", ["ESTREITO", "COVA DA MANDIOCA"]))
    assert t["boletim"] and t["mes"] == "2026-08" and t["ufs"] == ["BA", "MG"]
    assert t["sistema_cab"] == "ESTREITO-COVA DA…" and t["acudes"] == ["COVA DA MANDIOCA", "ESTREITO"]
    bocaina = cab("Março de 2026", "BOCAINA", "PI", titulo="BOLETIM DE ACOMPANHAMENTO DO SISTEMA HÍDRICO")
    assert boletins.ler_texto(bocaina)["mes"] == "2026-03"
    assert not boletins.ler_texto("TERMO DE ALOCAÇÃO DE ÁGUA 2026/2027\nSISTEMA HÍDRICO SUMÉ (PB)")["boletim"]


SIS = {"ceraima": {"nome": "Ceraíma", "ufs": "BA", "slugs": ["ceraima"]},
       "epitacio": {"nome": "Poções–Epitácio Pessoa", "ufs": "PB", "slugs": ["pocoes-epitacio-pessoa", "pocoes-epitacio"]},
       "estreito": {"nome": "Estreito–Cova da Mandioca", "ufs": "BA e MG", "slugs": ["estreito-cova-da-mandioca"]},
       "avidos": {"nome": "Engenheiro Ávidos–São Gonçalo", "ufs": "PB", "slugs": ["avidos-sao-goncalo"]},
       "dutra": {"nome": "Marechal Dutra", "ufs": "RN", "slugs": ["marechal-dutra"]},
       "andorinha": {"nome": "Andorinha II", "ufs": "BA", "slugs": ["andorinha-ii"]},
       "ingazeiras": {"nome": "Ingazeiras", "ufs": "PI", "slugs": ["ingazeiras"]}}
ACU = {"ceraima": {"CERAÍMA"}, "epitacio": {"POÇÕES", "CAMALAÚ", "EPITÁCIO PESSOA"},
       "estreito": {"ESTREITO", "COVA DA MANDIOCA"}, "avidos": {"ENG. AVIDOS", "SÃO GONÇALO"}, "dutra": {"MARECHAL DUTRA"},
       "andorinha": {"ANDORINHA II"}, "ingazeiras": {"INGAZEIRAS"}}
TEXTOS = {  # arquivo -> texto do PDF
    "cerama_08-2026.pdf": cab("Agosto de 2026", "CERAÍMA", "BA", ["CERAÍMA"]),
    "boletim-epitacio-setembro.pdf": cab("Setembro de 2026", "POÇÕES-EPITÁCIO PESSOA", "PB",
                                         ["POÇÕES", "CAMALAÚ", "EPITÁCIO PESSOA"]),
    "marechal-dutra_07-2026.pdf": cab("Agosto de 2026", "MARECHAL DUTRA", "RN"),
    "estreito-cova-da-mandioca_08-2026.pdf": cab("Agosto de 2026", "ESTREITO-COVA DA…", "BA-MG",
                                                 ["ESTREITO", "COVA DA MANDIOCA"]),
    # grafia diferente dentro do PDF
    "ceraima_09-2026.pdf": cab("Setembro de 2026", "CERAIMA", "BA", ["CERAIMA"]),
    "avidos-sao-goncalo_09-2026.pdf": cab("Setembro de 2026", "ENG. ÁVIDOS-SÃO GONÇALO", "PB",
                                          ["ENGENHEIRO ÁVIDOS", "SÃO GONÇALO"]),
    "marechal-dutra_09-2026.pdf": cab("Setembro de 2026", "MARECHAL DUTRA", "RN", ["MARECHAL DUTRA", "DOURADO"]),
    "ceraima_10-2026.pdf": cab("Outubro de 2026", "CERAÍM", "BA", ["CERAÍM"]),
    # nome do arquivo sem relação com o sistema e açude só parecido: falta a segunda prova
    "documento-123_08-2026.pdf": cab("Agosto de 2026", "OUTRO", "BA", ["CERAÍM"]),
    # falsos positivos que não podem acontecer
    "andorinha_08-2026.pdf": cab("Agosto de 2026", "ANDORINHA", "BA", ["ANDORINHA"]),
    "ingazeira_08-2026.pdf": cab("Agosto de 2026", "INGAZEIRA", "PE", ["INGAZEIRA"]),
    "outro-sistema_08-2026.pdf": cab("Agosto de 2026", "OUTRO SISTEMA", "BA", ["CERAIMA DE BAIXO"]),
    "ceraima-x_08-2026.pdf": cab("Agosto de 2026", "CERAÍMA", "CE", ["CERAÍMA"]),
    "novo-sistema_08-2026.pdf": cab("Agosto de 2026", "XIQUE-XIQUE", "BA", ["XIQUE-XIQUE"]),
    "TermoQualquer.pdf": "TERMO DE ALOCAÇÃO DE ÁGUA 2026/2027",
}


def arquivos(nomes, mod="16/09/2026 16h00"):
    return [{"url": f"https://x/alocacao-de-agua/{n}", "modificado": mod} for n in nomes]


def classificar(arq, registro=None):
    lidos = []

    def ler(url):
        lidos.append(url)
        return boletins.ler_texto(TEXTOS[url.rsplit("/", 1)[1]])

    return boletins.classificar(arq, SIS, ACU, {"mucuri": ""}, registro or {}, HOJE, ler), lidos


def um(nome):
    (bols, _, notas, pend), _ = classificar(arquivos([nome]))
    return bols[0], notas, pend


def test_conteudo_reconhece_nome_com_letra_faltando_e_fora_do_padrao():
    b, notas, pend = um("cerama_08-2026.pdf")
    assert (b["sistema"], b["mes"], b["via"]) == ("ceraima", "2026-08", "exato") and not pend and notas
    b, _, pend = um("boletim-epitacio-setembro.pdf")
    assert (b["sistema"], b["mes"]) == ("epitacio", "2026-09") and not pend


def test_mes_do_cabecalho_vale_mais_que_o_do_nome_e_boletim_sem_pagina_por_acude():
    b, notas, _ = um("marechal-dutra_07-2026.pdf")
    assert (b["sistema"], b["mes"], b["via"]) == ("dutra", "2026-08", "cabecalho")
    assert any("Mês no nome" in n for n in notas)


def test_nome_do_sistema_truncado_no_cabecalho():
    b, _, pend = um("estreito-cova-da-mandioca_08-2026.pdf")
    assert b["sistema"] == "estreito" and not pend


def test_grafia_diferente_dentro_do_pdf_liga_com_prova():
    b, _, pend = um("ceraima_09-2026.pdf")  # sem acento: exato
    assert b["sistema"] == "ceraima" and b["via"] == "exato" and not pend
    b, _, pend = um("avidos-sao-goncalo_09-2026.pdf")  # "ENGENHEIRO ÁVIDOS" x "ENG. AVIDOS": abreviação por extenso
    assert b["sistema"] == "avidos" and b["via"] == "exato" and not pend
    b, _, pend = um("ceraima_10-2026.pdf")  # letra faltando no açude: parecido + slug + UF
    assert b["sistema"] == "ceraima" and b["via"] == "parecido" and not pend


def test_acude_so_parecido_sem_segunda_prova_nao_liga():
    b, _, pend = um("documento-123_08-2026.pdf")
    assert b["sistema"] is None and len(pend) == 1 and "Parece ser Ceraíma" in pend[0]


def test_acude_a_mais_liga_e_pede_cadastro():
    b, _, pend = um("marechal-dutra_09-2026.pdf")
    assert b["sistema"] == "dutra" and b["via"] == "a_mais" and len(pend) == 1 and "DOURADO" in pend[0]


@pytest.mark.parametrize("arq,motivo", [
    ("andorinha_08-2026.pdf", "não batem"),        # Andorinha não é Andorinha II
    ("ingazeira_08-2026.pdf", "UF"),               # Ingazeira-PE não é Ingazeiras-PI
    ("outro-sistema_08-2026.pdf", "não batem"),    # açude de nome parecido em outro sistema
    ("ceraima-x_08-2026.pdf", "UF"),               # mesmo nome de açude, outra UF
    ("novo-sistema_08-2026.pdf", "não batem"),     # sistema fora do cadastro
])
def test_falso_positivo_nao_liga_e_avisa(arq, motivo):
    b, _, pend = um(arq)
    assert b["sistema"] is None and len(pend) == 1 and motivo in pend[0]


def test_termo_nao_e_boletim_antigo_vai_pelo_nome_e_nao_rele():
    arq = arquivos(["cerama_08-2026.pdf", "TermoQualquer.pdf"]) + \
        arquivos(["pocoes-epitacio_12-2025.pdf"], "16/01/2026 15h07") + arquivos(["mucuri_08-2026.pdf"])
    (bols, reg, _, pend), lidos = classificar(arq)
    assert len(lidos) == 2 and not pend
    assert reg["https://x/alocacao-de-agua/TermoQualquer.pdf"]["boletim"] is False
    antigo = [b for b in bols if b["slug"] == "pocoes-epitacio"][0]
    assert antigo["sistema"] == "epitacio" and antigo["via"] == "nome"
    _, lidos2 = classificar(arq, reg)
    assert lidos2 == []


def test_ultimo_boletim_do_sistema():
    bols = [{"sistema": "a", "mes": "2026-07", "publicado_em": "10/08/2026 10h00"},
            {"sistema": "a", "mes": "2026-08", "publicado_em": "16/09/2026 10h00"},
            {"sistema": None, "mes": "2026-09", "publicado_em": "16/10/2026 10h00"}]
    assert boletins.ultimo_por_sistema(bols)["a"]["mes"] == "2026-08"


def test_janela_do_painel():
    u = {"a": {"mes": "2026-08"}, "b": {"mes": "2026-06"}, "c": {"mes": "2026-05"}}
    assert boletins.meses_entre("2025-12", "2026-02") == 2
    assert boletins.no_painel(u, "2026-08", janela=2) == {"a", "b"}
    assert boletins.no_painel(u, "2026-08", janela=0) == {"a"}


def test_rotulo_do_mes():
    assert boletins.rotulo_mes("2026-03") == "março de 2026"
