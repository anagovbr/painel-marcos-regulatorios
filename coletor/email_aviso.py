# -*- coding: utf-8 -*-
"""Envia por e-mail os avisos do vigia e as falhas dos robôs, sem depender das notificações do GitHub.

    python -m coletor.email_aviso --assunto "..." [--arquivo avisos.md] [--texto "..."] [--link URL]

Configuração, como secrets do repositório (Settings > Secrets and variables > Actions), lidos do ambiente:
    AVISO_SMTP_HOST      servidor SMTP (ex.: smtp.gmail.com)
    AVISO_SMTP_PORTA     465 (SSL) ou 587 (STARTTLS); padrão 465
    AVISO_SMTP_USUARIO   conta remetente
    AVISO_SMTP_SENHA     senha (no Gmail, uma "senha de app")
    AVISO_PARA           destinatários, separados por vírgula
Sem servidor, conta, senha ou destinatário configurados, não envia nada e diz isso no log (não derruba a rodada).
Só usa a biblioteca padrão do Python, para rodar mesmo quando a instalação de dependências da rodada falhou.
"""
import argparse
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage

CAMPOS = ("AVISO_SMTP_HOST", "AVISO_SMTP_USUARIO", "AVISO_SMTP_SENHA", "AVISO_PARA")


def configurado(env=os.environ):
    return all(env.get(k) for k in CAMPOS)


def mensagem(assunto, corpo, env=os.environ):
    m = EmailMessage()
    m["Subject"] = assunto
    m["From"] = env["AVISO_SMTP_USUARIO"]
    m["To"] = ", ".join(x.strip() for x in env["AVISO_PARA"].split(",") if x.strip())
    m.set_content(corpo)
    return m


def enviar(assunto, corpo, env=os.environ):
    if not configurado(env):
        faltam = [k for k in CAMPOS if not env.get(k)]
        print("e-mail de aviso não enviado: faltam os secrets " + ", ".join(faltam))
        return False
    porta = int(env.get("AVISO_SMTP_PORTA") or 465)
    m = mensagem(assunto, corpo, env)
    contexto = ssl.create_default_context()
    if porta == 465:
        with smtplib.SMTP_SSL(env["AVISO_SMTP_HOST"], porta, context=contexto, timeout=60) as s:
            s.login(env["AVISO_SMTP_USUARIO"], env["AVISO_SMTP_SENHA"])
            s.send_message(m)
    else:
        with smtplib.SMTP(env["AVISO_SMTP_HOST"], porta, timeout=60) as s:
            s.starttls(context=contexto)
            s.login(env["AVISO_SMTP_USUARIO"], env["AVISO_SMTP_SENHA"])
            s.send_message(m)
    print(f"e-mail de aviso enviado para {m['To']}")
    return True


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--assunto", required=True)
    ap.add_argument("--arquivo", help="corpo do e-mail (por exemplo, o avisos.md do vigia)")
    ap.add_argument("--texto", default="")
    ap.add_argument("--link", default="", help="link da issue ou da rodada, no fim do e-mail")
    args = ap.parse_args(argv)
    corpo = args.texto
    if args.arquivo and os.path.exists(args.arquivo):
        corpo = open(args.arquivo, encoding="utf-8").read() + ("\n" + corpo if corpo else "")
    if args.link:
        corpo += f"\n\n{args.link}\n"
    corpo += "\n-- \nPainel dos açudes com alocação de água (robô do GitHub Actions)\n"
    try:
        enviar(args.assunto, corpo)
    except (smtplib.SMTPException, OSError) as e:
        # falha no e-mail não derruba a rodada; aparece no log
        print(f"e-mail de aviso falhou: {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
