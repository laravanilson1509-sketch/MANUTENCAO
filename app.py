import streamlit as st
import pandas as pd
from datetime import date, datetime
import os
import io
from dotenv import load_dotenv
from supabase import create_client, Client

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Manutenção", layout="wide", page_icon="🔧")
# --- 2. CONEXÃO SEGURA (REESCRITO PARA CORRIGIR O ERRO DO CLOUD) ---
load_dotenv()

# Pegamos os valores e limpamos espaços invisíveis com .strip()
url_raw = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
key_raw = st.secrets.get("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not url_raw or not key_raw:
    st.error("## ❌ Credenciais não encontradas!")
    st.stop()

URL = url_raw.strip()
KEY = key_raw.strip()

# Usamos cache para evitar que a conexão caia ou dê erro de DNS
@st.cache_resource
def abrir_conexao():
    return create_client(URL, KEY)

try:
    supabase: Client = abrir_conexao()
except Exception as e:
    st.error(f"Erro de DNS/Conexão: {e}")
    st.stop()

# --- 3. FUNÇÕES DE DADOS ---
def carregar_listas():
    try:
        u = supabase.table('usuarios').select('id, nome').order('nome').execute()
        m = supabase.table('mecanicos').select('id, nome').order('nome').execute()
        q = supabase.table('maquinas').select('id, nome').order('nome').execute()
        return u.data, m.data, q.data
    except Exception as e:
        st.sidebar.error(f"Erro ao carregar cadastros: {e}")
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
    except Exception as e:
        st.sidebar.error(f"Erro ao carregar cadastros: {e}")
        return [], [], []

def carregar_solicitacoes(ordem_por):
    """Carrega as OS da tabela principal com base no filtro selecionado"""
    try:
        # Define a coluna de ordenação
        col = 'ordem_manual'
        if ordem_por == "Prioridade": 
            col = 'prioridade'
        elif ordem_por == "Data Solicitação": 
            col = 'data_solicitacao'
        
        # Faz o Join com as tabelas relacionadas para pegar os NOMES em vez dos IDs
        s = supabase.table('solicitacoes').select(
            '*, usuarios(nome), mecanicos(nome), maquinas(nome)'
        ).order(col, desc=True).execute()
        
        return s.data
    except Exception as e:
        st.error(f"Erro ao carregar fila: {e}")
        return []
# --- INTERFACE ---
st.title("🔧 Gestão de Manutenção v19.0")
usuarios_raw, mecanicos_raw, maquinas_raw = carregar_listas()

# --- BARRA LATERAL (CADASTROS COM DELETE) ---
with st.sidebar:
    st.header("⚙️ Configurações")
    if st.button("🔄 Atualizar"): st.rerun()
    
    ordem_sel = st.selectbox("Ordenar por:", ["Fila Manual", "Prioridade", "Data Solicitação"])
    
    st.divider()
    st.header("➕ Gerenciar Cadastros")
    
    # Gerenciar Usuários
    with st.expander("👤 Usuários"):
        with st.form("cad_u", clear_on_submit=True):
            n_u = st.text_input("Novo Usuário")
            if st.form_submit_button("Adicionar"):
                if n_u: 
                    supabase.table('usuarios').insert({"nome": n_u}).execute()
                    st.rerun()
        
        for u in usuarios_raw:
            col_u1, col_u2 = st.columns([3, 1])
            col_u1.write(u['nome'])
            if col_u2.button("🗑️", key=f"del_u_{u['id']}"):
                try:
                    supabase.table('usuarios').delete().eq("id", u['id']).execute()
                    st.rerun()
                except: st.error("Possui OS vinculada")

    # Gerenciar Máquinas
    with st.expander("🚜 Máquinas"):
        with st.form("cad_q", clear_on_submit=True):
            n_q = st.text_input("Nova Máquina")
            if st.form_submit_button("Adicionar"):
                if n_q:
                    supabase.table('maquinas').insert({"nome": n_q}).execute()
                    st.rerun()
        
        for q in maquinas_raw:
            col_q1, col_q2 = st.columns([3, 1])
            col_q1.write(q['nome'])
            if col_q2.button("🗑️", key=f"del_q_{q['id']}"):
                try:
                    supabase.table('maquinas').delete().eq("id", q['id']).execute()
                    st.rerun()
                except: st.error("Possui OS vinculada")

    # Gerenciar Mecânicos
    with st.expander("👨‍🔧 Mecânicos"):
        with st.form("cad_m", clear_on_submit=True):
            n_m = st.text_input("Novo Mecânico")
            if st.form_submit_button("Adicionar"):
                if n_m:
                    supabase.table('mecanicos').insert({"nome": n_m}).execute()
                    st.rerun()
        for m in mecanicos_raw:
            col_m1, col_m2 = st.columns([3, 1])
            col_m1.write(m['nome'])
            if col_m2.button("🗑️", key=f"del_m_{m['id']}"):
                try:
                    supabase.table('mecanicos').delete().eq("id", m['id']).execute()
                    st.rerun()
                except: st.error("Possui OS vinculada")

# --- RESTO DO CÓDIGO (NOVA OS E TABELA) ---
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

# [Tabela de solicitações continua igual à v18.0...]
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
        
        # Ações da Tabela
        btns = r[7].columns(5)
        if s['status'] != "Finalizado" and btns[0].button("🏁", key=f"f_{s['id']}"):
            supabase.table('solicitacoes').update({"status": "Finalizado", "data_fim": str(date.today())}).eq("id", s['id']).execute()
            st.rerun()
        if btns[1].button("📝", key=f"e_{s['id']}"): st.session_state[f"ed_{s['id']}"] = True
        
        curr_o = s.get('ordem_manual', 0)
        if btns[2].button("🔼", key=f"u_{s['id']}"):
            supabase.table('solicitacoes').update({"ordem_manual": curr_o + 100}).eq("id", s['id']).execute()
            st.rerun()
        if btns[3].button("🔽", key=f"d_{s['id']}"):
            supabase.table('solicitacoes').update({"ordem_manual": curr_o - 100}).eq("id", s['id']).execute()
            st.rerun()
        if btns[4].button("🗑️", key=f"x_{s['id']}"):
            supabase.table('solicitacoes').delete().eq("id", s['id']).execute()
            st.rerun()
        st.divider()
