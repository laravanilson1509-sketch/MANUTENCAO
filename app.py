import streamlit as st
import pandas as pd
from datetime import date, datetime
import os
import io
from dotenv import load_dotenv
from supabase import create_client, Client
from openpyxl import Workbook

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Manutenção", layout="wide", page_icon="🔧")

# --- 2. CONEXÃO SEGURA ---
load_dotenv()
URL = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
KEY = st.secrets.get("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not URL or not KEY:
    st.error("❌ Credenciais do Supabase não encontradas. Verifique seu arquivo .env ou Secrets.")
    st.stop()

supabase: Client = create_client(URL, KEY)

# --- 3. CARGA DE DADOS ---
def carregar_listas():
    u = supabase.table('usuarios').select('id, nome').execute()
    m = supabase.table('mecanicos').select('id, nome').execute()
    q = supabase.table('maquinas').select('id, nome').execute()
    return u.data, m.data, q.data

def carregar_solicitacoes(ordem_por="ID"):
    col_sort = 'id'
    if ordem_por == "Prioridade": col_sort = 'prioridade'
    elif ordem_por == "Data Solicitação": col_sort = 'data_solicitacao'
    
    s = supabase.table('solicitacoes').select(
        '*, usuarios(nome), mecanicos(nome), maquinas(nome)'
    ).order(col_sort, desc=True).execute()
    return s.data

# Inicialização de dados
usuarios_raw, mecanicos_raw, maquinas_raw = carregar_listas()

# --- 4. BARRA LATERAL (CADASTROS E FILTROS) ---
with st.sidebar:
    st.header("⚙️ Configurações")
    ordem_sel = st.selectbox("Ordenar por:", ["ID", "Prioridade", "Data Solicitação"])
    
    with st.expander("➕ Novos Cadastros"):
        tipo = st.selectbox("Tipo", ["usuarios", "mecanicos", "maquinas"])
        nome = st.text_input("Nome")
        if st.button("Salvar Cadastro"):
            if nome:
                supabase.table(tipo).insert({"nome": nome}).execute()
                st.rerun()

# Atualiza a lista com base na ordem escolhida
solicitacoes = carregar_solicitacoes(ordem_sel)

# --- 5. CABEÇALHO ---
st.title("🔧 Gestão de Manutenção v15.0")

# --- 6. ABRIR NOVA ORDEM DE SERVIÇO ---
with st.expander("📝 ABRIR NOVA ORDEM DE SERVIÇO", expanded=False):
    with st.form("form_nova_os", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        u_os = c1.selectbox("Solicitante", [i['nome'] for i in usuarios_raw])
        m_os = c1.selectbox("Máquina", [i['nome'] for i in maquinas_raw])
        mec_os = c2.selectbox("Mecânico", ["Não Definido"] + [i['nome'] for i in mecanicos_raw])
        prio_os = c2.select_slider("Prioridade", ["Baixa", "Média", "Alta", "Urgente"])
        data_ini_os = c3.date_input("Início Programado", value=date.today())
        
        desc_os = st.text_area("Descrição do problema")
        
        if st.form_submit_button("🔨 Registrar OS"):
            u_id = [i['id'] for i in usuarios_raw if i['nome'] == u_os][0]
            m_id = [i['id'] for i in maquinas_raw if i['nome'] == m_os][0]
            mec_id = next((i['id'] for i in mecanicos_raw if i['nome'] == mec_os), None)
            
            supabase.table('solicitacoes').insert({
                "usuario_id": u_id, "maquina_id": m_id, "mecanico_id": mec_id,
                "descricao": desc_os, "prioridade": prio_os, "status": "Pendente",
                "data_solicitacao": str(date.today()), "data_inicio": str(data_ini_os)
            }).execute()
            st.rerun()

st.divider()

# --- 7. FILA DE ORDENS ---
st.subheader("📋 Fila de Ordens de Serviço")

if solicitacoes:
    # Cabeçalho da Tabela
    cols = st.columns([0.6, 1.2, 1.5, 1.2, 1.2, 1.2, 1, 2])
    titulos = ["ID", "Abertura", "Máquina", "Status", "Início", "Fim", "Prior.", "Ações"]
    for col, tit in zip(cols, titulos):
        col.markdown(f"**{tit}**")
    st.divider()

    for s in solicitacoes:
        r_id, r_ab, r_ma, r_st, r_in, r_fi, r_pr, r_ac = st.columns([0.6, 1.2, 1.5, 1.2, 1.2, 1.2, 1, 2])
        
        # Estilização de Status
        cor = "🔴" if s['status'] == "Pendente" else "🟡" if s['status'] == "Em andamento" else "🟢"
        
        r_id.write(f"#{s['id']}")
        r_ab.write(s.get('data_solicitacao') or "---")
        r_ma.write((s.get('maquinas') or {}).get('nome', 'N/A'))
        r_st.write(f"{cor} {s['status']}")
        r_in.write(s.get('data_inicio') or "---")
        r_fi.write(s.get('data_fim') or "---")
        r_pr.write(s['prioridade'])

        # Coluna de Ações
        b_fin, b_edit, b_del = r_ac.columns(3)
        
        # Botão Finalizar Rápido
        if s['status'] != "Finalizado":
            if b_fin.button("🏁", key=f"f_{s['id']}", help="Finalizar OS"):
                supabase.table('solicitacoes').update({"status": "Finalizado", "data_fim": str(date.today())}).eq("id", s['id']).execute()
                st.rerun()
        
        # Botão Editar
        if b_edit.button("📝", key=f"e_{s['id']}", help="Editar Datas/Status"):
            st.session_state[f"editando_{s['id']}"] = not st.session_state.get(f"editando_{s['id']}", False)

        # Botão Excluir Funcional
        if b_del.button("🗑️", key=f"d_{s['id']}", help="Excluir OS permanentemente"):
            supabase.table('solicitacoes').delete().eq("id", s['id']).execute()
            st.rerun()

        # Formulário de Edição (Abre abaixo da linha)
        if st.session_state.get(f"editando_{s['id']}", False):
            with st.form(key=f"form_ed_{s['id']}"):
                st.info(f"Ajustando OS #{s['id']}")
                fe1, fe2, fe3 = st.columns(3)
                
                # Funções de ajuda para datas
                def conv_dt(d_str):
                    try: return datetime.strptime(d_str, '%Y-%m-%d').date()
                    except: return date.today()

                opcoes_status = ["Pendente", "Em andamento", "Finalizado"]
                idx_st = opcoes_status.index(s['status']) if s['status'] in opcoes_status else 0
                
                novo_st = fe1.selectbox("Status", opcoes_status, index=idx_st)
                nova_i = fe2.date_input("Data Início", conv_dt(s.get('data_inicio')))
                nova_f = fe3.date_input("Data Fim", conv_dt(s.get('data_fim')))
                
                c_ok, c_cancel = st.columns(2)
                if c_ok.form_submit_button("✅ Salvar"):
                    supabase.table('solicitacoes').update({
                        "status": novo_st,
                        "data_inicio": str(nova_i),
                        "data_fim": str(nova_f)
                    }).eq("id", s['id']).execute()
                    st.session_state[f"editando_{s['id']}"] = False
                    st.rerun()
                if c_cancel.form_submit_button("❌ Cancelar"):
                    st.session_state[f"editando_{s['id']}"] = False
                    st.rerun()
        
        st.divider()
else:
    st.info("Nenhuma ordem de serviço pendente.")
