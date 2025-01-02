import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
from mplsoccer import Pitch
from PIL import Image
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from io import BytesIO
import pytz
from datetime import datetime
import logging
import re
import numpy as np
import plotly.express as px

# ---------------------------------------------------------------------------
# 1. PAGE & STYLE CONFIGURATION
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Premier League Next-Gen",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Configure logging
logging.basicConfig(
    filename='fpl_dashboard.log',
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s'
)

# Custom CSS for a "website" feel
CUSTOM_CSS = """
<style>
/* Hide Streamlit's default header/footer */
header, footer {visibility: hidden;}

body {
    background-color: #2b2b2b; 
    color: #f0f0f0;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

div[data-testid="stToolbar"] {
    visibility: hidden;
    height: 0%;
    position: fixed;
}

.hero-banner {
    position: relative;
    text-align: center;
    color: white;
    height: 300px;
    background: url('https://images.pexels.com/photos/114296/pexels-photo-114296.jpeg?auto=compress&cs=tinysrgb&h=750&w=1260') no-repeat center center;
    background-size: cover;
    display: flex;
    justify-content: center;
    align-items: center;
}
.hero-text h1 {
    font-size: 3rem;
    font-weight: 700;
    margin-bottom: 0.5rem;
    text-shadow: 2px 2px 5px #000;
}
.hero-text p {
    font-size: 1.2rem;
    color: #f7f7f7;
    text-shadow: 2px 2px 5px #000;
    max-width: 600px;
    margin: 0 auto;
}

/* Perfectly circular floating button in the top-right */
.floating-btn {
    position: fixed;
    top: 25px;        /* Position from the top */
    right: 25px;      /* Position from the right */
    width: 55px;      /* Fixed width to form a circle */
    height: 55px;     /* Fixed height to form a circle */
    border-radius: 50%;
    background-color: #FF4B4B;
    border: none;
    outline: none;
    color: white;
    cursor: pointer;
    font-size: 25px;  /* Larger text/icon size */
    text-align: center;
    line-height: 55px; /* Ensures icon/text is vertically centered */
    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    transition: 0.3s;
    z-index: 9999;
}
.floating-btn:hover {
    background-color: #CC0000;
}

hr {
    border: 1px solid #555;
    margin: 2rem 0;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 2. SESSION STATE SETUP
# ---------------------------------------------------------------------------
if "raw_fpl_data" not in st.session_state:
    st.session_state["raw_fpl_data"] = {}
if "players" not in st.session_state:
    st.session_state["players"] = pd.DataFrame()
if "clubs" not in st.session_state:
    st.session_state["clubs"] = pd.DataFrame()
if "club_difficulty" not in st.session_state:
    st.session_state["club_difficulty"] = pd.DataFrame()

# ---------------------------------------------------------------------------
# 3. DATA FETCHING & PREPARATION
# ---------------------------------------------------------------------------
@st.cache_data(ttl=60 * 60)
def fetch_fpl_data():
    """
    Fetch raw JSON from the official FPL 'bootstrap-static' endpoint.
    """
    try:
        url = "https://fantasy.premierleague.com/api/bootstrap-static/"
        resp = requests.get(url)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        st.error(f"Error fetching FPL data: {e}")
        logging.error(f"Error fetching FPL data: {e}")
        return {}

@st.cache_data(ttl=60 * 60)
def prepare_data(data):
    """
    Convert raw JSON into structured DataFrames for players & clubs.
    Renames columns for a fresh look and merges with clubs data.
    """
    if not data:
        return pd.DataFrame(), pd.DataFrame()

    players_df = pd.DataFrame(data.get("elements", []))
    clubs_df = pd.DataFrame(data.get("teams", []))
    positions_df = pd.DataFrame(data.get("element_types", []))

    if players_df.empty or clubs_df.empty:
        return players_df, clubs_df

    # Rename columns
    players_df.rename(
        columns={
            "second_name": "last_name",
            "team": "club_id",
            "now_cost": "cost",
            "minutes": "minutes_played",
            "selected_by_percent": "popularity"
        },
        inplace=True
    )

    # Merge clubs
    players_df = players_df.merge(
        clubs_df[["id", "name"]],
        left_on="club_id",
        right_on="id",
        how="left"
    )
    players_df.drop(columns=["id", "club_id"], inplace=True, errors="ignore")
    players_df.rename(columns={"name": "club"}, inplace=True)

    # Convert cost -> decimal
    players_df["cost"] = players_df["cost"] / 10.0

    # Convert minutes -> hours
    players_df["hours_played"] = players_df["minutes_played"] / 60.0

    # Popularity -> numeric
    players_df["popularity"] = pd.to_numeric(players_df["popularity"], errors="coerce")

    # Convert form -> numeric
    players_df["form"] = pd.to_numeric(players_df["form"], errors="coerce").fillna(0.0)

    # Map element_type -> position
    if not positions_df.empty:
        id_to_position = dict(zip(positions_df["id"], positions_df["singular_name"]))
        players_df["position"] = players_df["element_type"].map(id_to_position)

    # Construct photo URLs
    players_df["photo_url"] = players_df["photo"].apply(lambda x: construct_photo_url(x))

    return players_df, clubs_df

def construct_photo_url(photo_str):
    """
    Constructs the full URL for a player's photo.
    If the photo_str is invalid, returns a placeholder image URL.
    """
    if pd.isnull(photo_str):
        return "https://via.placeholder.com/110x140.png?text=No+Image"
    
    match = re.match(r'(\d+)\.jpg', photo_str)
    if match:
        player_id = match.group(1)
        return f"https://resources.premierleague.com/premierleague/photos/players/110x140/p{player_id}.png"
    else:
        return "https://via.placeholder.com/110x140.png?text=No+Image"

@st.cache_data(ttl=60 * 60)
def fetch_fixtures_data():
    """
    Minimal fixture fetch from FPL's '/fixtures/' endpoint to compute
    each club's next difficulty and opponent for the Best XI.
    """
    try:
        url = "https://fantasy.premierleague.com/api/fixtures/"
        resp = requests.get(url)
        resp.raise_for_status()
        return pd.DataFrame(resp.json())
    except requests.RequestException as e:
        st.error(f"Error fetching fixture data: {e}")
        logging.error(f"Error fetching fixture data: {e}")
        return pd.DataFrame()

def compute_next_fixture_difficulty(clubs_df):
    """
    For each club, find the earliest *un-finished* fixture with kickoff_time after now
    and record its difficulty and opponent. Return a DataFrame with:
       club, club_next_difficulty, club_next_opponent
    """
    fix_df = fetch_fixtures_data()
    if fix_df.empty:
        st.warning("No fixture data available.")
        return pd.DataFrame(columns=["club", "club_next_difficulty", "club_next_opponent"])

    # Convert kickoff_time to datetime and localize to UTC if naive
    fix_df["kickoff_time"] = pd.to_datetime(fix_df["kickoff_time"], errors="coerce")
    if fix_df["kickoff_time"].dt.tz is None:
        fix_df["kickoff_time"] = fix_df["kickoff_time"].dt.tz_localize('UTC')
    else:
        fix_df["kickoff_time"] = fix_df["kickoff_time"].dt.tz_convert('UTC')

    # Get current time in UTC
    now_utc = datetime.now(pytz.UTC)

    # Filter for fixtures that are not finished and have kickoff_time after now
    fix_df = fix_df[(fix_df["finished"] == False) & (fix_df["kickoff_time"] > now_utc)].copy()
    if fix_df.empty:
        st.warning("No upcoming fixtures after the current time.")
        return pd.DataFrame(columns=["club", "club_next_difficulty", "club_next_opponent"])

    # Map club IDs to names
    id_map = dict(zip(clubs_df["id"], clubs_df["name"]))
    fix_df["HomeName"] = fix_df["team_h"].map(id_map)
    fix_df["AwayName"] = fix_df["team_a"].map(id_map)

    # Rename difficulty columns
    fix_df.rename(columns={
        "team_h_difficulty": "HomeDiff",
        "team_a_difficulty": "AwayDiff"
    }, inplace=True)

    # Create two entries per fixture: one for home, one for away
    home_entries = fix_df[["HomeName", "AwayName", "HomeDiff", "kickoff_time"]].copy()
    home_entries.rename(columns={
        "HomeName": "club",
        "AwayName": "opponent",
        "HomeDiff": "difficulty"
    }, inplace=True)

    away_entries = fix_df[["AwayName", "HomeName", "AwayDiff", "kickoff_time"]].copy()
    away_entries.rename(columns={
        "AwayName": "club",
        "HomeName": "opponent",
        "AwayDiff": "difficulty"
    }, inplace=True)

    combined_df = pd.concat([home_entries, away_entries], ignore_index=True)

    # Sort by club and kickoff_time
    combined_df.sort_values(by=["club", "kickoff_time"], inplace=True)
    combined_df = combined_df.drop_duplicates(subset=["club"], keep='first')

    combined_df.rename(columns={
        "difficulty": "club_next_difficulty",
        "opponent": "club_next_opponent"
    }, inplace=True)

    combined_df = combined_df[["club", "club_next_difficulty", "club_next_opponent"]]
    return combined_df

def refresh_data():
    """
    Fetch new data, prepare players/clubs, compute next fixture difficulty,
    and store everything in session state.
    """
    raw_data = fetch_fpl_data()
    p_df, c_df = prepare_data(raw_data)

    if not c_df.empty:
        difficulty_df = compute_next_fixture_difficulty(c_df)
    else:
        difficulty_df = pd.DataFrame(columns=["club", "club_next_difficulty", "club_next_opponent"])

    st.session_state["raw_fpl_data"] = raw_data
    st.session_state["players"], st.session_state["clubs"] = p_df, c_df
    st.session_state["club_difficulty"] = difficulty_df

# ---------------------------------------------------------------------------
# 4. PAGE SECTIONS / TABS
# ---------------------------------------------------------------------------
def hero_banner():
    st.markdown(
        """
        <div class="hero-banner">
            <div class="hero-text">
                <h1>Premier League Next-Gen</h1>
                <p>An interactive, real-time dashboard for Fantasy Premier League fans!</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def instructions_expander():
    with st.expander("Click for Quick Instructions & Navigation Tips"):
        st.write("""
        **Navigation**:
        - The app is organized into different **Tabs** below.
        - Each tab has a unique feature: from 'Overview' to 'Best XI'.

        **Data Refresh**:
        - Click the **floating refresh button** at the top-right 
          corner to re-fetch the latest FPL data & fixture difficulties.

        **Key Features**:
        - **Overview**: Explore top players by various metrics.
        - **Search Player**: Search by last name substring (and see player images).
        - **Compare Clubs**: Compare aggregated stats between two clubs.
        - **Compare Players**: Compare multiple players side by side (with photos and a chart).
        - **Best Players**: Position-based top performers by advanced metrics.
        - **Advanced Explorer**: Pick any numeric columns for a custom scatter plot.
        - **Best XI**: Incorporates next fixture difficulty and opponent into the scoring formula.
        
        Enjoy exploring the data!
        """)

