import pymysql

# Configurações de conexão TiDB Cloud
DB_CONFIG = {
    "host": "gateway03.us-east-1.prod.aws.tidbcloud.com",
    "port": 4000,
    "user": "9evrav9ZWbmZpgi.d8890d9f02dd",
    "password": "i7huZS8NRLL7Q2e1dkd5",
    "database": "VVF9ZhsGg7oyqRAu62UhcZ",
    "ssl": {"rejectUnauthorized": True}
}

def get_connection():
    try:
        conn = pymysql.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Erro ao conectar no banco de dados: {e}")
        return None
