from services.connection import get_db


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
