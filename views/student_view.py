import pandas as pd
import streamlit as st
import backend as db


def render_student_dashboard(logout_callback):
    current_user = st.session_state["user"]
    student_school_id = st.session_state["school_id"]
    student_class_id = st.session_state["class_id"]

    school_name, class_name = db.get_school_and_class_names(student_school_id, student_class_id)
    balance = float(db.get_balance(current_user))
    pending_out = db.get_pending_outgoing_amount(current_user)

    st.sidebar.title("👋 Menu do Aluno")
    st.sidebar.write(f"Usuário: **{current_user}**")
    st.sidebar.write(f"Escola: **{school_name}**")
    st.sidebar.write(f"Série/Turma: **{class_name}**")
    if st.sidebar.button("Sair", type="secondary", use_container_width=True):
        logout_callback()

    st.title("🪙 B+ Bank")
    st.metric(label="Seu Saldo Atual", value=f"{balance:.2f} B+")
    if pending_out > 0:
        st.caption(f"⏳ Você possui **{pending_out:.2f} B+** em solicitações aguardando aprovação do administrador.")

    tab_transfer, tab_withdraw, tab_history, tab_settings = st.tabs([
        "💸 Transferir",
        "💵 Sacar",
        "📜 Extrato",
        "🔑 Alterar Senha"
    ])

    with tab_transfer:
        st.subheader("Transferência de B+")
        st.caption("ℹ️ Você pode solicitar transferência de B+ para alunos de qualquer escola e turma. A operação será efetivada após aprovação do administrador.")
        grouped_students = db.get_students_grouped_by_school(exclude_username=current_user)
        if not grouped_students:
            st.info("Não há outros alunos cadastrados para receber transferências.")
        else:
            school_options = list(grouped_students.keys())
            default_school_idx = school_options.index(school_name) if school_name in school_options else 0
            selected_dest_school = st.selectbox(
                "1. Selecione a Escola do Destinatário",
                school_options,
                index=default_school_idx,
                key="student_transf_school"
            )
            school_students = grouped_students[selected_dest_school]
            student_labels = [
                f"{item['username']} ({item['class_name']})" for item in school_students
            ]
            label_to_username = {
                f"{item['username']} ({item['class_name']})": item["username"]
                for item in school_students
            }
            selected_label = st.selectbox(
                f"2. Selecione o Destinatário ({selected_dest_school})",
                student_labels,
                key="student_transf_recipient"
            )
            destinatario = label_to_username[selected_label]
            valor_transf = st.number_input("Valor (B+)", min_value=1.0, value=10.0, step=5.0)

            if st.button("Solicitar Envio", type="primary"):
                success, msg = db.request_transfer(
                    current_user,
                    "Aluno",
                    current_user,
                    destinatario,
                    valor_transf,
                    description="Transferência solicitada pelo aluno"
                )
                if success:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")

    with tab_withdraw:
        st.subheader("Sacar B+")
        st.caption("ℹ️ O saque será efetivado após aprovação do administrador.")
        max_avail = max(1.0, balance - pending_out)
        valor_saque = st.number_input("Valor do Saque (B+)", min_value=1.0, max_value=max_avail, value=min(10.0, max_avail), step=5.0)

        if st.button("Solicitar Saque", type="primary"):
            success, msg = db.request_withdraw(current_user, "Aluno", current_user, valor_saque, description="Saque solicitado pelo aluno")
            if success:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")

    with tab_history:
        st.subheader("Extrato de Transações Efetivadas")
        history = db.get_history(current_user)
        if not history:
            st.info("Nenhuma movimentação efetivada ainda.")
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

        st.divider()
        st.subheader("Status de Solicitações (Depósitos, Saques e Transferências)")
        student_reqs = db.get_user_operation_requests(current_user)
        if not student_reqs:
            st.info("Nenhuma solicitação registrada.")
        else:
            req_records = []
            for rq in student_reqs:
                st_label = "⏳ PENDENTE" if rq["status"] == "PENDENTE" else ("✅ APROVADA" if rq["status"] == "APROVADA" else "❌ REPROVADA")
                if rq["op_type"] == "DEPOSITO":
                    tipo_label = "Depósito"
                    origem_label = "ADMIN / DEPÓSITO"
                    destino_label = rq["receiver_username"]
                elif rq["op_type"] == "SAQUE":
                    tipo_label = "Saque"
                    origem_label = rq["sender_username"]
                    destino_label = "CAIXA / SAQUE"
                else:
                    tipo_label = "Transferência"
                    origem_label = rq["sender_username"]
                    destino_label = rq["receiver_username"]

                req_records.append({
                    "ID": rq["id"],
                    "Tipo": tipo_label,
                    "Origem": origem_label,
                    "Destino": destino_label,
                    "Valor (B+)": f"{float(rq['amount']):.2f}",
                    "Motivo / Descrição": rq["description"] or "-",
                    "Status": st_label,
                    "Obs. Admin": rq["review_note"] or "-",
                    "Data": str(rq["created_at"])
                })
            st.dataframe(pd.DataFrame(req_records), use_container_width=True, hide_index=True)

    with tab_settings:
        st.subheader("Alterar Senha")

        if st.session_state.pop("student_clear_pass_fields", False):
            st.session_state["s_old_p"] = ""
            st.session_state["s_new_p"] = ""

        pass_feedback = st.session_state.pop("student_pass_feedback", None)
        if pass_feedback:
            level, text = pass_feedback
            if level == "success":
                st.success(text)
            else:
                st.error(text)

        old_p = st.text_input("Senha Atual", type="password", key="s_old_p")
        new_p = st.text_input("Nova Senha", type="password", key="s_new_p")

        if st.button("Salvar Nova Senha", type="primary"):
            success, msg = db.change_password(current_user, old_p, new_p)
            if success:
                st.session_state["student_pass_feedback"] = ("success", f"✅ {msg}")
                st.session_state["student_clear_pass_fields"] = True
                st.rerun()
            else:
                st.error(f"❌ {msg}")