# ------------------ 4a. Overview ------------------
def tab_overview(players_df):
    st.markdown("## Overview: Explore Top Performers by Your Preferred Metric")
    if players_df.empty:
        st.warning("No player data available.")
        return

    metric_options = [
        "total_points", "goals_scored", "assists", 
        "clean_sheets", "minutes_played", "popularity", 
        "cost", "form"
    ]
    chosen_metric = st.selectbox("Choose a Metric to Rank Players By:", metric_options, index=0)
    top_n = st.slider("How many top players to display?", min_value=5, max_value=50, value=10)

    top_players = players_df.sort_values(by=chosen_metric, ascending=False).head(top_n)
    
    st.write(f"### Top {top_n} Players by **{chosen_metric.replace('_', ' ').title()}**")
    fig = px.bar(
        top_players,
        x="last_name",
        y=chosen_metric,
        color="club",
        title=f"Top {top_n} by {chosen_metric.replace('_', ' ').title()}",
        color_discrete_sequence=px.colors.qualitative.Pastel2
    )
    fig.update_layout(template="plotly_dark", xaxis_title="Player", yaxis_title=chosen_metric.replace('_', ' ').title())
    st.plotly_chart(fig)
    
    st.write("### Detailed Stats Table")
    st.dataframe(
        top_players[
            [
                "first_name", "last_name", "club", "position", 
                "total_points", "goals_scored", "assists", 
                "clean_sheets", "cost", "popularity", "form", 
                "hours_played"
            ]
        ],
        height=600
    )

