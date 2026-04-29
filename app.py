import streamlit as st
import pandas as pd
from datetime import date, datetime
from io import BytesIO
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
import re

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="INOVAFLEX - Gestão", layout="wide", page_icon="🔧")

# Inicialização Global de Session States
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'dados_f' not in st.session_state: st.session_state.dados_f = None
if 'f_key' not in st.session_state: st.session_state.f_key = 0
if 't_p' not in st.session_state: st.session_state.t_p = ""
if 'fam_p' not in st.session_state: st.session_state.fam_p = "Todas"
if 'l_mq' not in st.session_state: st.session_state.l_mq = "TODOS"
if 'l_st' not in st.session_state: st.session_state.l_st = "TODOS"
if 'l_pr' not in st.session_state: st.session_state.l_pr = "TODAS"
if 'tela_selecionada' not in st.session_state: st.session_state.tela_selecionada = "📋 Fila de Manutenção"

st.markdown("""<style> 
    [data-testid="column"] { min-width: 95px !important; white-space: nowrap !important; } 
    .main .block-container { padding-left: 1rem; padding-right: 1rem; } 
    .login-container { max-width: 400px; margin: 50px auto; padding: 30px; border-radius: 15px; background-color: #1e1e1e; border: 1px solid #333; } 
    .stButton>button { width: 100% !important; font-weight: bold !important; } 
    div[data-testid="stForm"] .stButton>button { background-color: #ff5e00 !important; color: white !important; } 
    
    /* Estilização das Prioridades */
    .p-urgente { color: #ff4b4b !important; font-weight: bold; border-left: 4px solid #ff4b4b; padding-left: 8px; background: rgba(255, 75, 75, 0.1); } 
    .p-alta { color: #ffa500 !important; font-weight: bold; border-left: 4px solid #ffa500; padding-left: 8px; background: rgba(255, 165, 0, 0.1); } 
    .p-media { color: #f1c40f !important; font-weight: bold; border-left: 4px solid #f1c40f; padding-left: 8px; background: rgba(241, 196, 15, 0.1); } 
    .p-baixa { color: #2ecc71 !important; font-weight: bold; border-left: 4px solid #2ecc71; padding-left: 8px; background: rgba(46, 204, 113, 0.1); } 
    
    .linha-divisoria { border-bottom: 2px solid #333; margin: 15px 0; width: 100%; }
    .menu-item { padding: 8px 0; border-radius: 8px; margin: 2px 0; transition: all 0.3s; }
    .menu-item:hover { background-color: #ff5e00 !important; color: white !important; }
</style>""", unsafe_allow_html=True)

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

def carregar_familias():
    try:
        q = supabase_admin.table('familias_produtos').select('nome').order('nome').execute()
        return [f['nome'] for f in q.data] if q.data else []
    except: return []

