import psycopg2
import psycopg2.extras
import hashlib
import os
import datetime
import pandas as pd
import streamlit as st

# Configuração da página do Streamlit
st.set_page_config(page_title="B+ Bank", page_icon="🪙", layout="centered")

# ==========================================
# 1. BANCO DE DADOS POSTGRESQL (psycopg2)
# ==========================================
def get_db():
    try:
        db_url = st.secrets["postgres_url"]
    except Exception:
        db_url = "postgresql://postgres.qubswavybduwpoumwfle:BLkJh8ACFA2N2g@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
        
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

# --- Funções Auxiliares ---
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

def get_other_users(current_username):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT username FROM users WHERE username != %s AND user_type = 1 ORDER BY username ASC", (current_username,))
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

def deposit_b_plus(username, amount, admin_user="ADMIN"):
    if not username:
        return False, "Selecione um aluno válido."
    username = username.strip()
    amount = float(amount)
    if amount <= 0:
        return False, "O valor do depósito deve ser maior que zero."

    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT balance FROM users WHERE username = %s AND user_type = 1", (username,))
                res = cursor.fetchone()
                if not res:
                    return False, "Aluno não encontrado."

                cursor.execute("UPDATE users SET balance = balance + %s WHERE username = %s", (amount, username))
                cursor.execute(
                    "INSERT INTO transactions (sender, receiver, amount, description) VALUES (%s, %s, %s, %s)",
                    ("ADMIN / DEPÓSITO", username, amount, f"Depósito efetuado pelo admin ({admin_user})")
                )
                return True, f"Depósito de {amount:.2f} B+ realizado com sucesso para {username}!"
    except Exception as e:
        return False, f"Erro ao processar o depósito: {str(e)}"
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
        return False, "O valor do saque deve ser maior que zero."

    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT balance FROM users WHERE username = %s", (username,))
                res = cursor.fetchone()
                if not res:
                    return False, "Usuário não encontrado."

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
        return False, f"Erro ao processar o saque: {str(e)}"
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

# Inicialização da base
init_db()

# ==========================================
# 2. GERENCIAMENTO DE SESSÃO (Streamlit)
# ==========================================
if "user" not in st.session_state:
    st.session_state["user"] = None
if "user_type" not in st.session_state:
    st.session_state["user_type"] = 1
if "school_id" not in st.session_state:
    st.session_state["school_id"] = None
if "class_id" not in st.session_state:
    st.session_state["class_id"] = None

def logout():
    st.session_state["user"] = None
    st.session_state["user_type"] = 1
    st.session_state["school_id"] = None
    st.session_state["class_id"] = None
    st.rerun()

# ==========================================
# 3. INTERFACE GRÁFICA (Streamlit)
# ==========================================

# --- TELA DE LOGIN ---
if st.session_state["user"] is None:
    st.title("🪙 B+ Bank - Acesso ao Sistema")
    
    with st.form("login_form"):
        user_input = st.text_input("Usuário")
        pass_input = st.text_input("Senha", type="password")
        submit = st.form_submit_button("Entrar", type="primary", use_container_width=True)
        
        if submit:
            success, res = login_user(user_input, pass_input)
            if success:
                st.session_state["user"] = res["username"]
                st.session_state["user_type"] = res["user_type"]
                st.session_state["school_id"] = res["school_id"]
                st.session_state["class_id"] = res["class_id"]
                st.rerun()
            else:
                st.error(f"❌ {res}")