# ------------------ 4b. Search Player ------------------
def tab_search_player(players_df):
    st.markdown("## Search for a Player")
    if players_df.empty:
        st.warning("No data.")
        return

    name_query = st.text_input("Type part of a last name (e.g., 'Salah'):")
    if name_query:
        results = players_df[players_df["last_name"].str.contains(name_query, case=False, na=False)]
        if results.empty:
            st.info("No matching players found.")
        else:
            st.write(f"**Found {len(results)} player(s).**")
            for idx, row in results.iterrows():
                photo_url = row.get("photo_url", "https://via.placeholder.com/110x140.png?text=No+Image")
                st.markdown(f"### {row['first_name']} {row['last_name']}")
                colA, colB = st.columns([1,2])
                with colA:
                    st.image(photo_url, width=110)
                with colB:
                    st.write(f"**Club**: {row['club']}")
                    st.write(f"**Position**: {row['position']}")
                    st.write(f"**Total Points**: {row['total_points']}")
                    st.write(f"**Goals Scored**: {row['goals_scored']}")
                    st.write(f"**Assists**: {row['assists']}")
                    st.write(f"**Clean Sheets**: {row['clean_sheets']}")
                    st.write(f"**Cost**: £{row['cost']}m")
                    st.write(f"**Popularity**: {row['popularity']}%")
                st.markdown("---")

