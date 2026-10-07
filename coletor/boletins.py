# -*- coding: utf-8 -*-
"""Boletins de acompanhamento da alocação publicados pela COMAR: listagem da pasta, reconhecimento de cada boletim e
regra de entrada no painel.

A pasta não tem API: a listagem `folder_listing` do Plone traz cada arquivo com o título e a data da última
modificação. Os arquivos são carregados à mão e o nome já variou (slug trocado, letra faltando, separador, mês por
extenso). Por isso o conteúdo manda: todo PDF novo da pasta (modificado nos últimos DIAS_RECENTES dias e ainda não
lido) é lido, e o que se leu fica em `registro` (dados/boletins.json) para não reler. No boletim, o cabeçalho é um bloco
fixo, repetido em toda página: mês ("Agosto de 2026"), sistema hídrico, campanha, local e UF; e cada açude tem a sua
página ("AÇUDE X"). O nome do arquivo (`nome_boletim`) só serve para os boletins antigos, que não são lidos, e como
prova a mais quando o conteúdo deixa dúvida.

Falso positivo (ligar o boletim de um sistema a outro) é pior que atraso: na dúvida, o boletim não é ligado e vira
pendência (aviso), e o sistema continua com o boletim anterior. Regras em `identificar`.
"""
import html
import io
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import unquote

import requests

from . import config

UA = {"User-Agent": "Mozilla/5.0 (painel-marcos-regulatorios)"}
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ",
       "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}
DIAS_RECENTES = 62
SEMELHANCA = 0.85  # dois nomes de açude ou de sistema acima disto são o mesmo (acento, letra faltando, abreviação)
SEMELHANCA_SLUG = 0.80
_SEM = [unicodedata.normalize("NFKD", m).encode("ascii", "ignore").decode() for m in MESES]
# Variações de nome vistas no Plone ou prováveis numa carga manual: "copy_of_" (cópia), "-1" e " (1)" (reenvio),
# "_v2", "_final", "_retificado"; prefixo "boletim_"; separador _ - . ou espaço; mês em número ou nome (ago, agosto);
# ano com 2 ou 4 dígitos, antes ou depois do mês.
_PREFIXO = re.compile(r"^(copy\d*[_-]of[_-])+|^boletim([_-]de[_-]acompanhamento)?([_-]d[ae][_-]aloca[cç]ao)?[_-]")
_SUFIXO = re.compile(r"([_\- ]*(\(\d+\)|v\d+|final|retificad[oa]|corrigid[oa]|atualizad[oa]|novo|rev\d*|(?<=\d)-\d))+$")
_SEP = r"[_\-. ]"
_SLUG_MES_ANO = re.compile(rf"([a-z0-9_ -]+?){_SEP}+(\d{{1,2}}|[a-z]{{3,9}}){_SEP}*((?:19|20)?\d{{2}})")
_SLUG_ANO_MES = re.compile(rf"([a-z0-9_ -]+?){_SEP}+((?:19|20)\d{{2}}){_SEP}*(\d{{1,2}}|[a-z]{{3,9}})")


