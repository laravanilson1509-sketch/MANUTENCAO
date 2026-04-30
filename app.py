import streamlit as st
import pandas as pd
from datetime import date, datetime
from io import BytesIO
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="INOVA FLEX - Gestão", layout="wide", page_icon="🔧")

# Inicialização de Session States
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_nickname' not in st.session_state:
    st.session_state.user_nickname = ""
if 'dados_f' not in st.session_state:
    st.session_state.dados_f = None
if 'f_key' not in st.session_state:
    st.session_state.f_key = 0
if 'tela_selecionada' not in st.session_state:
    st.session_state.tela_selecionada = "📋 Fila de Manutenção"

# Estilos CSS
st.markdown("""
<style>
    button[kind="primary"], button[kind="secondary"], button[kind="tertiary"] {
        display: flex !important; justify-content: center !important; align-items: center !important;
        padding: 0px !important; min-height: 35px !important;
    }
    [data-testid="column"] { display: flex !important; justify-content: center !important; align-items: center !important; }
    .p-urgente { color: #ff4b4b !important; font-weight: bold; border-left: 4px solid #ff4b4b; padding-left: 8px; background: rgba(255, 75, 75, 0.1); width: 100%; text-align: center; }
    .p-alta { color: #ffa500 !important; font-weight: bold; border-left: 4px solid #ffa500; padding-left: 8px; background: rgba(255, 165, 0, 0.1); width: 100%; text-align: center; }
    .p-media { color: #f1c40f !important; font-weight: bold; border-left: 4px solid #f1c40f; padding-left: 8px; background: rgba(241, 196, 15, 0.1); width: 100%; text-align: center; }
    .p-baixa { color: #2ecc71 !important; font-weight: bold; border-left: 4px solid #2ecc71; padding-left: 8px; background: rgba(46, 204, 113, 0.1); width: 100%; text-align: center; }
    .linha-divisoria { border-bottom: 2px solid #333; margin: 15px 0; width: 100%; }
</style>
""", unsafe_allow_html=True)

def formatar_data_br(data_str):
    if not data_str or data_str == "---": return "---"
    try: return datetime.strptime(data_str, '%Y-%m-%d').strftime('%d/%m/%y')
    except: return data_str

# --- 2. CONEXÃO ---
URL = st.secrets.get("SUPABASE_URL")
ANON = st.secrets.get("SUPABASE_ANON_KEY")
SERVICE = st.secrets.get("SUPABASE_SERVICE_KEY")

@st.cache_resource
def conectar_admin():
    return create_client(URL, SERVICE)

supabase_admin = conectar_admin()

# --- 3. LÓGICA DE LOGIN (CALLBACK PARA 1 CLIQUE) ---
def btn_login_callback():
    # Acessando diretamente do session_state para evitar erro de campos vazios
    u = st.session_state.get('login_user_input', '').strip()
    p = st.session_state.get('login_pass_input', '').strip()
    
    if not u or not p:
        st.error("Preencha todos os campos corretamente.")
        return
        
    try:
        u_limpo = u.lower()
        res = supabase_admin.auth.sign_in_with_password({"email": f"{u_limpo}@inovaflex.com", "password": p})
        
        if res.user:
            perfil = supabase_admin.table('perfis').select('nivel').eq('id', res.user.id).execute()
            if perfil.data:
                st.session_state.authenticated = True
                st.session_state.user_token = res.session.access_token
                st.session_state.user_id = res.user.id
                st.session_state.user_nickname = u_limpo.upper()
                st.session_state.user_level = perfil.data[0]['nivel']
            else:
                st.error("Perfil não encontrado no banco de dados.")
    except Exception as e:
        st.error("Usuário ou senha inválidos.")

# Tela de Login
if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align:center; color:#0052cc; margin-top:50px;'>INOVA FLEX</h2>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1,1,1])
    with col_l2:
        st.text_input("Usuário", key="login_user_input")
        st.text_input("Senha", type="password", key="login_pass_input")
        st.button("ENTRAR", use_container_width=True, on_click=btn_login_callback, type="primary")
    st.stop()

# --- ABAIXO SÓ EXECUTA SE AUTENTICADO ---
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

def carregar_usuarios_cadastrados():
    try:
        q = supabase_admin.table('perfis_simples').select('nome').order('nome').execute()
        return [u['nome'] for u in q.data] if q.data else []
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

