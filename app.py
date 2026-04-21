import streamlit as st
import pandas as pd
from datetime import date, datetime
import os
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

try:
    supabase = conectar()
except Exception as e:
    st.error(f"Erro ao conectar ao banco: {e}")
    st.stop()

# --- 3. FUNÇÕES DE DADOS ---
def carregar_listas():
    try:
        u = supabase.table('usuarios').select('id, nome').order('nome').execute()
        m = supabase.table('mecanicos').select('id, nome').order('nome').execute()
        q = supabase.table('maquinas').select('id, nome').order('nome').execute()
        return u.data, m.data, q.data
    except:
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
    except:
        return []

# --- 4. INTERFACE ---
st.title("🔧 Plano de Manutenção")
usuarios_raw, mecanicos_raw, maquinas_raw = carregar_listas()
solicitacoes_metrics = carregar_solicitacoes("Fila Manual")

# --- INDICADORES (CARDS) ---
if solicitacoes_metrics:
    df_m = pd.DataFrame(solicitacoes_metrics)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pendentes", len(df_m[df_m['status'] == 'Pendente']))
    c2.metric("Em andamento", len(df_m[df_m['status'] == 'Em andamento']))
    c3.metric("Finalizados", len(df_m[df_m['status'] == 'Finalizado']))
    c4.metric("Urgentes", len(df_m[df_m['prioridade'] == 'Urgente']))

# --- BARRA LATERAL (CADASTROS) ---
with st.sidebar:
    st.header("⚙️ Configurações")
    if st.button("🔄 Atualizar Página"): st.rerun()
    ordem_sel = st.selectbox("Ordenar por:", ["Fila Manual", "Prioridade", "Data Solicitação"])
    
    st.divider()
    st.header("➕ Gerenciar Cadastros")
    
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
                supabase.table('usuarios').delete().eq("id", u['id']).execute(); st.rerun()

    with st.expander("🚜 Máquinas"):
        for q in maquinas_raw:
            c1, c2 = st.columns([3, 1])
            c1.write(q['nome'])
            if c2.button("🗑️", key=f"del_q_{q['id']}"):
                supabase.table('maquinas').delete().eq("id", q['id']).execute(); st.rerun()

    with st.expander("👨‍🔧 Mecânicos"):
        with st.form("cad_m", clear_on_submit=True):
            n_m = st.text_input("Novo Mecânico")
            if st.form_submit_button("Adicionar"):
                if n_m:
                    supabase.table('mecanicos').insert({"nome": n_m}).execute()
                    st.rerun()
        for m in mecanicos_raw:
            c1, c2 = st.columns([3, 1])
            c1.write(m['nome'])
            if c2.button("🗑️", key=f"del_m_{m['id']}"):
                supabase.table('mecanicos').delete().eq("id", m['id']).execute(); st.rerun()

# --- 5. NOVA ORDEM DE SERVIÇO ---
solicitacoes = carregar_solicitacoes(ordem_sel)

