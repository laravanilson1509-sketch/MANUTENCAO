import streamlit as st
import pandas as pd
from datetime import date, datetime
import os
import io
from supabase import create_client, Client

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Manutenção", layout="wide", page_icon="🔧")

# --- 2. CONEXÃO SEGURA ---
URL_RAW = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
KEY_RAW = st.secrets.get("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not URL_RAW or not KEY_RAW:
    st.error("## ❌ Credenciais não encontradas!")
    st.stop()

URL = URL_RAW.strip().replace(" ", "")
KEY = KEY_RAW.strip().replace(" ", "")

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
        st.sidebar.error(f"Erro ao carregar listas: {e}")
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
        st.error(f"Erro ao carregar fila: {e}")
        return []

# --- 4. INTERFACE ---
st.title("🔧 Gestão de Manutenção v22.0")
usuarios_raw, mecanicos_raw, maquinas_raw = carregar_listas()

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Configurações")
    if st.button("🔄 Atualizar"): st.rerun()
    
    ordem_sel = st.selectbox("Ordenar por:", ["Fila Manual", "Prioridade", "Data Solicitação"])
    
    st.divider()
    st.header("➕ Gerenciar Cadastros")
    
    # Usuários
    with st.expander("👤 Usuários"):
        with st.form("cad_u", clear_on_submit=True):
            n_u = st.text_input("Novo Usuário")
            if st.form_submit_button("Adicionar"):
                if n_u: 
                    supabase.table('usuarios').insert({"nome": n_u}).execute()
                    st.rerun()
        for u in usuarios_raw:
            c1, c2 = st.columns([3, 1])
            c1.write(u['nome'])
            if c2.button("🗑️", key=f"del_u_{u['id']}"):
                supabase.table('usuarios').delete().eq("id", u['id']).execute()
                st.rerun()

    # Máquinas
    with st.expander("🚜 Máquinas"):
        with st.form("cad_q", clear_on_submit=True):
            n_q = st.text_input("Nova Máquina")
            if st.form_submit_button("Adicionar"):
                if n_q:
                    supabase.table('maquinas').insert({"nome": n_q}).execute()
                    st.rerun()
        for q in maquinas_raw:
            c1, c2 = st.columns([3, 1])
            c1.write(q['nome'])
            if c2.button("🗑️", key=f"del_q_{q['id']}"):
                supabase.table('maquinas').delete().eq("id", q['id']).execute()
                st.rerun()

# --- NOVA ORDEM DE SERVIÇO ---
solicitacoes = carregar_solicitacoes(ordem_sel)

with st.expander("📝 NOVA ORDEM DE SERVIÇO"):
    with st.form("f_nova"):
        c1, c2 = st.columns(2)
        u_sel = c1.selectbox("Solicitante", [i['nome'] for i in usuarios_raw])
        m_sel = c1.selectbox("Máquina", [i['nome'] for i in maquinas_raw])
        prio = c2.select_slider("Prioridade", ["Baixa", "Média", "Alta", "Urgente"])
        dt_i = c2.date_input("Início")
        desc = st.text_area("Descrição")
        
        if st.form_submit_button("🔨 Abrir OS"):
            u_id = next(i['id'] for i in usuarios_raw if i['nome'] == u_sel)
            m_id = next(i['id'] for i in maquinas_raw if i['nome'] == m_sel)
            supabase.table('solicitacoes').insert({
                "usuario_id": u_id, "maquina_id": m_id, "descricao": desc,
                "prioridade": prio, "status": "Pendente", "data_solicitacao": str(date.today()),
                "data_inicio": str(dt_i), "ordem_manual": int(datetime.now().timestamp())
            }).execute()
            st.rerun()

# --- TABELA DE SOLICITAÇÕES ---
if solicitacoes:
    st.divider()
    h = st.columns([0.5, 1, 1.2, 1, 1, 1, 0.8, 2.5])
    for col, t in zip(h, ["ID", "Abertura", "Máquina", "Status", "Início", "Fim", "Prior.", "Ações"]):
        col.markdown(f"**{t}**")
    
    for s in solicitacoes:
        r = st.columns([0.5, 1, 1.2, 1, 1, 1, 0.8, 2.5])
        r[0].write(f"#{s['id']}")
        r[1].write(s['data_solicitacao'])
        r[2].write(s['maquinas']['nome'] if s['maquinas'] else "Excluída")
        cor = "🔴" if s['status'] == "Pendente" else "🟡" if s['status'] == "Em andamento" else "🟢"
        r[3].write(f"{cor} {s['status']}")
        r[4].write(s['data_inicio'] or "---")
        r[5].write(s['data_fim'] or "---")
        r[6].write(s['prioridade'])
        
        # Ações
        btns = r[7].columns(5)
        
        # Finalizar
        if s['status'] != "Finalizado" and btns[0].button("🏁", key=f"f_{s['id']}"):
            supabase.table('solicitacoes').update({"status": "Finalizado", "data_fim": str(date.today())}).eq("id", s['id']).execute()
            st.rerun()
            
        # Editar
        if btns[1].button("📝", key=f"e_{s['id']}"):
            st.session_state[f"ed_{s['id']}"] = True
        
        # Ordem (Setas)
        curr_o = s.get('ordem_manual', 0)
        if btns[2].button("🔼", key=f"u_{s['id']}"):
            supabase.table('solicitacoes').update({"ordem_manual": curr_o + 100}).eq("id", s['id']).execute()
            st.rerun()
        if btns[3].button("🔽", key=f"d_{s['id']}"):
            supabase.table('solicitacoes').update({"ordem_manual": curr_o - 100}).eq("id", s['id']).execute()
            st.rerun()
            
        # Excluir
        if btns[4].button("🗑️", key=f"x_{s['id']}"):
            supabase.table('solicitacoes').delete().eq("id", s['id']).execute()
            st.rerun()

        # FORMULÁRIO DE EDIÇÃO (Abaixo da linha)
        if st.session_state.get(f"ed_{s['id']}", False):
            with st.form(f"form_ed_{s['id']}"):
                st.info(f"Editando OS #{s['id']}")
                f1, f2, f3, f4 = st.columns(4)
                ns = f1.selectbox("Status", ["Pendente", "Em andamento", "Finalizado"], index=["Pendente", "Em andamento", "Finalizado"].index(s['status']))
                np = f2.selectbox("Prioridade", ["Baixa", "Média", "Alta", "Urgente"], index=["Baixa", "Média", "Alta", "Urgente"].index(s['prioridade']))
                
                # Tratamento de datas seguras para o editor
                try: d_ini = datetime.strptime(s['data_inicio'], '%Y-%m-%d').date()
                except: d_ini = date.today()
                try: d_fim = datetime.strptime(s['data_fim'], '%Y-%m-%d').date()
                except: d_fim = date.today()
                
                ni = f3.date_input("Início", d_ini)
                nf = f4.date_input("Fim", d_fim)
                
                c_btn = st.columns(2)
                if c_btn[0].form_submit_button("Salvar"):
                    supabase.table('solicitacoes').update({
                        "status": ns, "prioridade": np, "data_inicio": str(ni), "data_fim": str(nf)
                    }).eq("id", s['id']).execute()
                    st.session_state[f"ed_{s['id']}"] = False
                    st.rerun()
                if c_btn[1].form_submit_button("Cancelar"):
                    st.session_state[f"ed_{s['id']}"] = False
                    st.rerun()
        st.divider()
else:
    st.info("Fila vazia.")
