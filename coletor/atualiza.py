# -*- coding: utf-8 -*-
"""Junta cadastro, boletins e a última medição de cada açude no contrato docs/dados/painel.json.

    py -m coletor.atualiza            grava o painel.json (só se o conteúdo mudou)
    py -m coletor.atualiza --seco     mostra a tabela e não grava
    py -m coletor.atualiza --comparar sar_portal sar_novo
                                      lê as duas fontes e lista as diferenças, valor a valor (para trocar de fonte)

Os alertas ficam ao lado do valor e nunca o alteram: o painel mostra o que o SAR publica. Se algum açude do cadastro
não casar com a fonte, a rodada falha e o painel.json anterior fica como está.
"""
import argparse
import json
import sys

from . import boletins as B
from . import cadastro, config, fontes

# Versão enxuta (Diego, 07/10/2026): medição do SAR, boletim e página da alocação. O modelo com estado hidrológico,
# termo e resolução está no branch modelo-completo, para quando a COMAR pedir.
CAMPOS_SISTEMA = ("nome", "ufs", "pagina_comar", "nota")
CAMPOS_RESERVATORIO = ("res_id", "sistema", "nome", "uf", "lat", "lon")


def na_janela(m, hoje):
    """A medição que o painel mostra: a regra do SAR (JANELA_MEDICAO_DIAS) vale para qualquer fonte, salvo quando
    BUSCA_MEDICAO_ANTERIOR_DIAS manda mostrar a última medição mais antiga (com o aviso da idade)."""
    if m is None or m["data"] is None:
        return None
    idade = (hoje - m["data"]).days
    limite = config.BUSCA_MEDICAO_ANTERIOR_DIAS or config.JANELA_MEDICAO_DIAS
    return m if idade <= limite else None


def alertas(m, hoje):
    if m is None or m["data"] is None:
        return ["sem_informacao"]
    a = []
    if m["data"] > hoje:
        a.append("data_futura")
    elif (hoje - m["data"]).days > config.JANELA_MEDICAO_DIAS:
        a.append("medicao_antiga")
    if m["volume_pct"] is not None and not 0 <= m["volume_pct"] <= config.VOLUME_PCT_MAXIMO:
        a.append("volume_fora_da_faixa")
    return a


def montar(sistemas, reservatorios, bol, medicoes, fonte, agora):
    hoje = agora.date()
    no_painel = [sid for sid in sistemas if bol["sistemas"].get(sid, {}).get("no_painel")]
    sis = []
    for sid in no_painel:
        b = bol["sistemas"][sid]
        sis.append({"id": sid, **{k: sistemas[sid][k] for k in CAMPOS_SISTEMA},
                    "boletim": {k: b.get(k) for k in ("mes", "rotulo", "url", "publicado_em", "campanha")}})
    res = []
    for r in reservatorios:
        if r["sistema"] not in no_painel:
            continue
        m = na_janela(medicoes.get(r["res_id"]), hoje)
        med = None
        if m and m["data"]:
            med = {**m, "data": m["data"].isoformat(), "dias": (hoje - m["data"]).days}
        res.append({**{k: r[k] for k in CAMPOS_RESERVATORIO}, "medicao": med, "alertas": alertas(m, hoje)})
    return {
        "versao": 1,
        "gerado_em": agora.isoformat(timespec="minutes"),
        "fontes": {
            "medicao": {"nome": fonte.NOME, "url": fonte.URL_PUBLICA, "lido_em": agora.isoformat(timespec="minutes")},
            "boletins": {"nome": "Agência Nacional de Águas e Saneamento Básico (ANA) – Coordenação de Marcos Regulatórios "
                                 "e Alocação de Água (COMAR)", "url": config.PAGINA_COMAR, "lido_em": bol["lido_em"]},
        },
        "criterio": {"boletim_mais_recente": bol["mais_recente"], "rotulo": B.rotulo_mes(bol["mais_recente"]),
                     "janela_meses": bol["janela_meses"], "janela_medicao_dias": config.JANELA_MEDICAO_DIAS,
                     "busca_medicao_dias": config.BUSCA_MEDICAO_ANTERIOR_DIAS},
        "sistemas": sis,
        "reservatorios": res,
    }


def sem_hora(p):
    """O conteúdo que importa para decidir se grava: tudo menos as horas de leitura."""
    q = json.loads(json.dumps(p))
    q.pop("gerado_em", None)
    for f in q["fontes"].values():
        f.pop("lido_em", None)
    return q


def comparar(nome_a, nome_b, reservatorios, hoje):
    a = fontes.carregar(nome_a).ultimas_medicoes(reservatorios, hoje)
    b = fontes.carregar(nome_b).ultimas_medicoes(reservatorios, hoje)
    difs = 0
    for r in reservatorios:
        ma, mb = a.get(r["res_id"]), b.get(r["res_id"])
        for k in fontes.MEDICAO:
            va, vb = (ma or {}).get(k), (mb or {}).get(k)
            if va != vb:
                difs += 1
                print(f"{r['res_id']} {r['nome']}: {k} {nome_a}={va} {nome_b}={vb}")
    print(f"{difs} diferenças em {len(reservatorios)} reservatórios")
    return 1 if difs else 0


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--seco", action="store_true")
    ap.add_argument("--comparar", nargs=2, metavar=("FONTE_A", "FONTE_B"))
    args = ap.parse_args(argv)

    agora = B.hoje_brasilia()
    sistemas, reservatorios = cadastro.sistemas(), cadastro.reservatorios()
    if args.comparar:
        return comparar(*args.comparar, reservatorios, agora.date())

    bol = json.loads(config.BOLETINS.read_text(encoding="utf-8"))
    entram = [r for r in reservatorios if bol["sistemas"].get(r["sistema"], {}).get("no_painel")]
    fonte = fontes.carregar(config.FONTE)
    medicoes = fonte.ultimas_medicoes(entram, agora.date(), busca_anterior_dias=config.BUSCA_MEDICAO_ANTERIOR_DIAS)
    painel = montar(sistemas, reservatorios, bol, medicoes, fonte, agora)

    for r in painel["reservatorios"]:
        m = r["medicao"] or {}
        print(f"{r['res_id']} {r['nome'][:26]:26s} {r['uf']} {str(m.get('volume_pct')):>7s}% {str(m.get('data')):10s} "
              f"{' '.join(r['alertas'])}")
    print(f"{len(painel['sistemas'])} sistemas, {len(painel['reservatorios'])} reservatórios no painel")
    if args.seco:
        return 0
    if config.PAINEL.exists() and sem_hora(json.loads(config.PAINEL.read_text(encoding="utf-8"))) == sem_hora(painel):
        print("painel.json sem mudança de conteúdo; não gravado")
        return 0
    config.PAINEL.parent.mkdir(parents=True, exist_ok=True)
    config.PAINEL.write_text(json.dumps(painel, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("gravado", config.PAINEL.relative_to(config.RAIZ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
