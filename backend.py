import psycopg2
import psycopg2.extras
import hashlib
import secrets
import os
import streamlit as st

# ==========================================
# CONEXÃO E SEGURANÇA
# ==========================================
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
                        balance REAL DEFAULT 100.0,
                        user_type INTEGER DEFAULT 1,
                        school_id INTEGER REFERENCES schools(id),
                        class_id INTEGER REFERENCES classes(id)
                    )
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

# ==========================================
# GERENCIAMENTO DE SESSÃO PERSISTENTE
# ==========================================
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

# ==========================================
# ESCOLAS, TURMAS E USUÁRIOS
# ==========================================
def add_school(name):
    name = name.strip()
    if not name:
        return False, "O nome da escola é obrigatório."
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO schools (name) VALUES (%s)", (name,))
                return True, f"Escola '{name}' cadastrada com sucesso!"
    except psycopg2.IntegrityError:
        return False, "Esta escola já está cadastrada."
    except Exception as e:
        return False, f"Erro ao cadastrar escola: {str(e)}"
    finally:
        conn.close()

def get_schools():
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name FROM schools ORDER BY name ASC")
            return cursor.fetchall()
    finally:
        conn.close()

def get_all_schools_details():
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT s.id AS "ID", 
                       s.name AS "Escola",
                       COUNT(DISTINCT c.id) AS "Total de Turmas",
                       COUNT(DISTINCT u.id) AS "Total de Alunos"
                FROM schools s
                LEFT JOIN classes c ON c.school_id = s.id
                LEFT JOIN users u ON u.school_id = s.id AND u.user_type = 1
                GROUP BY s.id, s.name
                ORDER BY s.id ASC
            ''')
            rows = cursor.fetchall()
            schools_list = []
            for r in rows:
                r_dict = dict(r)
                r_dict["Total de Turmas"] = int(r_dict["Total de Turmas"])
                r_dict["Total de Alunos"] = int(r_dict["Total de Alunos"])
                schools_list.append(r_dict)
            return schools_list
    finally:
        conn.close()

def add_class(name, school_id):
    name = name.strip()
    if not name:
        return False, "O nome da classe/turma é obrigatório."
    if not school_id:
        return False, "Selecione uma escola válida."
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO classes (name, school_id) VALUES (%s, %s)", (name, school_id))
                return True, f"Classe '{name}' cadastrada com sucesso!"
    except Exception as e:
        return False, f"Erro ao cadastrar classe: {str(e)}"
    finally:
        conn.close()

def get_classes_by_school(school_id):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name FROM classes WHERE school_id = %s ORDER BY name ASC", (school_id,))
            return cursor.fetchall()
    finally:
        conn.close()

def get_school_and_class_names(school_id, class_id):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT name FROM schools WHERE id = %s", (school_id,))
            sch = cursor.fetchone()
            cursor.execute("SELECT name FROM classes WHERE id = %s", (class_id,))
            cls = cursor.fetchone()
            school_name = sch["name"] if sch else "N/A"
            class_name = cls["name"] if cls else "N/A"
            return school_name, class_name
    finally:
        conn.close()

def get_students_school_map():
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT u.username, COALESCE(s.name, 'N/A') AS school_name
                FROM users u
                LEFT JOIN schools s ON u.school_id = s.id
                WHERE u.user_type = 1
            ''')
            return {row["username"]: row["school_name"] for row in cursor.fetchall()}
    finally:
        conn.close()

