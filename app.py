import streamlit as st
import pandas as pd
from datetime import date, datetime
import os
import io
from supabase import create_client, Client

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Manutenção", layout="wide", page_icon="🔧")

# --- 2. CONEXÃO SEGURA ---
url_raw = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
key_raw = st.secrets.get("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not url_raw or not key_raw:
    st.error("❌ Credenciais não encontradas. Verifique os Secrets.")
    st.stop()

URL = url_raw.strip().rstrip("/")
KEY = key_raw.strip()

@st.cache_resource
def conectar():
    return create_client(URL, KEY)

supabase = conectar()

# --- 3. FUNÇÕES DE DADOS ---
def carregar_listas():
    try:
        u = supabase.table('usuarios').select('id, nome').order('nome').execute()
        m = supabase.table('mecanicos').select('id, nome').order('nome').execute()
        q = supabase.table('maquinas').select('id, nome').order('nome').execute()
        return u.data, m.data, q.data
    except Exception as e:
        st.error(f"Erro ao carregar listas: {e}")
        return [], [], []

def carregar_solicitacoes(ordem_por):
    try:
        col = 'ordem_manual'
        if ordem_por == "Prioridade": col = 'prioridade'
        elif ordem_por == "Data Solicitação": col = 'data_solicitacao'
        
        s = supabase.table('solicitacoes').select(
            '*, usuarios(nome), mecanicos(nome), maquinas(nome)'
        ).order(col, desc=True).execute()
        return s.data
    except Exception as e:
        st.error(f"Erro ao carregar solicitações: {e}")
        return []

# --- 4. INTERFACE ---
st.title("🔧 Gestão de Manutenção v22.0")
usuarios_raw, mecanicos_raw, maquinas_raw = carregar_listas()

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Configurações")
    if st.button("🔄 Atualizar Dados"): 
        st.rerun()
    
    ordem_sel = st.selectbox("Ordenar fila por:", ["Fila Manual", "Prioridade", "Data Solicitação"])
    
    st.divider()
    st.header("➕ Gerenciar Cadastros")
    
    # Cadastro de Usuários
    with st.expander("👤 Usuários"):
        with st.form("cad_u", clear_on_submit=True):
            n_u = st.text_input("Nome do Usuário")
            if st.form_submit_button("Salvar"):
                if n_u: supabase.table('usuarios').insert({"nome": n_u}).execute(); st.rerun()
        for u in usuarios_raw:
            c1, c2 = st.columns([3, 1])
            c1.write(u['nome'])
            if c2.button("🗑️", key=f"du_{u['id']}"):
                supabase.table('usuarios').delete().eq("id", u['id']).execute(); st.rerun()

    # Cadastro de Máquinas
    with st.expander("🚜 Máquinas"):
        with st.form("cad_q", clear_on_submit=True):
            n_q = st.text_input("Nome da Máquina")
            if st.form_submit_button("Salvar"):
                if n_q: supabase.table('maquinas').insert({"nome": n_q}).execute(); st.rerun()
        for q in maquinas_raw:
            c1, c2 = st.columns([3, 1])
            c1.write(q['nome'])
            if c2.button("🗑️", key=f"dq_{q['id']}"):
                supabase.table('maquinas').delete().eq("id", q['id']).execute(); st.rerun()

# --- NOVA ORDEM DE SERVIÇO ---
with st.expander("📝 NOVA ORDEM DE SERVIÇO", expanded=False):
    with st.form("f_nova", clear_on_submit=True):
        c1, c2 = st.columns(2)
        u_sel = c1.selectbox("Solicitante", [i['nome'] for i in usuarios_raw])
        m_sel = c1.selectbox("Máquina", [i['nome'] for i in maquinas_raw])
        prio = c2.select_slider("Prioridade", ["Baixa", "Média", "Alta", "Urgente"])
        dt_i = c2.date_input("Início")
        desc = st.text_area("Descrição do Problema")
        
        if st.form_submit_button("🔨 Abrir OS"):
            u_id = next(i['id'] for i in usuarios_raw if i['nome'] == u_sel)
            m_id = next(i['id'] for i in maquinas_raw if i['nome'] == m_sel)
            supabase.table('solicitacoes').insert({
                "usuario_id": u_id, "maquina_id": m_id, "descricao": desc,
                "prioridade": prio, "status": "Pendente", "data_solicitacao": str(date.today()),
                "data_inicio": str(dt_i), "ordem_manual": int(datetime.now().timestamp())
            }).execute()
            st.rerun()

# --- FILA DE TRABALHO ---
solicitacoes = carregar_solicitacoes(ordem_sel)

if solicitacoes:
    st.divider()
    # Cabeçalho da Tabela
    h = st.columns([0.5, 1, 1.2, 1, 1, 1, 0.8, 2.5])
    for col, t in zip(h, ["ID", "Abertura", "Máquina", "Status", "Início", "Fim", "Prior.", "Ações"]):
        col.markdown(f"**{t}**")
    
    for s in solicitacoes:
        r = st.columns([0.5, 1, 1.2, 1, 1, 1, 0.8, 2.5])
        r[0].write(f"#{s['id']}")
        r[1].write(s['data_solicitacao'])
        r[2].write(s['maquinas']['nome'] if s['maquinas'] else "N/A")
        
        cor = "🔴" if s['status'] == "Pendente" else "🟡" if s['status'] == "Em andamento" else "🟢"
        r[3].write(f"{cor} {s['status']}")
        r[4].write(s['data_inicio'] or "---")
        r[5].write(s['data_fim'] or "---")
        r[6].write(s['prioridade'])

        # --- BOTÕES DE AÇÃO ---
        btns = r[7].columns(5)
        
        # 1. Finalizar
        if s['status'] != "Finalizado":
            if btns[0].button("🏁", key=f"f_{s['id']}", help="Finalizar"):
                supabase.table('solicitacoes').update({"status": "Finalizado", "data_fim": str(date.today())}).eq("id", s['id']).execute()
                st.rerun()

        # 2. Editar
        if btns[1].button("📝", key=f"e_{s['id']}"):
            st.session_state[f"ed_{s['id']}"] = True

        # 3. Setas (Ordem)
        curr_o = s.get('ordem_manual', 0)
        if btns[2].button("🔼", key=f"u_{s['id']}"):
            supabase.table('solicitacoes').update({"ordem_manual": curr_o + 100}).eq("id", s['id']).execute(); st.rerun()
        if btns[3].button("🔽", key=f"d_{s['id']}"):
            supabase.table('solicitacoes').update({"ordem_manual": curr_o - 100}).eq("id", s['id']).execute(); st.rerun()

        # 4. Excluir
        if btns[4].button("🗑️", key=f"x_{s['id']}"):
            supabase.table('solicitacoes').delete().eq("id", s['id']).execute(); st.rerun()

        # --- ÁREA DE EDIÇÃO ---
        if st.session_state.get(f"ed_{s['id']}", False):
            with st.form(f"form_ed_{s['id']}"):
                st.info(f"Editando OS #{s['id']}")
                fe1, fe2, fe3, fe4 = st.columns(4)
                n_st = fe1.selectbox("Status", ["Pendente", "Em andamento", "Finalizado"], index=["Pendente", "Em andamento", "Finalizado"].index(s['status']))
                n_pr = fe2.selectbox("Prioridade", ["Baixa", "Média", "Alta", "Urgente"], index=["Baixa", "Média", "Alta", "Urgente"].index(s['prioridade']))
                
                def conv_dt(d): return datetime.strptime(d, '%Y-%m-%d').date() if d else date.today()
                n_dt_i = fe3.date_input("Data Início", conv_dt(s['data_inicio']))
                n_dt_f = fe4.date_input("Data Fim", conv_dt(s['data_fim']))
                
                b1, b2 = st.columns(2)
                if b1.form_submit_button("✅ Salvar"):
                    supabase.table('solicitacoes').update({
                        "status": n_st, "prioridade": n_pr, "data_inicio": str(n_dt_i), "data_fim": str(n_dt_f)
                    }).eq("id", s['id']).execute()
                    st.session_state[f"ed_{s['id']}"] = False
                    st.rerun()
                if b2.form_submit_button("❌ Cancelar"):
                    st.session_state[f"ed_{s['id']}"] = False
                    st.rerun()
        st.divider()
else:
    st.info("Fila vazia.")
