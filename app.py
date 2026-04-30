import streamlit as st
import pandas as pd
from datetime import date, datetime
from io import BytesIO
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
import re

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="INOVA FLEX - Gestão", layout="wide", page_icon="🔧")

# Inicialização Global de Session States
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'dados_f' not in st.session_state: st.session_state.dados_f = None
if 'f_key' not in st.session_state: st.session_state.f_key = 0
if 'tela_selecionada' not in st.session_state: st.session_state.tela_selecionada = "📋 Fila de Manutenção"

st.markdown("""
<style>
    button[kind="primary"], button[kind="secondary"], button[kind="tertiary"] {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        padding: 0px !important;
        min-height: 35px !important;
    }

    button div[data-testid="stMarkdownContainer"] p {
        display: flex !important;
        margin: 0px !important;
        padding: 0px !important;
        width: 100% !important;
        justify-content: center !important;
        align-items: center !important;
    }

    button div[data-testid="stButtonInternalContainer"] {
        gap: 0px !important;
        justify-content: center !important;
        width: 100% !important;
    }

    [data-testid="column"] {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
    }
    
    .p-urgente { color: #ff4b4b !important; font-weight: bold; border-left: 4px solid #ff4b4b; padding-left: 8px; background: rgba(255, 75, 75, 0.1); width: 100%; text-align: center; }
    .p-alta { color: #ffa500 !important; font-weight: bold; border-left: 4px solid #ffa500; padding-left: 8px; background: rgba(255, 165, 0, 0.1); width: 100%; text-align: center; }
    .p-media { color: #f1c40f !important; font-weight: bold; border-left: 4px solid #f1c40f; padding-left: 8px; background: rgba(241, 196, 15, 0.1); width: 100%; text-align: center; }
    .p-baixa { color: #2ecc71 !important; font-weight: bold; border-left: 4px solid #2ecc71; padding-left: 8px; background: rgba(46, 204, 113, 0.1); width: 100%; text-align: center; }
    .linha-divisoria { border-bottom: 2px solid #333; margin: 15px 0; width: 100%; }
</style>
""", unsafe_allow_html=True)

def formatar_data_br(data_str):
    if not data_str or data_str == "---": return "---"
    try: 
        return datetime.strptime(data_str, '%Y-%m-%d').strftime('%d/%m/%y')
    except: 
        return data_str

# --- 2. CONEXÃO ---
URL = st.secrets.get("SUPABASE_URL")
ANON = st.secrets.get("SUPABASE_ANON_KEY")
SERVICE = st.secrets.get("SUPABASE_SERVICE_KEY")

@st.cache_resource
def conectar_admin():
    return create_client(URL, SERVICE)

supabase_admin = conectar_admin()

# --- 3. LÓGICA DE LOGIN ---
def realizar_login(u, p):
    try:
        u_limpo = u.strip().lower()
        res = supabase_admin.auth.sign_in_with_password({
            "email": f"{u_limpo}@inovaflex.com", 
            "password": p
        })
        
        if res.user:
            perfil = supabase_admin.table('perfis').select('nivel').eq('id', res.user.id).execute()
            if perfil.data and len(perfil.data) > 0:
                st.session_state['authenticated'] = True
                st.session_state['user_token'] = res.session.access_token
                st.session_state['user_id'] = res.user.id
                st.session_state['user_nickname'] = u_limpo.upper()
                st.session_state['user_level'] = perfil.data[0]['nivel']
                st.rerun()
    except Exception:
        st.error("Usuário ou senha inválidos.")

if not st.session_state.get('authenticated', False):
    st.markdown("<h2 style='text-align:center; color:#0052cc; margin-top:50px;'>INOVA FLEX</h2>", unsafe_allow_html=True)
    with st.container():
        col_l1, col_l2, col_l3 = st.columns([1,1,1])
        with col_l2:
            with st.form("login_form"):
                u_input = st.text_input("Usuário")
                p_input = st.text_input("Senha", type="password")
                if st.form_submit_button("ENTRAR", use_container_width=True): 
                    realizar_login(u_input, p_input)
    st.stop()

try:
    opts = ClientOptions(headers={"Authorization": f"Bearer {st.session_state['user_token']}"})
    supabase = create_client(URL, ANON, options=opts)
except:
    supabase = supabase_admin

# --- 4. FUNÇÕES DE DADOS ---
def carregar_listas():
    try:
        q = supabase.table('maquinas').select('id, nome').order('nome').execute()
        return q.data if q.data else []
    except: return []

