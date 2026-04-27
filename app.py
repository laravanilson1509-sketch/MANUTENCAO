import streamlit as st
import pandas as pd
from datetime import date, datetime
from io import BytesIO
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="INOVAFLEX - Gestão", layout="wide", page_icon="🔧")

st.markdown("""
    <style>
    [data-testid="column"] { min-width: 95px !important; white-space: nowrap !important; }
    .main .block-container { padding-left: 1rem; padding-right: 1rem; }
    .login-container { 
        max-width: 400px; margin: 50px auto; padding: 30px; 
        border-radius: 15px; background-color: #1e1e1e; border: 1px solid #333; 
    }
    .stButton>button { width: 100% !important; font-weight: bold !important; }
    div[data-testid="stForm"] .stButton>button { background-color: #ff5e00 !important; color: white !important; }
    
    .p-urgente { color: #ff4b4b !important; font-weight: bold; border-left: 4px solid #ff4b4b; padding-left: 5px; }
    .p-alta { color: #ffa500 !important; font-weight: bold; border-left: 4px solid #ffa500; padding-left: 5px; }
    .p-media { color: #f1c40f !important; font-weight: bold; border-left: 4px solid #f1c40f; padding-left: 5px; }
    .p-baixa { color: #2ecc71 !important; font-weight: bold; border-left: 4px solid #2ecc71; padding-left: 5px; }
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

# --- 3. LOGIN ---
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

def realizar_login(usuario, password):
    try:
        u_limpo = usuario.strip().lower()
        email_fake = f"{u_limpo}@inovaflex.com"
        res = supabase_admin.auth.sign_in_with_password({"email": email_fake, "password": password.strip()})
        if res.user:
            perfil = supabase_admin.table('perfis').select('nivel').eq('id', res.user.id).execute()
            if perfil.data:
                st.session_state['authenticated'] = True
                st.session_state['user_token'] = res.session.access_token
                st.session_state['user_id'] = res.user.id
                st.session_state['user_nickname'] = u_limpo
                st.session_state['user_level'] = perfil.data[0]['nivel']
                st.rerun()
    except Exception:
        st.error(f"Erro: Usuário ou senha inválidos.")

if not st.session_state['authenticated']:
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown("<h2 style='text-align:center; color:#ff5e00;'>INOVAFLEX</h2>", unsafe_allow_html=True)
    with st.form("login_form"):
        u_input = st.text_input("Usuário")
        p_input = st.text_input("Senha", type="password")
        if st.form_submit_button("ENTRAR"):
            realizar_login(u_input, p_input)
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

try:
    opts = ClientOptions(headers={"Authorization": f"Bearer {st.session_state['user_token']}"})
    supabase = create_client(URL, ANON, options=opts)
except:
    supabase = supabase_admin

# --- 4. FUNÇÕES ---
def carregar_listas():
    try:
        q = supabase.table('maquinas').select('id, nome').order('nome').execute()
        return q.data if q.data else []
    except: return []

def carregar_solicitacoes(maquina_id, nivel, uid, f_status=None, f_prioridade=None):
    try:
        query = supabase.table('solicitacoes').select('*, maquinas(nome)')
        if nivel == 'operador': query = query.eq('criado_por_uuid', uid)
        if maquina_id and maquina_id != "Todas": query = query.eq('maquina_id', maquina_id)
        if f_status and f_status != "Todos": query = query.eq('status', f_status)
        if f_prioridade and f_prioridade != "Todas": query = query.eq('prioridade', f_prioridade)
        return query.order('ordem_manual', desc=True).execute().data
    except: return []

@st.cache_data(show_spinner=False)
def gerar_excel_cache(dados):
    if not dados: return None
    df = pd.DataFrame(dados)
    if 'maquinas' in df.columns:
        df['Máquina'] = df['maquinas'].apply(lambda x: x['nome'] if x else '---')
    out = BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
        cols = ['data_solicitacao','Máquina','status','prioridade','descricao','data_inicio','data_fim']
        df[[c for c in cols if c in df.columns]].to_excel(wr, index=False)
    return out.getvalue()

# --- 5. INTERFACE (SIDEBAR) ---
maquinas_raw = carregar_listas()
nivel_atual = st.session_state.get('user_level', 'operador')
e_admin = nivel_atual == 'admin'
e_mecanico = nivel_atual == 'mecanico' or e_admin

with st.sidebar:
    st.markdown("### ⚙️ Configurações")
    st.write(f"Usuário: **{st.session_state['user_nickname']}**")
    if st.button("🚪 Sair"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

    if 'dados_atuais' in st.session_state and st.session_state.dados_atuais:
        st.divider()
        st.write("📊 Exportar Dados")
        excel_bin = gerar_excel_cache(st.session_state.dados_atuais)
        st.download_button("📥 Baixar Relatório", excel_bin, "relatorio.xlsx", use_container_width=True)

    st.divider()
    with st.expander("🔑 Alterar Minha Senha"):
        with st.form("alt_pass"):
            nova_p = st.text_input("Nova Senha", type="password")
            if st.form_submit_button("Atualizar"):
                if len(nova_p) >= 6:
                    supabase.auth.update_user({"password": nova_p})
                    st.success("Senha alterada!")
                else: st.error("Mínimo 6 caracteres.")
    
    if e_admin:
        with st.expander("👤 Cadastrar Funcionário"):
            with st.form("cad_user", clear_on_submit=True):
                nu = st.text_input("Nome")
                ns = st.text_input("Senha", type="password")
                nl = st.selectbox("Perfil", ["operador", "mecanico", "admin"])
                if st.form_submit_button("Criar"):
                    try:
                        em = f"{nu.strip().lower()}@inovaflex.com"
                        u_a = supabase_admin.auth.admin.create_user({
                            "email": em, 
                            "password": ns, 
                            "email_confirm": True
                        })
                        supabase_admin.table('perfis').insert({
                            "id": u_a.user.id, 
                            "email": em, 
                            "nivel": nl
                        }).execute()
                        st.success(f"Funcionário {nu} criado!")
                    except Exception as e:
                        st.error(f"Erro ao criar: {e}")

    with st.expander("🏭 Cadastro de Máquinas"):
        if e_mecanico:
            nm = st.text_input("Nova Máquina")
            if st.button("Adicionar") and nm:
                supabase.table('maquinas').insert({"nome": nm}).execute(); st.rerun()
        st.write("---")
        for q in maquinas_raw:
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.caption(f"📍 {q['nome']}")
            if e_mecanico and c2.button("📝", key=f"ed_mq_{q['id']}"):
                st.session_state[f"edit_mode_mq_{q['id']}"] = True
            if e_mecanico and c3.button("🗑️", key=f"mq_{q['id']}"):
                check = supabase.table('solicitacoes').select('id', count='exact').eq('maquina_id', q['id']).execute()
                if check.count > 0:
                    st.error(f"Não é possível excluir. A máquina '{q['nome']}' possui registros.")
                else:
                    supabase.table('maquinas').delete().eq("id", q['id']).execute(); st.rerun()
            if st.session_state.get(f"edit_mode_mq_{q['id']}", False):
                with st.form(f"f_ed_mq_{q['id']}"):
                    novo_nome = st.text_input("Novo nome:", value=q['nome'])
                    if st.form_submit_button("Salvar"):
                        supabase.table('maquinas').update({"nome": novo_nome}).eq("id", q['id']).execute()
                        st.session_state[f"edit_mode_mq_{q['id']}"] = False
                        st.rerun()

# --- 6. PLANO DE MANUTENÇÃO ---
st.header("🔧 Plano de Manutenção")

if 'os_form_key' not in st.session_state: st.session_state.os_form_key = 0
with st.expander("📝 ABRIR NOVA ORDEM DE SERVIÇO"):
    with st.form(key=f"nova_os_{st.session_state.os_form_key}"):
        c1, c2 = st.columns(2)
        mq = c1.selectbox("Máquina", ["Selecione..."] + [m['nome'] for m in maquinas_raw])
        pr = c2.selectbox("Prioridade", ["Baixa", "Média", "Alta", "Urgente"])
        ds = st.text_area("Descrição da Solicitação", value="")
        if st.form_submit_button("GERAR ORDEM DE SERVIÇO"):
            if mq != "Selecione..." and ds:
                mid = next(m['id'] for m in maquinas_raw if m['nome'] == mq)
                supabase.table('solicitacoes').insert({
                    "maquina_id": mid, "descricao": ds, "prioridade": pr, "status": "Pendente",
                    "data_solicitacao": date.today().isoformat(), "criado_por_uuid": st.session_state['user_id'],
                    "ordem_manual": int(datetime.now().timestamp())
                }).execute()
                st.session_state.os_form_key += 1
                st.rerun()

# --- 7. FILA DE MANUTENÇÃO ---
st.divider()
st.subheader("📋 Fila de Manutenção")

if 'f_reset' not in st.session_state: st.session_state.f_reset = 0
op_filt = [{"id": "", "nome": "Selecione uma máquina..."}] + [{"id": "Todas", "nome": "TODAS AS MÁQUINAS"}] + maquinas_raw

with st.container(border=True):
    c_f1, c_f2, c_f3, c_f4, c_f5 = st.columns([2, 1, 1, 1, 1])
    with c_f1:
        f_id = st.selectbox("Máquina:", [o['id'] for o in op_filt], format_func=lambda x: next(o['nome'] for o in op_filt if o['id'] == x), key=f"f_mq_{st.session_state.f_reset}")
    with c_f2:
        f_st = st.selectbox("Status:", ["Todos", "Pendente", "Em andamento", "Finalizado"], key=f"f_st_{st.session_state.f_reset}")
    with c_f3:
        f_pr = st.selectbox("Prioridade:", ["Todas", "Baixa", "Média", "Alta", "Urgente"], key=f"f_pr_{st.session_state.f_reset}")
    with c_f4:
        st.write("")
        btn_filtrar = st.button("🔍 FILTRAR", type="primary")
    with c_f5:
        st.write("")
        if st.button("🧹 Limpar"):
            st.session_state.f_reset += 1
            st.session_state.dados_atuais = []
            st.rerun()

if btn_filtrar or (f_id != "" and 'dados_atuais' in st.session_state):
    if f_id == "":
        st.warning("Selecione pelo menos uma máquina ou 'Todas' para filtrar.")
    else:
        lista = carregar_solicitacoes(f_id, nivel_atual, st.session_state['user_id'], f_st, f_pr)
        st.session_state.dados_atuais = lista
        
        if lista:
            header = st.columns([0.8, 1.2, 1.0, 1.0, 0.9, 0.8, 1.6, 2.2])
            titulos = ["Data","Máquina","Status","Prioridade","Início","Fim","Solicitação","Ações"]
            for col, t in zip(header, titulos): col.markdown(f"**{t}**")
            
            for i, s in enumerate(lista):
                r = st.columns([0.8, 1.2, 1.0, 1.0, 0.9, 0.8, 1.6, 2.2])
                r[0].write(formatar_data_br(s['data_solicitacao']))
                r[1].write(f"**{s['maquinas']['nome']}**")
                r[2].write(s['status'])
                
                p = s['prioridade']
                if p == "Urgente": r[3].markdown(f'<div class="p-urgente">🔴 {p}</div>', unsafe_allow_html=True)
                elif p == "Alta": r[3].markdown(f'<div class="p-alta">🟠 {p}</div>', unsafe_allow_html=True)
                elif p == "Média": r[3].markdown(f'<div class="p-media">🟡 {p}</div>', unsafe_allow_html=True)
                else: r[3].markdown(f'<div class="p-baixa">🟢 {p}</div>', unsafe_allow_html=True)
                
                r[4].write(formatar_data_br(s.get('data_inicio')))
                r[5].write(formatar_data_br(s.get('data_fim')))
                r[6].caption(s['descricao'])
                
                b = r[7].columns(5)
                if e_mecanico:
                    if b[0].button("🏁", key=f"f{s['id']}", help="Finalizar"):
                        supabase.table('solicitacoes').update({"status":"Finalizado","data_fim":date.today().isoformat()}).eq("id",s['id']).execute(); st.rerun()
                    if b[1].button("📝", key=f"e{s['id']}", help="Editar"): st.session_state[f"ed{s['id']}"] = True
                    
                    ov = s.get('ordem_manual', 0)
                    if b[2].button("🔼", key=f"u{s['id']}"):
                        if i > 0:
                            outro = lista[i-1]
                            supabase.table('solicitacoes').update({"ordem_manual": outro['ordem_manual']}).eq("id", s['id']).execute()
                            supabase.table('solicitacoes').update({"ordem_manual": ov}).eq("id", outro['id']).execute()
                            st.rerun()
                    if b[3].button("🔽", key=f"d{s['id']}"):
                        if i < len(lista) - 1:
                            outro = lista[i+1]
                            supabase.table('solicitacoes').update({"ordem_manual": outro['ordem_manual']}).eq("id", s['id']).execute()
                            supabase.table('solicitacoes').update({"ordem_manual": ov}).eq("id", outro['id']).execute()
                            st.rerun()
                if e_admin and b[4].button("🗑️", key=f"x{s['id']}"):
                    supabase.table('solicitacoes').delete().eq("id", s['id']).execute(); st.rerun()

                if st.session_state.get(f"ed{s['id']}", False):
                    with st.container(border=True):
                        with st.form(f"ed_{s['id']}"):
                            st.subheader(f"Editar OS: {s['maquinas']['nome']}")
                            e1, e2 = st.columns(2)
                            st_at = e1.selectbox("Status", ["Pendente", "Em andamento", "Finalizado"], index=["Pendente", "Em andamento", "Finalizado"].index(s['status']))
                            pr_at = e2.selectbox("Prioridade", ["Baixa", "Média", "Alta", "Urgente"], index=["Baixa", "Média", "Alta", "Urgente"].index(s['prioridade']))
                            d1, d2 = st.columns(2)
                            ini_v = datetime.strptime(s['data_inicio'], '%Y-%m-%d').date() if s.get('data_inicio') else None
                            fim_v = datetime.strptime(s['data_fim'], '%Y-%m-%d').date() if s.get('data_fim') else None
                            n_ini = d1.date_input("Início", value=ini_v)
                            n_fim = d2.date_input("Fim", value=fim_v)
                            st.info(f"Histórico: {s['descricao']}")
                            ds_add = st.text_area("Nova Observação")
                            if st.form_submit_button("SALVAR"):
                                desc_final = s['descricao']
                                if ds_add.strip(): desc_final += f"\n\n**[{date.today().strftime('%d/%m/%y')}]:** {ds_add.strip()}"
                                upd = {"status": st_at, "prioridade": pr_at, "descricao": desc_final}
                                if n_ini: upd["data_inicio"] = n_ini.isoformat()
                                if n_fim: upd["data_fim"] = n_fim.isoformat()
                                supabase.table('solicitacoes').update(upd).eq("id", s['id']).execute()
                                st.session_state[f"ed{s['id']}"] = False
                                st.rerun()
                        if st.button("CANCELAR", key=f"can_{s['id']}"):
                            st.session_state[f"ed{s['id']}"] = False
                            st.rerun()
        else:
            st.info("Nenhum registro encontrado para os filtros selecionados.")
elif f_id == "":
    st.info("💡 Selecione os filtros acima e clique em 'FILTRAR' para carregar a fila de manutenção.")
