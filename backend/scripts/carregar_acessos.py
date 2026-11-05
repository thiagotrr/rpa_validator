"""Carga manual dos e-mails autorizados no Firebase Auth.

Uso (a partir de backend/, com credencial de administrador do Firebase no ADC):
    python -m scripts.carregar_acessos --arquivo acessos.txt --projeto meu-projeto [--remover-ausentes] [--simular]

Os links de definição de senha dos usuários NOVOS são impressos na tela: envie cada um à pessoa por canal seguro.
"""

import argparse
import sys
from pathlib import Path

from app.acessos import AdministradorFirebase, ler_lista_emails, sincronizar_acessos


def principal(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Carga manual de acessos (Firebase Auth)")
    p.add_argument("--arquivo", required=True, type=Path, help="um e-mail por linha; '#' para comentários")
    p.add_argument("--projeto", help="ID do projeto GCP/Firebase")
    p.add_argument("--claim", default="rpa_autorizado")
    p.add_argument("--remover-ausentes", action="store_true", help="retira o acesso de quem não está no arquivo")
    p.add_argument("--simular", action="store_true", help="mostra o que seria feito, sem alterar nada")
    args = p.parse_args(argv)

    emails, invalidos = ler_lista_emails(args.arquivo.read_text(encoding="utf-8"))
    if invalidos:
        print(f"E-mails inválidos (corrija e rode de novo): {', '.join(invalidos)}", file=sys.stderr)
        return 2
    r = sincronizar_acessos(
        emails,
        AdministradorFirebase(args.claim, args.projeto),
        remover_ausentes=args.remover_ausentes,
        simular=args.simular,
    )
    prefixo = "[SIMULAÇÃO] " if args.simular else ""
    print(
        f"{prefixo}criados: {len(r.criados)} | autorizados: {len(r.autorizados)} | "
        f"já autorizados: {len(r.ja_autorizados)} | removidos: {len(r.removidos)}"
    )
    for email in r.removidos:
        print(f"  acesso removido: {email}")
    for email, link in r.links_definicao_senha.items():
        print(f"  definir senha — {email}: {link}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