def register_teacher(username, password, confirm_password, school_id, class_id):
    username = username.strip()
    if not username or not password:
        return False, "Usuário e senha são obrigatórios."
    if len(username) < 3:
        return False, "O usuário deve ter pelo menos 3 caracteres."
    if len(password) < 4:
        return False, "A senha deve ter pelo menos 4 caracteres."
    if password != confirm_password:
        return False, "As senhas não coincidem."
    if not school_id or not class_id:
        return False, "A seleção da escola e da classe é obrigatória."

    salt_hex, hash_hex = hash_password(password)
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO users (username, salt, password_hash, balance, user_type, school_id, class_id) 
                       VALUES (%s, %s, %s, %s, 3, %s, %s)""",
                    (username, salt_hex, hash_hex, 0.0, school_id, class_id)
                )
                return True, f"Professor '{username}' cadastrado com sucesso!"
    except psycopg2.IntegrityError:
        return False, "Nome de usuário já está em uso."
    except Exception as e:
        return False, f"Erro ao cadastrar professor: {str(e)}"
    finally:
        conn.close()

def register_student(username, password, confirm_password, school_id, class_id):
    username = username.strip()
    if not username or not password:
        return False, "Usuário e senha são obrigatórios."
    if len(username) < 3:
        return False, "O usuário deve ter pelo menos 3 caracteres."
    if len(password) < 4:
        return False, "A senha deve ter pelo menos 4 caracteres."
    if password != confirm_password:
        return False, "As senhas não coincidem."
    if not school_id or not class_id:
        return False, "A seleção da escola e da classe é obrigatória."

    salt_hex, hash_hex = hash_password(password)
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO users (username, salt, password_hash, balance, user_type, school_id, class_id) 
                       VALUES (%s, %s, %s, %s, 1, %s, %s)""",
                    (username, salt_hex, hash_hex, 100.0, school_id, class_id)
                )
                cursor.execute(
                    "INSERT INTO transactions (sender, receiver, amount, description) VALUES (%s, %s, %s, %s)",
                    ("SISTEMA", username, 100.0, "Bônus de boas-vindas")
                )
                return True, f"Aluno '{username}' cadastrado com sucesso!"
    except psycopg2.IntegrityError:
        return False, "Nome de usuário já está em uso."
    except Exception as e:
        return False, f"Erro ao cadastrar aluno: {str(e)}"
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
                cursor.execute("UPDATE users SET salt = %s, password_hash = %s WHERE username = %s", (new_salt, new_hash, username))
                return True, "Senha alterada com sucesso!"
    except Exception as e:
        return False, f"Erro ao alterar senha: {str(e)}"
    finally:
        conn.close()

def get_all_students():
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT u.id AS "ID", u.username AS "Aluno", 
                       COALESCE(s.name, 'N/A') AS "Escola", 
                       COALESCE(c.name, 'N/A') AS "Classe",
                       u.balance AS "Saldo (B+)"
                FROM users u 
                LEFT JOIN schools s ON u.school_id = s.id 
                LEFT JOIN classes c ON u.class_id = c.id 
                WHERE u.user_type = 1 
                ORDER BY u.id ASC
            ''')
            rows = cursor.fetchall()
            students = []
            for r in rows:
                r_dict = dict(r)
                r_dict["Saldo (B+)"] = float(r_dict["Saldo (B+)"])
                students.append(r_dict)
            return students
    finally:
        conn.close()

def get_all_student_usernames():
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT username FROM users WHERE user_type = 1 ORDER BY username ASC")
            return [row["username"] for row in cursor.fetchall()]
    finally:
        conn.close()

def get_student_usernames_by_class(class_id):
    if not class_id:
        return []
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT username FROM users WHERE user_type = 1 AND class_id = %s ORDER BY username ASC",
                (class_id,)
            )
            return [row["username"] for row in cursor.fetchall()]
    finally:
        conn.close()

def get_students_by_school(school_id):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT u.id AS "ID", u.username AS "Aluno", 
                       COALESCE(s.name, 'N/A') AS "Escola", 
                       COALESCE(c.name, 'N/A') AS "Classe",
                       u.balance AS "Saldo (B+)"
                FROM users u 
                LEFT JOIN schools s ON u.school_id = s.id 
                LEFT JOIN classes c ON u.class_id = c.id 
                WHERE u.user_type = 1 AND u.school_id = %s
                ORDER BY u.id ASC
            ''', (school_id,))
            rows = cursor.fetchall()
            students = []
            for r in rows:
                r_dict = dict(r)
                r_dict["Saldo (B+)"] = float(r_dict["Saldo (B+)"])
                students.append(r_dict)
            return students
    finally:
        conn.close()

def get_other_users(current_username, school_id):
    if not school_id:
        return []
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT username FROM users WHERE username != %s AND user_type = 1 AND school_id = %s ORDER BY username ASC",
                (current_username, school_id)
            )
            return [row["username"] for row in cursor.fetchall()]
    finally:
        conn.close()

def get_balance(username):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT balance FROM users WHERE username = %s", (username,))
            res = cursor.fetchone()
            return float(res["balance"]) if res else 0.0
    finally:
        conn.close()

