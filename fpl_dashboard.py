import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import numpy as np

# ------------------------------------------------------------------------------
# 1. PAGE & STYLE CONFIGURATION
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Premier League Next-Gen",
    layout="wide",
    initial_sidebar_state="collapsed"
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

# ------------------------------------------------------------------------------
# 2. SESSION STATE SETUP
# ------------------------------------------------------------------------------
if "raw_fpl_data" not in st.session_state:
    st.session_state["raw_fpl_data"] = {}
if "players" not in st.session_state:
    st.session_state["players"] = pd.DataFrame()
if "clubs" not in st.session_state:
    st.session_state["clubs"] = pd.DataFrame()
if "club_difficulty" not in st.session_state:
    st.session_state["club_difficulty"] = pd.DataFrame()

# ------------------------------------------------------------------------------
# 3. DATA FETCHING & PREPARATION
# ------------------------------------------------------------------------------
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

    return players_df, clubs_df

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
        return pd.DataFrame()

def compute_next_fixture_difficulty(clubs_df):
    """
    For each club, find the earliest *un-finished* fixture
    and record its difficulty and opponent. Return a DataFrame with:
       club, club_next_difficulty, club_next_opponent
    """
    fix_df = fetch_fixtures_data()
    if fix_df.empty:
        return pd.DataFrame(columns=["club", "club_next_difficulty", "club_next_opponent"])

    fix_df["kickoff_time"] = pd.to_datetime(fix_df["kickoff_time"], errors="coerce")
    fix_df = fix_df[fix_df["finished"] == False].copy()
    if fix_df.empty:
        return pd.DataFrame(columns=["club", "club_next_difficulty", "club_next_opponent"])

    # Map IDs to club names
    id_map = dict(zip(clubs_df["id"], clubs_df["name"]))
    fix_df["HomeName"] = fix_df["team_h"].map(id_map)
    fix_df["AwayName"] = fix_df["team_a"].map(id_map)

    fix_df.rename(columns={
        "team_h_difficulty": "HomeDiff",
        "team_a_difficulty": "AwayDiff"
    }, inplace=True)

    fix_df.sort_values("kickoff_time", inplace=True)

    # Home perspective
    home_df = fix_df[["HomeName", "AwayName", "HomeDiff", "kickoff_time"]].dropna(subset=["HomeName"])
    home_df["club"] = home_df["HomeName"]
    home_df["club_next_difficulty"] = home_df["HomeDiff"]
    home_df["club_next_opponent"] = home_df["AwayName"]  # Opponent for home club is the away team
    home_df = home_df.groupby("club", as_index=False).first()
    home_df = home_df[["club", "club_next_difficulty", "club_next_opponent"]]

    # Away perspective
    away_df = fix_df[["AwayName", "HomeName", "AwayDiff", "kickoff_time"]].dropna(subset=["AwayName"])
    away_df["club"] = away_df["AwayName"]
    away_df["club_next_difficulty"] = away_df["AwayDiff"]
    away_df["club_next_opponent"] = away_df["HomeName"]  # Opponent for away club is the home team
    away_df = away_df.groupby("club", as_index=False).first()
    away_df = away_df[["club", "club_next_difficulty", "club_next_opponent"]]

    # Combine home and away DataFrames
    combined_df = pd.concat([home_df, away_df], ignore_index=True)

    # Group by club to ensure each club appears only once with their earliest fixture
    combined_df = combined_df.groupby("club", as_index=False).first()

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
        # Ensure 'club_next_opponent' is included even if no data
        difficulty_df = pd.DataFrame(columns=["club", "club_next_difficulty", "club_next_opponent"])

    st.session_state["raw_fpl_data"] = raw_data
    st.session_state["players"], st.session_state["clubs"] = p_df, c_df
    st.session_state["club_difficulty"] = difficulty_df

