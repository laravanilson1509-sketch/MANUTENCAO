import streamlit as st
import pandas as pd
from datetime import date, datetime
import os
import io
from dotenv import load_dotenv
from supabase import create_client, Client
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Manutenção", layout="wide", page_icon="🔧")

# --- 2. CONEXÃO SEGURA ---
load_dotenv()
# Prioriza Secrets do Streamlit Cloud, depois tenta arquivo local
URL = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
KEY = st.secrets.get("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not URL or not KEY:
    st.error("❌ Credenciais do Supabase não encontradas. Verifique seus Secrets.")
    st.stop()

supabase: Client = create_client(URL, KEY)

# --- 3. FUNÇÕES DE CARGA DE DADOS ---
def carregar_listas():
    u = supabase.table('usuarios').select('id, nome').execute()
    m = supabase.table('mecanicos').select('id, nome').execute()
    q = supabase.table('maquinas').select('id, nome').execute()
    return u.data, m.data, q.data

def carregar_solicitacoes():
    s = supabase.table('solicitacoes').select(
        '*, usuarios(nome), mecanicos(nome), maquinas(nome)'
    ).order('id', desc=True).execute()
    return s.data

# --- 4. FUNÇÃO PARA GERAR EXCEL ---
def gerar_excel(dados):
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Relatorio_Manutencao"
    
    headers = ["ID", "Solicitante", "Máquina", "Mecânico", "Status", "Prioridade", "Solicitado", "Início", "Fim"]
    ws.append(headers)
    
    for s in dados:
        ws.append([
            s.get('id'),
            (s.get('usuarios') or {}).get('nome', 'N/A'),
            (s.get('maquinas') or {}).get('nome', 'N/A'),
            (s.get('mecanicos') or {}).get('nome', '---'),
            s.get('status'),
            s.get('prioridade'),
            s.get('data_solicitacao'),
            s.get('data_inicio'),
            s.get('data_fim')
        ])
    wb.save(output)
    return output.getvalue()

# Inicialização de dados
usuarios_raw, mecanicos_raw, maquinas_raw = carregar_listas()
solicitacoes = carregar_solicitacoes()

# --- 5. BARRA LATERAL: ADMINISTRAÇÃO ---
with st.sidebar:
    st.title("⚙️ Administração")
    
    with st.expander("➕ Novos Cadastros"):
        tipo_cad = st.selectbox("O que cadastrar?", ["usuarios", "mecanicos", "maquinas"])
        nome_cad = st.text_input("Nome completo")
        if st.button("Salvar Novo"):
            if nome_cad:
                supabase.table(tipo_cad).insert({"nome": nome_cad}).execute()
                st.success("Cadastrado!")
                st.rerun()

    with st.expander("🗑️ Excluir Registros"):
        tipo_del = st.selectbox("Excluir de:", ["usuarios", "mecanicos", "maquinas"], key="del_tipo")
        lista_opcoes = usuarios_raw if tipo_del == "usuarios" else mecanicos_raw if tipo_del == "mecanicos" else maquinas_raw
        
        if lista_opcoes:
            item_del = st.selectbox("Selecione o registro:", [i['nome'] for i in lista_opcoes])
            if st.button("🔥 Apagar Permanente", type="primary"):
                id_del = [i['id'] for i in lista_opcoes if i['nome'] == item_del][0]
                try:
                    supabase.table(tipo_del).delete().eq("id", id_del).execute()
                    st.warning(f"{item_del} removido.")
                    st.rerun()
                except:
                    st.error("Erro: Este registro possui vínculos ativos.")

    if solicitacoes:
        st.divider()
        st.download_button("📥 Baixar Relatório Excel", data=gerar_excel(solicitacoes), file_name="relatorio_manutencao.xlsx")

# --- 6. CORPO PRINCIPAL ---
st.title("🛠️ Plano de Manutenção v11.5")

# FORMULÁRIO DE NOVA OS
with st.expander("📝 ABRIR NOVA ORDEM DE SERVIÇO", expanded=False):
    with st.form("form_os", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            u_os = st.selectbox("Solicitante", [i['nome'] for i in usuarios_raw])
            m_os = st.selectbox("Máquina", [i['nome'] for i in maquinas_raw])
        with c2:
            mec_os = st.selectbox("Mecânico Responsável", ["Não Definido"] + [i['nome'] for i in mecanicos_raw])
            prio_os = st.select_slider("Prioridade", ["Baixa", "Média", "Alta", "Urgente"])
        
        desc_os = st.text_area("Descrição técnica do problema")
        
        if st.form_submit_button("🔨 Registrar Ordem de Serviço"):
            u_id = [i['id'] for i in usuarios_raw if i['nome'] == u_os][0]
            m_id = [i['id'] for i in maquinas_raw if i['nome'] == m_os][0]
            mec_id = next((i['id'] for i in mecanicos_raw if i['nome'] == mec_os), None)
                
            supabase.table('solicitacoes').insert({
                "usuario_id": u_id, "maquina_id": m_id, "mecanico_id": mec_id,
                "descricao": desc_os, "prioridade": prio_os, "status": "Pendente",
                "data_solicitacao": str(date.today())
            }).execute()
            st.success("✅ OS Registrada!")
            st.rerun()

st.divider()

# --- 7. ATUALIZAR SOLICITAÇÃO (LISTA SUSPENSA/EXPANDER) ---
st.subheader("🚀 Gerenciamento de OS")

if solicitacoes:
    with st.expander("📑 Clique aqui para Editar ou Finalizar uma OS", expanded=False):
        opcoes_update = {f"ID: {s['id']} | {s.get('maquinas',{}).get('nome', 'N/A')}" : s for s in solicitacoes}
        escolha = st.selectbox("Selecione a Ordem de Serviço:", list(opcoes_update.keys()))
        
        if escolha:
            dados_atuais = opcoes_update[escolha]
            with st.form(f"edit_form_{dados_atuais['id']}"):
                at1, at2, at3 = st.columns(3)
                
                with at1:
                    idx_status = ["Pendente", "Em andamento", "Finalizado"].index(dados_atuais['status'])
                    novo_status = st.selectbox("Alterar Status", ["Pendente", "Em andamento", "Finalizado"], index=idx_status)
                
                with at2:
                    d_ini_val = datetime.strptime(dados_atuais['data_inicio'], '%Y-%m-%d').date() if dados_atuais.get('data_inicio') else date.today()
                    nova_data_i = st.date_input("Data de Início", value=d_ini_val)
                
                with at3:
                    d_fim_val = datetime.strptime(dados_atuais['data_fim'], '%Y-%m-%d').date() if dados_atuais.get('data_fim') else date.today()
                    nova_data_f = st.date_input("Data de Finalização", value=d_fim_val)
                
                if st.form_submit_button("✅ Salvar Alterações Detalhadas"):
                    supabase.table('solicitacoes').update({
                        "status": novo_status,
                        "data_inicio": str(nova_data_i),
                        "data_fim": str(nova_data_f)
                    }).eq("id", dados_atuais['id']).execute()
                    
                    st.success(f"OS {dados_atuais['id']} atualizada!")
                    st.rerun()

st.divider()

# --- 8. FILA DE ORDENS (VISUALIZAÇÃO) ---
st.subheader("📋 Fila de Ordens de Serviço")
if solicitacoes:
    df_lista = []
    for s in solicitacoes:
        df_lista.append({
            "ID": s['id'],
            "Máquina": (s.get('maquinas') or {}).get('nome', 'N/A'),
            "Mecânico": (s.get('mecanicos') or {}).get('nome', '---'),
            "Status": s.get('status'),
            "Início": s.get('data_inicio'),
            "Final": s.get('data_fim'),
            "Prioridade": s.get('prioridade')
        })
    st.dataframe(pd.DataFrame(df_lista), use_container_width=True, hide_index=True)
else:
    st.info("Nenhuma ordem de serviço encontrada.")
