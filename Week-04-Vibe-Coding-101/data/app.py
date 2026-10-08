import re
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="MovieLens Dashboard", page_icon="🎞️", layout="wide")

# ---------- Palette ----------
BG, PANEL, INK, MUTED, GRID = "#14121F", "#1E1A2E", "#F2EDE4", "#9C95B0", "#2E2942"
GOLD, TEAL, CORAL = "#E8B04A", "#4FB3A9", "#E26D5A"
DIM = "#4A4466"  # bars that aren't the focus

# ---------- Page styling ----------
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@500;700;800&display=swap');
    .block-container {{ padding-top: 2.2rem; max-width: 1250px; }}
    h1, h2, h3 {{ font-family: 'Bricolage Grotesque', sans-serif !important; letter-spacing: -0.02em; }}
    h1 {{ font-size: 3.2rem !important; font-weight: 800 !important; margin-bottom: 0; }}
    h3 {{ font-weight: 700 !important; margin-top: 0.4rem; }}
    [data-testid="stMetric"] {{
        background: {PANEL}; border: 1px solid {GRID}; border-left: 4px solid {GOLD};
        padding: 14px 18px; border-radius: 10px;
    }}
    [data-testid="stMetricValue"] {{ font-family: 'Bricolage Grotesque', sans-serif; font-weight: 800; }}
    [data-testid="stSidebar"] {{ border-right: 1px solid {GRID}; }}
    [data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 12px; }}
    footer {{ visibility: hidden; }}
    .takeaway {{ color: {MUTED}; font-size: 0.95rem; margin: -0.3rem 0 0.6rem 0; }}
    .takeaway b {{ color: {INK}; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- Data ----------
@st.cache_data
def load_data():
    df = pd.read_csv(Path(__file__).parent / "movie_ratings.csv")
    df = df.rename(columns={"movie_id": "movieId", "user_id": "userId"})
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year", "rating"])
    df["year"] = df["year"].astype(int)
    df["genres"] = df["genres"].fillna("(no genres listed)")
    return df


df = load_data()
all_genres = sorted({g for gs in df["genres"].unique() for g in gs.split("|")})


# ---------- Chart helpers ----------
def finish(chart, height=None):
    if height:
        chart = chart.properties(height=height)
    chart = (
        chart.configure(background="transparent")
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor=MUTED, titleColor=MUTED, gridColor=GRID, domainColor=GRID,
            tickColor=GRID, labelFontSize=12, titleFontSize=12,
        )
    )
    st.altair_chart(chart, use_container_width=True)


def hbar(data, x, y, x_title, fmt, domain=None):
    """Sorted horizontal bars with value labels. `data` needs a 'color' column of hex values."""
    xscale = alt.Scale(domain=domain) if domain else alt.Scale()
    base = alt.Chart(data).encode(
        y=alt.Y(f"{y}:N", sort="-x", title=None, axis=alt.Axis(labelLimit=280, ticks=False)),
        x=alt.X(f"{x}:Q", title=x_title, scale=xscale),
    )
    bars = base.mark_bar(cornerRadiusEnd=3).encode(
        color=alt.Color("color:N", scale=None),
        tooltip=[y, alt.Tooltip(f"{x}:Q", format=fmt)],
    )
    labels = base.mark_text(align="left", dx=5, color=INK, fontSize=11).encode(
        text=alt.Text(f"{x}:Q", format=fmt)
    )
    return bars + labels


# ---------- Sidebar ----------
st.sidebar.header("Filters")
yr_min, yr_max = int(df["year"].min()), int(df["year"].max())
year_range = st.sidebar.slider("Movie release year", yr_min, yr_max, (yr_min, yr_max))
genre_sel = st.sidebar.multiselect("Genres (empty = all)", all_genres)
st.sidebar.divider()
st.sidebar.caption("Chart-specific settings")
min_year_n = st.sidebar.slider("Ratings Q3 needs per release year", 1, 200, 20,
                               help="Hides years with too few ratings to be reliable.")
floor_a = st.sidebar.slider("Q4: first ratings floor", 10, 500, 50, step=10)
floor_b = st.sidebar.slider("Q4: second ratings floor", 10, 500, 150, step=10)

# ---------- Filtering ----------
f = df[(df["year"] >= year_range[0]) & (df["year"] <= year_range[1])]
if genre_sel:
    pattern = "|".join(f"(?:^|\\|){re.escape(g)}(?:\\||$)" for g in genre_sel)
    f = f[f["genres"].str.contains(pattern, regex=True)]

# One row per (rating, genre): a multi-genre movie counts once in EACH of its genres.
exploded = f.assign(genre=f["genres"].str.split("|")).explode("genre")
if genre_sel:
    exploded = exploded[exploded["genre"].isin(genre_sel)]

# ---------- Header ----------
st.title("🎞️ MovieLens Dashboard")
st.markdown(
    f"<p class='takeaway'>What people watched, what they loved, and how it has changed across "
    f"movie release years.</p>",
    unsafe_allow_html=True,
)

if f.empty:
    st.warning("No ratings match these filters. Widen the year range or clear the genre selection.")
    st.stop()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Ratings", f"{len(f):,}")
k2.metric("Movies", f"{f['movieId'].nunique():,}")
k3.metric("Users", f"{f['userId'].nunique():,}")
k4.metric("Average rating", f"{f['rating'].mean():.2f} / 5")

st.write("")

# ---------- Q1 + Q2 ----------
c1, c2 = st.columns(2)

with c1:
    with st.container(border=True):
        st.subheader("Which genres dominate?")
        st.caption(
            "Distinct rated movies per genre. A movie with several genres counts once in each, "
            "so bars add up to more than the movie total."
        )
        q1 = (
            exploded.groupby("genre")["movieId"].nunique()
            .reset_index(name="movies").sort_values("movies", ascending=False)
        )
        q1["color"] = [GOLD if i < 3 else DIM for i in range(len(q1))]
        finish(hbar(q1, "movies", "genre", "Rated movies", ",d"), height=max(240, 26 * len(q1)))

with c2:
    with st.container(border=True):
        st.subheader("Which genres are rated highest?")
        st.caption("Mean of all individual ratings per genre. Bars start at zero, so gaps look small but are real.")
        q2 = exploded.groupby("genre")["rating"].agg(avg="mean", n="count").reset_index()
        q2 = q2.sort_values("avg", ascending=False).reset_index(drop=True)
        q2["color"] = DIM
        q2.loc[:2, "color"] = GOLD
        q2.loc[len(q2) - 3:, "color"] = CORAL
        finish(hbar(q2, "avg", "genre", "Mean rating", ".2f", domain=[0, 5]),
               height=max(240, 26 * len(q2)))
        if len(q2) >= 2:
            st.markdown(
                f"<p class='takeaway'>Highest: <b>{q2.iloc[0]['genre']}</b> ({q2.iloc[0]['avg']:.2f}) &nbsp;|&nbsp; "
                f"Lowest: <b>{q2.iloc[-1]['genre']}</b> ({q2.iloc[-1]['avg']:.2f})</p>",
                unsafe_allow_html=True,
            )

# ---------- Q3 ----------
with st.container(border=True):
    st.subheader("How have ratings changed by release year?")
    st.caption("X-axis is the year the movie was released, not the year it was rated. "
               "The dashed line is the overall average.")
    q3 = f.groupby("year")["rating"].agg(avg="mean", n="count").reset_index()
    q3 = q3[q3["n"] >= min_year_n]
    if q3.empty:
        st.info("No release year has enough ratings. Lower the Q3 slider in the sidebar.")
    else:
        base = alt.Chart(q3).encode(
            x=alt.X("year:Q", title="Release year", axis=alt.Axis(format="d"),
                    scale=alt.Scale(zero=False)),
            y=alt.Y("avg:Q", title="Mean rating", scale=alt.Scale(zero=False)),
        )
        area = base.mark_area(color=GOLD, opacity=0.12)
        line = base.mark_line(color=GOLD, strokeWidth=2.5).encode(
            tooltip=["year:Q", alt.Tooltip("avg:Q", format=".3f", title="Mean rating"),
                     alt.Tooltip("n:Q", title="Ratings")]
        )
        pts = base.mark_circle(color=GOLD, size=45)
        mean_rule = alt.Chart(pd.DataFrame({"m": [f["rating"].mean()]})).mark_rule(
            color=MUTED, strokeDash=[5, 5]
        ).encode(y="m:Q")
        finish(area + line + pts + mean_rule, height=320)

# ---------- Q4 ----------
with st.container(border=True):
    st.subheader("Best-rated movies, with a minimum-ratings floor")
    st.caption("Top 5 by mean rating among movies with at least this many ratings. "
               "Ties are broken by number of ratings. Compare how the list shifts as the floor rises.")
    movie_stats = f.groupby(["movieId", "title"])["rating"].agg(avg="mean", n="count").reset_index()
    cols = st.columns(2)
    for col, floor, color in zip(cols, [floor_a, floor_b], [GOLD, TEAL]):
        t = movie_stats[movie_stats["n"] >= floor].sort_values(["avg", "n"], ascending=False).head(5).copy()
        with col:
            st.markdown(f"**At least {floor} ratings**")
            if t.empty:
                st.info("No movies meet this floor. Lower it or widen the filters.")
                continue
            t["color"] = color
            finish(hbar(t, "avg", "title", "Mean rating", ".2f", domain=[0, 5]), height=230)