# --- PAINEL DO ADMINISTRADOR (Tipo 2) ---
elif st.session_state["user_type"] == 2:
    st.sidebar.title("🛡️ Painel Admin")
    st.sidebar.write(f"Conectado como: **{st.session_state['user']}**")
    if st.sidebar.button("Sair", type="secondary", use_container_width=True):
        logout()

    st.title("🛡️ Administração B+ Bank")
    
    (
        tab_schools,
        tab_classes,
        tab_teachers,
        tab_students,
        tab_finance,
        tab_list_students,
        tab_list_schools,
    ) = st.tabs([
        "🏫 Escolas", 
        "📚 Turmas", 
        "👨‍🏫 Cadastrar Professor",
        "➕ Cadastrar Aluno",
        "💰 Operações Financeiras",
        "📋 Lista de Alunos",
        "🏢 Lista de Escolas"
    ])

    with tab_schools:
        st.subheader("Cadastrar Nova Escola")
        school_name = st.text_input("Nome da Escola", placeholder="Ex: Escola Estadual Machado de Assis")
        if st.button("Salvar Escola", type="primary"):
            success, msg = add_school(school_name)
            if success:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")

    with tab_classes:
        st.subheader("Cadastrar Nova Classe / Turma")
        schools = get_schools()
        if not schools:
            st.warning("Cadastre primeiro pelo menos uma escola na aba 'Escolas'.")
        else:
            school_dict = {s['name']: s['id'] for s in schools}
            sel_school = st.selectbox("Selecione a Escola", list(school_dict.keys()), key="class_school_select")
            class_name = st.text_input("Nome da Classe", placeholder="Ex: 5º Ano A")
            
            if st.button("Salvar Classe", type="primary"):
                success, msg = add_class(class_name, school_dict[sel_school])
                if success:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")

    with tab_teachers:
        st.subheader("Cadastrar Novo Professor")
        schools = get_schools()
        if not schools:
            st.warning("Cadastre escolas e turmas antes de adicionar professores.")
        else:
            school_dict = {s['name']: s['id'] for s in schools}
            sel_school_teacher = st.selectbox("Escola do Professor", list(school_dict.keys()), key="teacher_school")
            
            classes = get_classes_by_school(school_dict[sel_school_teacher])
            if not classes:
                st.warning("Nenhuma turma cadastrada para esta escola.")
            else:
                class_dict = {c['name']: c['id'] for c in classes}
                sel_class_teacher = st.selectbox("Classe/Turma do Professor", list(class_dict.keys()), key="teacher_class")
                
                prof_user = st.text_input("Usuário do Professor", key="prof_user")
                prof_pass = st.text_input("Senha", type="password", key="prof_pass")
                prof_pass_conf = st.text_input("Confirmar Senha", type="password", key="prof_pass_conf")
                
                if st.button("Salvar Professor", type="primary"):
                    success, msg = register_teacher(
                        prof_user, prof_pass, prof_pass_conf, 
                        school_dict[sel_school_teacher], class_dict[sel_class_teacher]
                    )
                    if success:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")

    with tab_students:
        st.subheader("Cadastrar Novo Aluno")
        schools = get_schools()
        if not schools:
            st.warning("Cadastre escolas e turmas antes de adicionar alunos.")
        else:
            school_dict = {s['name']: s['id'] for s in schools}
            sel_school_student = st.selectbox("Escola do Aluno", list(school_dict.keys()), key="student_school")
            
            classes = get_classes_by_school(school_dict[sel_school_student])
            if not classes:
                st.warning("Nenhuma turma cadastrada para esta escola.")
            else:
                class_dict = {c['name']: c['id'] for c in classes}
                sel_class_student = st.selectbox("Classe do Aluno", list(class_dict.keys()), key="student_class")
                
                std_user = st.text_input("Usuário do Aluno")
                std_pass = st.text_input("Senha", type="password")
                std_pass_conf = st.text_input("Confirmar Senha", type="password")
                
                if st.button("Salvar Aluno", type="primary"):
                    success, msg = register_student(
                        std_user, std_pass, std_pass_conf, 
                        school_dict[sel_school_student], class_dict[sel_class_student]
                    )
                    if success:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")

    with tab_finance:
        st.subheader("Operações Financeiras em Contas de Alunos")
        all_student_names = get_all_student_usernames()

        if not all_student_names:
            st.info("Nenhum aluno cadastrado para realizar operações financeiras.")
        else:
            operacao = st.radio(
                "Selecione a operação:",
                ["💵 Depositar B+", "💸 Sacar B+", "🔄 Transferir B+"],
                horizontal=True
            )
            st.divider()

            if operacao == "💵 Depositar B+":
                st.markdown("#### Depositar B+ na conta de um aluno")
                target_student = st.selectbox("Selecione o Aluno", all_student_names, key="adm_dep_student")
                dep_amount = st.number_input("Valor do Depósito (B+)", min_value=0.01, value=10.0, step=5.0, key="adm_dep_val")

                if st.button("Confirmar Depósito", type="primary", key="btn_adm_dep"):
                    success, msg = deposit_b_plus(target_student, dep_amount, st.session_state["user"])
                    if success:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")

                current_bal = float(get_balance(target_student))
                st.caption(f"Saldo atual de **{target_student}**: **{current_bal:.2f} B+**")

            elif operacao == "💸 Sacar B+":
                st.markdown("#### Sacar B+ da conta de um aluno")
                target_student = st.selectbox("Selecione o Aluno", all_student_names, key="adm_with_student")
                with_amount = st.number_input("Valor do Saque (B+)", min_value=0.01, value=10.0, step=5.0, key="adm_with_val")

                if st.button("Confirmar Saque", type="primary", key="btn_adm_with"):
                    desc = f"Saque efetuado pelo admin ({st.session_state['user']})"
                    success, msg = withdraw_b_plus(target_student, with_amount, description=desc)
                    if success:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")

                current_bal = float(get_balance(target_student))
                st.caption(f"Saldo atual de **{target_student}**: **{current_bal:.2f} B+**")

            elif operacao == "🔄 Transferir B+":
                st.markdown("#### Transferir B+ entre alunos")
                if len(all_student_names) < 2:
                    st.warning("É necessário ter pelo menos 2 alunos cadastrados para realizar transferências.")
                else:
                    sender_student = st.selectbox("Aluno de Origem (Quem envia)", all_student_names, key="adm_transf_sender")
                    receiver_options = [u for u in all_student_names if u != sender_student]
                    receiver_student = st.selectbox("Aluno de Destino (Quem recebe)", receiver_options, key="adm_transf_receiver")
                    transf_amount = st.number_input("Valor da Transferência (B+)", min_value=0.01, value=10.0, step=5.0, key="adm_transf_val")

                    if st.button("Confirmar Transferência", type="primary", key="btn_adm_transf"):
                        desc = f"Transferência efetuada pelo admin ({st.session_state['user']})"
                        success, msg = transfer_b_plus(sender_student, receiver_student, transf_amount, description=desc)
                        if success:
                            st.success(f"✅ {msg}")
                        else:
                            st.error(f"❌ {msg}")

                    sender_bal = float(get_balance(sender_student))
                    receiver_bal = float(get_balance(receiver_student))
                    st.caption(
                        f"Saldo de **{sender_student}**: **{sender_bal:.2f} B+** | "
                        f"Saldo de **{receiver_student}**: **{receiver_bal:.2f} B+**"
                    )

    with tab_list_students:
        st.subheader("Lista de Todos os Alunos Cadastrados")
        students = get_all_students()
        if not students:
            st.info("Nenhum aluno cadastrado no momento.")
        else:
            st.caption(f"Total de alunos cadastrados: **{len(students)}**")
            df_students = pd.DataFrame(students)
            st.dataframe(df_students, use_container_width=True, hide_index=True)

    with tab_list_schools:
        st.subheader("Lista de Todas as Escolas Cadastradas")
        schools_details = get_all_schools_details()
        if not schools_details:
            st.info("Nenhuma escola cadastrada no momento.")
        else:
            st.caption(f"Total de escolas cadastradas: **{len(schools_details)}**")
            df_schools = pd.DataFrame(schools_details)
            st.dataframe(df_schools, use_container_width=True, hide_index=True)