# ------------------------------------------------------------------------------
# 4. PAGE SECTIONS / TABS
# ------------------------------------------------------------------------------

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
        - **Compare Players**: Compare multiple players side by side (with photos and a comparison chart).
        - **Best Players**: Position-based top performers by advanced metrics.
        - **Advanced Explorer**: Pick any numeric columns for a custom scatter plot.
        - **Best XI**: Incorporates next fixture difficulty and opponent into the scoring formula 
          (1-4-3-3 formation).
        
        Enjoy exploring the data!
        """)

# --- 4a. Overview ---
def tab_overview(players_df):
    """
    Enhanced Overview:
    1) Lets users pick a 'metric' to rank players (e.g., 'total_points', 'goals_scored', etc.).
    2) Allows a slider to choose how many top players to display (from 5 up to 50).
    3) Displays a bar chart + a detailed stats table with the chosen top players.
    """
    st.markdown("## Overview: Explore Top Performers by Your Preferred Metric")
    
    # If there's no data, bail out
    if players_df.empty:
        st.warning("No player data available.")
        return
    
    # Define a few interesting metrics users might want to sort by
    metric_options = [
        "total_points", "goals_scored", "assists", 
        "clean_sheets", "minutes_played", "popularity", 
        "cost", "form"
    ]
    
    # Let the user pick which metric to rank by
    chosen_metric = st.selectbox("Choose a Metric to Rank Players By:", metric_options, index=0)
    
    # Let the user pick how many players to display
    top_n = st.slider("How many top players to display?", min_value=5, max_value=50, value=10)
    
    # Sort players by the chosen metric (descending) and pick top_n
    top_players = players_df.sort_values(by=chosen_metric, ascending=False).head(top_n)
    
    # Display a bar chart
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
    
    # Display a stats table
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

# --- 4b. Search Player (with Images) ---
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
                photo_str = row.get("photo", "")
                if photo_str.endswith(".jpg"):
                    numeric_part = photo_str.replace(".jpg", "")
                    photo_url = f"https://resources.premierleague.com/premierleague/photos/players/110x140/p{numeric_part}.png"
                else:
                    photo_url = "https://via.placeholder.com/110x140.png?text=No+Image"

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

# --- 4c. Compare Clubs ---
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

# --- 4d. Compare Players (Multi-select with Photos and Graph) ---
def tab_compare_players(players_df):
    """
    Allows the user to select multiple players from a dropdown,
    display each player's photo/stats, AND create a grouped bar chart
    comparing key metrics among all selected players.
    """
    st.markdown("## Compare Players")

    if players_df.empty:
        st.warning("No player data available.")
        return

    # Sort by last_name for an easier selection
    player_list = sorted(players_df["last_name"].unique().tolist())
    selected_players = st.multiselect(
        "Select one or more players to compare:",
        options=player_list
    )

    if not selected_players:
        st.info("No players selected.")
        return

    # Filter the main DataFrame
    selected_df = players_df[players_df["last_name"].isin(selected_players)].copy()

    # Cap the display at 5 players (to keep layout manageable)
    n_players = len(selected_df)
    max_cols = min(n_players, 5)

    if n_players > 5:
        st.warning("Displaying first 5 players only for side-by-side layout.")
        selected_df = selected_df.head(5)

    # Display each selected player's info in columns
    cols = st.columns(max_cols)
    for idx, (i, row) in enumerate(selected_df.iterrows()):
        col_index = idx % max_cols
        with cols[col_index]:
            # Construct the player photo URL
            photo_str = row.get("photo", "")
            if photo_str.endswith(".jpg"):
                numeric_part = photo_str.replace(".jpg", "")
                photo_url = f"https://resources.premierleague.com/premierleague/photos/players/110x140/p{numeric_part}.png"
            else:
                photo_url = "https://via.placeholder.com/110x140.png?text=No+Image"

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

    # Decide which metrics to compare in the bar chart
    metrics = ["total_points", "goals_scored", "assists", "clean_sheets", "cost"]

    # Build a comparison DataFrame with rows = metrics, columns = players
    chart_data = {"Metric": metrics}
    for idx, (i, row) in enumerate(selected_df.iterrows()):
        player_name = f"{row['first_name']} {row['last_name']}"
        values = [row[m] for m in metrics]
        chart_data[player_name] = values

    comparison_df = pd.DataFrame(chart_data)

    # Use Plotly Express to create a grouped bar chart
    fig_comp = px.bar(
        comparison_df,
        x="Metric",
        y=list(comparison_df.columns.drop("Metric")),  # All player columns
        barmode="group",
        title="Key Metrics Comparison",
        labels={"value": "Value", "variable": "Player"},
        template="plotly_dark"
    )
    fig_comp.update_layout(legend_title_text="Players")
    st.plotly_chart(fig_comp)

# --- 4e. Best Players ---
def tab_best_players(players_df):
    st.markdown("## Best Players by Position")
    if players_df.empty or "position" not in players_df.columns:
        st.warning("No players or missing 'position' info.")
        return

    metrics_map = {
        "Goalkeeper": ["saves", "clean_sheets", "form"],
        "Defender": ["expected_goals", "expected_assists", "clean_sheets", "influence", "creativity", "threat", "form"],
        "Midfielder": ["expected_goals", "expected_assists", "influence", "creativity", "threat", "form"],
        "Forward": ["expected_goals", "expected_assists", "influence", "creativity", "threat", "form"]
    }

    positions_in_data = sorted(players_df["position"].dropna().unique().tolist())
    chosen_position = st.selectbox("Position", positions_in_data)
    relevant_metrics = metrics_map.get(chosen_position, [])

    pos_df = players_df[players_df["position"] == chosen_position].copy()
    for m in relevant_metrics:
        pos_df[m] = pd.to_numeric(pos_df[m], errors="coerce").fillna(0)

    pos_df["combined_score"] = pos_df[relevant_metrics].sum(axis=1)
    top_10 = pos_df.sort_values("combined_score", ascending=False).head(10)

    fig = px.bar(
        top_10,
        x="last_name",
        y="combined_score",
        color="club",
        color_discrete_sequence=px.colors.qualitative.Set3,
        title=f"Top 10 {chosen_position}s"
    )
    fig.update_layout(template="plotly_dark", xaxis_title="Player", yaxis_title="Score")
    st.plotly_chart(fig)

    st.dataframe(top_10[["first_name", "last_name", "club", "position"] + relevant_metrics])

# --- 4f. Advanced Explorer ---
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

# --- 4g. Best XI with Difficulty and Opponent ---
def tab_best_xi(players_df, difficulty_df):
    """
    1) Merge each player's club to 'club_next_difficulty' & 'club_next_opponent'
    2) Compute: score_for_best_xi = total_points + 1.5*form + 3.0*(club_next_difficulty)
    3) Pick a 1-4-3-3 squad
    """
    st.markdown("## Best XI (1-4-3-3) with Difficulty & Opponent Info")
    if players_df.empty or "position" not in players_df.columns:
        st.warning("No player data or missing 'position' info.")
        return

    # If difficulty_df is empty, fallback to default values
    if difficulty_df.empty:
        players_df["club_next_difficulty"] = 3
        players_df["club_next_opponent"] = "Unknown"
    else:
        # Merge on 'club' to include difficulty and opponent info
        players_df = players_df.merge(
            difficulty_df,
            on="club",
            how="left"
        )
        players_df["club_next_difficulty"] = players_df["club_next_difficulty"].fillna(3)
        players_df["club_next_opponent"] = players_df["club_next_opponent"].fillna("Unknown")

    # Weighted formula for Best XI scoring
    players_df["score_for_best_xi"] = (
        players_df["total_points"] 
        + 1.5 * players_df["form"] 
        + 3.0 * ( (5-players_df["club_next_difficulty"])
    )

    # Function to pick top N players per position
    def pick_top_n(position, n):
        subset = players_df[players_df["position"] == position]
        return subset.sort_values("score_for_best_xi", ascending=False).head(n)

    # Select players for each position
    gk = pick_top_n("Goalkeeper", 1)
    defenders = pick_top_n("Defender", 4)
    mids = pick_top_n("Midfielder", 3)
    fwds = pick_top_n("Forward", 3)

    # Combine into Best XI
    best_11 = pd.concat([gk, defenders, mids, fwds], ignore_index=True)

    # Display Best XI Bar Chart
    fig = px.bar(
        best_11,
        x="last_name",
        y="score_for_best_xi",
        color="club",
        color_discrete_sequence=px.colors.qualitative.Pastel2,
        title="Recommended XI (Weighted by Points, Form, & Next Fixture Difficulty)"
    )
    fig.update_layout(template="plotly_dark", xaxis_title="Player", yaxis_title="Score")
    st.plotly_chart(fig)

    # Display Detailed Best XI Table Including Opponent
    st.write("### Detailed Best XI Table")
    columns_to_show = [
        "first_name", "last_name", "club", "position", "total_points", "form",
        "club_next_difficulty", "club_next_opponent", "score_for_best_xi",
        "goals_scored", "assists", "clean_sheets", "cost"
    ]
    st.dataframe(best_11[columns_to_show])

# ------------------------------------------------------------------------------
# 5. MAIN APP
# ------------------------------------------------------------------------------
if "players" not in st.session_state or st.session_state["players"].empty:
    refresh_data()

# Hero Banner & Intro
hero_banner()
instructions_expander()

# Tabs (Includes 'Compare Players' but no full fixtures tab)
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