with st.expander("📝 NOVA ORDEM DE SERVIÇO"):
    with st.form("f_nova", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        u_sel = c1.selectbox("Solicitante", [i['nome'] for i in usuarios_raw])
        m_sel = c2.selectbox("Máquina", [i['nome'] for i in maquinas_raw])
        prio_sel = c3.selectbox("Prioridade", ["Baixa", "Média", "Alta", "Urgente"])
        
        c4, c5 = st.columns(2)
        mec_sel = c4.selectbox("Mecânico Responsável", ["Nenhum"] + [i['nome'] for i in mecanicos_raw])
        dt_i = c5.date_input("Data de Início", date.today())
        
        desc = st.text_area("Observação / Descrição do Problema")
        
        if st.form_submit_button("🔨 Abrir Ordem de Serviço", use_container_width=True):
            u_id = next(i['id'] for i in usuarios_raw if i['nome'] == u_sel)
            m_id = next(i['id'] for i in maquinas_raw if i['nome'] == m_sel)
            mec_id = next((i['id'] for i in mecanicos_raw if i['nome'] == mec_sel), None)
            
            supabase.table('solicitacoes').insert({
                "usuario_id": u_id, "maquina_id": m_id, "mecanico_id": mec_id, "descricao": desc,
                "prioridade": prio_sel, "status": "Pendente", "data_solicitacao": date.today().isoformat(),
                "data_inicio": dt_i.isoformat(), "ordem_manual": int(datetime.now().timestamp())
            }).execute()
            st.rerun()

# --- 6. TABELA DE FILA ---
if solicitacoes:
    st.divider()
    cols = st.columns([0.8, 1.2, 1.0, 1.0, 0.9, 0.7, 0.7, 1.6, 1.8])
    labels = ["Abertura", "Máquina", "Mecânico", "Status", "Prioridade", "Início", "Fim", "Obs", "Ações"]
    for col, t in zip(cols, labels):
        col.markdown(f"**{t}**")
    
    for s in solicitacoes:
        r = st.columns([0.8, 1.2, 1.0, 1.0, 0.9, 0.7, 0.7, 1.6, 1.8])
        
        r[0].write(s['data_solicitacao'])
        r[1].write(f"**{s['maquinas']['nome'] if s['maquinas'] else '---'}**")
        r[2].write(s['mecanicos']['nome'] if s['mecanicos'] else "---")
        
        status_map = {"Pendente": "🟦 Pendente", "Em andamento": "🟧 Em andamento", "Finalizado": "🟩 Finalizado"}
        r[3].write(status_map.get(s['status'], s['status']))
        
        p = s['prioridade']
        cor_p = "🟢 Baixa" if p == "Baixa" else "🟡 Média" if p == "Média" else "🟠 Alta" if p == "Alta" else "🔴 Urgente"
        r[4].write(cor_p)
        
        r[5].write(s['data_inicio'] or "---")
        r[6].write(s['data_fim'] or "---")
        r[7].caption(s['descricao'] if s['descricao'] else "---")
        
        btns = r[8].columns(5)
        if s['status'] != "Finalizado" and btns[0].button("🏁", key=f"f_{s['id']}"):
            supabase.table('solicitacoes').update({
                "status": "Finalizado", 
                "data_fim": date.today().isoformat()
            }).eq("id", s['id']).execute()
            st.rerun()

        if btns[1].button("📝", key=f"e_{s['id']}"): 
            st.session_state[f"ed_{s['id']}"] = True
        
        curr_o = s.get('ordem_manual', 0)
        if btns[2].button("🔼", key=f"u_{s['id']}"):
            supabase.table('solicitacoes').update({"ordem_manual": curr_o + 100}).eq("id", s['id']).execute(); st.rerun()
        if btns[3].button("🔽", key=f"d_{s['id']}"):
            supabase.table('solicitacoes').update({"ordem_manual": curr_o - 100}).eq("id", s['id']).execute(); st.rerun()
        if btns[4].button("🗑️", key=f"x_{s['id']}"):
            supabase.table('solicitacoes').delete().eq("id", s['id']).execute(); st.rerun()

        # FORMULÁRIO DE EDIÇÃO
        if st.session_state.get(f"ed_{s['id']}", False):
            with st.container(border=True):
                with st.form(key=f"form_ed_{s['id']}"):
                    st.write(f"### Editar OS - {s['maquinas']['nome'] if s['maquinas'] else ''}")
                    e1, e2, e3 = st.columns(3)
                    
                    new_status = e1.selectbox("Status", ["Pendente", "Em andamento", "Finalizado"], 
                                             index=["Pendente", "Em andamento", "Finalizado"].index(s['status']))
                    new_prio = e2.selectbox("Prioridade", ["Baixa", "Média", "Alta", "Urgente"],
                                           index=["Baixa", "Média", "Alta", "Urgente"].index(s['prioridade']))
                    
                    lista_mecs = [i['nome'] for i in mecanicos_raw]
                    idx_mec = lista_mecs.index(s['mecanicos']['nome']) if s['mecanicos'] and s['mecanicos']['nome'] in lista_mecs else 0
                    new_mec = e3.selectbox("Responsável", lista_mecs, index=idx_mec)

                    d1, d2 = st.columns(2)
                    try:
                        val_ini = datetime.strptime(s['data_inicio'], '%Y-%m-%d').date() if s['data_inicio'] else date.today()
                    except:
                        val_ini = date.today()
                        
                    try:
                        val_fim = datetime.strptime(s['data_fim'], '%Y-%m-%d').date() if s['data_fim'] else date.today()
                    except:
                        val_fim = date.today()

                    new_dt_inicio = d1.date_input("Data Início", val_ini, key=f"dtin_{s['id']}")
                    new_dt_fim = d2.date_input("Data Fim", val_fim, key=f"dtfim_{s['id']}")
                    
                    new_desc = st.text_area("Editar Observação", value=s['descricao'])
                    
                    if st.form_submit_button("✅ Salvar Alterações", use_container_width=True):
                        m_id_edit = next(i['id'] for i in mecanicos_raw if i['nome'] == new_mec)
                        
                        payload = {
                            "status": new_status,
                            "prioridade": new_prio,
                            "mecanico_id": m_id_edit,
                            "descricao": new_desc,
                            "data_inicio": new_dt_inicio.isoformat(),
                        }
                        
                        if new_status == "Finalizado":
                            payload["data_fim"] = new_dt_fim.isoformat()
                        else:
                            payload["data_fim"] = None

                        supabase.table('solicitacoes').update(payload).eq("id", s['id']).execute()
                        st.session_state[f"ed_{s['id']}"] = False
                        st.rerun()
                
                if st.button("❌ Cancelar", key=f"can_{s['id']}", use_container_width=True):
                    st.session_state[f"ed_{s['id']}"] = False
                    st.rerun()
        st.divider()