# Carregamento dinâmico
maquinas_raw = carregar_listas()
usuarios_lista = carregar_usuarios_cadastrados()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.markdown("<div style='background: linear-gradient(135deg, #003366 0%, #0052cc 100%); padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px;'><h2 style='color: white; margin: 0; font-size: 1.5em;'>🔧 INOVA FLEX</h2></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='padding:10px; background:#1e1e1e; border-radius:10px; margin-bottom:15px; color:#007bff; font-weight:bold; text-align:center;'>👤 {st.session_state.user_nickname}</div>", unsafe_allow_html=True)
    
    if st.button("📋 Fila de Manutenção", use_container_width=True):
        st.session_state.tela_selecionada = "📋 Fila de Manutenção"
        st.rerun()
    if st.button("⚙️ Cadastros", use_container_width=True):
        st.session_state.tela_selecionada = "⚙️ Cadastros"
        st.rerun()
    
    st.divider()
    if st.button("🚪 SAIR", use_container_width=True):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

# --- 6. TELAS ---
if st.session_state.tela_selecionada == "📋 Fila de Manutenção":
    st.title("📋 Fila de Manutenção")
    
    with st.expander("➕ CRIAR NOVA ORDEM DE SERVIÇO"):
        with st.form("n_os", clear_on_submit=True):
            c_f1, c_f2, c_f3 = st.columns([1, 1, 1])
            mq = c_f1.selectbox("🛠️ Máquina:", ["SELECIONE..."] + [m['nome'].upper() for m in maquinas_raw])
            pr = c_f2.selectbox("🔥 Prioridade:", ["BAIXA", "MÉDIA", "ALTA", "URGENTE"])
            solicitante = c_f3.selectbox("👤 Solicitante:", ["SELECIONE..."] + usuarios_lista)
            
            ds = st.text_area("📝 Descrição do Problema:").upper()
            if st.form_submit_button("🚀 GERAR OS", type="primary"):
                if mq != "SELECIONE..." and solicitante != "SELECIONE..." and ds.strip():
                    mid = next(m['id'] for m in maquinas_raw if m['nome'].upper() == mq)
                    supabase.table('solicitacoes').insert({
                        "maquina_id": mid, 
                        "descricao": ds, 
                        "prioridade": pr, 
                        "solicitante_nome": solicitante, 
                        "status": "PENDENTE", 
                        "data_solicitacao": date.today().isoformat(), 
                        "criado_por_uuid": st.session_state.user_id, 
                        "ordem_manual": int(datetime.now().timestamp())
                    }).execute()
                    st.session_state.dados_f = None
                    st.success("✅ OS Criada!")
                    st.rerun()
                else:
                    st.error("Preencha todos os campos!")

    st.divider()
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([1.5, 1, 1, 1, 1])
        f_mq = c1.selectbox("🛠️ Máquina:", ["TODOS"] + [m['id'] for m in maquinas_raw], format_func=lambda x: next((m['nome'].upper() for m in maquinas_raw if m['id'] == x), "TODOS"), key=f"filt_mq_{st.session_state.f_key}")
        f_st = c2.selectbox("📊 Status:", ["TODOS", "PENDENTE", "EM ANDAMENTO"], key=f"filt_st_{st.session_state.f_key}")
        f_pr = c3.selectbox("🔥 Prioridade:", ["TODAS", "BAIXA", "MÉDIA", "ALTA", "URGENTE"], key=f"filt_pr_{st.session_state.f_key}")
        
        if c4.button("🔍 FILTRAR", type="primary", use_container_width=True):
            st.session_state.dados_f = carregar_solicitacoes(f_mq, st.session_state.user_level, st.session_state.user_id, f_st, f_pr)
            st.rerun()
        if c5.button("🧹 LIMPAR", use_container_width=True):
            st.session_state.f_key += 1
            st.session_state.dados_f = None
            st.rerun()

    if st.session_state.dados_f:
        header = st.columns([1.0, 1.0, 0.9, 1.0, 0.8, 0.8, 0.8, 1.5, 1.8])
        for col, t in zip(header, ["Solicitante", "Solicit.", "Máquina", "Status", "Prior.", "Início", "Fim", "Descrição", "Ações"]):
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
            if btn[0].button("🏁", key=f"fin_{s['id']}", help="Finalizar"):
                supabase.table('solicitacoes').update({"status":"FINALIZADO","data_fim":date.today().isoformat()}).eq("id",s['id']).execute()
                st.session_state.dados_f = None
                st.rerun()
            if btn[1].button("📝", key=f"edt_{s['id']}", help="Editar"):
                st.session_state[f"ed_{s['id']}"] = True
                st.rerun()
            if btn[2].button("⬆️", key=f"up_{s['id']}", help="Subir Fila"):
                supabase.table('solicitacoes').update({"ordem_manual":int(datetime.now().timestamp())}).eq("id",s['id']).execute()
                st.session_state.dados_f = None
                st.rerun()
            if btn[3].button("⬇️", key=f"down_{s['id']}", help="Descer Fila"):
                supabase.table('solicitacoes').update({"ordem_manual":int(datetime.now().timestamp()) * -1}).eq("id",s['id']).execute()
                st.session_state.dados_f = None
                st.rerun()
            if btn[4].button("🗑️", key=f"del_{s['id']}"):
                supabase.table('solicitacoes').delete().eq("id",s['id']).execute()
                st.session_state.dados_f = None
                st.rerun()

            if st.session_state.get(f"ed_{s['id']}", False):
                with st.expander(f"✏️ EDITANDO OS - {s['maquinas']['nome']}", expanded=True):
                    with st.form(key=f"form_ed_{s['id']}"):
                        c_e1, c_e2 = st.columns(2)
                        st_n = c_e1.selectbox("Status", ["PENDENTE", "EM ANDAMENTO", "FINALIZADO"], index=["PENDENTE", "EM ANDAMENTO", "FINALIZADO"].index(s['status']) if s['status'] in ["PENDENTE", "EM ANDAMENTO", "FINALIZADO"] else 0)
                        pr_n = c_e1.selectbox("Prioridade", ["BAIXA", "MÉDIA", "ALTA", "URGENTE"], index=["BAIXA", "MÉDIA", "ALTA", "URGENTE"].index(s['prioridade']) if s['prioridade'] in ["BAIXA", "MÉDIA", "ALTA", "URGENTE"] else 0)
                        
                        sol_atual = s.get('solicitante_nome', '')
                        idx_sol = usuarios_lista.index(sol_atual) if sol_atual in usuarios_lista else 0
                        sol_n = c_e1.selectbox("Solicitante", usuarios_lista, index=idx_sol)
                        
                        d_i = c_e2.date_input("Início", value=date.fromisoformat(s['data_inicio']) if s.get('data_inicio') else date.today())
                        d_f = c_e2.date_input("Fim", value=date.fromisoformat(s['data_fim']) if s.get('data_fim') else None)
                        ds_n = st.text_area("Descrição", value=s['descricao'])
                        
                        if st.form_submit_button("💾 SALVAR ALTERAÇÕES"):
                            supabase.table('solicitacoes').update({
                                "status":st_n, 
                                "prioridade":pr_n, 
                                "descricao":ds_n, 
                                "solicitante_nome": sol_n, 
                                "data_inicio":d_i.isoformat(), 
                                "data_fim":d_f.isoformat() if d_f else None
                            }).eq("id",s['id']).execute()
                            st.session_state[f"ed_{s['id']}"] = False
                            st.session_state.dados_f = None
                            st.success("Atualizado!")
                            st.rerun()

