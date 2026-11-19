import streamlit as st
import backend as db
from views.admin_view import render_admin_dashboard
from views.teacher_view import render_teacher_dashboard
from views.student_view import render_student_dashboard

# Configuração da página do Streamlit
st.set_page_config(page_title="B+ Bank", page_icon="🪙", layout="centered")

# Inicialização da base
db.init_db()

# ==========================================
# GERENCIAMENTO DE SESSÃO (Streamlit)
# ==========================================
if "user" not in st.session_state:
    st.session_state["user"] = None
if "user_type" not in st.session_state:
    st.session_state["user_type"] = 1
if "school_id" not in st.session_state:
    st.session_state["school_id"] = None
if "class_id" not in st.session_state:
    st.session_state["class_id"] = None
if "session_token" not in st.session_state:
    st.session_state["session_token"] = None

# Restaura sessão automaticamente caso o usuário atualize (F5) a página
if st.session_state["user"] is None:
    url_token = st.query_params.get("token")
    if url_token:
        restored_user = db.validate_session_token(url_token)
        if restored_user:
            st.session_state["user"] = restored_user["username"]
            st.session_state["user_type"] = restored_user["user_type"]
            st.session_state["school_id"] = restored_user["school_id"]
            st.session_state["class_id"] = restored_user["class_id"]
            st.session_state["session_token"] = url_token
        else:
            st.query_params.clear()

def logout():
    token = st.session_state.get("session_token") or st.query_params.get("token")
    if token:
        db.delete_session_token(token)
    st.query_params.clear()
    st.session_state["user"] = None
    st.session_state["user_type"] = 1
    st.session_state["school_id"] = None
    st.session_state["class_id"] = None
    st.session_state["session_token"] = None
    st.rerun()

# ==========================================
# ROTEAMENTO DE TELAS
# ==========================================
if st.session_state["user"] is None:
    st.title("🪙 B+ Bank Teste - Acesso ao Sistema")
    
    with st.form("login_form"):
        user_input = st.text_input("Usuário")
        pass_input = st.text_input("Senha", type="password")
        submit = st.form_submit_button("Entrar", type="primary", use_container_width=True)
        
        if submit:
            success, res = db.login_user(user_input, pass_input)
            if success:
                token = db.create_session_token(res["username"])
                st.session_state["user"] = res["username"]
                st.session_state["user_type"] = res["user_type"]
                st.session_state["school_id"] = res["school_id"]
                st.session_state["class_id"] = res["class_id"]
                st.session_state["session_token"] = token
                st.query_params["token"] = token
                st.rerun()
            else:
                st.error(f"❌ {res}")

elif st.session_state["user_type"] == 2:
    render_admin_dashboard(logout)

elif st.session_state["user_type"] == 3:
    render_teacher_dashboard(logout)

else:
    render_student_dashboard(logout)
