import os
import pymysql
from db import get_connection

def initialize_database():
    print("Iniciando conexão com TiDB...")
    conn = get_connection()
    if not conn:
        print("Falha na conexão. Abortando inicialização.")
        return

    print("Conexão bem-sucedida! Lendo schema SQL...")
    
    # Caminho do esquema (voltando 1 pasta para acessar a raiz do projeto)
    schema_path = os.path.join(os.path.dirname(__file__), "..", "database_schema.sql")
    
    with open(schema_path, "r", encoding="utf-8") as file:
        sql_commands = file.read()

    # Separar os comandos por ';'
    commands = sql_commands.split(';')
    
    try:
        with conn.cursor() as cursor:
            for command in commands:
                cmd = command.strip()
                if cmd:
                    print(f"Executando parte do schema...")
                    cursor.execute(cmd)
            conn.commit()
            print("=== Banco de Dados Inicializado e Populado com Sucesso! ===")
    except Exception as e:
        print(f"Erro ao executar schema: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    initialize_database()