def get_pending_outgoing_amount(username):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT COALESCE(SUM(amount), 0) AS total 
                   FROM pending_operations 
                   WHERE sender_username = %s AND status = 'PENDENTE' AND op_type IN ('SAQUE', 'TRANSFERENCIA')""",
                (username,)
            )
            res = cursor.fetchone()
            return float(res["total"]) if res else 0.0
    finally:
        conn.close()

# ==========================================
# SOLICITAÇÕES DE OPERAÇÕES (PENDENTES)
# ==========================================
def request_deposit(requester_username, requester_role, target_username, amount, reason=""):
    if not target_username:
        return False, "Selecione um aluno válido."
    target_username = target_username.strip()
    amount = float(amount)
    if amount <= 0:
        return False, f"O valor do depósito para {target_username} deve ser maior que zero."

    reason_clean = reason.strip() if reason else ""
    base_desc = f"Depósito solicitado por {requester_role.lower()} ({requester_username})"
    full_desc = f"{base_desc} | Motivo: {reason_clean}" if reason_clean else base_desc

    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE username = %s AND user_type = 1", (target_username,))
                if not cursor.fetchone():
                    return False, f"Aluno '{target_username}' não encontrado."

                cursor.execute(
                    """INSERT INTO pending_operations 
                       (op_type, requester_username, requester_role, sender_username, receiver_username, amount, description, status) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDENTE')""",
                    ("DEPOSITO", requester_username, requester_role, "ADMIN / DEPÓSITO", target_username, amount, full_desc)
                )
                return True, f"Solicitação de depósito de {amount:.2f} B+ para {target_username} enviada!"
    except Exception as e:
        return False, f"Erro ao registrar solicitação de depósito para {target_username}: {str(e)}"
    finally:
        conn.close()

def request_withdraw(requester_username, requester_role, target_username, amount, description="Saque em espécie de B+"):
    if not target_username:
        return False, "Selecione um usuário válido."
    target_username = target_username.strip()
    amount = float(amount)
    if amount <= 0:
        return False, f"O valor do saque para {target_username} deve ser maior que zero."

    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT balance FROM users WHERE username = %s AND user_type = 1", (target_username,))
                res = cursor.fetchone()
                if not res:
                    return False, f"Aluno '{target_username}' não encontrado."

                current_balance = float(res["balance"])
                cursor.execute(
                    """SELECT COALESCE(SUM(amount), 0) AS total 
                       FROM pending_operations 
                       WHERE sender_username = %s AND status = 'PENDENTE' AND op_type IN ('SAQUE', 'TRANSFERENCIA')""",
                    (target_username,)
                )
                pending_sum = float(cursor.fetchone()["total"])
                available_balance = current_balance - pending_sum

                if available_balance < amount:
                    return False, (
                        f"Saldo disponível insuficiente para {target_username}! "
                        f"Saldo atual: {current_balance:.2f} B+ | Pendente: {pending_sum:.2f} B+ | "
                        f"Disponível: {available_balance:.2f} B+."
                    )

                cursor.execute(
                    """INSERT INTO pending_operations 
                       (op_type, requester_username, requester_role, sender_username, receiver_username, amount, description, status) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDENTE')""",
                    ("SAQUE", requester_username, requester_role, target_username, None, amount, description)
                )
                return True, f"Solicitação de saque de {amount:.2f} B+ ({target_username}) enviada! Aguardando aprovação do administrador."
    except Exception as e:
        return False, f"Erro ao registrar solicitação de saque: {str(e)}"
    finally:
        conn.close()

