import os
import pymysql
from pymysql.cursors import DictCursor


class DatabaseConnection:
    """SQLite-style interface backed by TiDB/MySQL."""

    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=()):
        query = query.replace("?", "%s")

        cursor = self.connection.cursor()
        cursor.execute(query, params)

        return cursor

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def get_db_connection():
    host = os.getenv("TIDB_HOST")
    user = os.getenv("TIDB_USER")
    password = os.getenv("TIDB_PASSWORD")
    database = os.getenv("TIDB_DATABASE")
    port = int(os.getenv("TIDB_PORT", "4000"))

    if not all([host, user, password, database]):
        raise RuntimeError(
            "Set TIDB_HOST, TIDB_USER, TIDB_PASSWORD "
            "and TIDB_DATABASE in environment variables."
        )

    connection = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset="utf8mb4",
        cursorclass=DictCursor,
        connect_timeout=15,
        ssl={}
    )

    return DatabaseConnection(connection)


def create_tables():
    connection = get_db_connection()

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS properties (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                owner_id BIGINT,
                title VARCHAR(255) NOT NULL,
                property_type VARCHAR(100) NOT NULL,
                location VARCHAR(500) NOT NULL,
                rent INT NOT NULL,
                deposit INT,
                facilities TEXT,
                image TEXT,
                status VARCHAR(50) DEFAULT 'Available'
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                user_id BIGINT,
                property_id BIGINT,
                status VARCHAR(50) DEFAULT 'Pending',
                request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS rent_records (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                tenant_id BIGINT,
                property_id BIGINT,
                amount INT NOT NULL,
                due_date DATE,
                status VARCHAR(50) DEFAULT 'Pending',
                payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS maintenance_requests (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                tenant_id BIGINT,
                property_id BIGINT,
                problem TEXT NOT NULL,
                status VARCHAR(50) DEFAULT 'Pending',
                request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
