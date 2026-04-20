import streamlit as st
import pandas as pd
from datetime import date, datetime
import os
import io
from supabase import create_client, Client

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Manutenção", layout="wide", page_icon="🔧")

# --- 2. CONEXÃO SEGURA (CORREÇÃO DE DNS) ---
# O .strip() remove espaços. O .replace() remove barras finais.
url_raw = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
key_raw = st.secrets.get("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not url_raw or not key_raw:
    st.error("❌ Credenciais não configuradas no Cloud.")
    st.stop()

# LIMPEZA DOS DADOS: Isso evita o erro 'Name or service not known'
URL = url_raw.strip().rstrip("/") 
KEY = key_raw.strip()

@st.cache_resource
def conectar():
    # Se a URL estiver errada, o erro aparecerá aqui
    return create_client(URL, KEY)

try:
    supabase = conectar()
except Exception as e:
    st.error(f"Erro fatal de DNS: {e}")
    st.stop()

URL = url_raw.strip().replace(" ", "")
KEY = key_raw.strip().replace(" ", "")

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
st.title("🔧 Gestão de Manutenção v21.0")
usuarios_raw, mecanicos_raw, maquinas_raw = carregar_listas()

with st.sidebar:
    st.header("⚙️ Configurações")
    if st.button("🔄 Atualizar"): 
        st.rerun()
    
    ordem_sel = st.selectbox("Ordenar por:", ["Fila Manual", "Prioridade", "Data Solicitação"])
    
    st.divider()
    st.header("➕ Gerenciar Cadastros")
    # Expander de Cadastros (Simplificado para o código não ficar gigante)
    with st.expander("Cadastrar Novo"):
        tipo = st.selectbox("Tipo", ["usuarios", "maquinas", "mecanicos"])
        nome_novo = st.text_input("Nome")
        if st.button("Salvar"):
            if nome_novo:
                supabase.table(tipo).insert({"nome": nome_novo}).execute()
                st.rerun()

solicitacoes = carregar_solicitacoes(ordem_sel)

# --- NOVA ORDEM DE SERVIÇO ---
with st.expander("📝 NOVA ORDEM DE SERVIÇO", expanded=False):
    with st.form("f_nova", clear_on_submit=True):
        c1, c2 = st.columns(2)
        u_sel = c1.selectbox("Solicitante", [i['nome'] for i in usuarios_raw])
        m_sel = c1.selectbox("Máquina", [i['nome'] for i in maquinas_raw])
        prio = c2.select_slider("Prioridade", ["Baixa", "Média", "Alta", "Urgente"])
        dt_i = c2.date_input("Início")
        desc = st.text_area("Descrição")
        
        if st.form_submit_button("🔨 Abrir OS"):
            try:
                u_id = next(i['id'] for i in usuarios_raw if i['nome'] == u_sel)
                m_id = next(i['id'] for i in maquinas_raw if i['nome'] == m_sel)
                
                supabase.table('solicitacoes').insert({
                    "usuario_id": u_id, 
                    "maquina_id": m_id, 
                    "descricao": desc,
                    "prioridade": prio, 
                    "status": "Pendente", 
                    "data_solicitacao": str(date.today()),
                    "data_inicio": str(dt_i), 
                    "ordem_manual": int(datetime.now().timestamp())
                }).execute()
                st.success("OS Criada!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar no banco: {e}")

st.divider()

# --- FILA DE TRABALHO ---
if solicitacoes:
    cols = st.columns([0.5, 1, 1.2, 1, 1, 1, 0.8, 2.5])
    titulos = ["ID", "Abertura", "Máquina", "Status", "Início", "Fim", "Prior.", "Ações"]
    for col, t in zip(cols, titulos): col.markdown(f"**{t}**")
    
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

        # --- AÇÕES ---
        b = r[7].columns(5)
        
        # 1. Finalizar
        if s['status'] != "Finalizado":
            if b[0].button("🏁", key=f"f_{s['id']}"):
                supabase.table('solicitacoes').update({"status": "Finalizado", "data_fim": str(date.today())}).eq("id", s['id']).execute()
                st.rerun()

        # 2. Editar (CORRIGIDO: Abre formulário fora da linha para não bugar o layout)
        if b[1].button("📝", key=f"e_{s['id']}"):
            st.session_state[f"editando_{s['id']}"] = True

        # 3. Setas
        curr_o = s.get('ordem_manual', 0)
        if b[2].button("🔼", key=f"u_{s['id']}"):
            supabase.table('solicitacoes').update({"ordem_manual": curr_o + 100}).eq("id", s['id']).execute()
            st.rerun()
        if b[3].button("🔽", key=f"d_{s['id']}"):
            supabase.table('solicitacoes').update({"ordem_manual": curr_o - 100}).eq("id", s['id']).execute()
            st.rerun()

        # 4. Excluir
        if b[4].button("🗑️", key=f"del_{s['id']}"):
            supabase.table('solicitacoes').delete().eq("id", s['id']).execute()
            st.rerun()

        # --- FORMULÁRIO DE EDIÇÃO ---
        if st.session_state.get(f"editando_{s['id']}", False):
            with st.container():
                st.info(f"Ajustando OS #{s['id']}")
                with st.form(f"form_edit_{s['id']}"):
                    fe1, fe2, fe3, fe4 = st.columns(4)
                    novo_st = fe1.selectbox("Status", ["Pendente", "Em andamento", "Finalizado"], index=["Pendente", "Em andamento", "Finalizado"].index(s['status']))
                    novo_pr = fe2.selectbox("Prioridade", ["Baixa", "Média", "Alta", "Urgente"], index=["Baixa", "Média", "Alta", "Urgente"].index(s['prioridade']))
                    
                    # Datas seguras
                    def converter_data(d_str):
                        try: return datetime.strptime(d_str, '%Y-%m-%d').date()
                        except: return date.today()

                    nova_dt_i = fe3.date_input("Data Início", converter_data(s['data_inicio']))
                    nova_dt_f = fe4.date_input("Data Fim", converter_data(s['data_fim']))
                    
                    c_btn1, c_btn2 = st.columns(2)
                    if c_btn1.form_submit_button("✅ Confirmar Alteração"):
                        supabase.table('solicitacoes').update({
                            "status": novo_st,
                            "prioridade": novo_pr,
                            "data_inicio": str(nova_dt_i),
                            "data_fim": str(nova_dt_f)
                        }).eq("id", s['id']).execute()
                        st.session_state[f"editando_{s['id']}"] = False
                        st.rerun()
                    
                    if c_btn2.form_submit_button("❌ Cancelar"):
                        st.session_state[f"editando_{s['id']}"] = False
                        st.rerun()
        st.divider()
else:
    st.info("Nenhuma ordem encontrada.")
