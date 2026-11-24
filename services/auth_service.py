import secrets
from services.connection import get_db, hash_password, verify_password


def create_session_token(username):
    token = secrets.token_urlsafe(32)
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM user_sessions WHERE expires_at < CURRENT_TIMESTAMP")
                cursor.execute(
                    """INSERT INTO user_sessions (token, username, expires_at) 
                       VALUES (%s, %s, CURRENT_TIMESTAMP + INTERVAL '24 hours')""",
                    (token, username)
                )
        return token
    finally:
        conn.close()


def validate_session_token(token):
    if not token:
        return None
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT u.username, u.balance, u.user_type, u.school_id, u.class_id
                FROM user_sessions s
                JOIN users u ON s.username = u.username
                WHERE s.token = %s AND s.expires_at > CURRENT_TIMESTAMP
            ''', (token,))
            user = cursor.fetchone()
            if user:
                return {
                    "username": user["username"],
                    "balance": float(user["balance"]),
                    "user_type": user["user_type"],
                    "school_id": user["school_id"],
                    "class_id": user["class_id"]
                }
        return None
    finally:
        conn.close()


def delete_session_token(token):
    if not token:
        return
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM user_sessions WHERE token = %s", (token,))
    finally:
        conn.close()


def login_user(username, password):
    username = username.strip()
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT username, salt, password_hash, balance, user_type, school_id, class_id FROM users WHERE username = %s",
                (username,)
            )
            user = cursor.fetchone()

            if user and verify_password(user["salt"], user["password_hash"], password):
                return True, {
                    "username": user["username"],
                    "balance": float(user["balance"]),
                    "user_type": user["user_type"],
                    "school_id": user["school_id"],
                    "class_id": user["class_id"]
                }
        return False, "Usuário ou senha incorretos."
    finally:
        conn.close()


def change_password(username, old_pass, new_pass):
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT salt, password_hash FROM users WHERE username = %s", (username,))
                user = cursor.fetchone()

                if not user or not verify_password(user["salt"], user["password_hash"], old_pass):
                    return False, "Senha atual incorreta."
                if len(new_pass) < 4:
                    return False, "A nova senha deve ter pelo menos 4 caracteres."

                new_salt, new_hash = hash_password(new_pass)
                cursor.execute(
                    "UPDATE users SET salt = %s, password_hash = %s WHERE username = %s",
                    (new_salt, new_hash, username)
                )
                return True, "Senha alterada com sucesso!"
    except Exception as e:
        return False, f"Erro ao alterar senha: {str(e)}"
    finally:
        conn.close()