# ------------------ 4c. Compare Clubs ------------------
def tab_team_comparison(players_df, clubs_df):
    st.markdown("## Compare Two Clubs")
    if players_df.empty or clubs_df.empty:
        st.warning("No data available.")
        return

    club_list = sorted(clubs_df["name"].dropna().unique().tolist())
    col1, col2 = st.columns(2)
    with col1:
        c1 = st.selectbox("Club 1", club_list, key="compare_club1")
    with col2:
        c2 = st.selectbox("Club 2", club_list, key="compare_club2")

    if c1 and c2:
        c1_data = players_df[players_df["club"] == c1]
        c2_data = players_df[players_df["club"] == c2]

        c1_sums = c1_data[["total_points", "goals_scored", "assists", "clean_sheets"]].sum()
        c2_sums = c2_data[["total_points", "goals_scored", "assists", "clean_sheets"]].sum()

        comp_df = pd.DataFrame({
            "Metric": ["Points", "Goals", "Assists", "Clean Sheets"],
            c1: c1_sums.values,
            c2: c2_sums.values
        })

        fig = px.bar(
            comp_df,
            x="Metric",
            y=[c1, c2],
            barmode="group",
            color_discrete_sequence=["#FFC107", "#03A9F4"],
            title=f"{c1} vs {c2}"
        )
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig)

# ------------------ 4d. Compare Players ------------------
def tab_compare_players(players_df):
    st.markdown("## Compare Players")
    if players_df.empty:
        st.warning("No player data available.")
        return

    player_list = sorted(players_df["last_name"].unique().tolist())
    selected_players = st.multiselect(
        "Select one or more players to compare:",
        options=player_list
    )
    if not selected_players:
        st.info("No players selected.")
        return

    selected_df = players_df[players_df["last_name"].isin(selected_players)].copy()

    # Cap the display at 5 players
    n_players = len(selected_df)
    max_cols = min(n_players, 5)

    if n_players > 5:
        st.warning("Displaying first 5 players only for side-by-side layout.")
        selected_df = selected_df.head(5)

    cols = st.columns(max_cols)
    for idx, (i, row) in enumerate(selected_df.iterrows()):
        col_index = idx % max_cols
        with cols[col_index]:
            photo_url = row.get("photo_url", "https://via.placeholder.com/110x140.png?text=No+Image")
            st.image(photo_url, width=110)
            st.markdown(f"### {row['first_name']} {row['last_name']}")
            st.write(f"**Club**: {row['club']}")
            st.write(f"**Position**: {row['position']}")
            st.write(f"**Total Points**: {row['total_points']}")
            st.write(f"**Goals**: {row['goals_scored']}")
            st.write(f"**Assists**: {row['assists']}")
            st.write(f"**Clean Sheets**: {row['clean_sheets']}")
            st.write(f"**Cost**: £{row['cost']}m")
            st.write(f"**Popularity**: {row['popularity']}%")

    st.write("---")
    st.markdown("### Comparison Chart")

    metrics = ["total_points", "goals_scored", "assists", "clean_sheets", "cost"]
    chart_data = {"Metric": metrics}
    for idx, (i, row) in enumerate(selected_df.iterrows()):
        player_name = f"{row['first_name']} {row['last_name']}"
        values = [row[m] for m in metrics]
        chart_data[player_name] = values

    comparison_df = pd.DataFrame(chart_data)
    fig_comp = px.bar(
        comparison_df,
        x="Metric",
        y=list(comparison_df.columns.drop("Metric")),
        barmode="group",
        title="Key Metrics Comparison",
        labels={"value": "Value", "variable": "Player"},
        template="plotly_dark"
    )
    fig_comp.update_layout(legend_title_text="Players")
    st.plotly_chart(fig_comp)

