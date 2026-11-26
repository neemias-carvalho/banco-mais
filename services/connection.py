import hashlib
import os
import psycopg2
import psycopg2.extras
import streamlit as st


def get_db():
    try:
        db_url = st.secrets["postgres_url"]
    except Exception:
        db_url = st.secrets["DB_USERNAME"]

    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


def hash_password(password, salt_hex=None):
    if salt_hex is None:
        salt = os.urandom(16)
    else:
        salt = bytes.fromhex(salt_hex)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex(), key.hex()


def verify_password(stored_salt, stored_hash, provided_password):
    _, key_hex = hash_password(provided_password, stored_salt)
    return key_hex == stored_hash


def init_db():
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS schools (
                        id SERIAL PRIMARY KEY,
                        name TEXT UNIQUE NOT NULL
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS classes (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        school_id INTEGER NOT NULL REFERENCES schools(id)
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        salt TEXT NOT NULL,
                        password_hash TEXT NOT NULL,
                        balance REAL DEFAULT 0.0,
                        user_type INTEGER DEFAULT 1,
                        school_id INTEGER REFERENCES schools(id),
                        class_id INTEGER REFERENCES classes(id),
                        welcome_bonus_claimed BOOLEAN DEFAULT FALSE
                    )
                ''')

                cursor.execute('''
                    ALTER TABLE users
                    ADD COLUMN IF NOT EXISTS welcome_bonus_claimed BOOLEAN DEFAULT FALSE
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS transactions (
                        id SERIAL PRIMARY KEY,
                        sender TEXT NOT NULL,
                        receiver TEXT NOT NULL,
                        amount REAL NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        description TEXT DEFAULT ''
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS pending_operations (
                        id SERIAL PRIMARY KEY,
                        op_type TEXT NOT NULL,
                        requester_username TEXT NOT NULL,
                        requester_role TEXT NOT NULL,
                        sender_username TEXT NOT NULL,
                        receiver_username TEXT,
                        amount REAL NOT NULL,
                        description TEXT DEFAULT '',
                        status TEXT DEFAULT 'PENDENTE',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        reviewed_by TEXT,
                        reviewed_at TIMESTAMP,
                        review_note TEXT DEFAULT ''
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        token TEXT PRIMARY KEY,
                        username TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL
                    )
                ''')

                # Admin Default (admin / b@nc0m@15)
                cursor.execute("SELECT id FROM users WHERE username = %s", ("admin",))
                if not cursor.fetchone():
                    salt_hex, hash_hex = hash_password("b@nc0m@15")
                    cursor.execute(
                        "INSERT INTO users (username, salt, password_hash, balance, user_type) VALUES (%s, %s, %s, %s, %s)",
                        ("admin", salt_hex, hash_hex, 0.0, 2)
                    )
    finally:
        conn.close()
