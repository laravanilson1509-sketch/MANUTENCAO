import streamlit as st
import pandas as pd
from datetime import date, datetime
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ── CONFIG ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Plano de Manutenção",
    page_icon="🔧",
    layout="wide"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

.block-container {
    max-width: 100% !important;
    padding: 1.5rem 2.5rem !important;
    background-color: #070d1a;
}
.main { background: #070d1a; }

.app-header {
    background: linear-gradient(135deg, #0a1628 0%, #0d2137 100%);
    border: 1px solid #1e3a5f;
    border-top: 3px solid #1a6cf5;
    border-radius: 14px;
    padding: 1.8rem 2.2rem;
    margin-bottom: 1.8rem;
}
.app-header h1 {
    font-family: 'Syne', sans-serif;
    color: #ffffff;
    font-size: 2rem;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.5px;
}
.app-header h1 span { color: #1a9cf5; }
.app-header p { color: #4a7aaa; font-size: .82rem; margin: 4px 0 0; }

.section-label {
    font-family: 'Syne', sans-serif;
    font-size: .7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .14em;
    color: #4a7aaa;
    margin-bottom: .6rem;
}

.sol-card {
    background: linear-gradient(145deg, #0c1a2e, #102035);
    border: 1px solid #1b3352;
    border-left: 4px solid #1a6cf5;
    border-radius: 12px;
    padding: 1.1rem 1.4rem;
    margin-bottom: .75rem;
}
.sol-card.urgente { border-left-color: #ff5252; }
.sol-card.alta    { border-left-color: #ffaa00; }
.sol-card.media   { border-left-color: #00d68f; }
.sol-card.baixa   { border-left-color: #4a7aaa; }
.sol-titulo { color: #dce8ff; font-size: .95rem; font-weight: 600; margin-bottom: 4px; font-family: 'Syne', sans-serif; }
.sol-meta   { color: #3d6080; font-size: .78rem; }

.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: .68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .06em;
}
.badge-urgente   { background: rgba(255,82,82,.15);  color: #ff5252; }
.badge-alta      { background: rgba(255,170,0,.15);  color: #ffaa00; }
.badge-media     { background: rgba(0,214,143,.15);  color: #00d68f; }
.badge-baixa     { background: rgba(74,122,170,.15); color: #6b9ec8; }
.badge-pendente  { background: rgba(74,122,170,.12); color: #6b9ec8; }
.badge-andamento { background: rgba(26,156,245,.15); color: #1a9cf5; }
.badge-finalizada{ background: rgba(0,214,143,.15);  color: #00d68f; }

div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-testid="stSelectbox"] > div > div {
    background: #060c18 !important;
    border: 1px solid #1b3352 !important;
    border-radius: 8px !important;
    color: #d0e4ff !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: .88rem !important;
}
label {
    color: #4a7aaa !important;
    font-size: .75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: .08em !important;
}

.stButton > button {
    border-radius: 8px !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    font-size: .78rem !important;
    letter-spacing: .05em !important;
    border: none !important;
    transition: all .18s !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #1a6cf5, #0d52cc) !important;
    color: white !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #2a7dff, #1a6cf5) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 5px 18px rgba(26,108,245,.35) !important;
}
.stButton > button[kind="secondary"] {
    background: rgba(255,82,82,.08) !important;
    color: #ff7070 !important;
    border: 1px solid rgba(255,82,82,.2) !important;
}
.stButton > button[kind="secondary"]:hover {
    background: rgba(255,82,82,.18) !important;
    border-color: #ff5252 !important;
}
div[data-testid="stDownloadButton"] > button {
    background: linear-gradient(135deg, #00a86b, #007a4d) !important;
    color: white !important;
    border-radius: 8px !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    font-size: .78rem !important;
    border: none !important;
}
div[data-testid="stDownloadButton"] > button:hover {
    background: linear-gradient(135deg, #00c47e, #00a86b) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 5px 16px rgba(0,168,107,.35) !important;
}

div[data-testid="metric-container"] {
    background: #0c1829 !important;
    border: 1px solid #1b3352 !important;
    border-radius: 10px !important;
    padding: 14px 16px !important;
}
div[data-testid="metric-container"] label { color: #3d6080 !important; font-size: .68rem !important; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #d0e4ff !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 800 !important;
}

details {
    background: #0c1829 !important;
    border: 1px solid #1b3352 !important;
    border-radius: 10px !important;
    margin-bottom: .5rem !important;
}
summary { color: #8ab4d8 !important; font-size: .88rem !important; }
hr { border-color: #1b3352 !important; margin: 1.2rem 0 !important; }
div[data-testid="stAlert"] { border-radius: 8px !important; font-size: .84rem !important; }
</style>
""", unsafe_allow_html=True)

# ── ESTADOS ───────────────────────────────────────────────────────────────────
if "solicitacoes" not in st.session_state:
    st.session_state.solicitacoes = []
if "maquinas" not in st.session_state:
    st.session_state.maquinas = ["MAQ FLEX 1", "MAQ FLEX 2", "MAQ FLEX 3", "MAQ CNC 1"]
if "editando" not in st.session_state:
    st.session_state.editando = None
if "form_key" not in st.session_state:
    st.session_state.form_key = 0

# ── HELPERS ───────────────────────────────────────────────────────────────────
def limpar_formulario():
    """Limpa completamente o formulário recriando todos os widgets."""
    st.session_state.form_key += 1
    st.session_state.editando = None
    st.rerun()

def excluir(idx):
    """Remove solicitação pelo índice."""
    st.session_state.solicitacoes.pop(idx)
    if st.session_state.editando == idx:
        st.session_state.editando = None
    st.rerun()

def cor_classe(prio):
    return {"Urgente":"urgente","Alta":"alta","Média":"media","Baixa":"baixa"}.get(prio,"baixa")

def badge_prio(prio):
    cls = {"Urgente":"badge-urgente","Alta":"badge-alta","Média":"badge-media","Baixa":"badge-baixa"}.get(prio,"badge-baixa")
    return f'<span class="badge {cls}">{prio}</span>'

def badge_status(status):
    cls = {"Pendente":"badge-pendente","Em andamento":"badge-andamento","Finalizada":"badge-finalizada"}.get(status,"badge-pendente")
    return f'<span class="badge {cls}">{status}</span>'

def gerar_excel():
    wb = Workbook()
    ws = wb.active
    ws.title = "Plano de Manutenção"
    thin  = Side(style="thin", color="1B3352")
    borda = Border(left=thin, right=thin, top=thin, bottom=thin)
    def fill(c): return PatternFill("solid", fgColor=c)

    ws.merge_cells("A1:H1")
    ws["A1"] = "PLANO DE MANUTENÇÃO"
    ws["A1"].font      = Font(name="Arial", bold=True, color="FFFFFF", size=14)
    ws["A1"].fill      = fill("0A1628")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 32

    ws.merge_cells("A2:H2")
    ws["A2"] = f"Exportado em {date.today().strftime('%d/%m/%Y')}"
    ws["A2"].font      = Font(name="Arial", color="4A7AAA", size=9)
    ws["A2"].fill      = fill("0A1628")
    ws["A2"].alignment = Alignment(horizontal="center")
    ws.row_dimensions[2].height = 16

    headers  = ["Solicitador","Máquina","Descrição","Data Solicitação","Data Início","Data Fim","Status","Prioridade"]
    larguras = [20,16,44,16,14,14,16,12]
    for col,(h,w) in enumerate(zip(headers,larguras),1):
        ws.column_dimensions[get_column_letter(col)].width = w
        c = ws.cell(row=4,column=col,value=h)
        c.font      = Font(name="Arial",bold=True,color="FFFFFF",size=9)
        c.fill      = fill("0D2137")
        c.alignment = Alignment(horizontal="center",vertical="center")
        c.border    = borda
    ws.row_dimensions[4].height = 20

    prio_cor = {"Urgente":"FF5252","Alta":"FFAA00","Média":"00D68F","Baixa":"4A7AAA"}
    stat_cor = {"Pendente":"6B9EC8","Em andamento":"1A9CF5","Finalizada":"00D68F"}

    for i,item in enumerate(st.session_state.solicitacoes):
        row = 5+i
        bg  = "0C1829" if i%2==0 else "0F1E33"
        vals = [
            item.get("Solicitador",""), item.get("Máquina",""),
            item.get("Descrição",""),   item.get("Data",""),
            item.get("DataInicio","") or "—", item.get("DataFim","") or "—",
            item.get("Status",""),      item.get("Prioridade",""),
        ]
        for col,val in enumerate(vals,1):
            c = ws.cell(row=row,column=col,value=val)
            c.fill      = fill(bg)
            c.border    = borda
            c.font      = Font(name="Arial",color="C0D8F0",size=9)
            c.alignment = Alignment(vertical="center",wrap_text=(col==3))
        ws.cell(row=row,column=7).font = Font(name="Arial",bold=True,size=9,color=stat_cor.get(item.get("Status",""),"FFFFFF"))
        ws.cell(row=row,column=8).font = Font(name="Arial",bold=True,size=9,color=prio_cor.get(item.get("Prioridade",""),"FFFFFF"))
        ws.row_dimensions[row].height = 18

    ws.freeze_panes = "A5"
    if st.session_state.solicitacoes:
        ws.auto_filter.ref = f"A4:H{4+len(st.session_state.solicitacoes)}"
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()

# ═══════════════════════════════════════════════════════════════════════════════
# LAYOUT
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="app-header">
  <h1>🔧 PLANO DE <span>MANUTENÇÃO</span></h1>
  <p>Gestão de solicitações e acompanhamento de ordens de serviço</p>
</div>
""", unsafe_allow_html=True)

# MÉTRICAS
sol = st.session_state.solicitacoes
m1,m2,m3,m4,m5 = st.columns(5)
m1.metric("📋 Total",        len(sol))
m2.metric("⏳ Pendentes",    sum(1 for s in sol if s.get("Status")=="Pendente"))
m3.metric("🔵 Em Andamento", sum(1 for s in sol if s.get("Status")=="Em andamento"))
m4.metric("✅ Finalizadas",  sum(1 for s in sol if s.get("Status")=="Finalizada"))
m5.metric("🔴 Urgentes",     sum(1 for s in sol if s.get("Prioridade")=="Urgente"))

st.divider()

# ── GERENCIAMENTO DE MÁQUINAS ─────────────────────────────────────────────────
with st.expander("⚙️ Gerenciar Máquinas", expanded=False):
    cM1,cM2 = st.columns([3,1])
    with cM1:
        nova_maq = st.text_input("Nome da máquina", placeholder="Ex: MAQ FLEX 5", key="nova_maq")
        if st.button("➕ Adicionar", type="primary", use_container_width=True):
            nm = nova_maq.strip()
            if nm and nm not in st.session_state.maquinas:
                st.session_state.maquinas.append(nm)
                st.success(f"✅ **{nm}** adicionada!")
                st.rerun()
            elif nm:
                st.warning("❌ Máquina já existe.")
    with cM2:
        if st.session_state.maquinas:
            maq_exc = st.selectbox("Remover", st.session_state.maquinas, key="maq_exc")
            if st.button("🗑️", type="secondary", use_container_width=True):
                st.session_state.maquinas.remove(maq_exc)
                st.success("✅ Máquina removida!")
                st.rerun()
    
    if st.session_state.maquinas:
        st.markdown("**Máquinas cadastradas:** " + "  ".join(f"`{m}`" for m in st.session_state.maquinas))

st.divider()

# ── FORMULÁRIO ────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">📋 Nova Solicitação</div>', unsafe_allow_html=True)

fk = st.session_state.form_key

col1,col2,col3 = st.columns([1.1,1,1.3])

with col1:
    solicitador = st.text_input("👤 Solicitador", placeholder="Nome do responsável", key=f"sol_{fk}")
    maq_ops = (["— Selecione —"] + st.session_state.maquinas) if st.session_state.maquinas else ["— Sem máquinas —"]
    maq_sel = st.selectbox("⚙️ Máquina", maq_ops, key=f"maq_{fk}")
    maquina = "" if maq_sel.startswith("—") else maq_sel
    prio_ops = ["— Selecione —","Urgente","Alta","Média","Baixa"]
    prio_sel = st.selectbox("🔥 Prioridade", prio_ops, key=f"prio_{fk}")
    prioridade = "" if prio_sel == "— Selecione —" else prio_sel

with col2:
    data_solic = st.date_input("📅 Data", value=date.today(), key=f"data_{fk}")

with col3:
    descricao = st.text_area("📝 Descrição do problema", height=148,
                            placeholder="Descreva detalhadamente…", key=f"desc_{fk}")

cB1,cB2 = st.columns([2,1])
with cB1:
    if st.button("🚀 Registrar Solicitação", type="primary", use_container_width=True):
        if maquina and prioridade and descricao.strip():
            st.session_state.solicitacoes.append({
                "Solicitador": solicitador,
                "Máquina": maquina,
                "Descrição": descricao.strip(),
                "Data": data_solic.strftime("%d/%m/%Y"),
                "DataInicio": "",
                "DataFim": "",
                "Status": "Pendente",  # ✅ SEMPRE nasce como Pendente
                "Prioridade": prioridade,
            })
            st.success("✅ **Solicitação registrada como Pendente!**")
            limpar_formulario()
        else:
            st.error("❌ Preencha **Máquina**, **Prioridade** e **Descrição**.")

with cB2:
    if st.button("🧹 Limpar Formulário", type="secondary", use_container_width=True, key=f"limpar_{fk}"):
        limpar_formulario()

st.divider()

# ── FILA ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">📊 Fila de Manutenção</div>', unsafe_allow_html=True)

cf1,cf2,cf3,cf4 = st.columns([1.5,1.5,1.5,1])
f_maq  = cf1.selectbox("Máquina",    ["Todas"] + st.session_state.maquinas, key="f_maq")
f_stat = cf2.selectbox("Status",     ["Todos","Pendente","Em andamento","Finalizada"], key="f_stat")
f_prio = cf3.selectbox("Prioridade", ["Todas","Urgente","Alta","Média","Baixa"], key="f_prio")
with cf4:
    st.write(""); st.write("")
    if st.session_state.solicitacoes:
        st.download_button(
            "📥 Exportar Excel",
            data=gerar_excel(),
            file_name=f"manutencao_{date.today().strftime('%d%m%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

lista = [
    (i,item) for i,item in enumerate(st.session_state.solicitacoes)
    if (f_maq == "Todas" or item.get("Máquina") == f_maq)
    and (f_stat == "Todos" or item.get("Status") == f_stat)
    and (f_prio == "Todas" or item.get("Prioridade") == f_prio)
]

if not lista:
    st.info("📭 Nenhuma solicitação encontrada.")
else:
    for i,item in lista:
        cls = cor_classe(item.get("Prioridade",""))
        st.markdown(f'<div class="sol-card {cls}">', unsafe_allow_html=True)

        cA,cB,cC = st.columns([4.5,2.5,2])
        with cA:
            st.markdown(
                f'<div class="sol-titulo">{item.get("Descrição","(sem descrição)")}</div>'
                f'<div class="sol-meta">⚙️ {item.get("Máquina","")} &nbsp;·&nbsp; '
                f'👤 {item.get("Solicitador","—")} &nbsp;·&nbsp; '
                f'📅 {item.get("Data","")}</div>',
                unsafe_allow_html=True
            )
            st.markdown(
                badge_prio(item.get("Prioridade","")) + "&nbsp;" + badge_status(item.get("Status","")),
                unsafe_allow_html=True
            )
        with cB:
            ini = item.get("DataInicio") or "—"
            fim = item.get("DataFim") or "—"
            st.markdown(
                f'<div class="sol-meta" style="margin-top:6px">'
                f'🟦 Início: <b style="color:#8ab4d8">{ini}</b>&nbsp;&nbsp;'
                f'🟥 Fim: <b style="color:#8ab4d8">{fim}</b></div>',
                unsafe_allow_html=True
            )
        with cC:
            b1,b2,b3,b4 = st.columns(4)
            with b1:
                if st.button("⬆️", key=f"up_{i}", help="Subir"):
                    if i > 0:
                        s = st.session_state.solicitacoes
                        s[i-1],s[i] = s[i],s[i-1]
                        st.rerun()
            with b2:
                if st.button("⬇️", key=f"dn_{i}", help="Descer"):
                    if i < len(st.session_state.solicitacoes)-1:
                        s = st.session_state.solicitacoes
                        s[i+1],s[i] = s[i],s[i+1]
                        st.rerun()
            with b3:
                label_edit = "✖️" if st.session_state.editando == i else "✏️"
                if st.button(label_edit, key=f"ed_{i}", help="Editar"):
                    st.session_state.editando = None if st.session_state.editando == i else i
                    st.rerun()
            with b4:
                if st.button("🗑️", key=f"dl_{i}", help="Excluir"):
                    st.warning("🗑️ **Excluir esta solicitação?**")
                    if st.button("CONFIRMAR", key=f"conf_{i}", type="secondary"):
                        excluir(i)

        # ── PAINEL EDITAR (COM STATUS, DATA INÍCIO E FIM) ────────────────────
        if st.session_state.editando == i:
            st.markdown("---")
            st.markdown("**✏️ Atualizar Solicitação**")

            e1,e2,e3,e4 = st.columns(4)
            with e1:
                try:
                    ini_def = datetime.strptime(item["DataInicio"], "%d/%m/%Y").date() if item.get("DataInicio") else date.today()
                except:
                    ini_def = date.today()
                nova_inicio = st.date_input("📅 Data Início", value=ini_def, key=f"ei_{i}")
            
            with e2:
                try:
                    fim_def = datetime.strptime(item["DataFim"], "%d/%m/%Y").date() if item.get("DataFim") else date.today()
                except:
                    fim_def = date.today()
                nova_fim = st.date_input("📅 Data Fim", value=fim_def, key=f"ef_{i}")
            
            with e3:
                stat_ops = ["Pendente", "Em andamento", "Finalizada"]
                stat_idx = stat_ops.index(item.get("Status", "Pendente")) if item.get("Status") in stat_ops else 0
                novo_status = st.selectbox("🏷️ Status", stat_ops, index=stat_idx, key=f"status_{i}")
            
            with e4:
                prio_ops = ["Urgente", "Alta", "Média", "Baixa"]
                prio_idx = prio_ops.index(item.get("Prioridade", "Baixa")) if item.get("Prioridade") in prio_ops else 0
                nova_prioridade = st.selectbox("🔥 Prioridade", prio_ops, index=prio_idx, key=f"prio_{i}")

            col_salvar, col_finalizar = st.columns([1,1])
            with col_salvar:
                if st.button("💾 Salvar", key=f"sv_{i}", type="primary", use_container_width=True):
                    item["DataInicio"] = nova_inicio.strftime("%d/%m/%Y")
                    item["DataFim"] = nova_fim.strftime("%d/%m/%Y")
                    item["Status"] = novo_status
                    item["Prioridade"] = nova_prioridade
                    st.session_state.editando = None
                    st.success("✅ **Solicitação atualizada!**")
                    st.rerun()
            
            with col_finalizar:
                if st.button("✅ Finalizar Agora", key=f"fn_{i}", use_container_width=True):
                    item["Status"] = "Finalizada"
                    item["DataInicio"] = item.get("DataInicio") or date.today().strftime("%d/%m/%Y")
                    item["DataFim"] = date.today().strftime("%d/%m/%Y")
                    st.session_state.editando = None
                    st.success("✅ **Solicitação finalizada!**")
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

st.divider()
st.caption("🛠️ Sistema de Manutenção — Todas as solicitações nascem como **Pendente** e são editadas no painel ✏️")
