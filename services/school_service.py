import psycopg2
from services.connection import get_db, hash_password


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
                    """INSERT INTO users (username, salt, password_hash, balance, user_type, school_id, class_id, welcome_bonus_claimed) 
                       VALUES (%s, %s, %s, %s, 1, %s, %s, FALSE)""",
                    (username, salt_hex, hash_hex, 0.0, school_id, class_id)
                )
                return True, f"Aluno '{username}' cadastrado com sucesso!"
    except psycopg2.IntegrityError:
        return False, "Nome de usuário já está em uso."
    except Exception as e:
        return False, f"Erro ao cadastrar aluno: {str(e)}"
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


def get_all_teachers():
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT u.id AS "ID", u.username AS "Professor", 
                       COALESCE(s.name, 'N/A') AS "Escola", 
                       COALESCE(c.name, 'N/A') AS "Classe"
                FROM users u 
                LEFT JOIN schools s ON u.school_id = s.id 
                LEFT JOIN classes c ON u.class_id = c.id 
                WHERE u.user_type = 3 
                ORDER BY u.id ASC
            ''')
            return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def update_user_school_and_class(username, school_id, class_id):
    if not username or not school_id or not class_id:
        return False, "Selecione um usuário, escola e turma válidos."
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET school_id = %s, class_id = %s WHERE username = %s",
                    (school_id, class_id, username)
                )
                if cursor.rowcount == 0:
                    return False, f"Usuário '{username}' não encontrado."
                return True, f"Escola e turma de '{username}' atualizadas com sucesso!"
    except Exception as e:
        return False, f"Erro ao atualizar perfil: {str(e)}"
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


def get_students_by_class(class_id):
    if not class_id:
        return []
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
                WHERE u.user_type = 1 AND u.class_id = %s
                ORDER BY u.username ASC
            ''', (class_id,))
            rows = cursor.fetchall()
            students = []
            for r in rows:
                r_dict = dict(r)
                r_dict["Saldo (B+)"] = float(r_dict["Saldo (B+)"])
                students.append(r_dict)
            return students
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


def get_other_users(current_username, school_id=None):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            if school_id is not None:
                cursor.execute(
                    "SELECT username FROM users WHERE username != %s AND user_type = 1 AND school_id = %s ORDER BY username ASC",
                    (current_username, school_id)
                )
            else:
                cursor.execute(
                    "SELECT username FROM users WHERE username != %s AND user_type = 1 ORDER BY username ASC",
                    (current_username,)
                )
            return [row["username"] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_students_grouped_by_school(exclude_username=None):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            if exclude_username:
                cursor.execute(
                    """SELECT u.username,
                              COALESCE(s.name, 'Sem Escola') AS school_name,
                              COALESCE(c.name, 'Sem Turma') AS class_name
                       FROM users u
                       LEFT JOIN schools s ON u.school_id = s.id
                       LEFT JOIN classes c ON u.class_id = c.id
                       WHERE u.user_type = 1 AND u.username != %s
                       ORDER BY school_name ASC, class_name ASC, u.username ASC""",
                    (exclude_username,)
                )
            else:
                cursor.execute(
                    """SELECT u.username,
                              COALESCE(s.name, 'Sem Escola') AS school_name,
                              COALESCE(c.name, 'Sem Turma') AS class_name
                       FROM users u
                       LEFT JOIN schools s ON u.school_id = s.id
                       LEFT JOIN classes c ON u.class_id = c.id
                       WHERE u.user_type = 1
                       ORDER BY school_name ASC, class_name ASC, u.username ASC"""
                )
            rows = cursor.fetchall()
            grouped = {}
            for r in rows:
                sch = r["school_name"]
                grouped.setdefault(sch, []).append({
                    "username": r["username"],
                    "class_name": r["class_name"],
                    "school_name": sch,
                })
            return grouped
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
