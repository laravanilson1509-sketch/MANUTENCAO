import streamlit as st
from datetime import date
from supabase import create_client

# ── SUPABASE (SECRETS) ─────────────────────────
SUPABASE_URL = "sua_chave"
SUPABASE_KEY = "sua_chave"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── CONFIG ─────────────────────────────────────
st.set_page_config(
    page_title="Plano de Manutenção",
    page_icon="🔧",
    layout="wide"
)

st.title("🔧 PLANO DE MANUTENÇÃO")

# ── FUNÇÕES ────────────────────────────────────
def carregar():
    response = supabase.table("solicitacoes").select("*").execute()
    st.write(response)
    return response.data

def carregar():
    try:
        response = supabase.table("solicitacoes").select("*").execute()
        return response.data
    except Exception as e:
        st.error(f"Erro Supabase: {e}")
        return []
# ── MÉTRICAS ───────────────────────────────────
dados = carregar()

col1, col2, col3, col4 = st.columns(4)

col1.metric("Total", len(dados))
col2.metric("Pendentes", sum(1 for d in dados if d["status"] == "Pendente"))
col3.metric("Andamento", sum(1 for d in dados if d["status"] == "Em andamento"))
col4.metric("Finalizadas", sum(1 for d in dados if d["status"] == "Finalizada"))

st.divider()

# ── FORMULÁRIO ─────────────────────────────────
st.subheader("📋 Nova Solicitação")

c1, c2, c3 = st.columns(3)

with c1:
    solicitador = st.text_input("Solicitador")
    maquina = st.text_input("Máquina")

with c2:
    prioridade = st.selectbox("Prioridade", ["Urgente", "Alta", "Média", "Baixa"])

with c3:
    descricao = st.text_area("Descrição")

if st.button("🚀 Registrar"):
    if maquina and descricao:
        inserir({
            "solicitador": solicitador,
            "maquina": maquina,
            "descricao": descricao,
            "data_solicitacao": date.today(),
            "data_inicio": None,
            "data_fim": None,
            "status": "Pendente",
            "prioridade": prioridade
        })
        st.success("✅ Salvo com sucesso!")
        st.rerun()
    else:
        st.error("Preencha os campos obrigatórios")

st.divider()

# ── LISTA ──────────────────────────────────────
st.subheader("📊 Fila de Manutenção")

dados = carregar()

if not dados:
    st.info("Nenhuma solicitação cadastrada.")
else:
    for item in dados:
        with st.container():
            st.markdown(f"### {item['descricao']}")

            st.write(f"👤 {item['solicitador']} | ⚙️ {item['maquina']}")
            st.write(f"🔥 {item['prioridade']} | 📌 {item['status']}")

            st.write(f"📅 Solicitação: {item['data_solicitacao']}")
            st.write(f"🟦 Início: {item['data_inicio'] or '-'}")
            st.write(f"🟥 Fim: {item['data_fim'] or '-'}")

            colA, colB, colC = st.columns(3)

            with colA:
                if st.button("▶️ Iniciar", key=f"iniciar_{item['id']}"):
                    atualizar(item["id"], {
                        "status": "Em andamento",
                        "data_inicio": date.today()
                    })
                    st.rerun()

            with colB:
                if st.button("✅ Finalizar", key=f"final_{item['id']}"):
                    atualizar(item["id"], {
                        "status": "Finalizada",
                        "data_fim": date.today()
                    })
                    st.rerun()

            with colC:
                if st.button("🗑️ Excluir", key=f"del_{item['id']}"):
                    deletar(item["id"])
                    st.rerun()

            st.divider()