# --- PAINEL DO PROFESSOR (Tipo 3) ---
elif st.session_state["user_type"] == 3:
    current_user = st.session_state["user"]
    teacher_school_id = st.session_state["school_id"]
    teacher_class_id = st.session_state["class_id"]

    school_name, class_name = get_school_and_class_names(teacher_school_id, teacher_class_id)

    st.sidebar.title("👨‍🏫 Painel do Professor")
    st.sidebar.write(f"Professor: **{current_user}**")
    st.sidebar.write(f"Escola: **{school_name}**")
    st.sidebar.write(f"Turma: **{class_name}**")
    if st.sidebar.button("Sair", type="secondary", use_container_width=True):
        logout()

    st.title("👨‍🏫 Portal do Professor")
    st.info(f"📍 **Escola Vinculada:** {school_name} | **Turma:** {class_name}")

    tab_add_student, tab_school_students, tab_settings = st.tabs([
        "➕ Cadastrar Aluno", 
        "📋 Alunos da Escola", 
        "🔑 Alterar Senha"
    ])

    with tab_add_student:
        st.subheader(f"Cadastrar Aluno em {class_name}")
        std_user = st.text_input("Usuário do Aluno", key="t_std_user")
        std_pass = st.text_input("Senha", type="password", key="t_std_pass")
        std_pass_conf = st.text_input("Confirmar Senha", type="password", key="t_std_pass_conf")
        
        if st.button("Cadastrar Aluno", type="primary"):
            success, msg = register_student(
                std_user, std_pass, std_pass_conf, 
                teacher_school_id, teacher_class_id
            )
            if success:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")

    with tab_school_students:
        st.subheader(f"Alunos da Escola ({school_name})")
        students = get_students_by_school(teacher_school_id)
        if not students:
            st.info("Nenhum aluno cadastrado nesta escola ainda.")
        else:
            df = pd.DataFrame(students)
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab_settings:
        st.subheader("Alterar Senha")
        old_p = st.text_input("Senha Atual", type="password", key="t_old_p")
        new_p = st.text_input("Nova Senha", type="password", key="t_new_p")
        
        if st.button("Salvar Nova Senha", type="primary"):
            success, msg = change_password(current_user, old_p, new_p)
            if success:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")

