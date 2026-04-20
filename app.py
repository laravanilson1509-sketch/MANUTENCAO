import streamlit as st
import pandas as pd
from datetime import date, datetime
import os
import io
from supabase import create_client, Client

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Manutenção", layout="wide", page_icon="🔧")

# --- 2. CONEXÃO SEGURA (PADRONIZADA CLOUD/DESKTOP) ---
# O st.secrets funciona no Cloud (pelo painel) e no Desktop (pelo arquivo .streamlit/secrets.toml)
URL_RAW = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
KEY_RAW = st.secrets.get("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not URL_RAW or not KEY_RAW:
    st.error("## ❌ Credenciais não encontradas!")
    st.info("No Desktop: Verifique o arquivo .streamlit/secrets.toml. No Cloud: Verifique a aba Secrets.")
    st.stop()

# Limpeza para evitar o erro "Name or service not known"
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
