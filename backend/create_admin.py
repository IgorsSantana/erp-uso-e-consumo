import os
import pymysql
from werkzeug.security import generate_password_hash
from db import get_connection

def create_admin():
    conn = get_connection()
    if not conn:
        print("Failed to connect.")
        return

    try:
        with conn.cursor() as cursor:
            # Create Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Usuarios (
                    ID INT AUTO_INCREMENT PRIMARY KEY,
                    Nome VARCHAR(100) NOT NULL,
                    Username VARCHAR(50) NOT NULL UNIQUE,
                    SenhaHash VARCHAR(255) NOT NULL,
                    Nivel_Acesso VARCHAR(20) DEFAULT 'Operacional',
                    Data_Criacao DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("Tabela Usuarios verificada/criada.")

            # Check if admin exists
            cursor.execute("SELECT ID FROM Usuarios WHERE Username = 'admin'")
            if cursor.fetchone() is None:
                # Insert admin
                hash_senha = generate_password_hash("admin")
                cursor.execute(
                    "INSERT INTO Usuarios (Nome, Username, SenhaHash, Nivel_Acesso) VALUES (%s, %s, %s, %s)",
                    ("Administrador", "admin", hash_senha, "Admin")
                )
                print("Usuário 'admin' (senha 'admin') criado com sucesso.")
            else:
                print("Usuário 'admin' já existe.")
        
        conn.commit()
    except Exception as e:
        print(f"Erro: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    create_admin()
