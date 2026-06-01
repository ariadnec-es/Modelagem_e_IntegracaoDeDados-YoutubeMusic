import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import re
import sqlite3
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "dados" / "youtube-top-100-songs-2025.csv"
DATA_DIR = BASE_DIR / "dados"
PLOT_COLORS = ["#2563eb", "#14b8a6", "#f97316", "#a855f7", "#ef4444", "#64748b"]

# Configuração da página
st.set_page_config(
    page_title="Sonora Dashboard",
    page_icon=str(BASE_DIR / "onda_sonora.png") if (BASE_DIR / "onda_sonora.png").exists() else "Sonora",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo customizado responsivo
st.markdown(
    """
    <style>
    :root { color-scheme: light; --sonora-blue: #2563eb; --sonora-teal: #14b8a6; --sonora-ink: #0f172a; }
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background: #f8fafc; color: #0f172a; }
    header, .css-18e3th9 { padding-top: 1.5rem; }
    section.main > div { padding-top: 1.4rem; }
    div.block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1460px; }
    [data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #e2e8f0; }
    [data-testid="stSidebar"] * { color: #0f172a; }
    [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p, label, .stRadio label, .stSelectbox label, .stTextInput label, .stNumberInput label {
        color: #0f172a;
    }
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
    }
    [data-testid="stMetric"] * { color: #0f172a; }
    div.stButton > button {
        background: #ffffff;
        color: #0f172a;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        font-weight: 700;
        border: 1px solid #cbd5e1;
        transition: all 0.2s;
    }
    div.stButton > button:hover { border-color: #2563eb; box-shadow: 0 8px 18px rgba(37, 99, 235, 0.14); }
    h1, h2, h3 { letter-spacing: 0; color: #0f172a; }
    .big-title { font-size: clamp(1.9rem, 4vw, 3rem); font-weight: 800; margin-bottom: 0.35rem; color: #ffffff; }
    .subtitle { color: #dbeafe; font-size: clamp(0.92rem, 2vw, 1.08rem); margin-top: 0.1rem; max-width: 900px; }
    .hero-box {
        background:
            linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(37, 99, 235, 0.9)),
            radial-gradient(circle at top right, rgba(20, 184, 166, 0.55), transparent 35%);
        color: #fff;
        border-radius: 8px;
        padding: 1.7rem 1.8rem;
        margin-bottom: 1.35rem;
        box-shadow: 0 18px 45px rgba(15, 23, 42, 0.18);
    }
    .insight-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #14b8a6;
        border-radius: 8px;
        padding: 0.9rem 1rem;
        margin: 0.35rem 0 1rem;
        color: #334155;
    }
    .db-note {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        color: #1e3a8a;
    }
    .stAlert { color: #0f172a; }
    @media (max-width: 768px) {
        div.block-container { padding-left: 0.5rem; padding-right: 0.5rem; }
        .big-title { font-size: 1.5rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Cabeçalho
st.markdown(
    """
    <div class="hero-box">
      <div class="big-title">Sonora Dashboard</div>
      <div class="subtitle">Sistema de gerenciamento de músicas e eventos para modelagem e integração de dados públicos</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================
# CARREGAMENTO DAS TABELAS CSV PARA HOSPEDAGEM
# ============================================
def ler_csv_tabela(nome_arquivo):
    """Lê CSVs exportados do banco, aceitando separador vírgula ou ponto e vírgula."""
    caminho = DATA_DIR / nome_arquivo
    if not caminho.exists():
        return pd.DataFrame()
    primeira_linha = caminho.read_text(encoding="utf-8-sig", errors="ignore").splitlines()[0]
    separador = ";" if primeira_linha.count(";") > primeira_linha.count(",") else ","
    try:
        return pd.read_csv(caminho, sep=separador, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(caminho, sep=separador, encoding="latin1")

@st.cache_resource
def get_connection():
    """Cria um SQLite em memória a partir dos CSVs em dados/, sem depender de MySQL local."""
    tabelas = {
        "youtube_hits_2025": "youtube_hits_2025.csv",
        "youtube_musics": "youtube_musics.csv",
        "events": "events.csv",
        "music_order": "music_order.csv",
    }

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.create_function("uuid", 0, lambda: str(uuid.uuid4()))

    for tabela, arquivo in tabelas.items():
        df = ler_csv_tabela(arquivo)
        if df.empty:
            df.to_sql(tabela, conn, index=False, if_exists="replace")
            continue

        for col in ["view_count", "duration", "channel_follower_count", "is_active", "order"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df.to_sql(tabela, conn, index=False, if_exists="replace")

    return conn

# ============================================
# FUNÇÕES DE VERIFICAÇÃO
# ============================================
# ============================================
# FUNÇÕES UTILITÁRIAS
# ============================================
def formatar_numero_grande(numero):
    """Formata números grandes em formato abreviado: 2000000 -> 2M."""
    if numero is None:
        return "0"

    numero = float(numero)
    abs_numero = abs(numero)
    if abs_numero >= 1_000_000_000:
        valor = f"{numero / 1_000_000_000:.1f}B"
    elif abs_numero >= 1_000_000:
        valor = f"{numero / 1_000_000:.1f}M"
    elif abs_numero >= 1_000:
        valor = f"{numero / 1_000:.1f}K"
    else:
        valor = f"{numero:.0f}"
    return valor.replace(".0", "")

def limpar_nome_musica(titulo):
    """Reduz títulos longos do YouTube para nomes mais legíveis nos gráficos."""
    texto = str(titulo or "").strip()
    texto = re.sub(r"\s*\([^)]*(official|video|audio|visualizer|lyrics|music video)[^)]*\)", "", texto, flags=re.I)
    texto = re.sub(r"\s*\[[^]]*(official|video|audio|visualizer|lyrics|music video)[^]]*\]", "", texto, flags=re.I)
    texto = re.sub(r"\s*-\s*(official\s*)?(music\s*)?(video|audio|visualizer|lyrics).*", "", texto, flags=re.I)
    texto = re.sub(r"\s+", " ", texto).strip(" -")

    if " - " in texto:
        partes = texto.split(" - ", 1)
        if len(partes[1]) >= 3:
            texto = partes[1].strip()

    return texto[:45] + "..." if len(texto) > 48 else texto

def normalizar_texto(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    texto = texto.lower()
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()

def detectar_generos_musicais(row):
    """Classifica uma música em um ou mais gêneros com curadoria e fallback por metadados."""
    titulo_norm = normalizar_texto(row.get("title", ""))
    canal_norm = normalizar_texto(row.get("channel", ""))
    texto = " ".join(
        str(row.get(col, "") or "")
        for col in ["title", "fulltitle", "description", "tags", "channel"]
    ).lower()
    texto_norm = normalizar_texto(texto)

    # Curadoria para faixas/artistas frequentes no dataset. A checagem acontece antes
    # do fallback para evitar erros como "k-pop" cair em Pop ou "Sapphire" cair só em acústico.
    generos_curados = [
        ("sapphire", ["Pop", "Folk-pop", "Balada romântica"]),
        ("enemy", ["Pop rock", "Pop rap", "Rock alternativo"]),
        ("apt", ["K-pop", "Pop rock", "Dance-pop"]),
        ("die with a smile", ["Pop", "Soul pop", "Balada romântica"]),
        ("leave me alone", ["Pop"]),
        ("mad", ["Pop"]),
        ("birds of a feather", ["Pop alternativo", "Dream pop"]),
        ("espresso", ["Pop", "Dance-pop"]),
        ("abracadabra", ["Dance-pop", "Synth-pop"]),
        ("blue", ["Indie pop", "Bedroom pop"]),
        ("wildflower", ["Pop alternativo", "Balada"]),
        ("how it s going", ["Hip-hop/Rap"]),
        ("ordinary", ["Pop", "Balada"]),
        ("luther", ["Hip-hop/Rap", "R&B"]),
        ("a bar song", ["Country", "Country rap", "Pop"]),
        ("not like us", ["Hip-hop/Rap", "West Coast rap"]),
        ("born again", ["K-pop", "Dance-pop", "Pop rap"]),
        ("vent", ["Dancehall", "Reggae"]),
        ("messy", ["Soul pop", "Indie pop"]),
        ("bad dreams", ["Soul", "Pop"]),
        ("extral", ["K-pop", "Hip-hop/Rap"]),
        ("please please please", ["Pop", "Country pop"]),
        ("sunset", ["Hip-hop/Rap"]),
        ("million dollar baby", ["R&B", "Funk", "Pop rap"]),
        ("manchild", ["Pop", "Country pop"]),
        ("anxiety", ["Hip-hop/Rap", "R&B"]),
        ("move", ["Afro house", "Dance/Eletrônica"]),
        ("afro disco", ["Afrobeat", "Dance/Eletrônica"]),
        ("chihiro", ["Pop alternativo", "Electropop"]),
        ("taste", ["Pop", "Dance-pop"]),
        ("i had some help", ["Country pop", "Pop rock"]),
        ("that s so true", ["Pop", "Folk-pop"]),
        ("night skies", ["R&B", "Pop"]),
        ("alibi", ["Alternative R&B", "Latin pop"]),
        ("stargazing", ["Folk-pop", "Pop"]),
        ("number one girl", ["K-pop", "Pop", "Balada"]),
        ("squabble up", ["Hip-hop/Rap"]),
        ("sally when the wine runs out", ["Indie pop", "Pop rock"]),
        ("toxic till the end", ["K-pop", "Pop rock"]),
        ("good luck babe", ["Synth-pop", "Pop"]),
        ("new woman", ["K-pop", "Latin pop", "Dance-pop"]),
        ("azizam", ["Pop", "Folk-pop"]),
        ("the real thing", ["R&B", "Soul"]),
        ("back to friends", ["Indie pop", "Pop alternativo"]),
        ("made me a man", ["Pop", "R&B"]),
        ("beautiful people", ["Dance-pop", "Dance/Eletrônica"]),
        ("sao paulo", ["R&B", "Funk brasileiro", "Dance-pop"]),
        ("wiickedest", ["R&B", "Dancehall"]),
        ("i don t wanna wait", ["Dance-pop", "Dance/Eletrônica"]),
        ("nokia", ["Hip-hop/Rap", "Pop rap"]),
        ("cry for me", ["R&B", "Synth-pop"]),
        ("sports car", ["Pop", "Dance-pop"]),
        ("rather be", ["R&B", "Soul"]),
        ("slow it down", ["Pop rock", "Balada"]),
        ("just keep watching", ["Pop", "Dance-pop"]),
        ("guess", ["Hyperpop", "Dance-pop"]),
        ("carry you home", ["Pop", "Folk-pop"]),
        ("you", ["R&B"]),
        ("priceless", ["Pop", "K-pop"]),
        ("with you", ["Pop", "Balada"]),
        ("mystical magical", ["Pop rock", "Pop"]),
        ("revolving door", ["Pop", "Dance-pop"]),
        ("fortnight", ["Synth-pop", "Pop alternativo"]),
        ("money feat dorty", ["Afrobeats", "Hip-hop/Rap"]),
        ("feel it", ["Alternative R&B", "Pop alternativo"]),
        ("born with a broken heart", ["Pop rock", "Balada"]),
        ("up next", ["Hip-hop/Rap"]),
        ("handlebars", ["K-pop", "Pop"]),
        ("capris", ["Indie pop", "Alt-pop"]),
        ("end of the world", ["Pop rock", "Pop"]),
        ("love me not", ["R&B", "Soul"]),
        ("it s ok i m ok", ["Pop", "Dance-pop"]),
        ("nice to meet you", ["Folk-pop", "Pop"]),
        ("candy", ["Pop", "Alt-pop"]),
        ("disease", ["Dance-pop", "Dark pop"]),
        ("push 2 start", ["Afrobeats", "Pop"]),
        ("all my love", ["Pop rock", "Soft rock"]),
        ("mantra", ["K-pop", "Dance-pop"]),
        ("open hearts", ["R&B", "Synth-pop"]),
        ("revenge", ["Alternative hip-hop", "Rap"]),
        ("take me to the beach", ["Pop rock", "Rock alternativo", "J-pop"]),
        ("daisies", ["Pop", "R&B"]),
        ("bed chem", ["Pop", "R&B"]),
        ("illusion", ["Dance-pop", "Nu-disco"]),
        ("busy woman", ["Pop"]),
        ("diet pepsi", ["Pop", "Dance-pop"]),
        ("stars n stripes", ["Hip-hop/Rap"]),
        ("juno", ["Pop"]),
        ("forever young", ["Dance-pop", "Dance/Eletrônica"]),
        ("soft spot", ["Pop", "R&B"]),
        ("dynamite", ["Afrobeats", "Pop"]),
        ("intro end of the world", ["Pop", "R&B"]),
        ("heroes", ["Pop", "Dance/Eletrônica"]),
        ("guilty as sin", ["Pop", "Folk-pop"]),
        ("sunset blvd", ["Pop"]),
        ("yukon", ["Pop", "R&B"]),
        ("twilight zone", ["Pop", "R&B"]),
        ("i love you i m sorry", ["Pop", "Folk-pop"]),
        ("miami", ["Hip-hop/Rap"]),
        ("let it talk to me", ["Dancehall", "Pop"]),
        ("how does it feel to be forgotten", ["Pop"]),
    ]

    for chave, generos in generos_curados:
        if chave in titulo_norm:
            return generos

    if "ed sheeran" in canal_norm:
        return ["Pop", "Folk-pop"]
    if "imagine" in canal_norm:
        return ["Pop rock", "Rock alternativo"]
    if "rose" in canal_norm or "lloud" in canal_norm or "jennie" in canal_norm:
        return ["K-pop", "Pop"]
    if "kendrick" in canal_norm or "drake" in canal_norm or "doechii" in canal_norm:
        return ["Hip-hop/Rap"]
    if "sabrina carpenter" in canal_norm or "lady gaga" in canal_norm:
        return ["Pop", "Dance-pop"]
    if "billie eilish" in canal_norm:
        return ["Pop alternativo"]
    if "tate mcrae" in canal_norm or "dua lipa" in canal_norm:
        return ["Pop", "Dance-pop"]
    if "the weeknd" in canal_norm or "giveon" in canal_norm or "roy woods" in canal_norm:
        return ["R&B", "Pop"]

    generos = [
        ("K-pop", ["k pop", "kpop", "blackpink", "bts", "rose", "yg entertainment"]),
        ("Hip-hop/Rap", ["hip hop", "hip hop rap", "rap", "trap", "kendrick", "drake", "eminem"]),
        ("R&B", ["r b", "rnb", "rhythm and blues", "bruno mars", "sza"]),
        ("Afrobeats", ["afrobeats", "afrobeat"]),
        ("Dancehall", ["dancehall"]),
        ("Reggae", ["reggae"]),
        ("Country", ["country", "shaboozey"]),
        ("Dance/Eletrônica", ["dance", "electronic", "eletronica", "edm", "house"]),
        ("Pop", ["pop", "sabrina carpenter", "lady gaga", "billie eilish", "taylor swift"]),
        ("Rock", ["rock", "guitar rock"]),
        ("Funk", ["funk", "funk brasileiro", "funk carioca"]),
        ("Metal", ["metal", "heavy metal"]),
        ("Alternativo", ["alternative", "alternativo", "indie", "alt pop"]),
        ("Gospel", ["gospel", "worship", "christian"]),
        ("Blues", ["blues"]),
        ("Jazz", ["jazz"]),
    ]

    encontrados = []
    for genero, termos in generos:
        if any(termo in texto_norm for termo in termos):
            encontrados.append(genero)

    return encontrados[:3] if encontrados else ["Não identificado"]

def genero_principal(generos):
    return generos[0] if generos else "Não identificado"

def agrupar_genero(genero):
    """Agrupa subgêneros em famílias principais para manter os gráficos legíveis."""
    genero = str(genero or "Não identificado")
    mapa = {
        "Pop": [
            "Pop", "Dance-pop", "Synth-pop", "Dream pop", "Soul pop", "Dark pop",
            "Alt-pop", "Hyperpop", "Latin pop", "Country pop", "Pop rap"
        ],
        "Hip-hop/Rap": [
            "Hip-hop/Rap", "Rap", "West Coast rap", "Alternative hip-hop", "Country rap"
        ],
        "R&B/Soul": [
            "R&B", "Soul", "Alternative R&B"
        ],
        "Rock/Alternativo": [
            "Rock", "Pop rock", "Rock alternativo", "Soft rock", "Alternativo",
            "Pop alternativo", "Indie pop", "Bedroom pop", "Metal"
        ],
        "K-pop": ["K-pop", "J-pop"],
        "Country/Folk": ["Country", "Folk-pop", "Balada", "Balada romântica"],
        "Dance/Eletrônica": ["Dance/Eletrônica", "Afro house", "Nu-disco"],
        "Afro/Reggae/Dancehall": [
            "Afrobeats", "Afrobeat", "Dancehall", "Reggae", "Funk brasileiro"
        ],
        "Blues/Jazz/Gospel": ["Blues", "Jazz", "Gospel"],
    }

    for grupo, generos in mapa.items():
        if genero in generos:
            return grupo
    return "Outros"

def agrupar_generos(generos):
    grupos = []
    for genero in generos or []:
        grupo = agrupar_genero(genero)
        if grupo not in grupos:
            grupos.append(grupo)
    return grupos or ["Outros"]

@st.cache_data
def carregar_youtube_csv():
    """Carrega o dataset público usado nas análises exploratórias."""
    if not CSV_PATH.exists():
        return pd.DataFrame()

    df = pd.read_csv(CSV_PATH)
    for col in ["view_count", "duration", "channel_follower_count"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "duration" in df.columns:
        df["duration_min"] = df["duration"] / 60

    df["musical_genres"] = df.apply(detectar_generos_musicais, axis=1)
    df["musical_genre"] = df["musical_genres"].apply(genero_principal)
    df["musical_genre_groups"] = df["musical_genres"].apply(agrupar_generos)
    df["musical_genre_group"] = df["musical_genre"].apply(agrupar_genero)

    if "title" in df.columns:
        df["is_collaboration"] = df["title"].fillna("").apply(eh_colaboracao)
        df["tipo_musica"] = np.where(df["is_collaboration"], "Colaboração", "Solo")

    return df

def eh_colaboracao(title):
    """Heurística simples para diferenciar faixas solo de colaborações pelo título."""
    texto = f" {str(title).lower()} "
    marcadores = [" ft ", " ft.", " feat ", " feat.", " featuring ", " x ", " with ", " & ", ","]
    return any(marcador in texto for marcador in marcadores)

def estilizar_figura(fig, height=430, show_legend=True):
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=20, r=20, t=105, b=80 if show_legend else 45),
        font=dict(family="Arial, sans-serif", color="#0f172a"),
        title=dict(y=0.98, yanchor="top", x=0.02, xanchor="left", pad=dict(b=22)),
        title_font=dict(size=18, color="#0f172a"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="top", y=-0.14, xanchor="left", x=0) if show_legend else None,
    )
    fig.update_xaxes(showgrid=True, gridcolor="#e2e8f0", zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#e2e8f0", zeroline=False)
    return fig

def abreviar_eixo_views(fig, eixo="y"):
    if eixo == "x":
        fig.update_xaxes(tickformat=".2s")
    else:
        fig.update_yaxes(tickformat=".2s")
    return fig

def tabela_existe(conn, nome_tabela):
    """Verifica se uma tabela ou view existe no banco"""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (nome_tabela,),
    )
    resultado = cursor.fetchone()
    cursor.close()
    return resultado is not None


# ============================================
# MENU LATERAL
# ============================================
if (BASE_DIR / "onda_sonora.png").exists():
    st.sidebar.image(str(BASE_DIR / "onda_sonora.png"), width=100)
    st.sidebar.markdown("### Sonora Dashboard")
else:
    st.sidebar.title("Sonora Dashboard")

st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "Navegação",
    ["Dashboard Principal", "Gerenciar Músicas", "Gerenciar Eventos", "Registrar Pedido"],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.info(
    """
    **Projeto:** Modelagem e Integração com Dados Públicos  
    **Disciplina:** Banco de Dados  
    **Tema:** Música e eventos com dados públicos de YouTube  
    **Base:** Streamlit + CSV Público
    """
)

# ============================================
# 1. DASHBOARD PRINCIPAL
# ============================================
if menu == "Dashboard Principal":
    st.header("Dashboard de Análise")
    
    conn = get_connection()
    if conn is None:
        st.stop()
    
    # ========================================
    # MÉTRICAS PRINCIPAIS
    # ========================================
    st.subheader("Métricas do Sistema")
    
    cursor = conn.cursor()
    
    # Contagem de registros
    cursor.execute("SELECT COUNT(*) FROM youtube_musics")
    total_musicas = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM youtube_hits_2025")
    total_youtube = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM events")
    total_eventos = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM music_order")
    total_pedidos = cursor.fetchone()[0]
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Músicas no Catálogo", formatar_numero_grande(total_musicas))
    with col2:
        st.metric("Dados YouTube", formatar_numero_grande(total_youtube))
    with col3:
        st.metric("Eventos Cadastrados", formatar_numero_grande(total_eventos))
    with col4:
        st.metric("Pedidos de Música", formatar_numero_grande(total_pedidos))

    st.markdown("---")

    st.subheader("Arquitetura do Banco de Dados")
    st.markdown(
        """
        <div class="db-note">
        Visão lógica das principais entidades do Sonora: catálogo, dados públicos do YouTube,
        eventos e pedidos de música.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.graphviz_chart(
        """
        digraph sonora_db {
            graph [rankdir=LR, bgcolor="transparent", pad="0.35", nodesep="0.55", ranksep="0.8"];
            node [shape=record, style="rounded,filled", fillcolor="#ffffff", color="#94a3b8", penwidth=1.4, fontname="Arial", fontsize=11];
            edge [color="#2563eb", penwidth=1.4, arrowsize=0.8, fontname="Arial", fontsize=10];

            youtube_hits_2025 [
                label="{youtube_hits_2025|title\\lview_count\\lyoutube_category\\lduration\\lchannel\\lchannel_follower_count\\l}"
            ];
            youtube_musics [
                label="{youtube_musics|id PK\\lname\\lsinger\\lurl\\lis_active\\l}"
            ];
            events [
                label="{events|id PK\\levent_name\\llocation\\lstart_date\\lend_date\\lis_active\\l}"
            ];
            music_order [
                label="{music_order|id PK\\lmusic_id FK\\levent_id FK\\lorder\\lstatus\\lcategory\\lis_active\\l}"
            ];

            youtube_hits_2025 -> youtube_musics [style=dashed, label="inspira/importa catálogo"];
            youtube_musics -> music_order [label="1:N"];
            events -> music_order [label="1:N"];
        }
        """,
        use_container_width=True,
    )
    
    st.markdown("---")
    
    # ========================================
    # ANÁLISE DOS DADOS DO YOUTUBE
    # ========================================
    st.subheader("Análise dos Dados Públicos do YouTube")
    
    # Estatísticas das views
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            MAX(view_count) as max_views,
            MIN(view_count) as min_views,
            AVG(view_count) as avg_views,
            SUM(view_count) as sum_views
        FROM youtube_hits_2025
        WHERE view_count > 0
    """)
    stats = cursor.fetchone()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total de Músicas", formatar_numero_grande(stats[0]))
    with col2:
        st.metric("Maior Views", formatar_numero_grande(stats[1]))
    with col3:
        st.metric("Menor Views", formatar_numero_grande(stats[2]))
    with col4:
        st.metric("Média Views", formatar_numero_grande(stats[3]))
    with col5:
        st.metric("Total Views", formatar_numero_grande(stats[4]))
    
    # Gráfico Top 10 YouTube
    top10 = pd.read_sql("""
        SELECT title, view_count 
        FROM youtube_hits_2025 
        ORDER BY view_count DESC 
        LIMIT 10
    """, conn)
    
    top10["musica_curta"] = top10["title"].apply(limpar_nome_musica)

    fig = px.bar(top10, x='musica_curta', y='view_count', 
                 title="Top 10 Músicas Mais Vistas no YouTube",
                 labels={'musica_curta': 'Música', 'view_count': 'Visualizações'},
                 color='view_count',
                 color_continuous_scale='Teal')
    fig.update_layout(xaxis_tickangle=-35)
    estilizar_figura(fig, height=500, show_legend=False)
    abreviar_eixo_views(fig)
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # ========================================
    # ANÁLISES ADICIONAIS DOS DADOS PÚBLICOS
    # ========================================
    st.subheader("Insights Adicionais do Dataset Público")
    
    # Análise de distribuição por faixas de views
    try:
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN view_count >= 1000000 THEN '1 Milhão+'
                    WHEN view_count >= 500000 THEN '500K - 1M'
                    WHEN view_count >= 100000 THEN '100K - 500K'
                    WHEN view_count >= 50000 THEN '50K - 100K'
                    WHEN view_count >= 10000 THEN '10K - 50K'
                    ELSE 'Menos de 10K'
                END as faixa_views,
                COUNT(*) as quantidade
            FROM youtube_hits_2025
            GROUP BY faixa_views
            ORDER BY view_count DESC
        """)
        
        dist_data = cursor.fetchall()
        if dist_data:
            dist_df = pd.DataFrame(dist_data, columns=['faixa_views', 'quantidade'])
            
            col1, col2 = st.columns(2)
            
            with col1:
                fig_dist_pie = px.pie(dist_df, values='quantidade', names='faixa_views',
                                      title="Distribuição de Música por Faixa de Views",
                                      hole=0.45,
                                      color_discrete_sequence=PLOT_COLORS)
                estilizar_figura(fig_dist_pie, show_legend=True)
                st.plotly_chart(fig_dist_pie, use_container_width=True)
            
            with col2:
                fig_dist_bar = px.bar(dist_df, x='faixa_views', y='quantidade',
                                     title="Quantidade de Músicas por Faixa",
                                     labels={'faixa_views': 'Faixa de Views', 'quantidade': 'Quantidade'},
                                     color='quantidade',
                                     color_continuous_scale='Teal')
                fig_dist_bar.update_layout(xaxis_tickangle=-35)
                estilizar_figura(fig_dist_bar, show_legend=False)
                st.plotly_chart(fig_dist_bar, use_container_width=True)
    except Exception as e:
        st.warning(f"Não foi possível carregar análise de distribuição: {e}")
    
    st.markdown("---")

    # ========================================
    # ANÁLISES DO CSV YOUTUBE TOP 100 2025
    # ========================================
    st.subheader("Análises Gráficas do CSV YouTube Top 100 Songs 2025")

    youtube_df = carregar_youtube_csv()
    if youtube_df.empty:
        st.warning("CSV público não encontrado em dados/youtube-top-100-songs-2025.csv.")
    else:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Faixas no CSV", len(youtube_df))
        with col2:
            st.metric("Canais únicos", youtube_df["channel"].nunique() if "channel" in youtube_df else 0)
        with col3:
            media_duracao = youtube_df["duration_min"].mean() if "duration_min" in youtube_df else 0
            st.metric("Duração média", f"{media_duracao:.1f} min")
        with col4:
            total_views_csv = youtube_df["view_count"].sum() if "view_count" in youtube_df else 0
            st.metric("Views no CSV", formatar_numero_grande(total_views_csv))

        st.markdown("##### Dominância por Canal/Artista")
        canais = (
            youtube_df.groupby("channel", as_index=False)
            .agg(musicas=("title", "count"), views_totais=("view_count", "sum"))
            .sort_values(["musicas", "views_totais"], ascending=[False, False])
            .head(15)
            .sort_values("musicas")
        )
        fig_canais = px.bar(
            canais,
            x="musicas",
            y="channel",
            orientation="h",
            title="Músicas por Canal/Artista no Top 100",
            labels={"musicas": "Quantidade de músicas", "channel": "Canal/Artista"},
            color="views_totais",
            color_continuous_scale="Teal",
            hover_data={"views_totais": ":,.0f"},
        )
        estilizar_figura(fig_canais, height=520, show_legend=False)
        st.plotly_chart(fig_canais, use_container_width=True)
        st.markdown(
            "<div class='insight-card'>Insight: canais com várias entradas no ranking indicam artistas mais dominantes no recorte do YouTube 2025.</div>",
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2)
        with col1:
            fig_duracao = px.scatter(
                youtube_df,
                x="duration_min",
                y="view_count",
                size="channel_follower_count",
                color="musical_genre_group",
                title="Duração das Músicas vs Popularidade",
                labels={
                    "duration_min": "Duração (minutos)",
                    "view_count": "Visualizações",
                    "channel_follower_count": "Seguidores",
                    "musical_genre_group": "Gênero principal",
                },
                hover_name="title",
                color_discrete_sequence=PLOT_COLORS,
            )
            estilizar_figura(fig_duracao, height=480)
            abreviar_eixo_views(fig_duracao)
            st.plotly_chart(fig_duracao, use_container_width=True)

        with col2:
            generos = youtube_df[["title", "musical_genre_groups"]].explode("musical_genre_groups")
            generos = generos["musical_genre_groups"].value_counts().reset_index()
            generos.columns = ["musical_genre", "quantidade"]
            fig_generos = px.pie(
                generos,
                names="musical_genre",
                values="quantidade",
                title="Principais Gêneros Musicais",
                hole=0.55,
                color_discrete_sequence=PLOT_COLORS,
            )
            estilizar_figura(fig_generos, height=480)
            st.plotly_chart(fig_generos, use_container_width=True)
            st.caption(
                "A coluna categories do CSV é uma categoria do YouTube, como Music ou People & Blogs. "
                "Este gráfico agrupa subgêneros em famílias principais para facilitar a leitura."
            )

        st.markdown("##### Correlação entre Canal e Sucesso da Música")
        corr_df = youtube_df[
            (youtube_df["channel_follower_count"] > 0) & (youtube_df["view_count"] > 0)
        ].copy()
        fig_corr = px.scatter(
            corr_df,
            x="channel_follower_count",
            y="view_count",
            color="musical_genre_group",
            size="duration",
            title="Views vs Seguidores do Canal",
            labels={
                "channel_follower_count": "Seguidores do canal",
                "view_count": "Visualizações da música",
                "musical_genre_group": "Gênero principal",
                "duration": "Duração (s)",
            },
            hover_name="title",
            color_discrete_sequence=PLOT_COLORS,
        )
        if len(corr_df) >= 2:
            coef = np.polyfit(corr_df["channel_follower_count"], corr_df["view_count"], 1)
            x_linha = np.linspace(corr_df["channel_follower_count"].min(), corr_df["channel_follower_count"].max(), 100)
            y_linha = coef[0] * x_linha + coef[1]
            fig_corr.add_trace(
                go.Scatter(
                    x=x_linha,
                    y=y_linha,
                    mode="lines",
                    name="Linha de tendência",
                    line=dict(color="#0f172a", width=3),
                )
            )
        estilizar_figura(fig_corr, height=500)
        abreviar_eixo_views(fig_corr, "x")
        abreviar_eixo_views(fig_corr)
        st.plotly_chart(fig_corr, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            comparativo = (
                youtube_df.groupby("tipo_musica", as_index=False)
                .agg(
                    musicas=("title", "count"),
                    media_views=("view_count", "mean"),
                    mediana_views=("view_count", "median"),
                )
            )
            fig_colab = px.bar(
                comparativo,
                x="tipo_musica",
                y=["media_views", "mediana_views"],
                barmode="group",
                title="Músicas Solo vs Colaborações",
                labels={"tipo_musica": "Tipo", "value": "Visualizações", "variable": "Métrica"},
                color_discrete_sequence=["#2563eb", "#14b8a6"],
            )
            fig_colab.update_layout(legend_title_text="")
            estilizar_figura(fig_colab, height=430)
            abreviar_eixo_views(fig_colab)
            st.plotly_chart(fig_colab, use_container_width=True)

        with col2:
            data_cols = [col for col in youtube_df.columns if col.lower() in ["release_date", "released_at", "upload_date", "date", "published_at"]]
            if data_cols:
                data_col = data_cols[0]
                periodo_df = youtube_df.copy()
                periodo_df[data_col] = pd.to_datetime(periodo_df[data_col], errors="coerce")
                periodo_df = periodo_df.dropna(subset=[data_col])
                periodo_df["periodo"] = periodo_df[data_col].dt.to_period("M").astype(str)
                periodo = periodo_df.groupby("periodo", as_index=False).size()
                fig_periodo = px.line(
                    periodo,
                    x="periodo",
                    y="size",
                    markers=True,
                    title="Lançamentos por Período",
                    labels={"periodo": "Período", "size": "Quantidade de músicas"},
                )
                estilizar_figura(fig_periodo, height=430, show_legend=False)
                st.plotly_chart(fig_periodo, use_container_width=True)

        st.markdown(
            "<div class='insight-card'>Insight: os gráficos ajudam a comparar alcance do canal, formato da faixa e categoria musical com o desempenho em visualizações.</div>",
            unsafe_allow_html=True,
        )
    
    # Comparativo removido para manter foco nas análises principais
    st.markdown("---")
    
    # ========================================
    # ANÁLISE: PEDIDOS vs POPULARIDADE YOUTUBE
    # ========================================
    st.subheader("Análise: Músicas Mais Solicitadas vs Mais Vistas no YouTube")
    
    try:
        # Comparação: músicas mais solicitadas vs mais vistas no YouTube
        col1, col2 = st.columns(2)
        
        with col1:
            # Top 10 músicas mais solicitadas
            musicas_solicitadas = pd.read_sql("""
                SELECT 
                    m.name AS musica,
                    m.singer AS artista,
                    COUNT(mo.id) AS total_pedidos
                FROM music_order mo
                JOIN youtube_musics m ON mo.music_id = m.id
                GROUP BY mo.music_id, m.name, m.singer
                ORDER BY total_pedidos DESC
                LIMIT 10
            """, conn)
            
            if len(musicas_solicitadas) > 0:
                musicas_solicitadas["musica_curta"] = musicas_solicitadas["musica"].apply(limpar_nome_musica)
                fig_mais_pedidas = px.bar(
                    musicas_solicitadas,
                    x='musica_curta',
                    y='total_pedidos',
                    title="Top 10 Músicas Mais Solicitadas",
                    labels={'musica_curta': 'Música', 'total_pedidos': 'Pedidos'},
                    color='total_pedidos',
                    color_continuous_scale='Teal'
                )
                fig_mais_pedidas.update_layout(xaxis_tickangle=-35)
                estilizar_figura(fig_mais_pedidas, height=400, show_legend=False)
                st.plotly_chart(fig_mais_pedidas, use_container_width=True)
            else:
                st.info("Ainda não há pedidos de música.")
        
        with col2:
            # Top 10 músicas mais vistas do YouTube (do catálogo)
            musicas_mais_vistas = pd.read_sql("""
                SELECT 
                    yh.title AS musica,
                    yh.view_count AS views
                FROM youtube_hits_2025 yh
                ORDER BY yh.view_count DESC
                LIMIT 10
            """, conn)
            
            if len(musicas_mais_vistas) > 0:
                musicas_mais_vistas["musica_curta"] = musicas_mais_vistas["musica"].apply(limpar_nome_musica)
                fig_mais_vistas = px.bar(
                    musicas_mais_vistas,
                    x='musica_curta',
                    y='views',
                    title="Top 10 Músicas Mais Vistas no YouTube",
                    labels={'musica_curta': 'Música', 'views': 'Visualizações'},
                    color='views',
                    color_continuous_scale='Teal'
                )
                fig_mais_vistas.update_layout(xaxis_tickangle=-35)
                estilizar_figura(fig_mais_vistas, height=400, show_legend=False)
                abreviar_eixo_views(fig_mais_vistas)
                st.plotly_chart(fig_mais_vistas, use_container_width=True)
    
    except Exception as e:
        st.warning(f"Não foi possível carregar comparação: {e}")
    
    st.markdown("---")
    
    # ========================================
    # ANÁLISE: EFETIVIDADE DO CATÁLOGO
    # ========================================
    st.subheader("Análise de Efetividade do Catálogo")
    
    try:
        # Estatísticas de uso do catálogo
        total_musicas_catalogo = int(total_musicas)
        musicas_solicitadas_count = int(pd.read_sql(
            "SELECT COUNT(DISTINCT music_id) FROM music_order", conn
        ).iloc[0, 0])
        
        musicas_nao_solicitadas = total_musicas_catalogo - musicas_solicitadas_count
        percentual_uso = (musicas_solicitadas_count / total_musicas_catalogo * 100) if total_musicas_catalogo > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Músicas no Catálogo", total_musicas_catalogo)
        
        with col2:
            st.metric("Músicas Solicitadas", musicas_solicitadas_count)
        
        with col3:
            st.metric("Não Solicitadas", musicas_nao_solicitadas)
        
        with col4:
            st.metric("Taxa de Uso", f"{percentual_uso:.1f}%")
        
        # Gráfico da cobertura
        cobertura_data = pd.DataFrame({
            'status': ['Solicitadas', 'Não Solicitadas'],
            'quantidade': [musicas_solicitadas_count, musicas_nao_solicitadas]
        })
        
        fig_cobertura = px.pie(
            cobertura_data,
            values='quantidade',
            names='status',
            title="Cobertura do Catálogo (Taxa de Solicitação)",
            color_discrete_sequence=['#2563eb', '#e5e7eb']
        )
        estilizar_figura(fig_cobertura)
        st.plotly_chart(fig_cobertura, use_container_width=True)
    
    except Exception as e:
        st.warning(f"Não foi possível carregar análise de efetividade: {e}")
    
    st.markdown("---")
    
    # Análise de status removida para simplificar o dashboard
    st.markdown("---")
    
    # ========================================
    # ANÁLISE DOS PEDIDOS POR EVENTO
    # ========================================
    st.subheader("Análise de Pedidos por Evento")
    
    pedidos_evento = pd.read_sql("""
        SELECT 
            e.event_name AS evento,
            COUNT(mo.id) AS total_pedidos,
            COUNT(CASE WHEN mo.category = 'interactive' THEN 1 END) AS interativas,
            COUNT(CASE WHEN mo.category = 'background' THEN 1 END) AS background
        FROM music_order mo
        JOIN events e ON mo.event_id = e.id
        GROUP BY e.id, e.event_name
        ORDER BY total_pedidos DESC
    """, conn)
    
    if len(pedidos_evento) > 0:
        col1, col2 = st.columns(2)
        
        with col1:
            fig2 = px.bar(pedidos_evento, x='evento', y='total_pedidos',
                          title="Pedidos por Evento",
                          labels={'evento': 'Evento', 'total_pedidos': 'Número de Pedidos'},
                          color='total_pedidos',
                          color_continuous_scale='Teal')
            fig2.update_layout(xaxis_tickangle=-35)
            estilizar_figura(fig2, height=400, show_legend=False)
            st.plotly_chart(fig2, use_container_width=True)
        
        with col2:
            # Distribuição por categoria
            total_interativas = pedidos_evento['interativas'].sum()
            total_background = pedidos_evento['background'].sum()
            
            categorias_df = pd.DataFrame({
                'Categoria': ['Interativas', 'Background'],
                'Total': [total_interativas, total_background]
            })
            
            fig3 = px.pie(categorias_df, values='Total', names='Categoria',
                          title="Distribuição por Tipo de Pedido",
                          color_discrete_sequence=['#2563eb', '#94a3b8'])
            estilizar_figura(fig3)
            st.plotly_chart(fig3, use_container_width=True)
        
        # Tabela detalhada
        st.subheader("Detalhamento dos Pedidos")
        st.dataframe(pedidos_evento, use_container_width=True)
    else:
        st.info("Nenhum pedido registrado ainda. Use o menu 'Registrar Pedido' para adicionar.")
    
    st.markdown("---")
    
    # ========================================
    # LISTA DE PEDIDOS REGISTRADOS
    # ========================================
    st.subheader("Pedidos de Música Registrados")
    
    pedidos_detalhados = pd.read_sql("""
        SELECT 
            e.event_name AS evento,
            m.name AS musica,
            m.singer AS artista,
            mo.order AS posicao,
            mo.category AS tipo,
            mo.status AS situacao
        FROM music_order mo
        JOIN events e ON mo.event_id = e.id
        JOIN youtube_musics m ON mo.music_id = m.id
        ORDER BY e.event_name, mo.order
    """, conn)
    
    if len(pedidos_detalhados) > 0:
        st.dataframe(pedidos_detalhados, use_container_width=True)
        
        # Download dos dados
        csv = pedidos_detalhados.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Baixar relatório de pedidos (CSV)",
            data=csv,
            file_name="relatorio_pedidos_sonora.csv",
            mime="text/csv",
        )
    else:
        st.info("Nenhum pedido registrado ainda.")
    
    conn.close()

# ============================================
# 2. GERENCIAR MÚSICAS (CRUD)
# ============================================
elif menu == "Gerenciar Músicas":
    st.header("Gerenciar Catálogo de Músicas")
    
    conn = get_connection()
    if conn is None:
        st.stop()
    
    tab1, tab2, tab3, tab4 = st.tabs(["Listar Músicas", "Adicionar Música", "Editar Música", "Remover Música"])
    
    with tab1:
        st.subheader("Músicas Cadastradas")
        musicas = pd.read_sql("""
            SELECT id, name AS música, singer AS artista, url, is_active AS ativo 
            FROM youtube_musics 
            ORDER BY name
        """, conn)
        if len(musicas) > 0:
            st.dataframe(musicas, use_container_width=True)
            st.caption(f"Total de músicas: {len(musicas)}")
        else:
            st.info("Nenhuma música cadastrada ainda.")
    
    with tab2:
        st.subheader("Adicionar Nova Música")
        with st.form("nova_musica", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                nome = st.text_input("Nome da Música*")
                artista = st.text_input("Artista/Banda*")
            with col2:
                url = st.text_input("URL do YouTube")
            
            submitted = st.form_submit_button("Salvar Música", type="primary")
            
            if submitted:
                if nome and artista:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO youtube_musics (id, name, singer, url, is_active)
                        VALUES (uuid(), ?, ?, ?, TRUE)
                    """, (nome, artista, url))
                    conn.commit()
                    st.success(f"Música '{nome}' adicionada com sucesso.")
                    st.rerun()
                else:
                    st.error("Nome e Artista são obrigatórios.")
    
    with tab3:
        st.subheader("Editar Música")
        musicas_edicao = pd.read_sql("SELECT id, name, singer FROM youtube_musics ORDER BY name", conn)
        if len(musicas_edicao) > 0:
            musica_editar = st.selectbox(
                "Selecione a música para editar",
                musicas_edicao['id'],
                format_func=lambda x: f"{musicas_edicao[musicas_edicao['id']==x]['name'].iloc[0]} - {musicas_edicao[musicas_edicao['id']==x]['singer'].iloc[0]}",
                key="select_musica_edit"
            )
            
            # Buscar dados da música selecionada
            musica_selecionada = pd.read_sql(
                "SELECT name, singer, url FROM youtube_musics WHERE id = ?",
                conn,
                params=(musica_editar,)
            ).iloc[0]
            
            with st.form("editar_musica", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    novo_nome = st.text_input("Nome da Música", value=musica_selecionada['name'])
                    novo_artista = st.text_input("Artista/Banda", value=musica_selecionada['singer'])
                with col2:
                    nova_url = st.text_input("URL do YouTube", value=musica_selecionada['url'] if musica_selecionada['url'] else "")
                
                submitted = st.form_submit_button("Salvar Alterações", type="primary")
                
                if submitted:
                    if novo_nome and novo_artista:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE youtube_musics
                            SET name = ?, singer = ?, url = ?
                            WHERE id = ?
                        """, (novo_nome, novo_artista, nova_url, musica_editar))
                        conn.commit()
                        st.success("Música atualizada com sucesso.")
                        st.rerun()
                    else:
                        st.error("Nome e Artista são obrigatórios.")
        else:
            st.info("Nenhuma música cadastrada para editar.")
    
    with tab4:
        st.subheader("Remover Música")
        musicas_lista = pd.read_sql("SELECT id, name, singer FROM youtube_musics ORDER BY name", conn)
        if len(musicas_lista) > 0:
            musica_remover = st.selectbox(
                "Selecione a música para remover",
                musicas_lista['id'],
                format_func=lambda x: f"{musicas_lista[musicas_lista['id']==x]['name'].iloc[0]} - {musicas_lista[musicas_lista['id']==x]['singer'].iloc[0]}"
            )
            if st.button("Remover", type="secondary"):
                cursor = conn.cursor()
                cursor.execute("DELETE FROM youtube_musics WHERE id = ?", (musica_remover,))
                conn.commit()
                st.warning("Música removida com sucesso!")
                st.rerun()
        else:
            st.info("Nenhuma música cadastrada para remover.")
    
    conn.close()

# ============================================
# 3. GERENCIAR EVENTOS (CRUD)
# ============================================
elif menu == "Gerenciar Eventos":
    st.header("Gerenciar Eventos")
    
    conn = get_connection()
    if conn is None:
        st.stop()
    
    tab1, tab2, tab3, tab4 = st.tabs(["Listar Eventos", "Criar Evento", "Editar Evento", "Remover Evento"])
    
    with tab1:
        st.subheader("Eventos Cadastrados")
        eventos = pd.read_sql("""
            SELECT id, event_name AS evento, location AS local, start_date AS data, is_active AS ativo 
            FROM events 
            ORDER BY start_date
        """, conn)
        if len(eventos) > 0:
            st.dataframe(eventos, use_container_width=True)
            st.caption(f"Total de eventos: {len(eventos)}")
        else:
            st.info("Nenhum evento cadastrado ainda.")
    
    with tab2:
        st.subheader("Criar Novo Evento")
        with st.form("novo_evento", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                nome_evento = st.text_input("Nome do Evento*")
                local = st.text_input("Local")
            with col2:
                data_evento = st.date_input("Data do Evento", datetime.now())
            
            submitted = st.form_submit_button("Criar Evento", type="primary")
            
            if submitted:
                if nome_evento:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO events (id, event_name, location, start_date, end_date, is_active)
                        VALUES (uuid(), ?, ?, ?, ?, TRUE)
                    """, (nome_evento, local, data_evento, data_evento))
                    conn.commit()
                    st.success(f"Evento '{nome_evento}' criado com sucesso.")
                    st.rerun()
                else:
                    st.error("Nome do evento é obrigatório.")
    
    with tab3:
        st.subheader("Editar Evento")
        eventos_edicao = pd.read_sql("SELECT id, event_name, location, start_date FROM events ORDER BY event_name", conn)
        if len(eventos_edicao) > 0:
            evento_editar = st.selectbox(
                "Selecione o evento para editar",
                eventos_edicao['id'],
                format_func=lambda x: f"{eventos_edicao[eventos_edicao['id']==x]['event_name'].iloc[0]} - {eventos_edicao[eventos_edicao['id']==x]['location'].iloc[0]}",
                key="select_evento_edit"
            )
            
            # Buscar dados do evento selecionado
            evento_selecionado = pd.read_sql(
                "SELECT event_name, location, start_date FROM events WHERE id = ?",
                conn,
                params=(evento_editar,)
            ).iloc[0]
            
            with st.form("editar_evento", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    novo_nome_evento = st.text_input("Nome do Evento", value=evento_selecionado['event_name'])
                    novo_local = st.text_input("Local", value=evento_selecionado['location'] if evento_selecionado['location'] else "")
                with col2:
                    nova_data_evento = st.date_input("Data do Evento", value=evento_selecionado['start_date'])
                
                submitted = st.form_submit_button("Salvar Alterações", type="primary")
                
                if submitted:
                    if novo_nome_evento:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE events
                            SET event_name = ?, location = ?, start_date = ?, end_date = ?
                            WHERE id = ?
                        """, (novo_nome_evento, novo_local, nova_data_evento, nova_data_evento, evento_editar))
                        conn.commit()
                        st.success("Evento atualizado com sucesso.")
                        st.rerun()
                    else:
                        st.error("Nome do evento é obrigatório.")
        else:
            st.info("Nenhum evento cadastrado para editar.")
    
    with tab4:
        st.subheader("Remover Evento")
        eventos_lista = pd.read_sql("SELECT id, event_name, location FROM events ORDER BY event_name", conn)
        if len(eventos_lista) > 0:
            evento_remover = st.selectbox(
                "Selecione o evento para remover",
                eventos_lista['id'],
                format_func=lambda x: f"{eventos_lista[eventos_lista['id']==x]['event_name'].iloc[0]} - {eventos_lista[eventos_lista['id']==x]['location'].iloc[0]}"
            )
            if st.button("Remover Evento", type="secondary"):
                cursor = conn.cursor()
                cursor.execute("DELETE FROM events WHERE id = ?", (evento_remover,))
                conn.commit()
                st.warning("Evento removido com sucesso!")
                st.rerun()
        else:
            st.info("Nenhum evento cadastrado para remover.")
    
    conn.close()

# ============================================
# 4. REGISTRAR PEDIDO
# ============================================
elif menu == "Registrar Pedido":
    st.header("Registrar Pedido de Música para Evento")
    
    conn = get_connection()
    if conn is None:
        st.stop()
    
    eventos_df = pd.read_sql("SELECT id, event_name FROM events ORDER BY event_name", conn)
    musicas_df = pd.read_sql("SELECT id, name, singer FROM youtube_musics ORDER BY name", conn)
    
    if len(eventos_df) == 0:
        st.warning("Nenhum evento cadastrado. Crie um evento primeiro.")
    elif len(musicas_df) == 0:
        st.warning("Nenhuma música cadastrada. Adicione uma música primeiro.")
    else:
        with st.form("novo_pedido", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                evento = st.selectbox(
                    "Selecione o Evento",
                    eventos_df['id'],
                    format_func=lambda x: eventos_df[eventos_df['id']==x]['event_name'].iloc[0],
                    key="evento_select"
                )
                ordem = st.number_input("Ordem de execução (1-30)", min_value=1, max_value=30, value=1)
            
            with col2:
                musica = st.selectbox(
                    "Selecione a Música",
                    musicas_df['id'],
                    format_func=lambda x: f"{musicas_df[musicas_df['id']==x]['name'].iloc[0]} - {musicas_df[musicas_df['id']==x]['singer'].iloc[0]}",
                    key="musica_select"
                )
                categoria = st.selectbox("Categoria", ["interactive", "background"])
            
            submitted = st.form_submit_button("Registrar Pedido", type="primary")
            
            if submitted:
                # Verificar se a ordem já existe para este evento
                ordem_existe = pd.read_sql(
                    "SELECT COUNT(*) FROM music_order WHERE event_id = ? AND `order` = ?",
                    conn,
                    params=(evento, ordem)
                ).iloc[0, 0]
                
                if ordem_existe > 0:
                    st.error(f"Já existe uma música na posição {ordem} deste evento. Escolha outra ordem.")
                else:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO music_order (id, music_id, event_id, `order`, status, category, is_active)
                            VALUES (uuid(), ?, ?, ?, 'accepted', ?, TRUE)
                        """, (musica, evento, ordem, categoria))
                        conn.commit()
                        st.success("Pedido registrado com sucesso.")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Erro ao registrar pedido: {err}")
    
    # Mostrar pedidos existentes
    st.markdown("---")
    st.subheader("Pedidos Registrados")
    
    pedidos = pd.read_sql("""
        SELECT 
            e.event_name AS evento,
            m.name AS musica,
            m.singer AS artista,
            mo.order AS posicao,
            mo.category AS tipo,
            mo.status AS situacao
        FROM music_order mo
        JOIN events e ON mo.event_id = e.id
        JOIN youtube_musics m ON mo.music_id = m.id
        ORDER BY e.event_name, mo.order
    """, conn)
    
    if len(pedidos) > 0:
        st.dataframe(pedidos, use_container_width=True)
        st.caption(f"Total de pedidos: {len(pedidos)}")
    else:
        st.info("Nenhum pedido registrado ainda.")
    
    conn.close()

# Rodapé
st.markdown("---")
st.markdown(
    "<center><small>Desenvolvido para a disciplina de Banco de Dados - Modelagem e Integração com Dados Públicos</small></center>",
    unsafe_allow_html=True
)