def carregar_pecas_estoque(apenas_ativos=True, termo_busca="", familia_sel="Todas"):
    try:
        query = supabase_admin.table('pecas').select('*')
        if apenas_ativos: query = query.eq('ativo', True)
        if familia_sel != "Todas": query = query.eq('familia', familia_sel)
        if termo_busca: 
            query = query.or_(f"descricao.ilike.%{termo_busca}%,produto.ilike.%{termo_busca}%")
        q = query.order('descricao').execute()
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
    pecas_estoque = carregar_pecas_estoque(apenas_ativos=False)
    df_os = pd.DataFrame(dados_os)
    if not df_os.empty:
        df_os['data_solicitacao'] = pd.to_datetime(df_os['data_solicitacao'], errors='coerce').dt.strftime('%d/%m/%Y')
        df_os['data_inicio'] = df_os['data_inicio'].apply(formatar_data_br)
        df_os['data_fim'] = df_os['data_fim'].apply(formatar_data_br)
        df_os = df_os[['id', 'maquinas', 'status', 'prioridade', 'data_solicitacao', 'data_inicio', 'data_fim', 'descricao']]
        df_os.columns = ['ID OS', 'Máquina', 'Status', 'Prioridade', 'Data Solicitação', 'Início', 'Fim', 'Descrição']
        df_os['Máquina'] = df_os['Máquina'].apply(lambda x: x['nome'] if isinstance(x, dict) else x)

    df_estoque = pd.DataFrame(pecas_estoque)
    if not df_estoque.empty:
        df_estoque = df_estoque[['id', 'produto', 'descricao', 'familia', 'quantidade', 'empenho', 'saldo', 'ativo']]
        df_estoque.columns = ['ID', 'Produto', 'Descrição', 'Família', 'Quantidade', 'Empenho', 'Saldo', 'Ativo']

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df_os.empty: df_os.to_excel(writer, sheet_name='Ordens_Servico', index=False)
        if not df_estoque.empty: df_estoque.to_excel(writer, sheet_name='Estoque_Pecas', index=False)
    output.seek(0)
    return output.getvalue()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.markdown("""
    <div style='background: linear-gradient(135deg, #ff5e00 0%, #ff8c00 100%); padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px;'>
        <h2 style='color: white; margin: 0; font-size: 1.5em;'>🔧 INOVAFLEX</h2>
        <p style='color: rgba(255,255,255,0.9); margin: 5px 0 0 0;'>Gestão de Manutenção</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div style="padding: 10px; border-radius: 10px; background-color: #1e1e1e; margin-bottom: 15px;">', unsafe_allow_html=True)
    col1, col2 = st.columns([3,1])
    with col1:
        st.markdown(f"<div class='menu-item' style='font-size: 1.1em; font-weight: bold; color: #ff5e00;'>👤 {st.session_state['user_nickname']}</div>", unsafe_allow_html=True)
    with col2:
        if st.button("🚪", key="sair_btn"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    menu_options = {"📋 Fila de Manutenção": "Gerenciar Ordens de Serviço", "📦 Estoque de Peças": "Consultar e ajustar estoque", "⚙️ Cadastros": "Cadastros e configurações"}
    for key, desc in menu_options.items():
        if st.button(key, key=f"menu_{key}", help=desc):
            st.session_state.tela_selecionada = key
            st.rerun()
    
    st.divider()
    if st.button("📊 **BAIXAR RELATÓRIO COMPLETO**", type="primary"):
        relatorio = gerar_relatorio_completo()
        st.download_button(label="⬇️ DOWNLOAD RELATÓRIO", data=relatorio, file_name=f"Inovaflex_Relatorio_{date.today().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

tela_selecionada = st.session_state.tela_selecionada
maquinas_raw = carregar_listas()
familias_raw = carregar_familias()

# --- 7. TELAS ---

# TELA 1: FILA DE MANUTENÇÃO
if tela_selecionada == "📋 Fila de Manutenção":
    st.title("📋 Fila de Manutenção")
    
    with st.expander("➕ ➕ CRIAR NOVA ORDEM DE SERVIÇO ➕ ➕", expanded=False):
        with st.form("n_os", clear_on_submit=True):
            col_mq, col_pr = st.columns(2)
            mq = col_mq.selectbox("🛠️ Máquina:", ["SELECIONE..."] + [m['nome'].upper() for m in maquinas_raw])
            pr = col_pr.selectbox("🔥 Prioridade:", ["BAIXA", "MÉDIA", "ALTA", "URGENTE"])
            col_desc1, col_desc2 = st.columns([1, 0.3])
            ds = col_desc1.text_area("📝 Descrição do Problema:", height=100).upper()
            col_desc2.info(f"**Data automática:**\n{date.today().strftime('%d/%m/%Y')}")
            if st.form_submit_button("🚀 GERAR OS", type="primary"):
                if mq != "SELECIONE..." and ds.strip():
                    mid = next(m['id'] for m in maquinas_raw if m['nome'].upper() == mq)
                    supabase.table('solicitacoes').insert({"maquina_id": mid, "descricao": ds, "prioridade": pr, "status": "PENDENTE", "data_solicitacao": date.today().isoformat(), "criado_por_uuid": st.session_state['user_id'], "ordem_manual": int(datetime.now().timestamp())}).execute()
                    st.success("✅ Ordem de serviço criada com sucesso!")
                    st.rerun()
                else: st.error("❌ Preencha Máquina e Descrição!")

    st.divider()
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([1.5, 1, 1, 1, 1])
        f_mq = c1.selectbox("🛠️ Máquina:", ["TODOS"] + [m['id'] for m in maquinas_raw], format_func=lambda x: next((m['nome'].upper() for m in maquinas_raw if m['id'] == x), "TODOS"), key=f"mq_{st.session_state.f_key}")
        f_st = c2.selectbox("📊 Status:", ["TODOS", "PENDENTE", "EM ANDAMENTO"], key=f"st_{st.session_state.f_key}")
        f_pr = c3.selectbox("🔥 Prioridade:", ["TODAS", "BAIXA", "MÉDIA", "ALTA", "URGENTE"], key=f"pr_{st.session_state.f_key}")
        if c4.button("🔍 APLICAR FILTROS", type="primary", use_container_width=True):
            st.session_state.l_mq, st.session_state.l_st, st.session_state.l_pr = f_mq, f_st, f_pr
            st.session_state.dados_f = carregar_solicitacoes(f_mq, st.session_state['user_level'], st.session_state['user_id'], f_st, f_pr)
            st.rerun()
        if c5.button("🧹 LIMPAR", use_container_width=True):
            st.session_state.f_key += 1
            st.session_state.dados_f = None
            st.rerun()

    def renderizar_tabela_os(dados_os, familias_list):
        if dados_os is None:
            st.info("Utilize os filtros e clique em 'APLICAR FILTROS'.")
            return
        header = st.columns([0.5, 1.0, 0.9, 1.0, 0.8, 0.8, 0.8, 1.5, 1.2, 1.8])
        cols_names = ["#OS", "Solicitação", "Máquina", "Status", "Priorid.", "Início", "Fim", "Descrição", "Peças", "Ações"]
        for col, t in zip(header, cols_names): col.markdown(f"**{t}**")
        
        for s in dados_os:
            st.markdown('<div class="linha-divisoria"></div>', unsafe_allow_html=True)
            r = st.columns([0.5, 1.0, 0.9, 1.0, 0.8, 0.8, 0.8, 1.5, 1.2, 1.8])
            
            # --- Lógica de Cores da Prioridade ---
            pri = s['prioridade'].upper()
            cor_classe = "p-baixa"
            if pri == "URGENTE": cor_classe = "p-urgente"
            elif pri == "ALTA": cor_classe = "p-alta"
            elif pri in ["MÉDIA", "MEDIA"]: cor_classe = "p-media"
            
            r[0].write(f"#{s['id']}")
            r[1].write(formatar_data_br(s.get('data_solicitacao', '---')))
            r[2].write(f"**{s['maquinas']['nome']}**")
            r[3].write(s['status'])
            
            # Aplicação da Prioridade com Cor
            r[4].markdown(f'<div class="{cor_classe}">{pri}</div>', unsafe_allow_html=True)
            
            r[5].write(formatar_data_br(s.get('data_inicio')))
            r[6].write(formatar_data_br(s.get('data_fim')))
            r[7].caption(s['descricao'])
            r[8].write(s.get('pecas_solicitadas', '---'))
            
            b_col = r[9].columns(5)
            if b_col[0].button("🏁", key=f"fin_{s['id']}", help="Finalizar"):
                supabase.table('solicitacoes').update({"status":"FINALIZADO","data_fim":date.today().isoformat()}).eq("id",s['id']).execute()
                st.rerun()
            if b_col[1].button("📝", key=f"edit_{s['id']}", help="Editar"):
                st.session_state[f"ed_{s['id']}"] = True
                st.rerun()
            if b_col[2].button("⬆️", key=f"up_{s['id']}", help="Subir Prioridade"):
                supabase.table('solicitacoes').update({"ordem_manual":int(datetime.now().timestamp())}).eq("id",s['id']).execute()
                st.rerun()
            if b_col[3].button("⬇️", key=f"down_{s['id']}", help="Descer Prioridade"):
                supabase.table('solicitacoes').update({"ordem_manual":int(datetime.now().timestamp()) * -1}).eq("id",s['id']).execute()
                st.rerun()
            if b_col[4].button("🗑️", key=f"del_{s['id']}", help="Excluir"):
                supabase.table('solicitacoes').delete().eq("id",s['id']).execute()
                st.rerun()
                
            if st.session_state.get(f"ed_{s['id']}", False):
                with st.expander(f"✏️ Editando OS #{s['id']} - {s['maquinas']['nome']}", expanded=True):
                    with st.form(key=f"form_os_{s['id']}"):
                        c_ed1, c_ed2, c_ed3 = st.columns(3)
                        with c_ed1:
                            st_n = st.selectbox("Status", ["PENDENTE", "EM ANDAMENTO", "FINALIZADO"], index=["PENDENTE", "EM ANDAMENTO", "FINALIZADO"].index(s['status']))
                            pr_n = st.selectbox("Prioridade", ["BAIXA", "MÉDIA", "ALTA", "URGENTE"], index=["BAIXA", "MÉDIA", "ALTA", "URGENTE"].index(s['prioridade']))
                        with c_ed2:
                            d_ini_val = date.fromisoformat(s['data_inicio']) if s.get('data_inicio') else date.today()
                            d_fim_val = date.fromisoformat(s['data_fim']) if s.get('data_fim') else None
                            d_ini_n = st.date_input("Data Início", value=d_ini_val)
                            d_fim_n = st.date_input("Data Fim", value=d_fim_val)
                        with c_ed3:
                            mq_idx = next((i for i, m in enumerate(maquinas_raw) if m['id'] == s['maquina_id']), 0)
                            mq_n = st.selectbox("Máquina", [m['id'] for m in maquinas_raw], index=mq_idx, format_func=lambda x: next(m['nome'].upper() for m in maquinas_raw if m['id'] == x))
                        ds_n = st.text_area("Descrição", value=s['descricao'], height=80)
                        col_salvar, col_cancelar = st.columns(2)
                        if col_salvar.form_submit_button("💾 SALVAR", type="primary"):
                            supabase.table('solicitacoes').update({"status": st_n, "prioridade": pr_n, "maquina_id": mq_n, "descricao": ds_n, "data_inicio": d_ini_n.isoformat(), "data_fim": d_fim_n.isoformat() if d_fim_n else None}).eq("id", s['id']).execute()
                            st.session_state[f"ed_{s['id']}"] = False
                            st.rerun()
                        if col_cancelar.form_submit_button("❌ CANCELAR"):
                            st.session_state[f"ed_{s['id']}"] = False
                            st.rerun()
    renderizar_tabela_os(st.session_state.get('dados_f'), familias_raw)

# TELA 2: ESTOQUE DE PEÇAS
elif tela_selecionada == "📦 Estoque de Peças":
    st.title("📦 Estoque de Peças")
    
    c1, c2 = st.columns([2, 1])
    busca = c1.text_input("🔍 Buscar peça (Descrição ou Produto):").upper()
    fam_sel = c2.selectbox("Filtrar Família:", ["Todas"] + familias_raw)
    
    pecas = carregar_pecas_estoque(termo_busca=busca, familia_sel=fam_sel)
    
    if pecas:
        df_pecas = pd.DataFrame(pecas)
        header = st.columns([1, 2, 3, 2, 1, 1, 1, 1.5])
        cols = ["ID", "Produto", "Descrição", "Família", "Qtd", "Emp.", "Saldo", "Ações"]
        for col, t in zip(header, cols): col.markdown(f"**{t}**")
        
        for _, p in df_pecas.iterrows():
            st.markdown('<div class="linha-divisoria"></div>', unsafe_allow_html=True)
            r = st.columns([1, 2, 3, 2, 1, 1, 1, 1.5])
            r[0].write(p['id'])
            r[1].write(p['produto'])
            r[2].write(p['descricao'])
            r[3].write(p['familia'])
            r[4].write(p['quantidade'])
            r[5].write(p['empenho'])
            r[6].write(p['saldo'])
            
            if r[7].button("➕/➖", key=f"adj_{p['id']}"):
                st.session_state[f"show_adj_{p['id']}"] = True
            
            if st.session_state.get(f"show_adj_{p['id']}", False):
                with st.form(f"form_adj_{p['id']}"):
                    nova_qtd = st.number_input("Nova Quantidade Total:", value=float(p['quantidade']))
                    if st.form_submit_button("Atualizar"):
                        novo_saldo = nova_qtd - (p['empenho'] or 0)
                        supabase_admin.table('pecas').update({"quantidade": nova_qtd, "saldo": novo_saldo}).eq("id", p['id']).execute()
                        st.session_state[f"show_adj_{p['id']}"] = False
                        st.rerun()
    else:
        st.warning("Nenhuma peça encontrada.")

# TELA 3: CADASTROS
elif tela_selecionada == "⚙️ Cadastros":
    st.title("⚙️ Gerenciamento de Cadastros")
    tab1, tab2 = st.tabs(["🏗️ Máquinas", "📦 Novas Peças"])
    
    with tab1:
        st.subheader("Cadastrar Nova Máquina")
        with st.form("cad_maq"):
            n_maq = st.text_input("Nome da Máquina:").upper()
            if st.form_submit_button("Cadastrar Máquina"):
                if n_maq:
                    supabase_admin.table('maquinas').insert({"nome": n_maq}).execute()
                    st.success("Máquina cadastrada!")
                    st.rerun()
        
        st.divider()
        st.write("Máquinas Atuais:")
        for m in maquinas_raw:
            c_maq = st.columns([3, 1])
            c_maq[0].write(m['nome'])
            if c_maq[1].button("Remover", key=f"del_maq_{m['id']}"):
                supabase_admin.table('maquinas').delete().eq("id", m['id']).execute()
                st.rerun()

    with tab2:
        st.subheader("Cadastrar Nova Peça no Estoque")
        with st.form("cad_peca"):
            c1, c2 = st.columns(2)
            prod = c1.text_input("Produto / Código:").upper()
            desc = c2.text_input("Descrição:").upper()
            fam = st.selectbox("Família:", familias_raw)
            qtd_ini = st.number_input("Quantidade Inicial:", min_value=0.0)
            
            if st.form_submit_button("Cadastrar Peça"):
                if prod and desc:
                    supabase_admin.table('pecas').insert({
                        "produto": prod, "descricao": desc, "familia": fam, 
                        "quantidade": qtd_ini, "saldo": qtd_ini, "ativo": True
                    }).execute()
                    st.success("Peça cadastrada!")
                    st.rerun()
