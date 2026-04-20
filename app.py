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

def carregar_solicitacoes(ordem_por="ID"):
    try:
        coluna_sort = 'id'
        if ordem_por == "Prioridade":
            coluna_sort = 'prioridade'
        elif ordem_por == "Data Solicitação":
            coluna_sort = 'data_solicitacao'

        s = supabase.table('solicitacoes').select(
            '*, usuarios(nome), mecanicos(nome), maquinas(nome)'
        ).order(coluna_sort, desc=True).execute()
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
            s.get('id'), s.get('data_solicitacao'),
            (s.get('usuarios') or {}).get('nome', 'N/A'),
            (s.get('maquinas') or {}).get('nome', 'N/A'),
            (s.get('mecanicos') or {}).get('nome', '---'),
            s.get('status'), s.get('prioridade'),
            s.get('data_inicio'), s.get('data_fim')
        ])
    wb.save(output)
    return output.getvalue()

# --- 5. CABEÇALHO ---
st.title("🔧 Gestão de Manutenção v14.0")

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
    ordem_sel = st.selectbox("Ordenar fila por:", ["ID", "Prioridade", "Data Solicitação"])

solicitacoes = carregar_solicitacoes(ordem_sel)

if solicitacoes:
    with st.sidebar:
        st.download_button("📥 Baixar Excel", data=gerar_excel(solicitacoes), file_name=f"OS_{date.today()}.xlsx")

# --- 7. ABRIR NOVA OS ---
with st.expander("📝 ABRIR NOVA ORDEM DE SERVIÇO", expanded=False):
    with st.form("form_nova_os", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        u_os = c1.selectbox("Solicitante", [i['nome'] for i in usuarios_raw])
        m_os = c1.selectbox("Máquina", [i['nome'] for i in maquinas_raw])
        mec_os = c2.selectbox("Mecânico", ["Não Definido"] + [i['nome'] for i in mecanicos_raw])
        prio_os = c2.select_slider("Prioridade", ["Baixa", "Média", "Alta", "Urgente"])
        data_ini_os = c3.date_input("Início Previsto", value=date.today())
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

# --- 8. FILA DE ORDENS ---
st.subheader("📋 Fila de Ordens de Serviço")

if solicitacoes:
    # Cabeçalho customizado
    cols = st.columns([0.6, 1.2, 1.5, 1.2, 1.2, 1.2, 1, 2])
    titulos = ["ID", "Abertura", "Máquina", "Status", "Início", "Fim", "Prior.", "Ações"]
    for col, tit in zip(cols, titulos):
        col.markdown(f"**{tit}**")
    st.divider()

    for s in solicitacoes:
        cor = "🔴" if s['status'] == "Pendente" else "🟡" if s['status'] == "Em andamento" else "🟢"
        
        r_id, r_ab, r_maq, r_st, r_ini, r_fim, r_prio, r_acao = st.columns([0.6, 1.2, 1.5, 1.2, 1.2, 1.2, 1, 2])
        
        r_id.write(f"#{s['id']}")
        r_ab.write(s.get('data_solicitacao', '---'))
        r_maq.write((s.get('maquinas') or {}).get('nome', 'N/A'))
        r_st.write(f"{cor} {s['status']}")
        r_ini.write(s.get('data_inicio') or "---")
        r_fim.write(s.get('data_fim') or "---")
        r_prio.write(s['prioridade'])

        # Coluna de Botões (Ações)
        btn_fin, btn_edit, btn_del = r_acao.columns(3)
        
        # Botão Finalizar Rápido
        if s['status'] != "Finalizado":
            if btn_fin.button("🏁", key=f"fin_{s['id']}", help="Finalizar OS"):
                supabase.table('solicitacoes').update({"status": "Finalizado", "data_fim": str(date.today())}).eq("id", s['id']).execute()
                st.rerun()
        
        # Botão Editar
        if btn_edit.button("📝", key=f"edit_btn_{s['id']}", help="Editar Dados"):
            st.session_state[f"ed_{s['id']}"] = not st.session_state.get(f"ed_{s['id']}", False)

        # Botão Excluir Funcional
        if btn_del.button("🗑️", key=f"del_{s['id']}", help="Excluir Solicitação"):
            try:
                supabase.table('solicitacoes').delete().eq("id", s['id']).execute()
                st.success(f"OS #{s['id']} excluída!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao excluir: {e}")

        # Seção de Edição (Condicional)
        if st.session_state.get(f"ed_{s['id']}", False):
            with st.container():
                st.info(f"Editando OS #{s['id']}")
                with st.form(key=f"form_ed_{s['id']}"):
                    e1, e2, e3 = st.columns(3)
                    
                    # Datas seguras
                    def converter_data(d_str):
                        try: return datetime.strptime(d_str, '%Y-%m-%d').date()
                        except: return date.today()

                    st_opcoes = ["Pendente", "Em andamento", "Finalizado"]
                    novo_st = e1.selectbox("Alterar Status", st_opcoes, index=st_opcoes.index(s['status']) if s['status'] in st_opcoes else 0)
                    nova_i = e2.date_input("Nova Data Início", converter_data(s.get('data_inicio')))
                    nova_f = e3.date_input("Nova Data Fim", converter_data(s.get('data_fim')))
                    
                    c_salvar, c_cancelar = st.columns(2)
                    if c_salvar.form_submit_button("✅ Salvar Alterações"):
                        supabase.table('solicitacoes').update({
                            "status": novo_st,
                            "data_inicio": str(nova_i),
                            "data_fim": str(nova_f)
                        }).eq("id", s['id']).execute()
                        st.session_state[f"ed_{s['id']}"] = False
                        st.rerun()
                    
                    if c_cancelar.form_submit_button("❌ Cancelar"):
                        st.session_state[f"ed_{s['id']}"] = False
                        st.rerun()
        
        st.divider()
else:
    st.info("Nenhuma ordem de serviço encontrada.")