# --- PAINEL DO ALUNO (Tipo 1) ---
else:
    current_user = st.session_state["user"]
    balance = float(get_balance(current_user))

    st.sidebar.title("👋 Menu do Aluno")
    st.sidebar.write(f"Usuário: **{current_user}**")
    if st.sidebar.button("Sair", type="secondary", use_container_width=True):
        logout()

    st.title("🪙 B+ Bank")
    st.metric(label="Seu Saldo Atual", value=f"{balance:.2f} B+")

    tab_transfer, tab_withdraw, tab_history, tab_settings = st.tabs([
        "💸 Transferir", 
        "💵 Sacar", 
        "📜 Extrato", 
        "🔑 Alterar Senha"
    ])

    with tab_transfer:
        st.subheader("Transferência de B+")
        other_users = get_other_users(current_user)
        if not other_users:
            st.info("Não há outros alunos cadastrados para receber transferências.")
        else:
            destinatario = st.selectbox("Selecione o Destinatário", other_users)
            valor_transf = st.number_input("Valor (B+)", min_value=1.0, value=10.0, step=5.0)
            
            if st.button("Confirmar Envio", type="primary"):
                success, msg = transfer_b_plus(current_user, destinatario, valor_transf)
                if success:
                    st.toast(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")

    with tab_withdraw:
        st.subheader("Sacar B+")
        valor_saque = st.number_input("Valor do Saque (B+)", min_value=1.0, max_value=max(1.0, balance), value=10.0, step=5.0)
        
        if st.button("Confirmar Saque", type="primary"):
            success, msg = withdraw_b_plus(current_user, valor_saque)
            if success:
                st.toast(f"✅ {msg}")
                st.rerun()
            else:
                st.error(f"❌ {msg}")

    with tab_history:
        st.subheader("Extrato de Transações")
        history = get_history(current_user)
        if not history:
            st.info("Nenhuma movimentação realizada ainda.")
        else:
            records = []
            for row in history:
                sender = row["sender"]
                receiver = row["receiver"]
                amt = float(row["amount"])
                timestamp = row["timestamp"]
                desc = row["description"]

                if sender == current_user:
                    tipo = "ENVIO ⬆️"
                    outro = f"Para: {receiver}"
                    val_str = f"-{amt:.2f} B+"
                else:
                    tipo = "RECEBIMENTO ⬇️"
                    outro = f"De: {sender}"
                    val_str = f"+{amt:.2f} B+"
                
                records.append({
                    "Tipo": tipo,
                    "Origem/Destino": outro,
                    "Descrição": desc,
                    "Valor": val_str,
                    "Data/Hora": str(timestamp)
                })
            
            df_hist = pd.DataFrame(records)
            st.dataframe(df_hist, use_container_width=True, hide_index=True)

    with tab_settings:
        st.subheader("Alterar Senha")
        old_p = st.text_input("Senha Atual", type="password", key="s_old_p")
        new_p = st.text_input("Nova Senha", type="password", key="s_new_p")
        
        if st.button("Salvar Nova Senha", type="primary"):
            success, msg = change_password(current_user, old_p, new_p)
            if success:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")
