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
    # Busca a URL de conexão configurada nos Secrets do Streamlit ou usa fallback local
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
                # Tabela de Escolas
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS schools (
                        id SERIAL PRIMARY KEY,
                        name TEXT UNIQUE NOT NULL
                    )
                ''')

                # Tabela de Classes / Turmas
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS classes (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        school_id INTEGER NOT NULL REFERENCES schools(id)
                    )
                ''')

                # Tabela de Usuários
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

                # Tabela de Transações
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
    finally:
        conn.close()

def login_user(username, password):
    username = username.strip()
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT username, salt, password_hash, balance, user_type FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            
            if user and verify_password(user["salt"], user["password_hash"], password):
                return True, {
                    "username": user["username"], 
                    "balance": user["balance"], 
                    "user_type": user["user_type"]
                }
        return False, "Usuário ou senha incorretos."
    finally:
        conn.close()

def get_all_students():
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT u.id AS ID, u.username AS Aluno, 
                       COALESCE(s.name, 'N/A') AS Escola, 
                       COALESCE(c.name, 'N/A') AS Classe,
                       u.balance AS "Saldo (B+)"
                FROM users u 
                LEFT JOIN schools s ON u.school_id = s.id 
                LEFT JOIN classes c ON u.class_id = c.id 
                WHERE u.user_type = 1 
                ORDER BY u.id ASC
            ''')
            return cursor.fetchall()
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
            return res["balance"] if res else 0.0
    finally:
        conn.close()

def transfer_b_plus(sender, receiver, amount):
    if not receiver:
        return False, "Selecione um destinatário válido."
    receiver = receiver.strip()
    if amount <= 0:
        return False, "O valor deve ser maior que zero."
    if sender.lower() == receiver.lower():
        return False, "Não é possível transferir para você mesmo."

    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT balance FROM users WHERE username = %s", (receiver,))
                rec = cursor.fetchone()
                if not rec:
                    return False, "Usuário destinatário não existe."

                cursor.execute("SELECT balance FROM users WHERE username = %s", (sender,))
                sender_bal = cursor.fetchone()["balance"]
                
                if sender_bal < amount:
                    return False, f"Saldo insuficiente! Saldo atual: {sender_bal:.2f} B+."

                cursor.execute("UPDATE users SET balance = balance - %s WHERE username = %s", (amount, sender))
                cursor.execute("UPDATE users SET balance = balance + %s WHERE username = %s", (amount, receiver))
                cursor.execute(
                    "INSERT INTO transactions (sender, receiver, amount, description) VALUES (%s, %s, %s, %s)",
                    (sender, receiver, amount, "Transferência efetuada")
                )
                return True, f"Sucesso! {amount:.2f} B+ enviadas para {receiver}."
    except Exception as e:
        return False, f"Erro ao processar a transação: {str(e)}"
    finally:
        conn.close()

def withdraw_b_plus(username, amount):
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

                current_balance = res["balance"]
                if current_balance < amount:
                    return False, f"Saldo insuficiente! Saldo disponível: {current_balance:.2f} B+."

                cursor.execute("UPDATE users SET balance = balance - %s WHERE username = %s", (amount, username))
                cursor.execute(
                    "INSERT INTO transactions (sender, receiver, amount, description) VALUES (%s, %s, %s, %s)",
                    (username, "CAIXA / SAQUE", amount, "Saque em espécie de B+")
                )
                return True, f"Saque de {amount:.2f} B+ realizado com sucesso!"
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

def logout():
    st.session_state["user"] = None
    st.session_state["user_type"] = 1
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
    
    tab_schools, tab_classes, tab_students, tab_list = st.tabs([
        "🏫 Escolas", 
        "📚 Turmas", 
        "➕ Cadastrar Aluno", 
        "📋 Lista de Alunos"
    ])

    # Tab 1: Cadastrar Escola
    with tab_schools:
        st.subheader("Cadastrar Nova Escola")
        school_name = st.text_input("Nome da Escola", placeholder="Ex: Escola Estadual Machado de Assis")
        if st.button("Salvar Escola", type="primary"):
            success, msg = add_school(school_name)
            if success:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")

    # Tab 2: Cadastrar Turma
    with tab_classes:
        st.subheader("Cadastrar Nova Classe / Turma")
        schools = get_schools()
        if not schools:
            st.warning("Cadastre primeiro pelo menos uma escola na aba 'Escolas'.")
        else:
            school_dict = {s['name']: s['id'] for s in schools}
            sel_school = st.selectbox("Selecione a Escola", list(school_dict.keys()))
            class_name = st.text_input("Nome da Classe", placeholder="Ex: 5º Ano A")
            
            if st.button("Salvar Classe", type="primary"):
                success, msg = add_class(class_name, school_dict[sel_school])
                if success:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")

    # Tab 3: Cadastrar Aluno
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

    # Tab 4: Lista de Alunos
    with tab_list:
        st.subheader("Lista de Alunos Cadastrados")
        students = get_all_students()
        if not students:
            st.info("Nenhum aluno cadastrado no momento.")
        else:
            df = pd.DataFrame([dict(s) for s in students])
            st.dataframe(df, use_container_width=True, hide_index=True)

# --- PAINEL DO ALUNO (Tipo 1) ---
else:
    current_user = st.session_state["user"]
    balance = get_balance(current_user)

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

    # Tab 1: Transferência
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
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")

    # Tab 2: Saque
    with tab_withdraw:
        st.subheader("Sacar B+")
        valor_saque = st.number_input("Valor do Saque (B+)", min_value=1.0, max_value=float(balance) if balance > 0 else 1.0, value=10.0, step=5.0)
        
        if st.button("Confirmar Saque", type="primary"):
            success, msg = withdraw_b_plus(current_user, valor_saque)
            if success:
                st.success(f"✅ {msg}")
                st.rerun()
            else:
                st.error(f"❌ {msg}")

    # Tab 3: Extrato
    with tab_history:
        st.subheader("Extrato de Transações")
        history = get_history(current_user)
        if not history:
            st.info("Nenhuma movimentação realizada ainda.")
        else:
            records = []
            for sender, receiver, amount, timestamp, desc in history:
                if sender == current_user:
                    tipo = "ENVIO ⬆️"
                    outro = f"Para: {receiver}"
                    val_str = f"-{amount:.2f} B+"
                else:
                    tipo = "RECEBIMENTO ⬇️"
                    outro = f"De: {sender}"
                    val_str = f"{amount:.2f} B+"
                
                records.append({
                    "Tipo": tipo,
                    "Origem/Destino": outro,
                    "Descrição": desc,
                    "Valor": val_str,
                    "Data/Hora": timestamp
                })
            
            df_hist = pd.DataFrame(records)
            st.dataframe(df_hist, use_container_width=True, hide_index=True)

    # Tab 4: Alterar Senha
    with tab_settings:
        st.subheader("Alterar Senha")
        old_p = st.text_input("Senha Atual", type="password")
        new_p = st.text_input("Nova Senha", type="password")
        
        if st.button("Salvar Nova Senha", type="primary"):
            success, msg = change_password(current_user, old_p, new_p)
            if success:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")