elif st.session_state.tela_selecionada == "⚙️ Cadastros":
    st.title("⚙️ Gerenciamento")
    t1, t2 = st.tabs(["🏗️ MÁQUINAS", "👤 USUÁRIOS"])
    
    with t1:
        with st.form("cad_maq"):
            n_m = st.text_input("Nome da Máquina:").upper()
            if st.form_submit_button("CADASTRAR MÁQUINA"):
                if n_m:
                    supabase_admin.table('maquinas').insert({"nome": n_m}).execute()
                    st.success("Máquina cadastrada!")
                    st.rerun()
        
        st.write("---")
        for m in maquinas_raw:
            c_m = st.columns([3,1])
            c_m[0].write(m['nome'])
            if c_m[1].button("Remover", key=f"rm_maq_{m['id']}"):
                supabase_admin.table('maquinas').delete().eq("id", m['id']).execute()
                st.rerun()

    with t2:
        with st.form("cad_user", clear_on_submit=True):
            nome_u = st.text_input("Nome do Colaborador:").upper()
            if st.form_submit_button("CADASTRAR USUÁRIO"):
                if nome_u:
                    supabase_admin.table('perfis_simples').insert({
                        "nome": nome_u, 
                        "nivel": "OPERADOR", 
                        "data_cadastro": date.today().isoformat()
                    }).execute()
                    st.success(f"Usuário {nome_u} cadastrado!")
                    st.rerun()
        
        st.write("---")
        for u in usuarios_lista:
            c_u = st.columns([3,1])
            c_u[0].write(u)
            if c_u[1].button("Remover", key=f"rm_user_{u}"):
                supabase_admin.table('perfis_simples').delete().eq("nome", u).execute()
                st.rerun()
