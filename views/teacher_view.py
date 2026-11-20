import pandas as pd
import streamlit as st
import backend as db

def render_teacher_dashboard(logout_callback):
    current_user = st.session_state["user"]
    teacher_school_id = st.session_state["school_id"]
    teacher_class_id = st.session_state["class_id"]

    school_name, class_name = db.get_school_and_class_names(teacher_school_id, teacher_class_id)

    st.sidebar.title("👨‍🏫 Painel do Professor")
    st.sidebar.write(f"Professor: **{current_user}**")
    st.sidebar.write(f"Escola: **{school_name}**")
    st.sidebar.write(f"Turma: **{class_name}**")
    if st.sidebar.button("Sair", type="secondary", use_container_width=True):
        logout_callback()

    st.title("👨‍🏫 Portal do Professor")
    st.info(f"📍 **Escola Vinculada:** {school_name} | **Turma:** {class_name}")

    tab_add_student, tab_finance, tab_school_students, tab_settings = st.tabs([
        "➕ Cadastrar Aluno",
        "💰 Operações Financeiras",
        "📋 Alunos da Escola", 
        "🔑 Alterar Senha"
    ])

    with tab_add_student:
        st.subheader(f"Cadastrar Aluno em {class_name}")
        std_user = st.text_input("Usuário do Aluno", key="t_std_user")
        std_pass = st.text_input("Senha", type="password", key="t_std_pass")
        std_pass_conf = st.text_input("Confirmar Senha", type="password", key="t_std_pass_conf")
        
        if st.button("Cadastrar Aluno", type="primary"):
            success, msg = db.register_student(
                std_user, std_pass, std_pass_conf, 
                teacher_school_id, teacher_class_id
            )
            if success:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")

    with tab_finance:
        st.subheader(f"Operações Financeiras — Turma {class_name}")
        st.caption("ℹ️ Depósitos, saques e transferências solicitados pelo professor passam pela aprovação do administrador antes de serem efetivados.")
        class_student_names = db.get_student_usernames_by_class(teacher_class_id)

        if not class_student_names:
            st.info("Nenhum aluno cadastrado na sua turma para realizar operações financeiras.")
        else:
            operacao = st.radio(
                "Selecione a operação:",
                ["💵 Depositar B+", "💸 Sacar B+", "🔄 Transferir B+"],
                horizontal=True,
                key="prof_op_radio"
            )
            st.divider()

            if operacao == "💵 Depositar B+":
                st.markdown(f"#### Solicitar Depósito de B+ para alunos da turma ({class_name})")
                selected_students = st.multiselect(
                    "Selecione os Alunos da Turma",
                    class_student_names,
                    placeholder="Escolha um ou mais alunos da sua turma...",
                    key="prof_dep_students"
                )

                if not selected_students:
                    st.info("Selecione pelo menos um aluno da sua turma para definir valores e motivos.")
                else:
                    dep_entries = {}
                    for std in selected_students:
                        curr_bal = float(db.get_balance(std))
                        with st.container(border=True):
                            st.markdown(f"👤 **{std}** — 💰 Saldo atual: **{curr_bal:.2f} B+**")
                            col_val, col_reason = st.columns([1, 2])
                            with col_val:
                                val = st.number_input(
                                    "Valor do Depósito (B+)",
                                    min_value=0.01,
                                    value=10.0,
                                    step=5.0,
                                    key=f"prof_dep_val_{std}"
                                )
                            with col_reason:
                                reason = st.text_input(
                                    "Motivo do depósito",
                                    placeholder="Ex: Tarefa concluída / Bom comportamento",
                                    key=f"prof_dep_reason_{std}"
                                )
                            dep_entries[std] = (val, reason)

                    if st.button("Solicitar Depósitos", type="primary", key="btn_prof_dep"):
                        for std, (val, reason) in dep_entries.items():
                            success, msg = db.request_deposit(current_user, "Professor", std, val, reason=reason)
                            if success:
                                st.success(f"✅ {msg}")
                            else:
                                st.error(f"❌ {msg}")

            elif operacao == "💸 Sacar B+":
                st.markdown(f"#### Solicitar Saque de B+ para alunos da turma ({class_name})")
                selected_students = st.multiselect(
                    "Selecione os Alunos da Turma",
                    class_student_names,
                    placeholder="Escolha um ou mais alunos da sua turma...",
                    key="prof_with_students"
                )

                if not selected_students:
                    st.info("Selecione pelo menos um aluno da sua turma para definir valores e motivos.")
                else:
                    with_entries = {}
                    for std in selected_students:
                        curr_bal = float(db.get_balance(std))
                        pending_out = db.get_pending_outgoing_amount(std)
                        with st.container(border=True):
                            st.markdown(
                                f"👤 **{std}** — 💰 Saldo atual: **{curr_bal:.2f} B+** | "
                                f"⏳ Pendente: **{pending_out:.2f} B+**"
                            )
                            col_val, col_reason = st.columns([1, 2])
                            with col_val:
                                val = st.number_input(
                                    "Valor do Saque (B+)",
                                    min_value=0.01,
                                    value=10.0,
                                    step=5.0,
                                    key=f"prof_with_val_{std}"
                                )
                            with col_reason:
                                reason = st.text_input(
                                    "Motivo do saque",
                                    placeholder="Ex: Compra na feirinha da turma",
                                    key=f"prof_with_reason_{std}"
                                )
                            with_entries[std] = (val, reason)

                    if st.button("Solicitar Saques", type="primary", key="btn_prof_with"):
                        for std, (val, reason) in with_entries.items():
                            reason_clean = reason.strip() if reason else ""
                            base_desc = f"Saque solicitado pelo professor ({current_user})"
                            full_desc = f"{base_desc} | Motivo: {reason_clean}" if reason_clean else base_desc
                            success, msg = db.request_withdraw(current_user, "Professor", std, val, description=full_desc)
                            if success:
                                st.success(f"✅ {msg}")
                            else:
                                st.error(f"❌ {msg}")

            elif operacao == "🔄 Transferir B+":
                st.markdown("#### Solicitar Transferência de B+ entre alunos da turma")
                if len(class_student_names) < 2:
                    st.warning("É necessário ter pelo menos 2 alunos cadastrados na sua turma para realizar transferências.")
                else:
                    sender_student = st.selectbox("Aluno de Origem (Quem envia)", class_student_names, key="prof_transf_sender")
                    receiver_options = [u for u in class_student_names if u != sender_student]
                    receiver_student = st.selectbox("Aluno de Destino (Quem recebe)", receiver_options, key="prof_transf_receiver")
                    transf_amount = st.number_input("Valor da Transferência (B+)", min_value=0.01, value=10.0, step=5.0, key="prof_transf_val")

                    if st.button("Solicitar Transferência", type="primary", key="btn_prof_transf"):
                        desc = f"Transferência solicitada pelo professor ({current_user})"
                        success, msg = db.request_transfer(current_user, "Professor", sender_student, receiver_student, transf_amount, description=desc)
                        if success:
                            st.success(f"✅ {msg}")
                        else:
                            st.error(f"❌ {msg}")

                    sender_bal = float(db.get_balance(sender_student))
                    receiver_bal = float(db.get_balance(receiver_student))
                    st.caption(
                        f"Saldo de **{sender_student}**: **{sender_bal:.2f} B+** | "
                        f"Saldo de **{receiver_student}**: **{receiver_bal:.2f} B+**"
                    )

            st.divider()
            st.markdown("#### Minhas Solicitações Recentes")
            prof_reqs = db.get_user_operation_requests(current_user)
            if not prof_reqs:
                st.info("Nenhuma solicitação realizada ainda.")
            else:
                req_rows = []
                for rq in prof_reqs:
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

                    req_rows.append({
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
                st.dataframe(pd.DataFrame(req_rows), use_container_width=True, hide_index=True)

    with tab_school_students:
        st.subheader(f"Alunos da Escola ({school_name})")
        students = db.get_students_by_school(teacher_school_id)
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
            success, msg = db.change_password(current_user, old_p, new_p)
            if success:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")
