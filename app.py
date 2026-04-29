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

st.markdown("""<style> 
    [data-testid="column"] { min-width: 95px !important; white-space: nowrap !important; } 
    .main .block-container { padding-left: 1rem; padding-right: 1rem; } 
    .login-container { max-width: 400px; margin: 50px auto; padding: 30px; border-radius: 15px; background-color: #1e1e1e; border: 1px solid #333; } 
    .stButton>button { width: 100% !important; font-weight: bold !important; } 
    div[data-testid="stForm"] .stButton>button { background-color: #ff5e00 !important; color: white !important; } 
    .p-urgente { color: #ff4b4b !important; font-weight: bold; border-left: 4px solid #ff4b4b; padding-left: 5px; } 
    .p-alta { color: #ffa500 !important; font-weight: bold; border-left: 4px solid #ffa500; padding-left: 5px; } 
    .p-media { color: #f1c40f !important; font-weight: bold; border-left: 4px solid #f1c40f; padding-left: 5px; } 
    .p-baixa { color: #2ecc71 !important; font-weight: bold; border-left: 4px solid #2ecc71; padding-left: 5px; } 
    .linha-divisoria { border-bottom: 2px solid #333; margin: 15px 0; width: 100%; }
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

# --- 3. LOGIN ---
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
                st.session_state['user_nickname'] = u_limpo.upper()
                st.session_state['user_level'] = perfil.data[0]['nivel']
                st.rerun()
    except Exception:
        st.error("Erro: Usuário ou senha inválidos.")

if not st.session_state['authenticated']:
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown("<h2 style='text-align:center; color:#ff5e00;'>INOVAFLEX</h2>", unsafe_allow_html=True)
    with st.form("login_form"):
        u_input = st.text_input("Usuário")
        p_input = st.text_input("Senha", type="password")
        if st.form_submit_button("ENTRAR"): realizar_login(u_input, p_input)
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
        if termo_busca: query = query.or_(f"descricao.ilike.%{termo_busca}%,produto.ilike.%{termo_busca}%")
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

def baixar_estoque_e_reservar(pid, qtd_vinculo):
    res = supabase_admin.table('pecas').select('quantidade, empenho').eq('id', pid).execute()
    if res.data:
        q_at = res.data[0]['quantidade']; e_at = res.data[0]['empenho']
        nq = max(0, q_at - qtd_vinculo); ne = e_at + qtd_vinculo
        supabase_admin.table('pecas').update({'quantidade': nq, 'empenho': ne, 'saldo': nq - ne}).eq('id', pid).execute()

def liberar_empenho_finalizacao(pecas_txt):
    if not pecas_txt: return
    try:
        matches = re.findall(r'\[ID: (\d+), QTD: (\d+)\]', pecas_txt)
        for pid, qtd in matches:
            res = supabase_admin.table('pecas').select('quantidade, empenho').eq('id', int(pid)).execute()
            if res.data:
                e_at = res.data[0]['empenho']; q_at = res.data[0]['quantidade']
                ne = max(0, e_at - int(qtd))
                supabase_admin.table('pecas').update({'empenho': ne, 'saldo': q_at - ne}).eq('id', int(pid)).execute()
    except: pass

# --- 5. SIDEBAR ---
with st.sidebar:
    st.header("🚀 MENU")
    tela_selecionada = st.selectbox("Navegar para:", ["📋 Fila de Manutenção", "📦 Estoque de Peças", "⚙️ Painel Admin"])
    st.divider()
    st.write(f"Usuário: **{st.session_state['user_nickname']}**")
    if st.button("🚪 Sair"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

# --- 6. RENDERIZAÇÃO DA FILA ---
def renderizar_tabela_os(dados_os, familias_list):
    if dados_os is None:
        st.info("Utilize os filtros e clique em 'APLICAR FILTROS'.")
        return
    if not dados_os:
        st.warning("Nenhuma Solicitação encontrada.")
        return

    header = st.columns([0.6, 1.0, 0.8, 0.8, 0.8, 0.8, 1.4, 1.2, 2.0])
    for col, t in zip(header, ["ID OS", "Máquina", "Status", "Prioridade", "Início", "Fim", "Solicitação", "Histórico Peças", "Ações"]): col.markdown(f"**{t}**")
    
    for i, s in enumerate(dados_os):
        st.markdown('<div class="linha-divisoria"></div>', unsafe_allow_html=True)
        r = st.columns([0.6, 1.0, 0.8, 0.8, 0.8, 0.8, 1.4, 1.2, 2.0])
        r[0].write(f"#{s['id']}"); r[1].write(f"**{s['maquinas']['nome']}**"); r[2].write(s['status'])
        p = s['prioridade']
        if p == "URGENTE": r[3].markdown(f'<div class="p-urgente">{p}</div>', unsafe_allow_html=True)
        elif p == "ALTA": r[3].markdown(f'<div class="p-alta">{p}</div>', unsafe_allow_html=True)
        elif p == "MÉDIA": r[3].markdown(f'<div class="p-media">{p}</div>', unsafe_allow_html=True)
        else: r[3].markdown(f'<div class="p-baixa">{p}</div>', unsafe_allow_html=True)
        r[4].write(formatar_data_br(s.get('data_inicio'))); r[5].write(formatar_data_br(s.get('data_fim')))
        r[6].caption(s['descricao']); r[7].write(s.get('pecas_solicitadas', '---'))
        
        b = r[8].columns(5)
        nivel_u = st.session_state.get('user_level', 'operador')
        e_mecanico_local = nivel_u in ['mecanico', 'admin']
        
        if e_mecanico_local:
            if s['status'] != "FINALIZADO" and b[0].button("🏁", key=f"f{s['id']}"):
                liberar_empenho_finalizacao(s.get('pecas_solicitadas'))
                supabase.table('solicitacoes').update({"status":"FINALIZADO","data_fim":date.today().isoformat()}).eq("id",s['id']).execute()
                st.session_state.dados_f = carregar_solicitacoes(st.session_state.l_mq, nivel_u, st.session_state['user_id'], st.session_state.l_st, st.session_state.l_pr)
                st.rerun()
            if b[1].button("📝", key=f"e{s['id']}"): st.session_state[f"ed{s['id']}"] = True; st.rerun()
            ov = s.get('ordem_manual', 0)
            if b[2].button("🔼", key=f"u{s['id']}"):
                if i > 0:
                    out = dados_os[i-1]
                    supabase.table('solicitacoes').update({"ordem_manual": out['ordem_manual']}).eq("id", s['id']).execute()
                    supabase.table('solicitacoes').update({"ordem_manual": ov}).eq("id", out['id']).execute()
                    st.session_state.dados_f = carregar_solicitacoes(st.session_state.l_mq, nivel_u, st.session_state['user_id'], st.session_state.l_st, st.session_state.l_pr)
                    st.rerun()
            if b[3].button("🔽", key=f"d{s['id']}"):
                if i < len(dados_os) - 1:
                    out = dados_os[i+1]
                    supabase.table('solicitacoes').update({"ordem_manual": out['ordem_manual']}).eq("id", s['id']).execute()
                    supabase.table('solicitacoes').update({"ordem_manual": ov}).eq("id", out['id']).execute()
                    st.session_state.dados_f = carregar_solicitacoes(st.session_state.l_mq, nivel_u, st.session_state['user_id'], st.session_state.l_st, st.session_state.l_pr)
                    st.rerun()
        if nivel_u == 'admin' and b[4].button("🗑️", key=f"x{s['id']}"):
            supabase.table('solicitacoes').delete().eq("id", s['id']).execute()
            st.session_state.dados_f = carregar_solicitacoes(st.session_state.l_mq, nivel_u, st.session_state['user_id'], st.session_state.l_st, st.session_state.l_pr)
            st.rerun()

        if st.session_state.get(f"ed{s['id']}", False):
            with st.container(border=True):
                st.subheader(f"✏️ Editar OS #{s['id']}")
                # FILTROS PARA VINCULAR PEÇAS
                f_c1, f_c2 = st.columns(2)
                v_busca = f_c1.text_input("Filtrar Peça por Código/Nome", key=f"v_t_{s['id']}").upper()
                v_fam = f_c2.selectbox("Filtrar por Família", ["Todas"] + familias_list, key=f"v_f_{s['id']}")
                
                with st.form(f"form_ed_{s['id']}"):
                    c1, c2 = st.columns(2)
                    st_at = c1.selectbox("Status", ["PENDENTE", "EM ANDAMENTO", "FINALIZADO"], index=["PENDENTE", "EM ANDAMENTO", "FINALIZADO"].index(s['status'].upper() if s['status'] else "PENDENTE"))
                    pr_at = c2.selectbox("Prioridade", ["BAIXA", "MÉDIA", "ALTA", "URGENTE"], index=["BAIXA", "MÉDIA", "ALTA", "URGENTE"].index(s['prioridade'].upper() if s['prioridade'] else "BAIXA"))
                    v_ini = datetime.strptime(s['data_inicio'], '%Y-%m-%d').date() if s.get('data_inicio') else None
                    v_fim = datetime.strptime(s['data_fim'], '%Y-%m-%d').date() if s.get('data_fim') else None
                    d_cols = st.columns(2)
                    n_ini = d_cols[0].date_input("Início", value=v_ini); n_fim = d_cols[1].date_input("Fim", value=v_fim)
                    ds_add = st.text_area("Nova Observação").upper()
                    
                    st.write("---")
                    st.write("⚙️ **Vincular Peças ao Código**")
                    p_loc = carregar_pecas_estoque(apenas_ativos=True, termo_busca=v_busca, familia_sel=v_fam)
                    op_p = {f"{p['produto']} - {p['descricao']} (Saldo: {p['saldo']}) [ID: {p['id']}]": p['id'] for p in p_loc if p['saldo'] > 0}
                    
                    p_sel = st.multiselect("Selecione os Itens para vincular:", list(op_p.keys()))
                    
                    # Interface para definir quantidades
                    vinc_dict = {}
                    if p_sel:
                        st.info("Ajuste as quantidades para vincular (diminuir estoque / aumentar empenho):")
                        for p_name in p_sel:
                            pid_l = op_p[p_name]
                            vinc_dict[pid_l] = st.number_input(f"Qtd para {p_name}:", min_value=1, value=1, key=f"q_{pid_l}_{s['id']}")
                    
                    if st.form_submit_button("SALVAR ALTERAÇÕES"):
                        string_vinc = ""
                        for p_id, q_vinc in vinc_dict.items():
                            baixar_estoque_e_reservar(p_id, q_vinc)
                            p_info = next(p for p in p_loc if p['id'] == p_id)
                            string_vinc += f"{p_info['produto']} (x{q_vinc}) [ID: {p_id}, QTD: {q_vinc}] | "
                        
                        desc_f = s['descricao']
                        if ds_add.strip(): desc_f += f"\n\n**[{date.today().strftime('%d/%m/%y')}]:** {ds_add}"
                        
                        pecas_hist = s.get('pecas_solicitadas', '')
                        pecas_final = f"{pecas_hist} {string_vinc}" if pecas_hist else string_vinc
                        
                        upd = {"status": st_at, "prioridade": pr_at, "descricao": desc_f, "pecas_solicitadas": pecas_final, "data_inicio": n_ini.isoformat() if n_ini else None, "data_fim": n_fim.isoformat() if n_fim else None}
                        supabase.table('solicitacoes').update(upd).eq("id", s['id']).execute()
                        st.session_state[f"ed{s['id']}"] = False
                        st.session_state.dados_f = carregar_solicitacoes(st.session_state.l_mq, nivel_u, st.session_state['user_id'], st.session_state.l_st, st.session_state.l_pr)
                        st.rerun()
                if st.button("FECHAR", key=f"can_{s['id']}"): st.session_state[f"ed{s['id']}"] = False; st.rerun()

# --- 7. TELAS ---
maquinas_raw = carregar_listas()
familias_raw = carregar_familias()

if tela_selecionada == "📋 Fila de Manutenção":
    st.title("📋 Fila de Manutenção")
    with st.expander("➕ ABRIR NOVA ORDEM DE SERVIÇO"):
        with st.form("n_os"):
            mq = st.selectbox("Máquina", ["SELECIONE..."] + [m['nome'].upper() for m in maquinas_raw])
            pr = st.selectbox("Prioridade", ["BAIXA", "MÉDIA", "ALTA", "URGENTE"])
            ds = st.text_area("Descrição").upper()
            if st.form_submit_button("GERAR"):
                if mq != "SELECIONE..." and ds:
                    mid = next(m['id'] for m in maquinas_raw if m['nome'].upper() == mq)
                    supabase.table('solicitacoes').insert({"maquina_id": mid, "descricao": ds, "prioridade": pr, "status": "PENDENTE", "data_solicitacao": date.today().isoformat(), "criado_por_uuid": st.session_state['user_id'], "ordem_manual": int(datetime.now().timestamp())}).execute(); st.rerun()
    st.divider()
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([1.5, 1, 1, 1, 1])
        f_mq = c1.selectbox("Máquina:", ["TODOS"] + [m['id'] for m in maquinas_raw], format_func=lambda x: next((m['nome'].upper() for m in maquinas_raw if m['id'] == x), "TODOS"), key=f"mq_{st.session_state.f_key}")
        f_st = c2.selectbox("Status:", ["TODOS", "PENDENTE", "EM ANDAMENTO"], key=f"st_{st.session_state.f_key}")
        f_pr = c3.selectbox("Prioridade:", ["TODAS", "BAIXA", "MÉDIA", "ALTA", "URGENTE"], key=f"pr_{st.session_state.f_key}")
        if c4.button("🔍 APLICAR FILTROS", type="primary"):
            st.session_state.l_mq = f_mq; st.session_state.l_st = f_st; st.session_state.l_pr = f_pr
            st.session_state.dados_f = carregar_solicitacoes(f_mq, st.session_state['user_level'], st.session_state['user_id'], f_st, f_pr); st.rerun()
        if c5.button("🧹 LIMPAR"): st.session_state.f_key += 1; st.session_state.dados_f = None; st.rerun()
    renderizar_tabela_os(st.session_state.dados_f, familias_raw)

elif tela_selecionada == "📦 Estoque de Peças":
    st.title("📦 Consulta de Estoque")
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 1, 0.5])
        bin = c1.text_input("🔍 Pesquisar:", value=st.session_state.t_p).upper()
        idx_f = (["Todas"] + familias_raw).index(st.session_state.fam_p) if st.session_state.fam_p in (["Todas"] + familias_raw) else 0
        fin = c2.selectbox("Família de Produto:", ["Todas"] + familias_raw, index=idx_f)
        if c3.button("🚀 START"): st.session_state.t_p = bin; st.session_state.fam_p = fin; st.rerun()
    p_all = carregar_pecas_estoque(apenas_ativos=True, termo_busca=st.session_state.t_p, familia_sel=st.session_state.fam_p)
    st.divider()
    if p_all:
        h = st.columns([0.4, 1.0, 1.5, 1.0, 0.8, 0.8, 0.8, 1.2])
        for col, t in zip(h, ["ID", "Produto", "Descrição", "Família de Produto", "Quantidade", "Empenho", "Saldo", "Ações"]): col.markdown(f"**{t}**")
        for p in p_all:
            r = st.columns([0.4, 1.0, 1.5, 1.0, 0.8, 0.8, 0.8, 1.2])
            r[0].write(p['id']); r[1].write(p['produto']); r[2].write(p['descricao']); r[3].write(p.get('familia', '---')); r[4].write(p['quantidade']); r[5].write(p['empenho']); r[6].write(p['saldo'])
            bc = r[7].columns(3)
            if bc[0].button("🚫", key=f"i{p['id']}"): supabase_admin.table('pecas').update({"ativo": False}).eq('id', p['id']).execute(); st.rerun()
            if st.session_state['user_level'] in ['mecanico', 'admin'] and bc[1].button("✏️", key=f"aj{p['id']}"): st.session_state[f"aj_e_{p['id']}"] = True; st.rerun()
            if st.session_state['user_level'] == 'admin' and bc[2].button("🗑️", key=f"ex{p['id']}"): supabase_admin.table('pecas').delete().eq('id', p['id']).execute(); st.rerun()
            if st.session_state.get(f"aj_e_{p['id']}", False):
                with st.form(f"f_aj_{p['id']}"):
                    nq = st.number_input("Quantidade Total:", value=p['quantidade']); ne = st.number_input("Empenho:", value=p['empenho'])
                    if st.form_submit_button("✅ SALVAR"):
                        supabase_admin.table('pecas').update({"quantidade": nq, "empenho": ne, "saldo": nq - ne}).eq('id', p['id']).execute()
                        st.session_state[f"aj_e_{p['id']}"] = False; st.rerun()
                    if st.form_submit_button("❌ FECHAR"): st.session_state[f"aj_e_{p['id']}"] = False; st.rerun()
    else: st.info("Nenhum item ativo encontrado.")

elif tela_selecionada == "⚙️ Cadastros":
    st.title("⚙️ Administração")
    if st.session_state['user_level'] != 'admin': st.error("Acesso negado.")
    else:
        t1, t2, t3, t4 = st.tabs(["Usuários", "Máquinas", "Famílias de Produto", "Estoque Geral"])
        with t1:
            with st.form("u"):
                un = st.text_input("Usuário").upper(); us = st.text_input("Senha", type="password"); up = st.selectbox("Perfil", ["operador", "mecanico", "admin"])
                if st.form_submit_button("Criar"):
                    try:
                        em = f"{un.strip().lower()}@inovaflex.com"; u = supabase_admin.auth.admin.create_user({"email": em, "password": us, "email_confirm": True})
                        supabase_admin.table('perfis').insert({"id": u.user.id, "email": em, "nivel": up}).execute(); st.success("Criado!")
                    except Exception as e: st.error(e)
        with t2:
            nm = st.text_input("Nova Máquina")
            if st.button("Salvar Máquina"):
                if nm: supabase.table('maquinas').insert({"nome": nm.upper()}).execute(); st.rerun()
        with t3:
            nf = st.text_input("Nova Família")
            if st.button("Cadastrar"):
                if nf: supabase_admin.table('familias_produtos').insert({"nome": nf.upper()}).execute(); st.rerun()
        with t4:
            c1, c2 = st.columns(2)
            with c1:
                arq = st.file_uploader("Upload Excel", type=["xlsx"])
                if arq and st.button("IMPORTAR"):
                    df = pd.read_excel(arq).fillna(0)
                    for _, r in df.iterrows():
                        supabase_admin.table('pecas').insert({"produto": str(r['Produto']).upper(), "descricao": str(r['Descrição']).upper(), "quantidade": int(r['Qtde.']), "empenho": int(r['Empenho']), "saldo": int(r['Saldo']), "familia": str(r.get('Família de Produto', '')).upper(), "ativo": True}).execute()
                    st.success("Estoque Atualizado!"); st.rerun()
            with c2:
                with st.form("cp"):
                    pp = st.text_input("Produto"); pd = st.text_input("Descrição"); pf = st.selectbox("Família", ["OUTROS"] + familias_raw); pq = st.number_input("Qtde Total", min_value=0); pe = st.number_input("Empenho", min_value=0)
                    if st.form_submit_button("Adicionar"):
                        supabase_admin.table('pecas').insert({"produto": pp.upper(), "descricao": pd.upper(), "familia": pf, "quantidade": pq, "empenho": pe, "saldo": pq - pe, "ativo": True}).execute(); st.rerun()
            st.divider()
            pecas_adm = carregar_pecas_estoque(apenas_ativos=False)
            for pa in pecas_adm:
                if not pa['ativo']:
                    c_r1, c_r2 = st.columns([4, 1])
                    c_r1.warning(f"Inativo: {pa['produto']} - {pa['descricao']}")
                    if c_r2.button("Reativar", key=f"re_{pa['id']}"): supabase_admin.table('pecas').update({"ativo": True}).eq('id', pa['id']).execute(); st.rerun()
