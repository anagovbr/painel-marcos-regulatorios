# -*- coding: utf-8 -*-
"""Vigia dos boletins da COMAR: atualiza dados/boletins.json e escreve os avisos para a issue do dia.

    py -m coletor.vigia_boletins [--avisos arquivo.md] [--sem-links]

- último boletim de cada sistema do cadastro (link, mês, data de publicação, campanha e açudes do PDF);
- quais sistemas ficam no painel (regra em config.JANELA_BOLETIM_MESES) e quais entraram ou saíram;
- boletim recente de slug que não está no cadastro nem na lista de ignorados (sistema novo a cadastrar);
- açudes do boletim diferentes dos do cadastro;
- links do cadastro que deixaram de abrir (só os novos, para não repetir o aviso todo dia).
"""
import argparse
import csv
import json
import sys

import requests

from . import boletins as B
from . import cadastro, config


def checar_link(url, sessao):
    try:
        r = sessao.head(url, headers=B.UA, timeout=60, allow_redirects=True)
        if r.status_code in (403, 405):
            r = sessao.get(url, headers=B.UA, timeout=60, stream=True)
        return r.status_code
    except requests.RequestException as e:
        return type(e).__name__


def ignorados():
    with open(config.RAIZ / "cadastro" / "slugs_ignorados.csv", encoding="utf-8-sig", newline="") as f:
        return {l["slug"]: l["motivo"] for l in csv.DictReader(f, delimiter=";")}


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--avisos", help="grava aqui os avisos (markdown) quando houver")
    ap.add_argument("--sem-links", action="store_true", help="não confere os links do cadastro")
    args = ap.parse_args(argv)

    agora = B.hoje_brasilia()
    sistemas = cadastro.sistemas()
    acudes_cadastro = {}
    for r in cadastro.reservatorios():
        acudes_cadastro.setdefault(r["sistema"], set()).add(r["nome_boletim"])
    anterior = json.loads(config.BOLETINS.read_text(encoding="utf-8")) if config.BOLETINS.exists() else {"sistemas": {}}

    with requests.Session() as s:
        por_slug = B.boletins_por_slug(B.listar_pasta(s), agora.date())
        mais_recente = max(m for v in por_slug.values() for (m, _, _) in v)
        ultimos = B.ultimo_por_sistema(sistemas, por_slug)
        dentro = B.no_painel(ultimos, mais_recente)
        avisos = []

        saida = {}
        for sid, b in sorted(ultimos.items()):
            ant = anterior["sistemas"].get(sid, {})
            if ant.get("url") == b["url"] and "acudes" in ant:
                pdf = {"campanha": ant.get("campanha"), "acudes": ant["acudes"]}
            else:
                pdf = B.ler_pdf(b["url"], s)
                if ant:
                    avisos.append(f"Boletim novo de **{sistemas[sid]['nome']}**: {B.rotulo_mes(b['mes'])} — {b['url']}")
            if pdf["acudes"] and set(pdf["acudes"]) != acudes_cadastro.get(sid, set()):
                avisos.append(f"Açudes do boletim de **{sistemas[sid]['nome']}** ({', '.join(pdf['acudes'])}) diferentes "
                              f"dos do cadastro ({', '.join(sorted(acudes_cadastro.get(sid, [])))}).")
            saida[sid] = {**b, "rotulo": B.rotulo_mes(b["mes"]), **pdf, "no_painel": sid in dentro}

        antes = {sid for sid, v in anterior["sistemas"].items() if v.get("no_painel")}
        for sid in sorted(dentro - antes):
            avisos.append(f"Entra no painel: **{sistemas[sid]['nome']}** (boletim de {saida[sid]['rotulo']}).")
        for sid in sorted(antes - dentro):
            mes = saida.get(sid, {}).get("rotulo", "sem boletim")
            avisos.append(f"Sai do painel: **{sistemas[sid]['nome']}** (último boletim: {mes}).")

        conhecidos = {slug for s_ in sistemas.values() for slug in s_["slugs"]} | set(ignorados())
        for slug, v in sorted(por_slug.items()):
            mes, url, _ = max(v)
            if slug not in conhecidos and B.meses_entre(mes, mais_recente) <= config.JANELA_BOLETIM_MESES:
                avisos.append(f"Boletim recente de sistema fora do cadastro: `{slug}` ({B.rotulo_mes(mes)}) — {url}. "
                              "Cadastrar (açudes e código SAR) ou acrescentar em cadastro/slugs_ignorados.csv.")

        quebrados = {}
        if not args.sem_links:
            for sid, s_ in sistemas.items():
                for campo in ("pagina_comar", "termo_link", "marco_link"):
                    if s_.get(campo):
                        st = checar_link(s_[campo], s)
                        if st != 200:
                            quebrados[s_[campo]] = f"{s_['nome']}, {campo}: {st}"
            ja = set(anterior.get("links_quebrados", {}))
            for url, txt in quebrados.items():
                if url not in ja:
                    avisos.append(f"Link que não abre ({txt}): {url}")
        else:
            quebrados = anterior.get("links_quebrados", {})

    config.BOLETINS.parent.mkdir(parents=True, exist_ok=True)
    novo = {"lido_em": agora.isoformat(timespec="minutes"), "fonte": config.PASTA_COMAR, "mais_recente": mais_recente,
            "janela_meses": config.JANELA_BOLETIM_MESES, "sistemas": saida, "links_quebrados": quebrados}
    config.BOLETINS.write_text(json.dumps(novo, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(saida)} sistemas com boletim; {len(dentro)} no painel; boletim mais recente: {mais_recente}; "
          f"{len(avisos)} avisos")
    for a in avisos:
        print(" -", a)
    if args.avisos and avisos:
        with open(args.avisos, "w", encoding="utf-8") as f:
            f.write("Avisos do vigia dos boletins da COMAR em " + agora.strftime("%d/%m/%Y %H:%M") + ":\n\n")
            f.write("\n".join(f"- [ ] {a}" for a in avisos) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