# ------------------ 4e. Best Players ------------------
def tab_best_players(players_df):
    st.markdown("## Best Players by Position")
    if players_df.empty or "position" not in players_df.columns:
        st.warning("No players or missing 'position' info.")
        return

    # Define relevant metrics per position
    metrics_map = {
        "Goalkeeper": ["saves", "clean_sheets", "form"],
        "Defender": ["expected_goals", "expected_assists", "clean_sheets", "influence", "creativity", "threat", "form"],
        "Midfielder": ["expected_goals", "expected_assists", "influence", "creativity", "threat", "form"],
        "Forward": ["expected_goals", "expected_assists", "influence", "creativity", "threat", "form"]
    }

    positions_in_data = sorted(players_df["position"].dropna().unique().tolist())
    chosen_position = st.selectbox("Select a Position", positions_in_data)
    relevant_metrics = metrics_map.get(chosen_position, [])

    # Filter for chosen position & compute combined_score
    pos_df = players_df[players_df["position"] == chosen_position].copy()
    for m in relevant_metrics:
        pos_df[m] = pd.to_numeric(pos_df[m], errors="coerce").fillna(0)

    pos_df["combined_score"] = pos_df[relevant_metrics].sum(axis=1)
    top_10 = pos_df.sort_values("combined_score", ascending=False).head(10).reset_index(drop=True)

    st.markdown(f"### Top 10 {chosen_position}s by Combined Score")

    # Create a bar chart using graph_objects
    fig = go.Figure()

    # Add a Bar trace
    fig.add_trace(
        go.Bar(
            x=top_10["last_name"],
            y=top_10["combined_score"],
            text=top_10["club"],
            textposition="auto",
            marker_color="indianred"  # pick any color or colormap you like
        )
    )

    # Add player images on top of each bar
    # We'll place each image slightly above the bar,
    # using xref="x", yref="y" so that coordinates align with data values.
    for i, row in top_10.iterrows():
        # Fallback if we have a missing photo:
        photo_url = row["photo_url"] if pd.notnull(row["photo_url"]) else "https://via.placeholder.com/110x140.png?text=No+Image"
        
        # We'll add a small offset to the bar's top so images don't overlap
        y_offset = row["combined_score"] * 0.05 + 1  # tweak as needed

        fig.add_layout_image(
            dict(
                source=photo_url,
                xref="x",      # x is in terms of the x-axis data
                yref="y",      # y is in terms of the y-axis data
                x=row.name,    # the index in top_10 => i
                y=row["combined_score"] + y_offset,
                xanchor="center",
                yanchor="bottom",
                sizex=0.6,     # how wide the image should be
                sizey=0.6,     # how tall the image should be
                sizing="contain",
                opacity=1.0,
                layer="above"
            )
        )

    fig.update_layout(
        template="plotly_dark",
        title=f"Top 10 {chosen_position}s with Player Images",
        xaxis_title="Player (Last Name)",
        yaxis_title="Combined Score",
        # Increase margins so images are not cut off
        margin=dict(l=60, r=60, t=80, b=80)
    )

    st.plotly_chart(fig, use_container_width=True)

    # Display a detailed stats table below
    st.markdown("### Detailed Stats for the Top 10")
    display_cols = ["first_name", "last_name", "club", "position"] + relevant_metrics + ["combined_score"]
    st.dataframe(top_10[display_cols].reset_index(drop=True), height=600)


