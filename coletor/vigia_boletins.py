# -*- coding: utf-8 -*-
"""Vigia dos boletins da COMAR: atualiza dados/boletins.json e escreve os avisos para a issue do dia.

    py -m coletor.vigia_boletins [--avisos arquivo.md] [--sem-links]

- lê todo PDF novo da pasta e reconhece os boletins pelo conteúdo (coletor/boletins.py), qualquer que seja o nome do
  arquivo; o último boletim de cada sistema do cadastro vai para o painel;
- quais sistemas ficam no painel (regra em config.JANELA_BOLETIM_MESES) e quais entraram ou saíram;
- links do cadastro que deixaram de abrir (uma vez por dia; o vigia roda de hora em hora).

Vira aviso (issue) só o que pede ação ou que o Diego pediu para saber: entrada e saída de sistema, boletim que não
bate com nenhum sistema do cadastro, açudes diferentes dos do cadastro e link fora do ar. O que o vigia resolve
sozinho (boletim novo, nome de arquivo fora do padrão) vai só para o log.
"""
import argparse
import csv
import json
import sys
import time
from datetime import datetime

import requests

from . import boletins as B
from . import cadastro, config

# Só 404 e 410 dizem que o arquivo saiu do ar. O gov.br derruba parte das conexões seguidas vindas do runner do GitHub
# (07/10/2026: 20 de cerca de 70 links com ConnectionError, todos abrindo normalmente fora dele); erro de conexão vai
# para o log e não vira aviso.
QUEBRADO = (404, 410)


def checar_link(url, sessao, tentativas=3):
    erro = None
    for i in range(tentativas):
        try:
            r = sessao.head(url, headers=B.UA, timeout=60, allow_redirects=True)
            if r.status_code in (403, 405):
                r = sessao.get(url, headers=B.UA, timeout=60, stream=True)
                r.close()
            if r.status_code < 500:
                return r.status_code
            erro = r.status_code
        except requests.RequestException as e:
            erro = type(e).__name__
        time.sleep(3 * (i + 1))
    return erro


def ignorados():
    with open(config.RAIZ / "cadastro" / "slugs_ignorados.csv", encoding="utf-8-sig", newline="") as f:
        return {l["slug"]: l["motivo"] for l in csv.DictReader(f, delimiter=";")}


def links_quebrados(sistemas, anterior, avisos, sessao):
    """Página da alocação de cada sistema; avisa só link novo fora do ar."""
    quebrados = {}
    for s_ in sistemas.values():
        url = s_["pagina_comar"]
        if url in quebrados:
            continue
        st = checar_link(url, sessao)
        time.sleep(0.5)
        if st in QUEBRADO:
            quebrados[url] = f"{s_['nome']}: {st}"
        elif st != 200:
            print(f"   link não conferido ({st}): {url}")
    for url, txt in quebrados.items():
        if url not in anterior.get("links_quebrados", {}):
            avisos.append(f"Link da página da alocação que não abre ({txt}): {url}")
    return quebrados


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--avisos", help="grava aqui os avisos (markdown) quando houver")
    ap.add_argument("--sem-links", action="store_true", help="não confere os links do cadastro")
    args = ap.parse_args(argv)

    agora = B.hoje_brasilia()
    sistemas = cadastro.sistemas()
    acudes = {}
    for r in cadastro.reservatorios():
        acudes.setdefault(r["sistema"], set()).add(r["nome_boletim"])
    anterior = json.loads(config.BOLETINS.read_text(encoding="utf-8")) if config.BOLETINS.exists() else {}

    with requests.Session() as s:
        bols, registro, notas, avisos = B.classificar(B.listar_pasta(s), sistemas, acudes, ignorados(),
                                                      anterior.get("registro", {}), agora.date(), lambda u: B.ler_pdf(u, s))
        mais_recente = max(b["mes"] for b in bols)
        ultimos = B.ultimo_por_sistema(bols)
        dentro = B.no_painel(ultimos, mais_recente)
        saida = {sid: {k: b[k] for k in ("mes", "url", "publicado_em", "slug", "via", "campanha", "acudes")}
                 | {"rotulo": B.rotulo_mes(b["mes"]), "no_painel": sid in dentro} for sid, b in sorted(ultimos.items())}
        for sid, b in saida.items():
            ant = anterior.get("sistemas", {}).get(sid, {})
            if ant and ant.get("url") != b["url"]:
                notas.append(f"Boletim novo de {sistemas[sid]['nome']}: {b['rotulo']} — {b['url']}")

        antes = {sid for sid, v in anterior.get("sistemas", {}).items() if v.get("no_painel")}
        if anterior:
            for sid in sorted(dentro - antes):
                avisos.append(f"Entra no painel: **{sistemas[sid]['nome']}** (boletim de {saida[sid]['rotulo']}).")
            for sid in sorted(antes - dentro):
                avisos.append(f"Sai do painel: **{sistemas[sid]['nome']}** "
                              f"(último boletim: {saida.get(sid, {}).get('rotulo', 'nenhum')}).")

        # o vigia roda de hora em hora; os links do cadastro só precisam ser conferidos uma vez por dia
        ultima = anterior.get("links_conferidos_em")
        conferir = not args.sem_links and (not ultima or (agora - datetime.fromisoformat(ultima)).total_seconds() > 20 * 3600)
        if conferir:
            quebrados, ultima = links_quebrados(sistemas, anterior, avisos, s), agora.isoformat(timespec="minutes")
        else:
            quebrados = anterior.get("links_quebrados", {})

    config.BOLETINS.parent.mkdir(parents=True, exist_ok=True)
    novo = {"lido_em": agora.isoformat(timespec="minutes"), "fonte": config.PASTA_COMAR, "mais_recente": mais_recente,
            "janela_meses": config.JANELA_BOLETIM_MESES, "sistemas": saida, "links_quebrados": quebrados,
            "links_conferidos_em": ultima, "registro": registro}
    config.BOLETINS.write_text(json.dumps(novo, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(saida)} sistemas com boletim; {len(dentro)} no painel; boletim mais recente: {mais_recente}; "
          f"{len(registro)} PDFs lidos guardados; {len(avisos)} avisos")
    for n in notas:
        print(" · " + n)
    for a in avisos:
        print(" - " + a)
    if args.avisos and avisos:
        with open(args.avisos, "w", encoding="utf-8") as f:
            f.write("Avisos do vigia dos boletins da COMAR em " + agora.strftime("%d/%m/%Y %H:%M") + ":\n\n")
            f.write("\n".join(f"- [ ] {a}" for a in avisos) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