def sem_acento(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()


def _mes(t):
    if t.isdigit():
        return int(t) if 1 <= int(t) <= 12 else None
    return next((i + 1 for i, nome in enumerate(_SEM) if len(t) >= 3 and nome.startswith(t)), None)


def nome_boletim(url):
    """(slug, 'AAAA-MM') pelo nome do arquivo, ou None se o nome não tem a forma de boletim."""
    arq = sem_acento(unquote(url)).lower().rsplit("/", 1)[-1]
    if not arq.endswith(".pdf"):
        return None
    base = _PREFIXO.sub("", _SUFIXO.sub("", arq[:-4]))
    for padrao, ordem in ((_SLUG_MES_ANO, (1, 2, 3)), (_SLUG_ANO_MES, (1, 3, 2))):
        m = padrao.fullmatch(base)
        if m:
            slug, mes, ano = (m.group(i) for i in ordem)
            n = _mes(mes)
            if n:
                ano = ano if len(ano) == 4 else "20" + ano
                return re.sub(r"[_ -]+", "-", slug).strip("-"), f"{ano}-{n:02d}"
    return None


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


def ler_texto(texto):
    """O que interessa no texto do boletim: é boletim?, mês, sistema e UF do cabeçalho, campanha e açudes."""
    linhas = [l.strip() for l in texto.replace("\xa0", " ").split("\n")]
    antes = lambda rotulo: next((linhas[i - 1] for i, l in enumerate(linhas) if l == rotulo and i), "")
    i_bol = next((i for i, l in enumerate(linhas) if l.upper().startswith("BOLETIM DE ACOMPANHAMENTO")), None)
    # o mês fica logo antes do título, às vezes partido em duas linhas ("Novembro de" / "2025")
    mes = re.search(r"(" + "|".join(MESES) + r") de\s*((?:19|20)\d{2})\s*$", " ".join(linhas[max(0, i_bol - 2):i_bol]),
                    re.I) if i_bol else None
    # nome do sistema: antes do rótulo "SISTEMA HÍDRICO"; no leiaute "BOLETIM DE ACOMPANHAMENTO DO SISTEMA HÍDRICO",
    # na linha depois da data de "boletim gerado em"
    sistema = antes("SISTEMA HÍDRICO")
    if not sistema:
        g = next((i for i, l in enumerate(linhas) if l.lower().startswith("boletim gerado em")), None)
        seguintes = [l for l in linhas[g + 1:g + 5] if l and not re.fullmatch(r"[\W\d/ ]*", l)] if g is not None else []
        sistema = seguintes[0] if seguintes else ""
    campanha = re.search(r"\b(20\d{2}-20\d{2})\b", texto)
    return {"boletim": i_bol is not None,
            "mes": f"{mes.group(2)}-{MESES.index(mes.group(1).lower()) + 1:02d}" if mes else None,
            "sistema_cab": sistema,
            "ufs": sorted(set(re.findall(r"[A-Z]{2}", antes("UF"))) & UFS),
            "campanha": campanha.group(1) if campanha else None,
            "acudes": sorted(set(a.strip() for a in re.findall(r"AÇUDE ([A-ZÀ-Ú' ().-]+?)\s*(?:\n|Data|$)", texto)))}


def ler_pdf(url, sessao=None):
    from pypdf import PdfReader

    r = (sessao or requests).get(url, headers=UA, timeout=180)
    r.raise_for_status()
    return ler_texto("\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(r.content)).pages))


ABREV = {"ENG": "ENGENHEIRO", "STO": "SANTO", "STA": "SANTA", "MAL": "MARECHAL", "GOV": "GOVERNADOR",
         "DEP": "DEPUTADO", "PRES": "PRESIDENTE", "CEL": "CORONEL", "DR": "DOUTOR"}


def _chave(s):
    """Nome comparável: sem acento nem pontuação, abreviações comuns por extenso (ENG. AVIDOS = ENGENHEIRO ÁVIDOS)."""
    return " ".join(ABREV.get(t, t) for t in re.sub(r"[^A-Z0-9]+", " ", sem_acento(s).upper()).split())


def _parecido(a, b):
    """Semelhança entre dois nomes; algarismo romano ou número diferente nunca é parecido (Andorinha × Andorinha II,
    Jaburu I × Jaburu II, Saco I × Saco II)."""
    a, b = _chave(a), _chave(b)
    if a == b:
        return 1.0
    marcas = lambda s: [t for t in s.split() if re.fullmatch(r"[IVX]+|\d+", t)]
    if marcas(a) != marcas(b):
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _nome_sistema_confere(cab, sistema):
    """Nome do sistema no cabeçalho (às vezes truncado com '…') parecido com o do cadastro."""
    if not cab:
        return False
    if cab.endswith(("…", "...")):
        return _chave(sistema["nome"]).startswith(_chave(cab.rstrip(".…")))
    return _parecido(cab, sistema["nome"]) >= SEMELHANCA


def ufs_do_cadastro(sistema):
    return set(re.findall(r"[A-Z]{2}", sistema["ufs"])) & UFS


def identificar(pdf, sistemas, acudes_por_sistema, slug):
    """(sistema, via, motivo) do boletim. sistema None = não ligar (motivo diz por quê; `via` traz o candidato).

    - "exato": os açudes do PDF são exatamente os do cadastro (nomes sem acento e pontuação). Liga, salvo se a UF do
      cabeçalho contradiz a do sistema.
    - "parecido" (grafia um pouco diferente) e "a_mais" (todos os do cadastro estão no PDF, mais algum): ligam só com
      UF do cabeçalho igual à do sistema E mais uma prova: nome do arquivo parecido com um slug do sistema ou nome do
      sistema no cabeçalho. Sem as duas, não liga.
    - "cabecalho": boletim sem página por açude; liga pelo nome do sistema no cabeçalho, se for um só e a UF não
      contradiz.
    """
    pdf_ac, ufs = pdf["acudes"], set(pdf["ufs"])
    uf_ok = lambda sid: not ufs or bool(ufs & ufs_do_cadastro(sistemas[sid]))
    if not pdf_ac:
        c = [sid for sid, s in sistemas.items() if _nome_sistema_confere(pdf["sistema_cab"], s)]
        if len(c) != 1:
            return None, None, "sem página por açude e o nome do sistema no cabeçalho não aponta um sistema só"
        return (c[0], "cabecalho", None) if uf_ok(c[0]) else (None, c[0], "UF do cabeçalho diferente da do sistema")
    pdf_chaves = {_chave(a) for a in pdf_ac}
    exatos = [sid for sid, cad in acudes_por_sistema.items() if {_chave(a) for a in cad} == pdf_chaves]
    if len(exatos) == 1:
        sid = exatos[0]
        return (sid, "exato", None) if uf_ok(sid) else (None, sid, "UF do cabeçalho diferente da do sistema")
    cands = []
    for sid, cad in acudes_por_sistema.items():
        par = {c: max(pdf_ac, key=lambda p: _parecido(c, p)) for c in cad}  # açude do PDF mais próximo de cada um
        cobre = sum(_parecido(c, p) for c, p in par.items()) / len(cad)
        if cobre >= SEMELHANCA:
            sobra = [p for p in pdf_ac if p not in par.values()]
            cands.append((cobre - 0.5 * len(sobra) / len(pdf_ac), sid, sobra))
    cands.sort(reverse=True)
    if not cands:
        return None, None, "os açudes não batem com nenhum sistema do cadastro"
    if len(cands) > 1 and cands[0][0] - cands[1][0] < 0.15:
        return None, cands[0][1], "os açudes lembram mais de um sistema"
    _, sid, sobra = cands[0]
    via = "a_mais" if sobra else "parecido"
    s = sistemas[sid]
    prova = (slug and max(SequenceMatcher(None, slug, x).ratio() for x in s["slugs"]) >= SEMELHANCA_SLUG) or \
        _nome_sistema_confere(pdf["sistema_cab"], s)
    if not ufs or not uf_ok(sid):
        return None, sid, "açudes só parecidos e a UF do cabeçalho não confirma"
    if not prova:
        return None, sid, "açudes só parecidos e nem o nome do arquivo nem o cabeçalho confirmam o sistema"
    return sid, via, None


def _data(modificado):
    try:
        return datetime.strptime(modificado[:10], "%d/%m/%Y").date()
    except (TypeError, ValueError):
        return None


def _pendencia(url, r, sistemas, motivo, candidato):
    ac = ", ".join(r["acudes"]) or "nenhuma página por açude"
    dica = f" Parece ser {sistemas[candidato]['nome']}; não liguei para não arriscar." if candidato else ""
    return (f"Boletim não ligado a nenhum sistema ({motivo}): {url} (mês {r['mes'] or '?'}, cabeçalho "
            f"'{r.get('sistema_cab') or '?'}' / {'-'.join(r.get('ufs') or []) or '?'}, açudes: {ac}).{dica} Se for sistema "
            "novo, cadastrar; se for do cadastro, acrescentar o slug do arquivo ao sistema; se não interessa, acrescentar "
            "o slug em cadastro/slugs_ignorados.csv.")


def classificar(arquivos, sistemas, acudes_por_sistema, ignorados, registro, hoje, ler, dias_recentes=DIAS_RECENTES):
    """Reconhece os boletins da pasta.

    Devolve (boletins, registro, notas, pendencias):
    - boletins: [{url, mes, sistema (None = não ligado), publicado_em, slug, via, acudes, campanha}];
    - registro: resultado da leitura de cada PDF lido (url -> dict), para não reler;
    - notas: o que o vigia resolveu sozinho (vai só para o log);
    - pendencias: o que precisa de alguém (vira aviso).
    """
    slug_sis = {slug: sid for sid, s in sistemas.items() for slug in s["slugs"]}
    boletins, novo, notas, pendencias = [], {}, [], []
    for a in arquivos:
        url = a["url"]
        if not url.lower().endswith(".pdf"):
            continue
        nb = nome_boletim(url)
        slug, mes_nome = nb if nb else (None, None)
        if slug in ignorados:
            continue
        mod = _data(a["modificado"])
        r = registro.get(url)
        if r is None and mod and (hoje - mod).days <= dias_recentes:
            pdf = ler(url)
            r = {"boletim": pdf["boletim"]}
            if pdf["boletim"]:
                sid, via, motivo = identificar(pdf, sistemas, acudes_por_sistema, slug)
                r.update(mes=pdf["mes"] or mes_nome, sistema=sid, via=via if sid else None, acudes=pdf["acudes"],
                         campanha=pdf["campanha"], sistema_cab=pdf["sistema_cab"], ufs=pdf["ufs"])
                nome = sistemas[sid]["nome"] if sid else None
                if sid is None:
                    pendencias.append(_pendencia(url, r, sistemas, motivo, via))
                elif via == "a_mais":
                    pendencias.append(f"Boletim de {nome} com açude que não está no cadastro ({', '.join(pdf['acudes'])}); "
                                      f"o boletim foi ligado ao sistema, falta cadastrar o açude: {url}")
                elif via == "parecido":
                    notas.append(f"Boletim de {nome} com nome de açude grafado diferente ({', '.join(pdf['acudes'])}): {url}")
                if sid and slug_sis.get(slug) != sid:
                    notas.append(f"Boletim de {nome} reconhecido pelo conteúdo (nome do arquivo fora do padrão): {url}")
                if mes_nome and pdf["mes"] and mes_nome != pdf["mes"]:
                    notas.append(f"Mês no nome ({mes_nome}) diferente do cabeçalho ({pdf['mes']}); valeu o cabeçalho: {url}")
        if r is not None:
            novo[url] = r
            if r["boletim"] and r.get("mes"):
                boletins.append({"url": url, "mes": r["mes"], "sistema": r.get("sistema"), "publicado_em": a["modificado"],
                                 "slug": slug, "via": r.get("via"), "acudes": r.get("acudes"), "campanha": r.get("campanha")})
        elif nb:
            boletins.append({"url": url, "mes": mes_nome, "sistema": slug_sis.get(slug), "publicado_em": a["modificado"],
                             "slug": slug, "via": "nome", "acudes": None, "campanha": None})
    teto = hoje.strftime("%Y-%m")
    return [b for b in boletins if b["mes"] <= teto], novo, notas, pendencias


def ultimo_por_sistema(boletins):
    """sistema -> boletim mais recente (pelo mês de referência e, no empate, pela data de publicação)."""
    saida = {}
    chave = lambda b: (b["mes"], _data(b["publicado_em"]) or datetime.min.date())
    for b in boletins:
        sid = b["sistema"]
        if sid and (sid not in saida or chave(b) > chave(saida[sid])):
            saida[sid] = b
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


def hoje_brasilia():
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo(config.FUSO))