def request_transfer(requester_username, requester_role, sender, receiver, amount, description="Transferência efetuada"):
    if not receiver:
        return False, "Selecione um destinatário válido."
    sender = sender.strip()
    receiver = receiver.strip()
    amount = float(amount)
    if amount <= 0:
        return False, "O valor deve ser maior que zero."
    if sender.lower() == receiver.lower():
        return False, "Não é possível transferir para o mesmo usuário."

    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT balance, school_id FROM users WHERE username = %s AND user_type = 1", (sender,))
                sender_res = cursor.fetchone()
                if not sender_res:
                    return False, "Aluno remetente não existe."

                cursor.execute("SELECT balance, school_id FROM users WHERE username = %s AND user_type = 1", (receiver,))
                rec_res = cursor.fetchone()
                if not rec_res:
                    return False, "Aluno destinatário não existe."

                if requester_role == "Aluno":
                    if not sender_res["school_id"] or sender_res["school_id"] != rec_res["school_id"]:
                        return False, "Transferências de alunos só são permitidas para colegas da mesma escola."

                sender_bal = float(sender_res["balance"])
                cursor.execute(
                    """SELECT COALESCE(SUM(amount), 0) AS total 
                       FROM pending_operations 
                       WHERE sender_username = %s AND status = 'PENDENTE' AND op_type IN ('SAQUE', 'TRANSFERENCIA')""",
                    (sender,)
                )
                pending_sum = float(cursor.fetchone()["total"])
                available_balance = sender_bal - pending_sum

                if available_balance < amount:
                    return False, (
                        f"Saldo disponível insuficiente para solicitar transferência! "
                        f"Saldo atual: {sender_bal:.2f} B+ | Pendente de aprovação: {pending_sum:.2f} B+ | "
                        f"Disponível: {available_balance:.2f} B+."
                    )

                cursor.execute(
                    """INSERT INTO pending_operations 
                       (op_type, requester_username, requester_role, sender_username, receiver_username, amount, description, status) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDENTE')""",
                    ("TRANSFERENCIA", requester_username, requester_role, sender, receiver, amount, description)
                )
                return True, f"Solicitação de transferência de {amount:.2f} B+ para {receiver} enviada! Aguardando aprovação do administrador."
    except Exception as e:
        return False, f"Erro ao registrar solicitação de transferência: {str(e)}"
    finally:
        conn.close()

def get_pending_operations():
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT po.id, po.op_type, po.requester_username, po.requester_role,
                       po.sender_username, po.receiver_username, po.amount,
                       po.description, po.status, po.created_at,
                       COALESCE(s_sender.name, 'N/A') AS sender_school,
                       COALESCE(c_sender.name, 'N/A') AS sender_class,
                       COALESCE(s_rec.name, 'N/A') AS receiver_school,
                       COALESCE(c_rec.name, 'N/A') AS receiver_class
                FROM pending_operations po
                LEFT JOIN users u_sender ON po.sender_username = u_sender.username
                LEFT JOIN schools s_sender ON u_sender.school_id = s_sender.id
                LEFT JOIN classes c_sender ON u_sender.class_id = c_sender.id
                LEFT JOIN users u_rec ON po.receiver_username = u_rec.username
                LEFT JOIN schools s_rec ON u_rec.school_id = s_rec.id
                LEFT JOIN classes c_rec ON u_rec.class_id = c_rec.id
                WHERE po.status = 'PENDENTE'
                ORDER BY po.id ASC
            ''')
            return cursor.fetchall()
    finally:
        conn.close()

def get_reviewed_operations():
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT po.id, po.op_type, po.requester_username, po.requester_role,
                       po.sender_username, po.receiver_username, po.amount,
                       po.description, po.status, po.created_at,
                       po.reviewed_by, po.reviewed_at, po.review_note,
                       COALESCE(s_sender.name, 'N/A') AS sender_school,
                       COALESCE(s_rec.name, 'N/A') AS receiver_school
                FROM pending_operations po
                LEFT JOIN users u_sender ON po.sender_username = u_sender.username
                LEFT JOIN schools s_sender ON u_sender.school_id = s_sender.id
                LEFT JOIN users u_rec ON po.receiver_username = u_rec.username
                LEFT JOIN schools s_rec ON u_rec.school_id = s_rec.id
                WHERE po.status IN ('APROVADA', 'REPROVADA')
                ORDER BY po.reviewed_at DESC, po.id DESC
            ''')
            return cursor.fetchall()
    finally:
        conn.close()

