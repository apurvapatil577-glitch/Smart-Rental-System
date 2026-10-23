import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.getenv("RENTAL_DB_PATH", os.path.join(BASE_DIR, "rental.db"))


def get_db_connection():

    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    return connection


def create_tables():

    connection = get_db_connection()


    # =========================
    # USERS TABLE
    # =========================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            email TEXT NOT NULL UNIQUE,

            password TEXT NOT NULL,

            role TEXT NOT NULL

        )
    """)


    # =========================
    # PROPERTIES TABLE
    # =========================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS properties (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            owner_id INTEGER,

            title TEXT NOT NULL,

            property_type TEXT NOT NULL,

            location TEXT NOT NULL,

            rent INTEGER NOT NULL,

            deposit INTEGER,

            facilities TEXT,

            image TEXT,

            status TEXT DEFAULT 'Available'

        )
    """)


    # =========================
    # BOOKINGS TABLE
    # =========================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS bookings (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER,

            property_id INTEGER,

            status TEXT DEFAULT 'Pending',

            request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )
    """)
# =========================
# RENT RECORDS TABLE
# =========================

    connection.execute("""
    CREATE TABLE IF NOT EXISTS rent_records (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        tenant_id INTEGER,

        property_id INTEGER,

        amount INTEGER NOT NULL,

        due_date TEXT,

        status TEXT DEFAULT 'Pending',

        payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
""")


    # =========================
    # MAINTENANCE REQUESTS TABLE
    # =========================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_requests (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            tenant_id INTEGER,

            property_id INTEGER,

            problem TEXT NOT NULL,

            status TEXT DEFAULT 'Pending',

            request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )
    """)


    connection.commit()

    connection.close()