# ------------------ 4f. Advanced Explorer ------------------
def tab_advanced(players_df):
    st.markdown("## Advanced Explorer (Scatter Plot)")
    if players_df.empty:
        st.warning("No data to explore.")
        return

    numeric_cols = [
        "total_points","goals_scored","assists","clean_sheets","influence",
        "creativity","threat","expected_goals","expected_assists","cost",
        "popularity","hours_played","yellow_cards","red_cards","form"
    ]
    col1, col2 = st.columns(2)
    with col1:
        x_metric = st.selectbox("X Axis Metric:", numeric_cols, index=numeric_cols.index("cost"))
    with col2:
        y_metric = st.selectbox("Y Axis Metric:", numeric_cols, index=numeric_cols.index("popularity"))

    color_by = st.selectbox("Color By:", ["club", "position"], index=0)
    size_metric = st.selectbox("Bubble Size (optional):", ["None"] + numeric_cols, index=0)

    scatter_config = dict(
        data_frame=players_df,
        x=x_metric,
        y=y_metric,
        hover_data=["last_name","club","position","cost","popularity","hours_played","form","total_points"],
        color=color_by,
        template="plotly_dark"
    )
    if size_metric != "None":
        scatter_config["size"] = size_metric
        scatter_config["size_max"] = 25
    
    fig = px.scatter(**scatter_config)
    fig.update_layout(title=f"{x_metric.replace('_', ' ').title()} vs {y_metric.replace('_', ' ').title()}")
    st.plotly_chart(fig)

