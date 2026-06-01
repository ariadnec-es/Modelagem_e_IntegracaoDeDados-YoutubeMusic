import re
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "dados"
PLOT_COLORS = ["#2563eb", "#14b8a6", "#f97316", "#a855f7", "#ef4444", "#64748b"]

st.set_page_config(
    page_title="Sonora Dashboard",
    page_icon=str(BASE_DIR / "onda_sonora.png") if (BASE_DIR / "onda_sonora.png").exists() else "Sonora",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root { color-scheme: light; }
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background: #f8fafc !important;
        color: #0f172a !important;
    }
    [data-testid="stSidebar"] {
        background: #ffffff !important;
        border-right: 1px solid #e2e8f0;
    }
    [data-testid="stSidebar"] *, [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] *, label, p, span, h1, h2, h3 {
        color: #0f172a !important;
    }
    div.block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1460px; }
    [data-testid="stMetric"] {
        background: #ffffff !important;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
    }
    [data-testid="stMetric"] * { color: #0f172a !important; }
    div.stButton > button {
        background: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        font-weight: 700;
    }
    div.stButton > button:hover { border-color: #2563eb; box-shadow: 0 8px 18px rgba(37, 99, 235, 0.14); }
    .hero-box {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(37, 99, 235, 0.9));
        color: #ffffff !important;
        border-radius: 8px;
        padding: 1.7rem 1.8rem;
        margin-bottom: 1.35rem;
        box-shadow: 0 18px 45px rgba(15, 23, 42, 0.18);
    }
    .hero-box * { color: #ffffff !important; }
    .big-title { font-size: clamp(1.9rem, 4vw, 3rem); font-weight: 800; margin-bottom: 0.35rem; }
    .subtitle { color: #dbeafe !important; font-size: clamp(0.92rem, 2vw, 1.08rem); max-width: 900px; }
    .insight-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #14b8a6;
        border-radius: 8px;
        padding: 0.9rem 1rem;
        margin: 0.35rem 0 1rem;
        color: #334155 !important;
    }
    .db-note {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        color: #1e3a8a !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero-box">
      <div class="big-title">Sonora Dashboard</div>
      <div class="subtitle">Sistema de gerenciamento de músicas e eventos com dados públicos de YouTube em CSV</div>
    </div>
    """,
    unsafe_allow_html=True,
)


def formatar_numero_grande(numero):
    if numero is None or pd.isna(numero):
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
    titulo_norm = normalizar_texto(row.get("title", ""))
    canal_norm = normalizar_texto(row.get("channel", ""))
    texto_norm = normalizar_texto(" ".join(str(row.get(col, "") or "") for col in ["title", "fulltitle", "description", "tags", "channel"]))

    generos_curados = [
        ("sapphire", ["Pop", "Folk-pop", "Balada romântica"]),
        ("enemy", ["Pop rock", "Pop rap", "Rock alternativo"]),
        ("apt", ["K-pop", "Pop rock", "Dance-pop"]),
        ("die with a smile", ["Pop", "Soul pop", "Balada romântica"]),
        ("birds of a feather", ["Pop alternativo", "Dream pop"]),
        ("espresso", ["Pop", "Dance-pop"]),
        ("abracadabra", ["Dance-pop", "Synth-pop"]),
        ("luther", ["Hip-hop/Rap", "R&B"]),
        ("a bar song", ["Country", "Country rap", "Pop"]),
        ("not like us", ["Hip-hop/Rap", "West Coast rap"]),
        ("born again", ["K-pop", "Dance-pop", "Pop rap"]),
        ("move", ["Afro house", "Dance/Eletrônica"]),
        ("i had some help", ["Country pop", "Pop rock"]),
        ("number one girl", ["K-pop", "Pop", "Balada"]),
        ("toxic till the end", ["K-pop", "Pop rock"]),
        ("new woman", ["K-pop", "Latin pop", "Dance-pop"]),
        ("sao paulo", ["R&B", "Funk brasileiro", "Dance-pop"]),
        ("nokia", ["Hip-hop/Rap", "Pop rap"]),
        ("guess", ["Hyperpop", "Dance-pop"]),
        ("priceless", ["Pop", "K-pop"]),
        ("mantra", ["K-pop", "Dance-pop"]),
        ("take me to the beach", ["Pop rock", "Rock alternativo", "J-pop"]),
    ]
    for chave, generos in generos_curados:
        if chave in titulo_norm:
            return generos

    if "ed sheeran" in canal_norm:
        return ["Pop", "Folk-pop"]
    if "imagine" in canal_norm:
        return ["Pop rock", "Rock alternativo"]
    if any(nome in canal_norm for nome in ["rose", "lloud", "jennie"]):
        return ["K-pop", "Pop"]
    if any(nome in canal_norm for nome in ["kendrick", "drake", "doechii", "hoodtrophy"]):
        return ["Hip-hop/Rap"]
    if any(nome in canal_norm for nome in ["sabrina carpenter", "lady gaga", "dua lipa", "tate mcrae"]):
        return ["Pop", "Dance-pop"]
    if "billie eilish" in canal_norm:
        return ["Pop alternativo"]
    if any(nome in canal_norm for nome in ["the weeknd", "giveon", "roy woods"]):
        return ["R&B", "Pop"]

    regras = [
        ("K-pop", ["k pop", "kpop", "blackpink", "bts", "rose", "yg entertainment"]),
        ("Hip-hop/Rap", ["hip hop", "rap", "trap"]),
        ("R&B", ["r b", "rnb", "rhythm and blues"]),
        ("Afrobeats", ["afrobeats", "afrobeat"]),
        ("Dancehall", ["dancehall"]),
        ("Reggae", ["reggae"]),
        ("Country", ["country"]),
        ("Dance/Eletrônica", ["dance", "electronic", "edm", "house"]),
        ("Pop", ["pop"]),
        ("Rock", ["rock"]),
        ("Funk", ["funk"]),
        ("Alternativo", ["alternative", "alternativo", "indie", "alt pop"]),
        ("Blues", ["blues"]),
        ("Jazz", ["jazz"]),
        ("Gospel", ["gospel", "worship"]),
    ]
    encontrados = [genero for genero, termos in regras if any(termo in texto_norm for termo in termos)]
    return encontrados[:3] if encontrados else ["Não identificado"]


def agrupar_genero(genero):
    mapa = {
        "Pop": ["Pop", "Dance-pop", "Synth-pop", "Dream pop", "Soul pop", "Dark pop", "Alt-pop", "Hyperpop", "Latin pop", "Country pop", "Pop rap"],
        "Hip-hop/Rap": ["Hip-hop/Rap", "Rap", "West Coast rap", "Alternative hip-hop", "Country rap"],
        "R&B/Soul": ["R&B", "Soul", "Alternative R&B"],
        "Rock/Alternativo": ["Rock", "Pop rock", "Rock alternativo", "Soft rock", "Alternativo", "Pop alternativo", "Indie pop", "Bedroom pop", "Metal"],
        "K-pop": ["K-pop", "J-pop"],
        "Country/Folk": ["Country", "Folk-pop", "Balada", "Balada romântica"],
        "Dance/Eletrônica": ["Dance/Eletrônica", "Afro house", "Nu-disco"],
        "Afro/Reggae/Dancehall": ["Afrobeats", "Afrobeat", "Dancehall", "Reggae", "Funk brasileiro"],
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


def detectar_separador(caminho):
    primeira_linha = caminho.read_text(encoding="utf-8-sig", errors="ignore").splitlines()[0]
    return ";" if primeira_linha.count(";") > primeira_linha.count(",") else ","


def ler_csv(nome_arquivo):
    caminho = DATA_DIR / nome_arquivo
    if not caminho.exists():
        return pd.DataFrame()
    sep = detectar_separador(caminho)
    try:
        return pd.read_csv(caminho, sep=sep, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(caminho, sep=sep, encoding="latin1")


def preparar_youtube_hits(df):
    if df.empty:
        return df
    df = df.copy()
    for col in ["id", "view_count", "duration", "channel_follower_count"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "id" in df.columns:
        df = df[df["id"].notna()]
    if "view_count" in df.columns:
        df = df[df["view_count"].notna() & (df["view_count"] > 0)]
    if "title" in df.columns:
        df = df[df["title"].notna()]
    df["duration_min"] = df["duration"] / 60 if "duration" in df.columns else 0
    df["musical_genres"] = df.apply(detectar_generos_musicais, axis=1)
    df["musical_genre"] = df["musical_genres"].apply(lambda generos: generos[0] if generos else "Não identificado")
    df["musical_genre_groups"] = df["musical_genres"].apply(agrupar_generos)
    df["musical_genre_group"] = df["musical_genre"].apply(agrupar_genero)
    df["tipo_musica"] = np.where(df["title"].fillna("").str.contains(r"\b(ft|feat|featuring|with|x)\b|&|,", case=False, regex=True), "Colaboração", "Solo")
    return df


@st.cache_data
def carregar_csvs_base():
    youtube_hits = preparar_youtube_hits(ler_csv("youtube_hits_2025.csv"))
    youtube_hits_original = preparar_youtube_hits(ler_csv("youtube-top-100-songs-2025.csv"))
    if len(youtube_hits) < 90 and len(youtube_hits_original) >= 90:
        youtube_hits = youtube_hits_original.copy()
        youtube_hits.insert(0, "id", range(1, len(youtube_hits) + 1))

    youtube_musics = ler_csv("youtube_musics.csv")
    events = ler_csv("events.csv")
    music_order = ler_csv("music_order.csv")

    for df in [youtube_musics, events, music_order]:
        if "is_active" in df.columns:
            df["is_active"] = pd.to_numeric(df["is_active"], errors="coerce").fillna(1).astype(int)
    if "order" in music_order.columns:
        music_order["order"] = pd.to_numeric(music_order["order"], errors="coerce").fillna(0).astype(int)
    return youtube_hits, youtube_musics, events, music_order


def tabelas():
    if "tables_loaded" not in st.session_state:
        youtube_hits, youtube_musics, events, music_order = carregar_csvs_base()
        st.session_state.youtube_hits = youtube_hits.copy()
        st.session_state.youtube_musics = youtube_musics.copy()
        st.session_state.events = events.copy()
        st.session_state.music_order = music_order.copy()
        st.session_state.tables_loaded = True
    return (
        st.session_state.youtube_hits,
        st.session_state.youtube_musics,
        st.session_state.events,
        st.session_state.music_order,
    )


def estilizar_figura(fig, height=430, show_legend=True):
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=20, r=20, t=105, b=80 if show_legend else 45),
        title=dict(y=0.98, yanchor="top", x=0.02, xanchor="left", pad=dict(b=22)),
        font=dict(family="Arial, sans-serif", color="#0f172a"),
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


def pedidos_com_detalhes(music_order, events, youtube_musics):
    if music_order.empty:
        return pd.DataFrame()
    pedidos = music_order.merge(events[["id", "event_name"]], left_on="event_id", right_on="id", how="left", suffixes=("", "_evento"))
    pedidos = pedidos.merge(youtube_musics[["id", "name", "singer"]], left_on="music_id", right_on="id", how="left", suffixes=("", "_musica"))
    return pd.DataFrame({
        "evento": pedidos.get("event_name", ""),
        "musica": pedidos.get("name", ""),
        "artista": pedidos.get("singer", ""),
        "posicao": pedidos.get("order", ""),
        "tipo": pedidos.get("category", ""),
        "situacao": pedidos.get("status", ""),
    }).sort_values(["evento", "posicao"], na_position="last")


if (BASE_DIR / "onda_sonora.png").exists():
    st.sidebar.image(str(BASE_DIR / "onda_sonora.png"), width=100)
    st.sidebar.markdown("### Sonora Dashboard")
else:
    st.sidebar.title("Sonora Dashboard")

st.sidebar.markdown("---")
menu = st.sidebar.radio("Navegação", ["Dashboard Principal", "Gerenciar Músicas", "Gerenciar Eventos", "Registrar Pedido"], index=0)
st.sidebar.markdown("---")
st.sidebar.info(
    """
    **Projeto:** Modelagem e Integração com Dados Públicos  
    **Disciplina:** Banco de Dados  
    **Base:** Streamlit + CSV
    """
)

youtube_hits, youtube_musics, events, music_order = tabelas()

if menu == "Dashboard Principal":
    st.header("Dashboard de Análise")
    total_musicas = len(youtube_musics)
    total_youtube = len(youtube_hits)
    total_eventos = len(events)
    total_pedidos = len(music_order)

    st.subheader("Métricas do Sistema")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Músicas no Catálogo", formatar_numero_grande(total_musicas))
    col2.metric("Dados YouTube", formatar_numero_grande(total_youtube))
    col3.metric("Eventos Cadastrados", formatar_numero_grande(total_eventos))
    col4.metric("Pedidos de Música", formatar_numero_grande(total_pedidos))

    st.markdown("---")
    st.subheader("Arquitetura do Banco de Dados")
    st.markdown("<div class='db-note'>Versão hospedada: as tabelas são carregadas dos CSVs em dados/.</div>", unsafe_allow_html=True)
    st.graphviz_chart(
        """
        digraph sonora_db {
            graph [rankdir=LR, bgcolor="transparent", pad="0.35", nodesep="0.55", ranksep="0.8"];
            node [shape=record, style="rounded,filled", fillcolor="#ffffff", color="#94a3b8", penwidth=1.4, fontname="Arial", fontsize=11];
            edge [color="#2563eb", penwidth=1.4, arrowsize=0.8, fontname="Arial", fontsize=10];
            youtube_hits_2025 [label="{youtube_hits_2025.csv|title\\lview_count\\lduration\\lchannel\\lchannel_follower_count\\l}"];
            youtube_musics [label="{youtube_musics.csv|id\\lname\\lsinger\\lurl\\lis_active\\l}"];
            events [label="{events.csv|id\\levent_name\\llocation\\lstart_date\\lend_date\\l}"];
            music_order [label="{music_order.csv|id\\lmusic_id\\levent_id\\lorder\\lstatus\\lcategory\\l}"];
            youtube_musics -> music_order [label="1:N"];
            events -> music_order [label="1:N"];
        }
        """,
        use_container_width=True,
    )

    st.markdown("---")
    st.subheader("Análise dos Dados Públicos do YouTube")
    if youtube_hits.empty:
        st.warning("Não foi possível carregar registros válidos de youtube_hits_2025.csv.")
    else:
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total de Músicas", formatar_numero_grande(len(youtube_hits)))
        col2.metric("Maior Views", formatar_numero_grande(youtube_hits["view_count"].max()))
        col3.metric("Menor Views", formatar_numero_grande(youtube_hits["view_count"].min()))
        col4.metric("Média Views", formatar_numero_grande(youtube_hits["view_count"].mean()))
        col5.metric("Total Views", formatar_numero_grande(youtube_hits["view_count"].sum()))

        top10 = youtube_hits.nlargest(10, "view_count")[["title", "view_count"]].copy()
        top10["musica_curta"] = top10["title"].apply(limpar_nome_musica)
        fig = px.bar(top10, x="musica_curta", y="view_count", title="Top 10 Músicas Mais Vistas no YouTube", labels={"musica_curta": "Música", "view_count": "Visualizações"}, color="view_count", color_continuous_scale="Teal")
        fig.update_layout(xaxis_tickangle=-35)
        estilizar_figura(fig, height=500, show_legend=False)
        abreviar_eixo_views(fig)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("Insights Adicionais do Dataset Público")
        bins = [-1, 10_000, 50_000, 100_000, 500_000, 1_000_000, np.inf]
        labels = ["Menos de 10K", "10K - 50K", "50K - 100K", "100K - 500K", "500K - 1M", "1 Milhão+"]
        dist_df = youtube_hits.assign(faixa_views=pd.cut(youtube_hits["view_count"], bins=bins, labels=labels)).groupby("faixa_views", observed=False).size().reset_index(name="quantidade")
        col1, col2 = st.columns(2)
        with col1:
            fig_dist_pie = px.pie(dist_df, values="quantidade", names="faixa_views", title="Distribuição por Faixa de Views", hole=0.45, color_discrete_sequence=PLOT_COLORS)
            estilizar_figura(fig_dist_pie)
            st.plotly_chart(fig_dist_pie, use_container_width=True)
        with col2:
            fig_dist_bar = px.bar(dist_df, x="faixa_views", y="quantidade", title="Quantidade por Faixa", color="quantidade", color_continuous_scale="Teal")
            fig_dist_bar.update_layout(xaxis_tickangle=-35)
            estilizar_figura(fig_dist_bar, show_legend=False)
            st.plotly_chart(fig_dist_bar, use_container_width=True)

        st.markdown("---")
        st.subheader("Análises Gráficas do YouTube Top Songs")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Faixas", len(youtube_hits))
        col2.metric("Canais únicos", youtube_hits["channel"].nunique())
        col3.metric("Duração média", f"{youtube_hits['duration_min'].mean():.1f} min")
        col4.metric("Views", formatar_numero_grande(youtube_hits["view_count"].sum()))

        canais = youtube_hits.groupby("channel", as_index=False).agg(musicas=("title", "count"), views_totais=("view_count", "sum")).sort_values(["musicas", "views_totais"], ascending=[False, False]).head(15).sort_values("musicas")
        fig_canais = px.bar(canais, x="musicas", y="channel", orientation="h", title="Músicas por Canal/Artista no Top", labels={"musicas": "Quantidade de músicas", "channel": "Canal/Artista"}, color="views_totais", color_continuous_scale="Teal")
        estilizar_figura(fig_canais, height=520, show_legend=False)
        st.plotly_chart(fig_canais, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            fig_duracao = px.scatter(youtube_hits, x="duration_min", y="view_count", size="channel_follower_count", color="musical_genre_group", title="Duração das Músicas vs Popularidade", labels={"duration_min": "Duração (minutos)", "view_count": "Visualizações", "musical_genre_group": "Gênero principal"}, hover_name="title", color_discrete_sequence=PLOT_COLORS)
            estilizar_figura(fig_duracao, height=480)
            abreviar_eixo_views(fig_duracao)
            st.plotly_chart(fig_duracao, use_container_width=True)
        with col2:
            generos = youtube_hits[["title", "musical_genre_groups"]].explode("musical_genre_groups")
            generos = generos["musical_genre_groups"].value_counts().reset_index()
            generos.columns = ["genero", "quantidade"]
            fig_generos = px.pie(generos, names="genero", values="quantidade", title="Principais Gêneros Musicais", hole=0.55, color_discrete_sequence=PLOT_COLORS)
            estilizar_figura(fig_generos, height=480)
            st.plotly_chart(fig_generos, use_container_width=True)

        corr_df = youtube_hits[(youtube_hits["channel_follower_count"] > 0) & (youtube_hits["view_count"] > 0)].copy()
        fig_corr = px.scatter(corr_df, x="channel_follower_count", y="view_count", color="musical_genre_group", size="duration", title="Views vs Seguidores do Canal", labels={"channel_follower_count": "Seguidores do canal", "view_count": "Visualizações", "musical_genre_group": "Gênero principal"}, hover_name="title", color_discrete_sequence=PLOT_COLORS)
        if len(corr_df) >= 2:
            coef = np.polyfit(corr_df["channel_follower_count"], corr_df["view_count"], 1)
            x_linha = np.linspace(corr_df["channel_follower_count"].min(), corr_df["channel_follower_count"].max(), 100)
            fig_corr.add_trace(go.Scatter(x=x_linha, y=coef[0] * x_linha + coef[1], mode="lines", name="Linha de tendência", line=dict(color="#0f172a", width=3)))
        estilizar_figura(fig_corr, height=500)
        abreviar_eixo_views(fig_corr, "x")
        abreviar_eixo_views(fig_corr)
        st.plotly_chart(fig_corr, use_container_width=True)

        comparativo = youtube_hits.groupby("tipo_musica", as_index=False).agg(media_views=("view_count", "mean"), mediana_views=("view_count", "median"))
        fig_colab = px.bar(comparativo, x="tipo_musica", y=["media_views", "mediana_views"], barmode="group", title="Músicas Solo vs Colaborações", labels={"tipo_musica": "Tipo", "value": "Visualizações", "variable": "Métrica"}, color_discrete_sequence=["#2563eb", "#14b8a6"])
        estilizar_figura(fig_colab, height=430)
        abreviar_eixo_views(fig_colab)
        st.plotly_chart(fig_colab, use_container_width=True)

    st.markdown("---")
    st.subheader("Análise: Músicas Mais Solicitadas vs Mais Vistas no YouTube")
    detalhes = pedidos_com_detalhes(music_order, events, youtube_musics)
    col1, col2 = st.columns(2)
    with col1:
        if not detalhes.empty:
            musicas_solicitadas = detalhes.groupby(["musica", "artista"], as_index=False).size().rename(columns={"size": "total_pedidos"}).sort_values("total_pedidos", ascending=False).head(10)
            musicas_solicitadas["musica_curta"] = musicas_solicitadas["musica"].apply(limpar_nome_musica)
            fig_pedidas = px.bar(musicas_solicitadas, x="musica_curta", y="total_pedidos", title="Top 10 Músicas Mais Solicitadas", color="total_pedidos", color_continuous_scale="Teal")
            fig_pedidas.update_layout(xaxis_tickangle=-35)
            estilizar_figura(fig_pedidas, height=400, show_legend=False)
            st.plotly_chart(fig_pedidas, use_container_width=True)
        else:
            st.info("Ainda não há pedidos de música.")
    with col2:
        if not youtube_hits.empty:
            top_views = youtube_hits.nlargest(10, "view_count")[["title", "view_count"]].rename(columns={"title": "musica", "view_count": "views"})
            top_views["musica_curta"] = top_views["musica"].apply(limpar_nome_musica)
            fig_views = px.bar(top_views, x="musica_curta", y="views", title="Top 10 Músicas Mais Vistas no YouTube", color="views", color_continuous_scale="Teal")
            fig_views.update_layout(xaxis_tickangle=-35)
            estilizar_figura(fig_views, height=400, show_legend=False)
            abreviar_eixo_views(fig_views)
            st.plotly_chart(fig_views, use_container_width=True)

    st.markdown("---")
    st.subheader("Análise de Efetividade do Catálogo")
    musicas_solicitadas_count = music_order["music_id"].nunique() if "music_id" in music_order else 0
    musicas_nao_solicitadas = max(total_musicas - musicas_solicitadas_count, 0)
    percentual_uso = (musicas_solicitadas_count / total_musicas * 100) if total_musicas else 0
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Músicas no Catálogo", total_musicas)
    col2.metric("Músicas Solicitadas", musicas_solicitadas_count)
    col3.metric("Não Solicitadas", musicas_nao_solicitadas)
    col4.metric("Taxa de Uso", f"{percentual_uso:.1f}%")
    fig_cobertura = px.pie(pd.DataFrame({"status": ["Solicitadas", "Não Solicitadas"], "quantidade": [musicas_solicitadas_count, musicas_nao_solicitadas]}), values="quantidade", names="status", title="Cobertura do Catálogo", color_discrete_sequence=["#2563eb", "#e5e7eb"])
    estilizar_figura(fig_cobertura)
    st.plotly_chart(fig_cobertura, use_container_width=True)

    st.markdown("---")
    st.subheader("Análise de Pedidos por Evento")
    if detalhes.empty:
        st.info("Nenhum pedido registrado ainda.")
    else:
        pedidos_evento = detalhes.groupby("evento", as_index=False).agg(total_pedidos=("musica", "count"))
        pedidos_evento["interativas"] = 0
        pedidos_evento["background"] = pedidos_evento["total_pedidos"]
        fig_eventos = px.bar(pedidos_evento, x="evento", y="total_pedidos", title="Pedidos por Evento", color="total_pedidos", color_continuous_scale="Teal")
        fig_eventos.update_layout(xaxis_tickangle=-35)
        estilizar_figura(fig_eventos, height=400, show_legend=False)
        st.plotly_chart(fig_eventos, use_container_width=True)
        st.subheader("Pedidos de Música Registrados")
        st.dataframe(detalhes, use_container_width=True)
        csv = detalhes.to_csv(index=False).encode("utf-8")
        st.download_button("Baixar relatório de pedidos (CSV)", data=csv, file_name="relatorio_pedidos_sonora.csv", mime="text/csv")

elif menu == "Gerenciar Músicas":
    st.header("Gerenciar Catálogo de Músicas")
    tab1, tab2, tab3, tab4 = st.tabs(["Listar Músicas", "Adicionar Música", "Editar Música", "Remover Música"])
    with tab1:
        musicas = youtube_musics[["id", "name", "singer", "url", "is_active"]].rename(columns={"name": "música", "singer": "artista", "is_active": "ativo"}).sort_values("música")
        st.dataframe(musicas, use_container_width=True)
        st.caption(f"Total de músicas: {len(musicas)}")
    with tab2:
        st.info("Na hospedagem, alterações ficam disponíveis apenas durante a sessão atual.")
        with st.form("nova_musica", clear_on_submit=True):
            col1, col2 = st.columns(2)
            nome = col1.text_input("Nome da Música*")
            artista = col1.text_input("Artista/Banda*")
            url = col2.text_input("URL do YouTube")
            if st.form_submit_button("Salvar Música", type="primary"):
                if nome and artista:
                    nova = pd.DataFrame([{"id": str(uuid.uuid4()), "name": nome, "singer": artista, "url": url, "is_active": 1, "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat()}])
                    st.session_state.youtube_musics = pd.concat([youtube_musics, nova], ignore_index=True)
                    st.success(f"Música '{nome}' adicionada nesta sessão.")
                    st.rerun()
                else:
                    st.error("Nome e Artista são obrigatórios.")
    with tab3:
        if youtube_musics.empty:
            st.info("Nenhuma música cadastrada para editar.")
        else:
            musica_id = st.selectbox("Selecione a música para editar", youtube_musics["id"], format_func=lambda x: f"{youtube_musics.loc[youtube_musics['id'] == x, 'name'].iloc[0]} - {youtube_musics.loc[youtube_musics['id'] == x, 'singer'].iloc[0]}")
            musica = youtube_musics[youtube_musics["id"] == musica_id].iloc[0]
            with st.form("editar_musica"):
                novo_nome = st.text_input("Nome da Música", value=musica.get("name", ""))
                novo_artista = st.text_input("Artista/Banda", value=musica.get("singer", ""))
                nova_url = st.text_input("URL do YouTube", value=musica.get("url", ""))
                if st.form_submit_button("Salvar Alterações", type="primary"):
                    idx = st.session_state.youtube_musics["id"] == musica_id
                    st.session_state.youtube_musics.loc[idx, ["name", "singer", "url"]] = [novo_nome, novo_artista, nova_url]
                    st.success("Música atualizada nesta sessão.")
                    st.rerun()
    with tab4:
        if youtube_musics.empty:
            st.info("Nenhuma música cadastrada para remover.")
        else:
            musica_id = st.selectbox("Selecione a música para remover", youtube_musics["id"], format_func=lambda x: f"{youtube_musics.loc[youtube_musics['id'] == x, 'name'].iloc[0]} - {youtube_musics.loc[youtube_musics['id'] == x, 'singer'].iloc[0]}", key="remove_musica")
            if st.button("Remover", type="secondary"):
                st.session_state.youtube_musics = youtube_musics[youtube_musics["id"] != musica_id].copy()
                st.warning("Música removida nesta sessão.")
                st.rerun()

elif menu == "Gerenciar Eventos":
    st.header("Gerenciar Eventos")
    tab1, tab2, tab3, tab4 = st.tabs(["Listar Eventos", "Criar Evento", "Editar Evento", "Remover Evento"])
    with tab1:
        eventos = events[["id", "event_name", "location", "start_date", "is_active"]].rename(columns={"event_name": "evento", "location": "local", "start_date": "data", "is_active": "ativo"}).sort_values("data")
        st.dataframe(eventos, use_container_width=True)
        st.caption(f"Total de eventos: {len(eventos)}")
    with tab2:
        st.info("Na hospedagem, alterações ficam disponíveis apenas durante a sessão atual.")
        with st.form("novo_evento", clear_on_submit=True):
            nome_evento = st.text_input("Nome do Evento*")
            local = st.text_input("Local")
            data_evento = st.date_input("Data do Evento", datetime.now())
            if st.form_submit_button("Criar Evento", type="primary"):
                if nome_evento:
                    novo = pd.DataFrame([{"id": str(uuid.uuid4()), "event_name": nome_evento, "location": local, "start_date": data_evento, "end_date": data_evento, "is_active": 1, "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat()}])
                    st.session_state.events = pd.concat([events, novo], ignore_index=True)
                    st.success(f"Evento '{nome_evento}' criado nesta sessão.")
                    st.rerun()
                else:
                    st.error("Nome do evento é obrigatório.")
    with tab3:
        if events.empty:
            st.info("Nenhum evento cadastrado para editar.")
        else:
            evento_id = st.selectbox("Selecione o evento para editar", events["id"], format_func=lambda x: events.loc[events["id"] == x, "event_name"].iloc[0])
            evento = events[events["id"] == evento_id].iloc[0]
            with st.form("editar_evento"):
                novo_nome = st.text_input("Nome do Evento", value=evento.get("event_name", ""))
                novo_local = st.text_input("Local", value=evento.get("location", ""))
                nova_data = st.date_input("Data do Evento", value=pd.to_datetime(evento.get("start_date", datetime.now())).date())
                if st.form_submit_button("Salvar Alterações", type="primary"):
                    idx = st.session_state.events["id"] == evento_id
                    st.session_state.events.loc[idx, ["event_name", "location", "start_date", "end_date"]] = [novo_nome, novo_local, nova_data, nova_data]
                    st.success("Evento atualizado nesta sessão.")
                    st.rerun()
    with tab4:
        if events.empty:
            st.info("Nenhum evento cadastrado para remover.")
        else:
            evento_id = st.selectbox("Selecione o evento para remover", events["id"], format_func=lambda x: events.loc[events["id"] == x, "event_name"].iloc[0], key="remove_evento")
            if st.button("Remover Evento", type="secondary"):
                st.session_state.events = events[events["id"] != evento_id].copy()
                st.warning("Evento removido nesta sessão.")
                st.rerun()

elif menu == "Registrar Pedido":
    st.header("Registrar Pedido de Música para Evento")
    if events.empty:
        st.warning("Nenhum evento cadastrado. Crie um evento primeiro.")
    elif youtube_musics.empty:
        st.warning("Nenhuma música cadastrada. Adicione uma música primeiro.")
    else:
        st.info("Na hospedagem, pedidos novos ficam disponíveis apenas durante a sessão atual.")
        with st.form("novo_pedido", clear_on_submit=True):
            col1, col2 = st.columns(2)
            evento = col1.selectbox("Selecione o Evento", events["id"], format_func=lambda x: events.loc[events["id"] == x, "event_name"].iloc[0])
            ordem = col1.number_input("Ordem de execução (1-30)", min_value=1, max_value=30, value=1)
            musica = col2.selectbox("Selecione a Música", youtube_musics["id"], format_func=lambda x: f"{youtube_musics.loc[youtube_musics['id'] == x, 'name'].iloc[0]} - {youtube_musics.loc[youtube_musics['id'] == x, 'singer'].iloc[0]}")
            categoria = col2.selectbox("Categoria", ["interactive", "background"])
            if st.form_submit_button("Registrar Pedido", type="primary"):
                existe = ((music_order["event_id"] == evento) & (music_order["order"] == int(ordem))).any() if not music_order.empty else False
                if existe:
                    st.error(f"Já existe uma música na posição {ordem} deste evento. Escolha outra ordem.")
                else:
                    novo = pd.DataFrame([{"id": str(uuid.uuid4()), "music_id": musica, "event_id": evento, "order": int(ordem), "status": "accepted", "category": categoria, "is_active": 1, "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat()}])
                    st.session_state.music_order = pd.concat([music_order, novo], ignore_index=True)
                    st.success("Pedido registrado nesta sessão.")
                    st.rerun()

    st.markdown("---")
    st.subheader("Pedidos Registrados")
    detalhes = pedidos_com_detalhes(st.session_state.music_order, st.session_state.events, st.session_state.youtube_musics)
    if detalhes.empty:
        st.info("Nenhum pedido registrado ainda.")
    else:
        st.dataframe(detalhes, use_container_width=True)
        st.caption(f"Total de pedidos: {len(detalhes)}")

st.markdown("---")
st.markdown(
    "<center><small>Desenvolvido para a disciplina de Banco de Dados - Modelagem e Integração com Dados Públicos</small></center>",
    unsafe_allow_html=True,
)