def carregar_solicitacoes(maquina_id, nivel, uid, f_status="TODOS", f_prioridade="TODAS"):
    try:
        query = supabase.table('solicitacoes').select('*, maquinas(nome)')
        if nivel == 'operador': query = query.eq('criado_por_uuid', uid)
        if maquina_id and maquina_id != "TODOS": query = query.eq('maquina_id', maquina_id)
        if f_status != "TODOS": query = query.eq('status', f_status)
        else: query = query.neq('status', 'FINALIZADO')
        if f_prioridade != "TODAS": query = query.eq('prioridade', f_prioridade)
        return query.order('ordem_manual', desc=True).execute().data
    except: return []

def gerar_relatorio_completo():
    dados_os = st.session_state.get('dados_f', [])
    df_os = pd.DataFrame(dados_os)
    if not df_os.empty:
        df_os['data_solicitacao'] = pd.to_datetime(df_os['data_solicitacao'], errors='coerce').dt.strftime('%d/%m/%Y')
        df_os['data_inicio'] = df_os['data_inicio'].apply(formatar_data_br)
        df_os['data_fim'] = df_os['data_fim'].apply(formatar_data_br)
        df_os = df_os[['solicitante_nome', 'maquinas', 'status', 'prioridade', 'data_solicitacao', 'data_inicio', 'data_fim', 'descricao']]
        df_os.columns = ['Solicitante', 'Máquina', 'Status', 'Prioridade', 'Data Solicitação', 'Início', 'Fim', 'Descrição']
        df_os['Máquina'] = df_os['Máquina'].apply(lambda x: x['nome'] if isinstance(x, dict) else x)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df_os.empty: df_os.to_excel(writer, sheet_name='Ordens_Servico', index=False)
    output.seek(0)
    return output.getvalue()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.markdown("""
    <div style='background: linear-gradient(135deg, #003366 0%, #0052cc 100%); padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px;'>
        <h2 style='color: white; margin: 0; font-size: 1.5em;'>🔧 INOVA FLEX</h2>
        <p style='color: rgba(255,255,255,0.9); margin: 5px 0 0 0;'>Gestão de Manutenção</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div style="padding: 10px; border-radius: 10px; background-color: #1e1e1e; margin-bottom: 15px;">', unsafe_allow_html=True)
    col_s1, col_s2 = st.columns([3,1])
    with col_s1:
        st.markdown(f"<div style='font-size: 1.1em; font-weight: bold; color: #007bff;'>👤 {st.session_state['user_nickname']}</div>", unsafe_allow_html=True)
    with col_s2:
        if st.button("🚪", key="sair_btn"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    menu_options = {"📋 Fila de Manutenção": "Gerenciar OS", "⚙️ Cadastros": "Configurações do Sistema"}
    for key, desc in menu_options.items():
        if st.button(key, key=f"menu_{key}", use_container_width=True):
            st.session_state.tela_selecionada = key
            st.rerun()
    
    st.divider()
    if st.button("📊 **RELATÓRIO COMPLETO**", type="primary", use_container_width=True):
        relatorio = gerar_relatorio_completo()
        st.download_button(label="⬇️ DOWNLOAD", data=relatorio, file_name=f"Inovaflex_Rel_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

maquinas_raw = carregar_listas()
tela_selecionada = st.session_state.tela_selecionada

# --- 7. TELAS ---

if tela_selecionada == "📋 Fila de Manutenção":
    st.title("📋 Fila de Manutenção")
    
    with st.expander("➕ CRIAR NOVA ORDEM DE SERVIÇO", expanded=False):
        with st.form("n_os", clear_on_submit=True):
            c_f1, c_f2, c_f3 = st.columns([1, 1, 1])
            mq = c_f1.selectbox("🛠️ Máquina:", ["SELECIONE..."] + [m['nome'].upper() for m in maquinas_raw])
            pr = c_f2.selectbox("🔥 Prioridade:", ["BAIXA", "MÉDIA", "ALTA", "URGENTE"])
            solicitante = c_f3.text_input("👤 Solicitante:", value=st.session_state['user_nickname']).upper()
            
            ds = st.text_area("📝 Descrição do Problema:").upper()
            if st.form_submit_button("🚀 GERAR OS", type="primary"):
                if mq != "SELECIONE..." and ds.strip() and solicitante.strip():
                    mid = next(m['id'] for m in maquinas_raw if m['nome'].upper() == mq)
                    supabase.table('solicitacoes').insert({
                        "maquina_id": mid, 
                        "descricao": ds, 
                        "prioridade": pr, 
                        "solicitante_nome": solicitante,
                        "status": "PENDENTE", 
                        "data_solicitacao": date.today().isoformat(), 
                        "criado_por_uuid": st.session_state['user_id'], 
                        "ordem_manual": int(datetime.now().timestamp())
                    }).execute()
                    st.success("✅ OS Criada!")
                    st.rerun()
                else: st.error("Preencha Máquina, Solicitante e Descrição!")

    st.divider()
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([1.5, 1, 1, 1, 1])
        f_mq = c1.selectbox("🛠️ Máquina:", ["TODOS"] + [m['id'] for m in maquinas_raw], format_func=lambda x: next((m['nome'].upper() for m in maquinas_raw if m['id'] == x), "TODOS"), key=f"mq_{st.session_state.f_key}")
        f_st = c2.selectbox("📊 Status:", ["TODOS", "PENDENTE", "EM ANDAMENTO"], key=f"st_{st.session_state.f_key}")
        f_pr = c3.selectbox("🔥 Prioridade:", ["TODAS", "BAIXA", "MÉDIA", "ALTA", "URGENTE"], key=f"pr_{st.session_state.f_key}")
        if c4.button("🔍 FILTRAR", type="primary", use_container_width=True):
            st.session_state.dados_f = carregar_solicitacoes(f_mq, st.session_state['user_level'], st.session_state['user_id'], f_st, f_pr)
            st.rerun()
        if c5.button("🧹 LIMPAR", use_container_width=True):
            st.session_state.f_key += 1
            st.session_state.dados_f = None
            st.rerun()

    if st.session_state.dados_f:
        header = st.columns([1.0, 1.0, 0.9, 1.0, 0.8, 0.8, 0.8, 1.5, 1.8])
        cols_titulos = ["Solicitante", "Solicit.", "Máquina", "Status", "Prior.", "Início", "Fim", "Descrição", "Ações"]
        for col, t in zip(header, cols_titulos):
            col.markdown(f"**{t}**")
        
        for s in st.session_state.dados_f:
            st.markdown('<div class="linha-divisoria"></div>', unsafe_allow_html=True)
            r = st.columns([1.0, 1.0, 0.9, 1.0, 0.8, 0.8, 0.8, 1.5, 1.8])
            
            pri = str(s['prioridade']).upper()
            cor_c = "p-baixa"
            if pri == "URGENTE": cor_c = "p-urgente"
            elif pri == "ALTA": cor_c = "p-alta"
            elif pri in ["MÉDIA", "MEDIA"]: cor_c = "p-media"
            
            r[0].write(s.get('solicitante_nome', '---'))
            r[1].write(formatar_data_br(s.get('data_solicitacao')))
            r[2].write(f"**{s['maquinas']['nome']}**")
            r[3].write(s['status'])
            r[4].markdown(f'<div class="{cor_c}">{pri}</div>', unsafe_allow_html=True)
            r[5].write(formatar_data_br(s.get('data_inicio')))
            r[6].write(formatar_data_br(s.get('data_fim')))
            r[7].caption(s['descricao'])
            
            btn = r[8].columns(5)
            if btn[0].button("🏁", key=f"f_{s['id']}", help="Finalizar"):
                supabase.table('solicitacoes').update({"status":"FINALIZADO","data_fim":date.today().isoformat()}).eq("id",s['id']).execute()
                st.rerun()
            if btn[1].button("📝", key=f"e_{s['id']}", help="Editar"):
                st.session_state[f"ed_{s['id']}"] = True
                st.rerun()
            if btn[2].button("⬆️", key=f"u_{s['id']}", help="Prioridade Alta"):
                supabase.table('solicitacoes').update({"ordem_manual":int(datetime.now().timestamp())}).eq("id",s['id']).execute()
                st.rerun()
            if btn[3].button("⬇️", key=f"d_{s['id']}", help="Prioridade Baixa"):
                supabase.table('solicitacoes').update({"ordem_manual":int(datetime.now().timestamp())*-1}).eq("id",s['id']).execute()
                st.rerun()
            if btn[4].button("🗑️", key=f"del_{s['id']}", help="Excluir"):
                supabase.table('solicitacoes').delete().eq("id",s['id']).execute()
                st.rerun()

            if st.session_state.get(f"ed_{s['id']}", False):
                with st.expander(f"✏️ EDITAR OS - {s['maquinas']['nome']}", expanded=True):
                    with st.form(key=f"fo_{s['id']}"):
                        c_e1, c_e2, c_e3 = st.columns(3)
                        with c_e1:
                            opts_st = ["PENDENTE", "EM ANDAMENTO", "FINALIZADO"]
                            st_at = str(s.get('status', 'PENDENTE')).upper()
                            st_n = st.selectbox("Status", opts_st, index=opts_st.index(st_at) if st_at in opts_st else 0)
                            opts_pr = ["BAIXA", "MÉDIA", "ALTA", "URGENTE"]
                            pr_at = str(s.get('prioridade', 'BAIXA')).upper()
                            pr_n = st.selectbox("Prioridade", opts_pr, index=opts_pr.index(pr_at) if pr_at in opts_pr else 0)
                        
                        with c_e2:
                            d_i_val = date.fromisoformat(s['data_inicio']) if s.get('data_inicio') else None
                            d_i = st.date_input("Início", value=d_i_val)
                            
                            d_f_val = date.fromisoformat(s['data_fim']) if s.get('data_fim') else None
                            d_f = st.date_input("Fim", value=d_f_val)
                            
                        with c_e3:
                            mq_idx = next((i for i, m in enumerate(maquinas_raw) if m['id'] == s['maquina_id']), 0)
                            mq_n = st.selectbox("Máquina", [m['id'] for m in maquinas_raw], index=mq_idx, format_func=lambda x: next(m['nome'].upper() for m in maquinas_raw if m['id']==x))
                        
                        sol_n = st.text_input("Solicitante", value=s.get('solicitante_nome', ''))
                        ds_n = st.text_area("Descrição", value=s['descricao'])
                        
                        if st.form_submit_button("💾 SALVAR"):
                            # Lógica para tratar datas nulas no banco e garantir gravação
                            data_inicio_envio = d_i.isoformat() if d_i else None
                            data_fim_envio = d_f.isoformat() if d_f else None

                            update_data = {
                                "status": st_n,
                                "prioridade": pr_n,
                                "maquina_id": mq_n,
                                "descricao": ds_n,
                                "solicitante_nome": sol_n,
                                "data_inicio": data_inicio_envio,
                                "data_fim": data_fim_envio
                            }
                            
                            supabase.table('solicitacoes').update(update_data).eq("id", s['id']).execute()
                            st.session_state[f"ed_{s['id']}"] = False
                            st.success("OS Atualizada!")
                            st.rerun()

elif tela_selecionada == "⚙️ Cadastros":
    st.title("⚙️ Gerenciamento")
    t1, t2 = st.tabs(["🏗️ MÁQUINAS", "👤 USUÁRIOS"])
    
    with t1:
        with st.form("cad_maq"):
            n_m = st.text_input("Nome da Máquina:").upper()
            if st.form_submit_button("CADASTRAR MÁQUINA"):
                if n_m:
                    supabase_admin.table('maquinas').insert({"nome": n_m}).execute()
                    st.rerun()
        st.write("Atuais:")
        for m in maquinas_raw:
            c_m = st.columns([3,1])
            c_m[0].write(m['nome'])
            if c_m[1].button("Remover", key=f"rm_{m['id']}"):
                supabase_admin.table('maquinas').delete().eq("id", m['id']).execute()
                st.rerun()

    with t2:
        st.subheader("Cadastro de Usuários (Tabela Auxiliar)")
        st.info("Utilize este campo para registrar os nomes dos colaboradores na tabela 'perfis_simples'.")
        with st.form("cad_user_simples", clear_on_submit=True):
            nome_u = st.text_input("Nome Completo ou Apelido:").upper()
            nivel_u = st.selectbox("Nível de Acesso:", ["OPERADOR", "ADMIN", "MANUTENCAO"])
            
            if st.form_submit_button("CADASTRAR USUÁRIO"):
                if nome_u.strip():
                    try:
                        # Certifique-se de rodar o SQL de permissão no painel do Supabase
                        supabase_admin.table('perfis_simples').insert({
                            "nome": nome_u,
                            "nivel": nivel_u,
                            "data_cadastro": date.today().isoformat()
                        }).execute()
                        st.success(f"Usuário {nome_u} cadastrado com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao cadastrar: {e}")
                else:
                    st.error("O campo nome não pode estar vazio!")
