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

# --- 4. FUNÇÕES DE DADOS ---
def carregar_listas():
    try:
        q = supabase.table('maquinas').select('id, nome').order('nome').execute()
        return q.data if q.data else []
    except: return []

def carregar_pecas():
    try:
        q = supabase.table('pecas').select('*').order('descricao').execute()
        return q.data if q.data else []
    except: return []

def carregar_solicitacoes(maquina_id, nivel, uid, f_status="Todos", f_prioridade="Todas"):
    try:
        query = supabase.table('solicitacoes').select('*, maquinas(nome)')
        if nivel == 'operador': query = query.eq('criado_por_uuid', uid)
        if maquina_id and maquina_id != "Todas": query = query.eq('maquina_id', maquina_id)
        if f_status != "Todos": query = query.eq('status', f_status)
        if f_prioridade != "Todas": query = query.eq('prioridade', f_prioridade)
        return query.order('ordem_manual', desc=True).execute().data
    except: return []

def baixar_estoque_por_id(lista_ids):
    for pid in lista_ids:
        res = supabase.table('pecas').select('quantidade, empenho').eq('id', pid).execute()
        if res.data:
            qtd_atual = res.data[0]['quantidade']
            emp_atual = res.data[0]['empenho']
            nova_qtd = max(0, qtd_atual - 1)
            supabase.table('pecas').update({
                'quantidade': nova_qtd,
                'saldo': nova_qtd - emp_atual
            }).eq('id', pid).execute()

# --- 5. SIDEBAR ---
maquinas_raw = carregar_listas()
pecas_raw = carregar_pecas()
nivel_atual = st.session_state.get('user_level', 'operador')
e_admin = nivel_atual == 'admin'
e_mecanico = nivel_atual == 'mecanico' or e_admin

