import psycopg2
from config.settings import CONFIG

# Replace these with your actual values or import from config
host = CONFIG.get('DB_HOST', "127.0.0.1")
port = CONFIG.get('DB_PORT', 5432)  # or tunnel.local_bind_port
db_name = CONFIG.get('DB_NAME', "your_db")
db_user = CONFIG.get('DB_USER', "your_user")
db_password = CONFIG.get('DB_PASSWORD', "your_password")

conn = psycopg2.connect(
    host=host,
    port=port,
    dbname=db_name,
    user=db_user,
    password=db_password
)