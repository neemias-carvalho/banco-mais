import pandas as pd
import streamlit as st
import backend as db


def _op_matches_school(op, selected_school):
    if selected_school == "Todas as escolas":
        return True
    if op["op_type"] == "DEPOSITO":
        return op["receiver_school"] == selected_school
    if op["op_type"] == "SAQUE":
        return op["sender_school"] == selected_school
    return op["sender_school"] == selected_school or op["receiver_school"] == selected_school


def _clear_val_selections():
    st.session_state["val_select_all"] = False
    for key in list(st.session_state.keys()):
        if key.startswith("val_chk_"):
            st.session_state[key] = False


def _toggle_select_all(op_ids):
    target_state = st.session_state.get("val_select_all", False)
    for oid in op_ids:
        st.session_state[f"val_chk_{oid}"] = target_state


def render_admin_dashboard(logout_callback):
    st.sidebar.title("🛡️ Painel Admin")
    st.sidebar.write(f"Conectado como: **{st.session_state['user']}**")
    if st.sidebar.button("Sair", type="secondary", use_container_width=True):
        logout_callback()

    st.title("🛡️ Administração B+ Bank")
    
    (
        tab_schools,
        tab_classes,
        tab_teachers,
        tab_students,
        tab_finance,
        tab_validation,
        tab_list_students,
        tab_list_schools,
    ) = st.tabs([
        "🏫 Escolas", 
        "📚 Turmas", 
        "👨‍🏫 Cadastrar Professor",
        "➕ Cadastrar Aluno",
        "💰 Operações Financeiras",
        "✅ Validação de Operações",
        "📋 Lista de Alunos",
        "🏢 Lista de Escolas"
    ])

    with tab_schools:
        st.subheader("Cadastrar Nova Escola")
        with st.form("form_add_school", clear_on_submit=True):
            school_name = st.text_input("Nome da Escola", placeholder="Ex: Escola Estadual Machado de Assis")
            submitted_school = st.form_submit_button("Salvar Escola", type="primary")
        if submitted_school:
            success, msg = db.add_school(school_name)
            if success:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")

    with tab_classes:
        st.subheader("Cadastrar Nova Classe / Turma")
        schools = db.get_schools()
        if not schools:
            st.warning("Cadastre primeiro pelo menos uma escola na aba 'Escolas'.")
        else:
            school_dict = {s['name']: s['id'] for s in schools}
            sel_school = st.selectbox("Selecione a Escola", list(school_dict.keys()), key="class_school_select")
            with st.form("form_add_class", clear_on_submit=True):
                class_name = st.text_input("Nome da Classe", placeholder="Ex: 5º Ano A")
                submitted_class = st.form_submit_button("Salvar Classe", type="primary")
            if submitted_class:
                success, msg = db.add_class(class_name, school_dict[sel_school])
                if success:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")

    with tab_teachers:
        st.subheader("Cadastrar Novo Professor")
        schools = db.get_schools()
        if not schools:
            st.warning("Cadastre escolas e turmas antes de adicionar professores.")
        else:
            school_dict = {s['name']: s['id'] for s in schools}
            sel_school_teacher = st.selectbox("Escola do Professor", list(school_dict.keys()), key="teacher_school")
            
            classes = db.get_classes_by_school(school_dict[sel_school_teacher])
            if not classes:
                st.warning("Nenhuma turma cadastrada para esta escola.")
            else:
                class_dict = {c['name']: c['id'] for c in classes}
                sel_class_teacher = st.selectbox("Classe/Turma do Professor", list(class_dict.keys()), key="teacher_class")
                
                with st.form("form_add_teacher", clear_on_submit=True):
                    prof_user = st.text_input("Usuário do Professor")
                    prof_pass = st.text_input("Senha", type="password")
                    prof_pass_conf = st.text_input("Confirmar Senha", type="password")
                    submitted_teacher = st.form_submit_button("Salvar Professor", type="primary")
                
                if submitted_teacher:
                    success, msg = db.register_teacher(
                        prof_user, prof_pass, prof_pass_conf, 
                        school_dict[sel_school_teacher], class_dict[sel_class_teacher]
                    )
                    if success:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")

    with tab_students:
        st.subheader("Cadastrar Novo Aluno")
        schools = db.get_schools()
        if not schools:
            st.warning("Cadastre escolas e turmas antes de adicionar alunos.")
        else:
            school_dict = {s['name']: s['id'] for s in schools}
            sel_school_student = st.selectbox("Escola do Aluno", list(school_dict.keys()), key="student_school")
            
            classes = db.get_classes_by_school(school_dict[sel_school_student])
            if not classes:
                st.warning("Nenhuma turma cadastrada para esta escola.")
            else:
                class_dict = {c['name']: c['id'] for c in classes}
                sel_class_student = st.selectbox("Classe do Aluno", list(class_dict.keys()), key="student_class")
                
                with st.form("form_add_student", clear_on_submit=True):
                    std_user = st.text_input("Usuário do Aluno")
                    std_pass = st.text_input("Senha", type="password")
                    std_pass_conf = st.text_input("Confirmar Senha", type="password")
                    submitted_student = st.form_submit_button("Salvar Aluno", type="primary")
                
                if submitted_student:
                    success, msg = db.register_student(
                        std_user, std_pass, std_pass_conf, 
                        school_dict[sel_school_student], class_dict[sel_class_student]
                    )
                    if success:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")

    with tab_finance:
        st.subheader("Operações Financeiras em Contas de Alunos")
        all_student_names = db.get_all_student_usernames()
        student_school_map = db.get_students_school_map()

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
                st.markdown("#### Depositar B+ para múltiplos alunos")
                selected_students = st.multiselect(
                    "Selecione os Alunos",
                    all_student_names,
                    placeholder="Escolha um ou mais alunos...",
                    key="adm_dep_students"
                )

                if not selected_students:
                    st.info("Selecione pelo menos um aluno acima para definir valores e motivos.")
                else:
                    dep_entries = {}
                    for std in selected_students:
                        std_school = student_school_map.get(std, "N/A")
                        curr_bal = float(db.get_balance(std))
                        with st.container(border=True):
                            st.markdown(f"👤 **{std}** — 🏫 Escola: **{std_school}** | 💰 Saldo atual: **{curr_bal:.2f} B+**")
                            col_val, col_reason = st.columns([1, 2])
                            with col_val:
                                val = st.number_input(
                                    "Valor (B+)",
                                    min_value=0.01,
                                    value=10.0,
                                    step=5.0,
                                    key=f"adm_dep_val_{std}"
                                )
                            with col_reason:
                                reason = st.text_input(
                                    "Motivo do depósito",
                                    placeholder="Ex: Participação em atividade",
                                    key=f"adm_dep_reason_{std}"
                                )
                            dep_entries[std] = (val, reason)

                    if st.button("Confirmar Depósitos", type="primary", key="btn_adm_dep"):
                        for std, (val, reason) in dep_entries.items():
                            success, msg = db.deposit_b_plus(std, val, st.session_state["user"], reason=reason)
                            if success:
                                st.success(f"✅ {msg}")
                            else:
                                st.error(f"❌ {msg}")

            elif operacao == "💸 Sacar B+":
                st.markdown("#### Sacar B+ de múltiplos alunos")
                selected_students = st.multiselect(
                    "Selecione os Alunos",
                    all_student_names,
                    placeholder="Escolha um ou mais alunos...",
                    key="adm_with_students"
                )

                if not selected_students:
                    st.info("Selecione pelo menos um aluno acima para definir valores e motivos.")
                else:
                    with_entries = {}
                    for std in selected_students:
                        std_school = student_school_map.get(std, "N/A")
                        curr_bal = float(db.get_balance(std))
                        with st.container(border=True):
                            st.markdown(f"👤 **{std}** — 🏫 Escola: **{std_school}** | 💰 Saldo atual: **{curr_bal:.2f} B+**")
                            col_val, col_reason = st.columns([1, 2])
                            with col_val:
                                val = st.number_input(
                                    "Valor do Saque (B+)",
                                    min_value=0.01,
                                    value=10.0,
                                    step=5.0,
                                    key=f"adm_with_val_{std}"
                                )
                            with col_reason:
                                reason = st.text_input(
                                    "Motivo do saque",
                                    placeholder="Ex: Resgate na lojinha",
                                    key=f"adm_with_reason_{std}"
                                )
                            with_entries[std] = (val, reason)

                    if st.button("Confirmar Saques", type="primary", key="btn_adm_with"):
                        for std, (val, reason) in with_entries.items():
                            reason_clean = reason.strip() if reason else ""
                            base_desc = f"Saque efetuado pelo admin ({st.session_state['user']})"
                            full_desc = f"{base_desc} | Motivo: {reason_clean}" if reason_clean else base_desc
                            success, msg = db.withdraw_b_plus(std, val, description=full_desc)
                            if success:
                                st.success(f"✅ {msg}")
                            else:
                                st.error(f"❌ {msg}")

            elif operacao == "🔄 Transferir B+":
                st.markdown("#### Transferir B+ entre alunos")
                if len(all_student_names) < 2:
                    st.warning("É necessário ter pelo menos 2 alunos cadastrados para realizar transferências.")
                else:
                    sender_student = st.selectbox("Aluno de Origem (Quem envia)", all_student_names, key="adm_transf_sender")
                    sender_school = student_school_map.get(sender_student, "N/A")
                    sender_bal = float(db.get_balance(sender_student))
                    st.caption(f"🏫 **Escola de origem:** {sender_school} | 💰 **Saldo:** {sender_bal:.2f} B+")

                    receiver_options = [u for u in all_student_names if u != sender_student]
                    receiver_student = st.selectbox("Aluno de Destino (Quem recebe)", receiver_options, key="adm_transf_receiver")
                    receiver_school = student_school_map.get(receiver_student, "N/A")
                    receiver_bal = float(db.get_balance(receiver_student))
                    st.caption(f"🏫 **Escola de destino:** {receiver_school} | 💰 **Saldo:** {receiver_bal:.2f} B+")

                    transf_amount = st.number_input("Valor da Transferência (B+)", min_value=0.01, value=10.0, step=5.0, key="adm_transf_val")

                    if st.button("Confirmar Transferência", type="primary", key="btn_adm_transf"):
                        desc = f"Transferência efetuada pelo admin ({st.session_state['user']})"
                        success, msg = db.transfer_b_plus(sender_student, receiver_student, transf_amount, description=desc)
                        if success:
                            st.success(f"✅ {msg}")
                        else:
                            st.error(f"❌ {msg}")

    with tab_validation:
        st.subheader("Validação de Depósitos, Saques e Transferências")

        batch_feedback = st.session_state.pop("val_batch_feedback", None)
        if batch_feedback:
            for level, text in batch_feedback:
                if level == "success":
                    st.success(text)
                else:
                    st.error(text)

        pending_ops = db.get_pending_operations()

        if not pending_ops:
            st.info("Não há operações pendentes de aprovação no momento.")
        else:
            registered_schools = [s["name"] for s in db.get_schools()]
            ops_schools = {
                op["receiver_school"] if op["op_type"] == "DEPOSITO" else op["sender_school"]
                for op in pending_ops
            }
            all_school_names = sorted(set(registered_schools) | {s for s in ops_schools if s and s != "N/A"})
            if "N/A" in ops_schools:
                all_school_names.append("N/A")

            school_filter_options = ["Todas as escolas"] + all_school_names
            selected_school = st.selectbox(
                "🏫 Filtrar solicitações por escola:",
                school_filter_options,
                key="val_school_filter",
                on_change=_clear_val_selections
            )

            filtered_ops = [op for op in pending_ops if _op_matches_school(op, selected_school)]

            if not filtered_ops:
                st.info(f"Não há solicitações pendentes para **{selected_school}**.")
            else:
                filtered_op_ids = [op["id"] for op in filtered_ops]

                for oid in filtered_op_ids:
                    if f"val_chk_{oid}" not in st.session_state:
                        st.session_state[f"val_chk_{oid}"] = False

                st.session_state["val_select_all"] = all(
                    st.session_state.get(f"val_chk_{oid}", False) for oid in filtered_op_ids
                )

                selected_op_ids = [
                    oid for oid in filtered_op_ids if st.session_state.get(f"val_chk_{oid}", False)
                ]

                with st.container(border=True):
                    top_col1, top_col2 = st.columns([3, 2])
                    with top_col1:
                        st.checkbox(
                            "Selecionar todas as solicitações listadas",
                            key="val_select_all",
                            on_change=_toggle_select_all,
                            args=(filtered_op_ids,)
                        )
                    with top_col2:
                        st.markdown(
                            f"<div style='text-align: right; padding-top: 6px;'>"
                            f"<b>{len(selected_op_ids)}</b> de <b>{len(filtered_ops)}</b> selecionada(s) "
                            f"(Total pendente: {len(pending_ops)})</div>",
                            unsafe_allow_html=True
                        )

                    batch_note = st.text_input(
                        "Observação em lote (opcional)",
                        key="val_batch_note",
                        placeholder="Ex: Validado em lote por escola"
                    )

                    batch_btn_col1, batch_btn_col2 = st.columns(2)
                    with batch_btn_col1:
                        if st.button(
                            f"✅ Aprovar Selecionadas ({len(selected_op_ids)})",
                            type="primary",
                            use_container_width=True,
                            disabled=len(selected_op_ids) == 0,
                            key="btn_batch_approve"
                        ):
                            feedback = []
                            for oid in selected_op_ids:
                                indiv_note = st.session_state.get(f"note_op_{oid}", "").strip()
                                final_note = indiv_note if indiv_note else batch_note
                                ok, msg = db.approve_operation(oid, st.session_state["user"], final_note)
                                feedback.append(("success" if ok else "error", f"{'✅' if ok else '❌'} {msg}"))
                                st.session_state.pop(f"val_chk_{oid}", None)
                            st.session_state["val_batch_feedback"] = feedback
                            st.rerun()

                    with batch_btn_col2:
                        if st.button(
                            f"❌ Reprovar Selecionadas ({len(selected_op_ids)})",
                            type="secondary",
                            use_container_width=True,
                            disabled=len(selected_op_ids) == 0,
                            key="btn_batch_reject"
                        ):
                            feedback = []
                            for oid in selected_op_ids:
                                indiv_note = st.session_state.get(f"note_op_{oid}", "").strip()
                                final_note = indiv_note if indiv_note else batch_note
                                ok, msg = db.reject_operation(oid, st.session_state["user"], final_note)
                                feedback.append(("success" if ok else "error", f"{'🚫' if ok else '❌'} {msg}"))
                                st.session_state.pop(f"val_chk_{oid}", None)
                            st.session_state["val_batch_feedback"] = feedback
                            st.rerun()

                for op in filtered_ops:
                    op_id = op["id"]
                    if op["op_type"] == "DEPOSITO":
                        op_label = "💵 Depósito"
                    elif op["op_type"] == "SAQUE":
                        op_label = "💸 Saque"
                    else:
                        op_label = "🔄 Transferência"

                    amt = float(op["amount"])
                    with st.container(border=True):
                        st.checkbox(
                            f"Selecionar solicitação #{op_id}",
                            key=f"val_chk_{op_id}"
                        )
                        col_info, col_actions = st.columns([3, 2])
                        with col_info:
                            st.markdown(f"**#{op_id} — {op_label} de {amt:.2f} B+**")
                            st.write(f"**Solicitante:** {op['requester_username']} ({op['requester_role']})")
                            if op["op_type"] == "DEPOSITO":
                                st.write(f"**Conta Beneficiada:** {op['receiver_username']} | **Escola:** {op['receiver_school']} ({op['receiver_class']})")
                            elif op["op_type"] == "SAQUE":
                                st.write(f"**Conta do Aluno:** {op['sender_username']} | **Escola:** {op['sender_school']} ({op['sender_class']})")
                            else:
                                st.write(f"**De:** {op['sender_username']} ({op['sender_school']}) ➡️ **Para:** {op['receiver_username']} ({op['receiver_school']})")
                            if op["description"]:
                                st.caption(f"Descrição / Motivo: {op['description']}")
                            st.caption(f"Solicitado em: {op['created_at']}")

                        with col_actions:
                            note_input = st.text_input(
                                "Observação / Motivo (opcional)",
                                key=f"note_op_{op_id}",
                                placeholder="Ex: Validado em sala"
                            )
                            btn_col1, btn_col2 = st.columns(2)
                            with btn_col1:
                                if st.button("✅ Aprovar", key=f"approve_op_{op_id}", type="primary", use_container_width=True):
                                    ok, msg = db.approve_operation(op_id, st.session_state["user"], note_input)
                                    if ok:
                                        st.session_state.pop(f"val_chk_{op_id}", None)
                                        st.toast(f"✅ {msg}")
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {msg}")
                            with btn_col2:
                                if st.button("❌ Reprovar", key=f"reject_op_{op_id}", type="secondary", use_container_width=True):
                                    ok, msg = db.reject_operation(op_id, st.session_state["user"], note_input)
                                    if ok:
                                        st.session_state.pop(f"val_chk_{op_id}", None)
                                        st.toast(f"🚫 {msg}")
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {msg}")

        st.divider()
        st.subheader("Histórico Detalhado de Operações Validadas")
        reviewed_ops = db.get_reviewed_operations()

        if not reviewed_ops:
            st.info("Nenhuma operação foi aprovada ou reprovada até o momento.")
        else:
            status_filter = st.radio(
                "Filtrar por status:",
                ["Todas", "Aprovadas", "Reprovadas"],
                horizontal=True,
                key="val_hist_filter"
            )
            hist_records = []
            for r in reviewed_ops:
                if status_filter == "Aprovadas" and r["status"] != "APROVADA":
                    continue
                if status_filter == "Reprovadas" and r["status"] != "REPROVADA":
                    continue

                status_badge = "✅ APROVADA" if r["status"] == "APROVADA" else "❌ REPROVADA"
                if r["op_type"] == "DEPOSITO":
                    tipo_str = "Depósito"
                    origem_str = "ADMIN / DEPÓSITO"
                    destino_str = f"{r['receiver_username']} ({r['receiver_school']})"
                elif r["op_type"] == "SAQUE":
                    tipo_str = "Saque"
                    origem_str = f"{r['sender_username']} ({r['sender_school']})"
                    destino_str = "CAIXA / SAQUE"
                else:
                    tipo_str = "Transferência"
                    origem_str = f"{r['sender_username']} ({r['sender_school']})"
                    destino_str = f"{r['receiver_username']} ({r['receiver_school']})"

                hist_records.append({
                    "ID": r["id"],
                    "Status": status_badge,
                    "Tipo": tipo_str,
                    "Solicitante": f"{r['requester_username']} ({r['requester_role']})",
                    "Origem": origem_str,
                    "Destino": destino_str,
                    "Valor (B+)": f"{float(r['amount']):.2f}",
                    "Descrição / Motivo": r["description"] or "-",
                    "Obs. Admin": r["review_note"] or "-",
                    "Avaliado Por": r["reviewed_by"] or "-",
                    "Data Solicitação": str(r["created_at"]),
                    "Data Avaliação": str(r["reviewed_at"]) if r["reviewed_at"] else "-"
                })

            if not hist_records:
                st.info("Nenhum registro encontrado para o filtro selecionado.")
            else:
                df_reviewed = pd.DataFrame(hist_records)
                st.dataframe(df_reviewed, use_container_width=True, hide_index=True)

    with tab_list_students:
        st.subheader("Lista de Todos os Alunos Cadastrados")
        students = db.get_all_students()
        if not students:
            st.info("Nenhum aluno cadastrado no momento.")
        else:
            st.caption(f"Total de alunos cadastrados: **{len(students)}**")
            df_students = pd.DataFrame(students)
            st.dataframe(df_students, use_container_width=True, hide_index=True)

    with tab_list_schools:
        st.subheader("Lista de Todas as Escolas Cadastradas")
        schools_details = db.get_all_schools_details()
        if not schools_details:
            st.info("Nenhuma escola cadastrada no momento.")
        else:
            st.caption(f"Total de escolas cadastradas: **{len(schools_details)}**")
            df_schools = pd.DataFrame(schools_details)
            st.dataframe(df_schools, use_container_width=True, hide_index=True)
