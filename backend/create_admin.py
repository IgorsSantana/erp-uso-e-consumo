"""Cadastre somente o primeiro administrador pelo fluxo oficial de configuração.

Uso: python -m backend.create_admin --nome "Seu nome" --username seu.usuario
A senha é solicitada no terminal, sem ser exibida ou gravada no histórico.
Administradores adicionais devem ser cadastrados na área Usuários do ERP.
"""

import argparse
from getpass import getpass

from backend.app import create_app


def create_admin():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nome", required=True, help="Nome do primeiro administrador")
    parser.add_argument("--username", required=True, help="Nome de usuário para entrar")
    args = parser.parse_args()
    password = getpass("Senha (mínimo de 10 caracteres): ")
    if password != getpass("Confirme a senha: "):
        parser.exit(1, "As senhas não coincidem. Nenhum usuário foi criado.\n")
    app = create_app()
    with app.test_client() as client:
        response = client.post(
            "/api/setup",
            json={"nome": args.nome, "username": args.username, "password": password},
        )
    if response.status_code not in (200, 201):
        payload = response.get_json(silent=True) or {}
        parser.exit(1, f"Não foi possível criar o administrador: {payload.get('error', 'verifique a configuração do ambiente')}.\n")
    print("Primeiro administrador criado. Entre pelo navegador com as credenciais escolhidas.")


if __name__ == "__main__":
    create_admin()