def get_user_operation_requests(username):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT id, op_type, requester_username, sender_username, receiver_username,
                       amount, description, status, created_at, reviewed_by, reviewed_at, review_note
                FROM pending_operations
                WHERE requester_username = %s OR sender_username = %s OR receiver_username = %s
                ORDER BY id DESC
            ''', (username, username, username))
            return cursor.fetchall()
    finally:
        conn.close()

def approve_operation(op_id, admin_username, review_note=""):
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM pending_operations WHERE id = %s AND status = 'PENDENTE' FOR UPDATE",
                    (op_id,)
                )
                op = cursor.fetchone()
                if not op:
                    return False, "Operação não encontrada ou já avaliada."

                op_type = op["op_type"]
                sender = op["sender_username"]
                receiver = op["receiver_username"]
                amount = float(op["amount"])
                base_desc = op["description"] or ""
                note_suffix = f" | Obs: {review_note.strip()}" if review_note and review_note.strip() else ""
                final_desc = f"{base_desc} (Aprovado por {admin_username}{note_suffix})"

                if op_type == "DEPOSITO":
                    cursor.execute("SELECT balance FROM users WHERE username = %s AND user_type = 1 FOR UPDATE", (receiver,))
                    if not cursor.fetchone():
                        return False, f"Aluno destinatário '{receiver}' não encontrado."

                    cursor.execute("UPDATE users SET balance = balance + %s WHERE username = %s", (amount, receiver))
                    cursor.execute(
                        "INSERT INTO transactions (sender, receiver, amount, description) VALUES (%s, %s, %s, %s)",
                        ("ADMIN / DEPÓSITO", receiver, amount, final_desc)
                    )

                elif op_type == "SAQUE":
                    cursor.execute("SELECT balance FROM users WHERE username = %s FOR UPDATE", (sender,))
                    sender_row = cursor.fetchone()
                    if not sender_row:
                        return False, f"Aluno de origem '{sender}' não encontrado."

                    sender_bal = float(sender_row["balance"])
                    if sender_bal < amount:
                        return False, f"Saldo insuficiente na conta de {sender} ({sender_bal:.2f} B+) para aprovar {amount:.2f} B+."

                    cursor.execute("UPDATE users SET balance = balance - %s WHERE username = %s", (amount, sender))
                    cursor.execute(
                        "INSERT INTO transactions (sender, receiver, amount, description) VALUES (%s, %s, %s, %s)",
                        (sender, "CAIXA / SAQUE", amount, final_desc)
                    )

                elif op_type == "TRANSFERENCIA":
                    cursor.execute("SELECT balance FROM users WHERE username = %s FOR UPDATE", (sender,))
                    sender_row = cursor.fetchone()
                    if not sender_row:
                        return False, f"Aluno de origem '{sender}' não encontrado."

                    sender_bal = float(sender_row["balance"])
                    if sender_bal < amount:
                        return False, f"Saldo insuficiente na conta de {sender} ({sender_bal:.2f} B+) para aprovar {amount:.2f} B+."

                    cursor.execute("SELECT balance FROM users WHERE username = %s FOR UPDATE", (receiver,))
                    if not cursor.fetchone():
                        return False, f"Aluno destinatário '{receiver}' não encontrado."

                    cursor.execute("UPDATE users SET balance = balance - %s WHERE username = %s", (amount, sender))
                    cursor.execute("UPDATE users SET balance = balance + %s WHERE username = %s", (amount, receiver))
                    cursor.execute(
                        "INSERT INTO transactions (sender, receiver, amount, description) VALUES (%s, %s, %s, %s)",
                        (sender, receiver, amount, final_desc)
                    )
                else:
                    return False, "Tipo de operação inválido."

                cursor.execute(
                    """UPDATE pending_operations 
                       SET status = 'APROVADA', reviewed_by = %s, reviewed_at = CURRENT_TIMESTAMP, review_note = %s 
                       WHERE id = %s""",
                    (admin_username, review_note.strip() if review_note else "", op_id)
                )
                return True, f"Operação #{op_id} aprovada e efetivada com sucesso!"
    except Exception as e:
        return False, f"Erro ao aprovar operação: {str(e)}"
    finally:
        conn.close()

def reject_operation(op_id, admin_username, review_note=""):
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM pending_operations WHERE id = %s AND status = 'PENDENTE' FOR UPDATE",
                    (op_id,)
                )
                if not cursor.fetchone():
                    return False, "Operação não encontrada ou já avaliada."

                cursor.execute(
                    """UPDATE pending_operations 
                       SET status = 'REPROVADA', reviewed_by = %s, reviewed_at = CURRENT_TIMESTAMP, review_note = %s 
                       WHERE id = %s""",
                    (admin_username, review_note.strip() if review_note else "", op_id)
                )
                return True, f"Operação #{op_id} reprovada."
    except Exception as e:
        return False, f"Erro ao reprovar operação: {str(e)}"
    finally:
        conn.close()

# ==========================================
# OPERAÇÕES DIRETAS (EXCLUSIVAS DO ADMIN)
# ==========================================
def deposit_b_plus(username, amount, admin_user="ADMIN", reason=""):
    if not username:
        return False, "Selecione um aluno válido."
    username = username.strip()
    amount = float(amount)
    if amount <= 0:
        return False, f"O valor do depósito para {username} deve ser maior que zero."

    reason_clean = reason.strip() if reason else ""
    base_desc = f"Depósito efetuado pelo admin ({admin_user})"
    final_desc = f"{base_desc} | Motivo: {reason_clean}" if reason_clean else base_desc

    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT balance FROM users WHERE username = %s AND user_type = 1", (username,))
                res = cursor.fetchone()
                if not res:
                    return False, f"Aluno '{username}' não encontrado."

                cursor.execute("UPDATE users SET balance = balance + %s WHERE username = %s", (amount, username))
                cursor.execute(
                    "INSERT INTO transactions (sender, receiver, amount, description) VALUES (%s, %s, %s, %s)",
                    ("ADMIN / DEPÓSITO", username, amount, final_desc)
                )
                return True, f"Depósito de {amount:.2f} B+ realizado com sucesso para {username}!"
    except Exception as e:
        return False, f"Erro ao processar o depósito para {username}: {str(e)}"
    finally:
        conn.close()

def transfer_b_plus(sender, receiver, amount, description="Transferência efetuada"):
    if not receiver:
        return False, "Selecione um destinatário válido."
    receiver = receiver.strip()
    amount = float(amount)
    if amount <= 0:
        return False, "O valor deve ser maior que zero."
    if sender.lower() == receiver.lower():
        return False, "Não é possível transferir para o mesmo usuário."

    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT balance FROM users WHERE username = %s", (receiver,))
                rec = cursor.fetchone()
                if not rec:
                    return False, "Usuário destinatário não existe."

                cursor.execute("SELECT balance FROM users WHERE username = %s", (sender,))
                sender_res = cursor.fetchone()
                if not sender_res:
                    return False, "Usuário remetente não existe."

                sender_bal = float(sender_res["balance"])
                if sender_bal < amount:
                    return False, f"Saldo insuficiente! Saldo atual de {sender}: {sender_bal:.2f} B+."

                cursor.execute("UPDATE users SET balance = balance - %s WHERE username = %s", (amount, sender))
                cursor.execute("UPDATE users SET balance = balance + %s WHERE username = %s", (amount, receiver))
                cursor.execute(
                    "INSERT INTO transactions (sender, receiver, amount, description) VALUES (%s, %s, %s, %s)",
                    (sender, receiver, amount, description)
                )
                return True, f"Transferência de {amount:.2f} B+ realizada de {sender} para {receiver}."
    except Exception as e:
        return False, f"Erro ao processar a transação: {str(e)}"
    finally:
        conn.close()

def withdraw_b_plus(username, amount, description="Saque em espécie de B+"):
    if not username:
        return False, "Selecione um usuário válido."
    amount = float(amount)
    if amount <= 0:
        return False, f"O valor do saque para {username} deve ser maior que zero."

    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT balance FROM users WHERE username = %s", (username,))
                res = cursor.fetchone()
                if not res:
                    return False, f"Usuário '{username}' não encontrado."

                current_balance = float(res["balance"])
                if current_balance < amount:
                    return False, f"Saldo insuficiente! Saldo disponível de {username}: {current_balance:.2f} B+."

                cursor.execute("UPDATE users SET balance = balance - %s WHERE username = %s", (amount, username))
                cursor.execute(
                    "INSERT INTO transactions (sender, receiver, amount, description) VALUES (%s, %s, %s, %s)",
                    (username, "CAIXA / SAQUE", amount, description)
                )
                return True, f"Saque de {amount:.2f} B+ realizado com sucesso da conta de {username}!"
    except Exception as e:
        return False, f"Erro ao processar o saque de {username}: {str(e)}"
    finally:
        conn.close()

def get_history(username):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT sender, receiver, amount, timestamp, description
                FROM transactions
                WHERE sender = %s OR receiver = %s
                ORDER BY id DESC
            ''', (username, username))
            return cursor.fetchall()
    finally:
        conn.close()
