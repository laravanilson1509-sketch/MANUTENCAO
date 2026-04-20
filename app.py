import streamlit as st
import pandas as pd
from datetime import date, datetime
import os
import io
from dotenv import load_dotenv
from supabase import create_client, Client
from openpyxl import Workbook

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Manutenção", layout="wide", page_icon="🔧")

# --- 2. CONEXÃO SEGURA ---
load_dotenv()
URL = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
KEY = st.secrets.get("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not URL or not KEY:
    st.error("❌ Credenciais do Supabase não encontradas.")
    st.stop()

supabase: Client = create_client(URL, KEY)

# --- 3. CARGA DE DADOS ---
def carregar_listas():
    try:
        u = supabase.table('usuarios').select('id, nome').execute()
        m = supabase.table('mecanicos').select('id, nome').execute()
        q = supabase.table('maquinas').select('id, nome').execute()
        return u.data, m.data, q.data
    except Exception as e:
        st.error(f"Erro ao carregar listas: {e}")
        return [], [], []

def carregar_solicitacoes(ordem_por="id"):
    try:
        # Define a lógica de ordenação
        coluna_sort = 'id'
        ascendente = False
        
        if ordem_por == "Prioridade":
            coluna_sort = 'prioridade'
        elif ordem_por == "Data Solicitação":
            coluna_sort = 'data_solicitacao'

        s = supabase.table('solicitacoes').select(
            '*, usuarios(nome), mecanicos(nome), maquinas(nome)'
        ).order(coluna_sort, desc=not ascendente).execute()
        return s.data
    except Exception as e:
        st.error(f"Erro ao carregar solicitações: {e}")
        return []

# Inicialização de dados
usuarios_raw, mecanicos_raw, maquinas_raw = carregar_listas()

# --- 4. FUNÇÃO PARA GERAR EXCEL ---
def gerar_excel(dados):
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Relatorio"
    headers = ["ID", "Abertura", "Solicitante", "Máquina", "Mecânico", "Status", "Prioridade", "Início", "Fim"]
    ws.append(headers)
    for s in dados:
        ws.append([
            s.get('id'),
            s.get('data_solicitacao'),
            (s.get('usuarios') or {}).get('nome', 'N/A'),
            (s.get('maquinas') or {}).get('nome', 'N/A'),
            (s.get('mecanicos') or {}).get('nome', '---'),
            s.get('status'),
            s.get('prioridade'),
            s.get('data_inicio'),
            s.get('data_fim')
        ])
    wb.save(output)
    return output.getvalue()

# --- 5. CABEÇALHO ---
st.title("🔧 Gestão de Manutenção v13.0")

# --- 6. BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Administração")
    with st.expander("➕ Novos Cadastros"):
        tipo_cad = st.selectbox("Tipo", ["usuarios", "mecanicos", "maquinas"])
        nome_cad = st.text_input("Nome do Registro")
        if st.button("Salvar Cadastro"):
            if nome_cad:
                supabase.table(tipo_cad).insert({"nome": nome_cad}).execute()
                st.success("Cadastrado!")
                st.rerun()

    st.divider()
    st.header("📊 Filtros e Ordem")
    ordem_selecionada = st.selectbox("Ordenar fila por:", ["ID", "Prioridade", "Data Solicitação"])

# Recarrega solicitações com base na ordem escolhida
solicitacoes = carregar_solicitacoes(ordem_selecionada)

if solicitacoes:
    with st.sidebar:
        st.download_button(
            label="📥 Baixar Relatório Excel",
            data=gerar_excel(solicitacoes),
            file_name=f"relatorio_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# --- 7. ABRIR NOVA ORDEM DE SERVIÇO ---
with st.expander("📝 ABRIR NOVA ORDEM DE SERVIÇO", expanded=False):
    with st.form("form_nova_os", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            u_os = st.selectbox("Solicitante", [i['nome'] for i in usuarios_raw])
            m_os = st.selectbox("Máquina", [i['nome'] for i in maquinas_raw])
        with c2:
            mec_os = st.selectbox("Mecânico Responsável", ["Não Definido"] + [i['nome'] for i in mecanicos_raw])
            prio_os = st.select_slider("Prioridade", ["Baixa", "Média", "Alta", "Urgente"])
        with c3:
            data_ini_os = st.date_input("Início Previsto", value=date.today())
        
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
            st.success("✅ OS Registrada!")
            st.rerun()

st.divider()

# --- 8. FILA DE ORDENS ---
st.subheader("📋 Fila de Ordens de Serviço")

if solicitacoes:
    # Cabeçalho da Tabela (Colunas ajustadas para incluir Data Solicitação)
    cols = st.columns([0.6, 1.2, 1.5, 1.2, 1.2, 1.2, 1, 1.5])
    titulos = ["ID", "Abertura", "Máquina", "Status", "Início", "Fim", "Prior.", "Ações"]
    for col, tit in zip(cols, titulos):
        col.markdown(f"**{tit}**")
    st.divider()

    for s in solicitacoes:
        cor = "🔴" if s['status'] == "Pendente" else "🟡" if s['status'] == "Em andamento" else "🟢"
        
        r_id, r_abert, r_maq, r_status, r_ini, r_fim, r_prio, r_acao = st.columns([0.6, 1.2, 1.5, 1.2, 1.2, 1.2, 1, 1.5])
        
        r_id.write(f"#{s['id']}")
        r_abert.write(s.get('data_solicitacao', '---'))
        r_maq.write((s.get('maquinas') or {}).get('nome', 'N/A'))
        r_status.write(f"{cor} {s['status']}")
        r_ini.write(s.get('data_inicio') or "---")
        r_fim.write(s.get('data_fim') or "---")
        r_prio.write(s['prioridade'])

        # --- AÇÕES (FINALIZAR E EDITAR) ---
        c_fin, c_edit = r_acao.columns(2)
        
        if s['status'] != "Finalizado":
            if c_fin.button("🏁", key=f"fin_{s['id']}", help="Finalizar Agora"):
                supabase.table('solicitacoes').update({
                    "status": "Finalizado", "data_fim": str(date.today())
                }).eq("id", s['id']).execute()
                st.rerun()
        
        if c_edit.button("📝", key=f"edit_btn_{s['id']}", help="Editar Datas/Status"):
            st.session_state[f"editando_{s['id']}"] = True

        # --- FORMULÁRIO DE EDIÇÃO (EXPANDE ABAIXO DA LINHA) ---
        if st.session_state.get(f"editando_{s['id']}", False):
            with st.form(key=f"form_edit_{s['id']}"):
                st.write(f"### Ajustar OS #{s['id']}")
                fe1, fe2, fe3 = st.columns(3)
                
                # Tratamento de datas para o input
                d_ini_atual = datetime.strptime(s['data_inicio'], '%Y-%m-%d').date() if s.get('data_inicio') else date.today()
                d_fim_atual = datetime.strptime(s['data_fim'], '%Y-%m-%d').date() if s.get('data_fim') else date.today()
                
                novo_st = fe1.selectbox("Status", ["Pendente", "Em andamento", "Finalizado"], index=["Pendente", "Em andamento", "Finalizado"].index(s['status']))
                nova_data_i = fe2.date_input("Nova Data Início", d_ini_atual)
                nova_data_f = fe3.date_input("Nova Data Fim", d_fim_atual)
                
                btn_salvar, btn_cancelar = st.columns(2)
                if btn_salvar.form_submit_button("Salvar Alterações"):
                    supabase.table('solicitacoes').update({
                        "status": novo_st,
                        "data_inicio": str(nova_data_i),
                        "data_fim": str(nova_data_f)
                    }).eq("id", s['id']).execute()
                    st.session_state[f"editando_{s['id']}"] = False
                    st.rerun()
                
                if btn_cancelar.form_submit_button("Cancelar"):
                    st.session_state[f"editando_{s['id']}"] = False
                    st.rerun()

        st.write('<style>div[data-testid="stHorizontalBlock"]{align-items: center;}</style>', unsafe_allow_html=True)
        st.divider()
else:
    st.info("Nenhuma ordem de serviço encontrada.")