# ------------------ 4g. Best XI ------------------
def tab_best_xi(players_df, difficulty_df):
    """
    Allows users to select a formation, computes the Best XI,
    and visualizes it on a football pitch. 
    Excludes suspended ('s') AND injured ('i') players.
    """
    st.markdown("## Best XI with Formation Selection")
    if players_df.empty or "position" not in players_df.columns:
        st.warning("No player data or missing 'position' info.")
        return

    # Exclude suspended + injured
    players_df = players_df[~players_df["status"].isin(["s", "i"])]

    formations = {
        '1-3-5-2': {'Goalkeeper':1, 'Defender':3, 'Midfielder':5, 'Forward':2},
        '1-4-3-3': {'Goalkeeper':1, 'Defender':4, 'Midfielder':3, 'Forward':3},
        '1-4-4-2': {'Goalkeeper':1, 'Defender':4, 'Midfielder':4, 'Forward':2},
        '1-5-3-2': {'Goalkeeper':1, 'Defender':5, 'Midfielder':3, 'Forward':2},
        '1-5-4-1': {'Goalkeeper':1, 'Defender':5, 'Midfielder':4, 'Forward':1},
        '1-4-5-1': {'Goalkeeper':1, 'Defender':4, 'Midfielder':5, 'Forward':1},
    }
    selected_formation = st.selectbox("Select Formation:", options=list(formations.keys()), index=0)
    formation_structure = formations[selected_formation]

    if difficulty_df.empty:
        players_df["club_next_difficulty"] = 3
        players_df["club_next_opponent"] = "Unknown"
    else:
        players_df = players_df.merge(difficulty_df, on="club", how="left")
        players_df["club_next_difficulty"] = players_df["club_next_difficulty"].fillna(3)
        players_df["club_next_opponent"] = players_df["club_next_opponent"].fillna("Unknown")

    # Weighted formula for picking best XI
    players_df["score_for_best_xi"] = (
        players_df["total_points"]
        + 1.5 * players_df["form"]
        + 3.0 / players_df["club_next_difficulty"]
    )

    def pick_top_n(position, n):
        subset = players_df[players_df["position"] == position]
        return subset.sort_values("score_for_best_xi", ascending=False).head(n)

    selected_players = []
    for pos, count in formation_structure.items():
        top_players = pick_top_n(pos, count)
        if len(top_players) < count:
            st.warning(f"Not enough players available for position: {pos}. Needed {count}, found {len(top_players)}.")
        selected_players.append(top_players)

    best_11 = pd.concat(selected_players, ignore_index=True)

    def assign_coordinates(best_11_df, formation):
        coordinates = []
        pos_counters = {"Goalkeeper": 0, "Defender": 0, "Midfielder": 0, "Forward": 0}
        x_positions = {
            'Goalkeeper': 5,
            'Defender': 30,
            'Midfielder': 50,
            'Forward': 70
        }
        y_ranges = {
            'Defender': {
                3: [20, 40, 60],
                4: [15, 30, 50, 65],
                5: [10, 25, 40, 55, 70]
            },
            'Midfielder': {
                3: [30, 50, 70],
                4: [20, 35, 65, 80],
                5: [10, 25, 40, 55, 70]
            },
            'Forward': {
                1: [50],
                2: [35, 65],
                3: [30, 50, 70]
            }
        }

        for _, row in best_11_df.iterrows():
            pos = row['position']
            count = pos_counters[pos]
            if pos == "Goalkeeper":
                x, y = x_positions[pos], 50
            else:
                total = formation_structure[pos]
                y_candidates = y_ranges.get(pos, {}).get(total, [50])
                if count < len(y_candidates):
                    y = y_candidates[count]
                else:
                    y = 50
                x = x_positions[pos]
            coordinates.append((x, y))
            pos_counters[pos] += 1

        best_11_df = best_11_df.copy()
        best_11_df["x"] = [coord[0] for coord in coordinates]
        best_11_df["y"] = [coord[1] for coord in coordinates]
        return best_11_df

    best_11 = assign_coordinates(best_11, selected_formation)

    @st.cache_data(show_spinner=False)
    def get_player_image(url):
        try:
            response = requests.get(url)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content))
            return img
        except:
            return Image.open(BytesIO(requests.get("https://via.placeholder.com/60x80.png?text=No+Image").content))

    pitch = Pitch(pitch_type='statsbomb', pitch_color='#2b2b2b', line_color='white', linewidth=2)
    fig, ax = pitch.draw(figsize=(10, 6))

    for idx, row in best_11.iterrows():
        img = get_player_image(row['photo_url'])
        img = img.resize((60, 80)) 
        img_np = np.array(img)

        x_pitch = (row['x'] / 100) * 120
        y_pitch = (row['y'] / 100) * 80

        imagebox = OffsetImage(img_np, zoom=0.6)
        ab = AnnotationBbox(imagebox, (x_pitch, y_pitch),
                            frameon=False, box_alignment=(0.5, 0.5))
        ax.add_artist(ab)

    st.pyplot(fig)

    st.write("### Detailed Best XI Table")
    columns_to_show = [
        "first_name", "last_name", "club", "position", "status", 
        "total_points", "form", "club_next_difficulty", "club_next_opponent", 
        "score_for_best_xi", "goals_scored", "assists", "clean_sheets", "cost"
    ]
    st.dataframe(best_11[columns_to_show].reset_index(drop=True))

# ---------------------------------------------------------------------------
# 5. MAIN APP
# ---------------------------------------------------------------------------
if "players" not in st.session_state or st.session_state["players"].empty:
    with st.spinner("Fetching and processing data..."):
        refresh_data()

hero_banner()
instructions_expander()

# Tabs (Ask Llama removed)
tab_labels = [
    "Overview", 
    "Search Player", 
    "Compare Clubs", 
    "Compare Players",
    "Best Players", 
    "Advanced Explorer", 
    "Best XI"
]
tabs = st.tabs(tab_labels)

with tabs[0]:
    tab_overview(st.session_state["players"])
with tabs[1]:
    tab_search_player(st.session_state["players"])
with tabs[2]:
    tab_team_comparison(st.session_state["players"], st.session_state["clubs"])
with tabs[3]:
    tab_compare_players(st.session_state["players"])
with tabs[4]:
    tab_best_players(st.session_state["players"])
with tabs[5]:
    tab_advanced(st.session_state["players"])
with tabs[6]:
    tab_best_xi(st.session_state["players"], st.session_state["club_difficulty"])

# Floating Refresh Button
st.markdown(
    """
    <button class="floating-btn" onclick="window.location.reload();">
        &#x21bb;
    </button>
    """,
    unsafe_allow_html=True
)