with st.sidebar:
    st.header("🚀 MENU")
    tela_selecionada = st.selectbox(
        "Navegar para:", 
        ["📋 Fila de Manutenção", "📦 Estoque de Peças", "⚙️ Painel Admin"]
    )
    st.divider()
    st.write(f"Usuário: **{st.session_state['user_nickname']}**")
    if st.button("🚪 Sair"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

# --- 6. RENDERIZAÇÃO DA FILA ---
def renderizar_tabela_os(dados_os):
    if not dados_os:
        st.info("Use os filtros acima e clique em 'APLICAR FILTROS'.")
        return
    
    header = st.columns([0.6, 1.0, 0.8, 0.8, 0.8, 0.8, 1.4, 1.2, 2.0])
    titulos = ["ID OS", "Máquina", "Status", "Prior.", "Início", "Fim", "Solicitação", "Peças", "Ações"]
    for col, t in zip(header, titulos): col.markdown(f"**{t}**")
    
    for i, s in enumerate(dados_os):
        r = st.columns([0.6, 1.0, 0.8, 0.8, 0.8, 0.8, 1.4, 1.2, 2.0])
        r[0].write(f"#{s['id']}")
        r[1].write(f"**{s['maquinas']['nome']}**")
        r[2].write(s['status'])
        
        p = s['prioridade']
        if p == "Urgente": r[3].markdown(f'<div class="p-urgente">{p}</div>', unsafe_allow_html=True)
        elif p == "Alta": r[3].markdown(f'<div class="p-alta">{p}</div>', unsafe_allow_html=True)
        elif p == "Média": r[3].markdown(f'<div class="p-media">{p}</div>', unsafe_allow_html=True)
        else: r[3].markdown(f'<div class="p-baixa">{p}</div>', unsafe_allow_html=True)
        
        r[4].write(formatar_data_br(s.get('data_inicio')))
        r[5].write(formatar_data_br(s.get('data_fim')))
        r[6].caption(s['descricao'])
        r[7].write(s.get('pecas_solicitadas') if s.get('pecas_solicitadas') else "---")
        
        b = r[8].columns(5)
        if e_mecanico:
            if s['status'] != "Finalizado" and b[0].button("🏁", key=f"f{s['id']}"):
                supabase.table('solicitacoes').update({"status":"Finalizado","data_fim":date.today().isoformat()}).eq("id",s['id']).execute(); st.rerun()
            
            if b[1].button("📝", key=f"e{s['id']}"): st.session_state[f"ed{s['id']}"] = True
            
            ov = s.get('ordem_manual', 0)
            if b[2].button("🔼", key=f"u{s['id']}"):
                if i > 0:
                    outro = dados_os[i-1]
                    supabase.table('solicitacoes').update({"ordem_manual": outro['ordem_manual']}).eq("id", s['id']).execute()
                    supabase.table('solicitacoes').update({"ordem_manual": ov}).eq("id", outro['id']).execute(); st.rerun()
            if b[3].button("🔽", key=f"d{s['id']}"):
                if i < len(dados_os) - 1:
                    outro = dados_os[i+1]
                    supabase.table('solicitacoes').update({"ordem_manual": outro['ordem_manual']}).eq("id", s['id']).execute()
                    supabase.table('solicitacoes').update({"ordem_manual": ov}).eq("id", outro['id']).execute(); st.rerun()
        
        if e_admin and b[4].button("🗑️", key=f"x{s['id']}"):
            supabase.table('solicitacoes').delete().eq("id", s['id']).execute(); st.rerun()

        if st.session_state.get(f"ed{s['id']}", False):
            with st.container(border=True):
                with st.form(f"f_ed_{s['id']}"):
                    st.subheader(f"✏️ Editar OS #{s['id']}")
                    c1, c2 = st.columns(2)
                    st_at = c1.selectbox("Status", ["Pendente", "Em andamento", "Finalizado"], index=["Pendente", "Em andamento", "Finalizado"].index(s['status']))
                    pr_at = c2.selectbox("Prioridade", ["Baixa", "Média", "Alta", "Urgente"], index=["Baixa", "Média", "Alta", "Urgente"].index(s['prioridade']))
                    
                    d1, d2 = st.columns(2)
                    # DATAS INICIAM COMO NONE SE NÃO EXISTIREM NO BANCO
                    val_ini = datetime.strptime(s['data_inicio'], '%Y-%m-%d').date() if s.get('data_inicio') else None
                    val_fim = datetime.strptime(s['data_fim'], '%Y-%m-%d').date() if s.get('data_fim') else None
                    
                    new_ini = d1.date_input("Data Início", value=val_ini)
                    new_fim = d2.date_input("Data Fim", value=val_fim)
                    
                    st.divider()
                    st.write("⚙️ **Baixa de Estoque por ID**")
                    op_pecas = {f"{p['produto']} - {p['descricao']} (Saldo: {p['saldo']})": p['id'] for p in pecas_raw}
                    pecas_sel = st.multiselect("Vincular Peças:", list(op_pecas.keys()))
                    p_txt = st.text_input("Observação Manual de Peças", value=s.get('pecas_solicitadas', ''))
                    
                    ds_add = st.text_area("Nova Observação")
                    if st.form_submit_button("SALVAR"):
                        # Processa a lista de IDs para baixar estoque
                        baixar_estoque_por_id([op_pecas[n] for n in pecas_sel])
                        
                        desc_f = s['descricao']
                        if ds_add.strip(): desc_f += f"\n\n**[{date.today().strftime('%d/%m/%y')}]:** {ds_add.strip()}"
                        
                        pecas_f = f"{', '.join(pecas_sel)} | {p_txt}" if pecas_sel else p_txt
                        upd = {
                            "status": st_at, "prioridade": pr_at, "descricao": desc_f, 
                            "pecas_solicitadas": pecas_f,
                            "data_inicio": new_ini.isoformat() if new_ini else None,
                            "data_fim": new_fim.isoformat() if new_fim else None
                        }
                        supabase.table('solicitacoes').update(upd).eq("id", s['id']).execute()
                        st.session_state[f"ed{s['id']}"] = False
                        st.rerun()
                if st.button("CANCELAR", key=f"can_{s['id']}"):
                    st.session_state[f"ed{s['id']}"] = False
                    st.rerun()

# --- 7. TELAS ---

if tela_selecionada == "📋 Fila de Manutenção":
    st.title("📋 Fila de Manutenção")
    
    with st.expander("➕ ABRIR NOVA ORDEM DE SERVIÇO"):
        with st.form("n_os"):
            mq = st.selectbox("Máquina", ["Selecione..."] + [m['nome'] for m in maquinas_raw])
            pr = st.selectbox("Prioridade", ["Baixa", "Média", "Alta", "Urgente"])
            ds = st.text_area("Descrição do Problema")
            if st.form_submit_button("GERAR"):
                if mq != "Selecione..." and ds:
                    mid = next(m['id'] for m in maquinas_raw if m['nome'] == mq)
                    supabase.table('solicitacoes').insert({
                        "maquina_id": mid, "descricao": ds, "prioridade": pr, "status": "Pendente",
                        "data_solicitacao": date.today().isoformat(), "criado_por_uuid": st.session_state['user_id'],
                        "ordem_manual": int(datetime.now().timestamp())
                    }).execute(); st.rerun()

    st.divider()
    
    # CONTROLE DE FILTROS COM KEY DINÂMICO PARA LIMPEZA
    if 'filtro_key' not in st.session_state: st.session_state.filtro_key = 0
    if 'dados_filtrados' not in st.session_state: st.session_state.dados_filtrados = None

    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([1.5, 1, 1, 1, 1])
        f_maq = c1.selectbox("Máquina:", ["Todas"] + [m['id'] for m in maquinas_raw], format_func=lambda x: next((m['nome'] for m in maquinas_raw if m['id'] == x), "Todas"), key=f"maq_{st.session_state.filtro_key}")
        f_st = c2.selectbox("Status:", ["Todos", "Pendente", "Em andamento", "Finalizado"], key=f"st_{st.session_state.filtro_key}")
        f_pr = c3.selectbox("Prioridade:", ["Todas", "Baixa", "Média", "Alta", "Urgente"], key=f"pr_{st.session_state.filtro_key}")
        
        st.write("")
        if c4.button("🔍 APLICAR FILTROS", type="primary", use_container_width=True):
            st.session_state.dados_filtrados = carregar_solicitacoes(f_maq, nivel_atual, st.session_state['user_id'], f_st, f_pr)
        
        if c5.button("🧹 LIMPAR", use_container_width=True):
            st.session_state.filtro_key += 1 # Muda a key e reseta os widgets
            st.session_state.dados_filtrados = None # Apaga os resultados da tela
            st.rerun()

    renderizar_tabela_os(st.session_state.dados_filtrados)

elif tela_selecionada == "📦 Estoque de Peças":
    st.title("📦  Estoque")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("📤 Upload via Excel")
        arq = st.file_uploader("Selecione o arquivo .xlsx", type=["xlsx"])
        if arq and st.button("CONFIRMAR IMPORTAÇÃO"):
            df = pd.read_excel(arq)
            for _, r in df.iterrows():
                supabase.table('pecas').insert({"produto": str(r['Produto']), "descricao": str(r['Descrição']), "quantidade": int(r['Qtde.']), "empenho": int(r['Empenho']), "saldo": int(r['Saldo'])}).execute()
            st.success("Estoque Atualizado!"); st.rerun()
    with c2:
        st.subheader("🆕 Cadastro Manual")
        with st.form("man"):
            p_p = st.text_input("Produto")
            p_d = st.text_input("Descrição")
            p_q = st.number_input("Qtde", min_value=0)
            p_e = st.number_input("Empenho", min_value=0)
            if st.form_submit_button("SALVAR PEÇA"):
                supabase.table('pecas').insert({"produto": p_p, "descricao": p_d, "quantidade": p_q, "empenho": p_e, "saldo": p_q - p_e}).execute(); st.rerun()

    st.divider()
    if pecas_raw:
        df_p = pd.DataFrame(pecas_raw)[['id', 'produto', 'descricao', 'quantidade', 'empenho', 'saldo']]
        df_p.columns = ['ID', 'Produto', 'Descrição', 'Qtde.', 'Empenho', 'Saldo']
        st.dataframe(df_p, use_container_width=True, hide_index=True)

elif tela_selecionada == "⚙️ Painel Admin":
    st.title("⚙️ Administração")
    if e_admin:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Máquinas")
            nm = st.text_input("Nome da Nova Máquina")
            if st.button("Adicionar"):
                supabase.table('maquinas').insert({"nome": nm}).execute(); st.rerun()
            for m in maquinas_raw: st.caption(f"ID {m['id']} - {m['nome']}")
        with c2:
            st.subheader("Usuários")
            with st.form("u_a"):
                un = st.text_input("Usuário")
                us = st.text_input("Senha", type="password")
                up = st.selectbox("Perfil", ["operador", "mecanico", "admin"])
                if st.form_submit_button("Criar Conta"):
                    try:
                        em = f"{un.strip().lower()}@inovaflex.com"
                        u = supabase_admin.auth.admin.create_user({"email": em, "password": us, "email_confirm": True})
                        supabase_admin.table('perfis').insert({"id": u.user.id, "email": em, "nivel": up}).execute()
                        st.success("Usuário criado com sucesso!")
                    except Exception as e: st.error(e)
    else: st.error("Acesso restrito.")
