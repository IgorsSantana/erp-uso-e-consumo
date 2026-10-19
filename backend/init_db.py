"""Inicialize/verifique o banco local sem executar os scripts MySQL legados.

Uso, a partir da raiz: python -m backend.init_db
"""

from backend.app import create_app
from backend.db import get_db


def initialize_database():
    app = create_app()
    with app.app_context():
        connection = get_db()
        result = connection.execute("PRAGMA quick_check").fetchone()[0]
        if result != "ok":
            raise SystemExit(f"Falha na verificação de integridade: {result}")
        print("Banco SQLite inicializado e verificado.")
        print("Abra /login.html para cadastrar o primeiro administrador, se necessário.")


if __name__ == "__main__":
    initialize_database()
