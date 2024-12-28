import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import numpy as np
import datetime

# ------------------------------------------------------------------------------
# 1. PAGE & STYLE CONFIGURATION
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Premier League Next-Gen",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# A custom CSS to create a hero banner, floating button, etc.
CUSTOM_CSS = """
<style>
/* Hide default Streamlit header/footer */
header, footer {visibility: hidden;}

body {
    background-color: #2b2b2b; /* Dark background */
    color: #f0f0f0;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

div[data-testid="stToolbar"] {
    visibility: hidden;
    height: 0%;
    position: fixed;
}

/* Hero Banner styling */
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

.floating-btn {
    position: fixed;
    bottom: 25px;
    right: 25px;
    background-color: #FF4B4B;
    border: none;
    outline: none;
    color: white;
    cursor: pointer;
    padding: 15px;
    border-radius: 50%;
    font-size: 20px;
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

# Inject the custom CSS
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

# ------------------------------------------------------------------------------
# 3. DATA FETCHING & PREPARATION
# ------------------------------------------------------------------------------
@st.cache_data(ttl=60 * 60)
def fetch_fpl_data():
    """Fetch raw JSON from the official FPL 'bootstrap-static' endpoint."""
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

def refresh_data():
    """Re-fetch data and populate session state."""
    raw_data = fetch_fpl_data()
    st.session_state["raw_fpl_data"] = raw_data
    p_df, c_df = prepare_data(raw_data)
    st.session_state["players"], st.session_state["clubs"] = p_df, c_df

# ------------------------------------------------------------------------------
# 4. PAGE SECTIONS / TABS
# ------------------------------------------------------------------------------

# Hero Banner
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
    """
    Provides a collapsible section with instructions or tips on using the site.
    """
    with st.expander("Click for Quick Instructions & Navigation Tips"):
        st.write("""
        **Navigation**:
        - The app is organized into different **Tabs** below.
        - Each tab has a unique feature: from 'Overview' to 'Best XI'.
        
        **Data Refresh**:
        - At any point, click the **floating refresh button** at the bottom-right 
          corner to re-fetch the latest FPL data from the official API.
        
        **Some Key Features**:
        - **Overview**: Quick glance at top players by total points.
        - **Search Player**: Search by last name substring (and see player images).
        - **Compare Clubs**: Compare aggregated stats between two clubs.
        - **Fixtures**: Filter upcoming/finished fixtures by team, status, or date.
        - **Best Players**: Position-based top performers by advanced metrics.
        - **Advanced Explorer**: Pick any numeric columns for a custom scatter plot.
        - **Best XI**: Our recommended lineup based on total points & form (1-4-3-3).
        
        Make yourself at home—enjoy exploring the data!
        """)

# --- 4a. Overview ---
def tab_overview(players_df):
    st.markdown("## Overview: Top 30 Players by Total Points")
    if players_df.empty:
        st.warning("No player data available.")
        return

    top_players = players_df.sort_values("total_points", ascending=False).head(30)

    fig = px.bar(
        top_players,
        x="last_name",
        y="total_points",
        color="club",
        color_discrete_sequence=px.colors.qualitative.Pastel2,
        title="Top Scoring Players"
    )
    fig.update_layout(template="plotly_dark", xaxis_title="Player", yaxis_title="Points")
    st.plotly_chart(fig)

    st.write("#### Quick Stats Table")
    st.dataframe(
        top_players[
            [
                "first_name", "last_name", "club", "position", 
                "total_points", "goals_scored", "assists", 
                "clean_sheets", "cost", "popularity"
            ]
        ],
        height=500
    )

# --- 4b. Search Player (with Images) ---
def tab_search_player(players_df):
    st.markdown("## Search for a Player (with Photo)")
    if players_df.empty:
        st.warning("No data.")
        return

    # We rely on the 'photo' column from the raw FPL data (elements).
    # Example value: '218753.jpg' -> We'll produce a URL: 
    # "https://resources.premierleague.com/premierleague/photos/players/110x140/p218753.png"
    # by parsing the numeric portion of the filename.

    name_query = st.text_input("Type part of a last name (e.g., 'Kane'):")
    if name_query:
        # Filter players whose 'last_name' contains the query
        results = players_df[players_df["last_name"].str.contains(name_query, case=False, na=False)]
        if results.empty:
            st.info("No matching players found.")
        else:
            st.write(f"**Found {len(results)} player(s).**")
            for idx, row in results.iterrows():
                # Construct the player photo URL if 'photo' field is valid
                photo_str = row.get("photo", "")  # e.g. "218753.jpg"
                # Attempt to parse the numeric portion
                if photo_str.endswith(".jpg"):
                    numeric_part = photo_str.replace(".jpg", "")
                    photo_url = f"https://resources.premierleague.com/premierleague/photos/players/110x140/p{numeric_part}.png"
                else:
                    # Fallback if we don't have a valid photo pattern
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
        c1 = st.selectbox("Club 1", club_list)
    with col2:
        c2 = st.selectbox("Club 2", club_list)

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

# --- 4d. Fixtures (Enhanced) ---
def tab_fixtures(clubs_df):
    st.markdown("## Upcoming & Recent Fixtures")
    try:
        # Fetch
        resp = requests.get("https://fantasy.premierleague.com/api/fixtures/")
        resp.raise_for_status()
        fix_df = pd.DataFrame(resp.json())

        if fix_df.empty:
            st.info("No fixture data found.")
            return

        fix_df["kickoff_time"] = pd.to_datetime(fix_df["kickoff_time"], errors="coerce")
        fix_df["Date"] = fix_df["kickoff_time"].dt.date
        fix_df["Time"] = fix_df["kickoff_time"].dt.strftime("%H:%M")

        # If all invalid
        if fix_df["Date"].dropna().empty:
            st.info("No valid fixture dates found.")
            return

        # Map clubs
        if not clubs_df.empty and "id" in clubs_df.columns and "name" in clubs_df.columns:
            id_map = dict(zip(clubs_df["id"], clubs_df["name"]))
            fix_df["Home"] = fix_df["team_h"].map(id_map)
            fix_df["Away"] = fix_df["team_a"].map(id_map)
        else:
            fix_df["Home"] = fix_df["team_h"]
            fix_df["Away"] = fix_df["team_a"]

        fix_df["Home Score"] = fix_df.get("team_h_score", None)
        fix_df["Away Score"] = fix_df.get("team_a_score", None)
        fix_df["Status"] = fix_df.apply(lambda x: "Finished" if x["finished"] else "Upcoming", axis=1)

        fix_df = fix_df[["Date","Time","Home","Away","Home Score","Away Score","Status"]]

        min_date = fix_df["Date"].min()
        max_date = fix_df["Date"].max()

        st.write("### Filter Options")
        if not clubs_df.empty:
            club_list = sorted(clubs_df["name"].dropna().unique().tolist())
            filter_club = st.selectbox("Filter by Club:", ["All"] + club_list)
        else:
            filter_club = "All"

        filter_status = st.selectbox("Filter by Status:", ["All","Upcoming","Finished"])

        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date)
        with col_end:
            end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)

        if start_date > end_date:
            st.warning("Start Date cannot be after End Date.")
            return

        # Apply filters
        filtered_df = fix_df.copy()
        if filter_club != "All":
            filtered_df = filtered_df[
                (filtered_df["Home"] == filter_club) | (filtered_df["Away"] == filter_club)
            ]
        if filter_status != "All":
            filtered_df = filtered_df[filtered_df["Status"] == filter_status]
        filtered_df = filtered_df[
            (filtered_df["Date"] >= start_date) & (filtered_df["Date"] <= end_date)
        ]

        if filtered_df.empty:
            st.info("No fixtures match your filters.")
            return

        st.write("### Fixtures by Date")
        fixture_counts = filtered_df.groupby("Date").size().reset_index(name="Num Fixtures")
        fixture_counts.sort_values("Date", inplace=True)

        fig_counts = px.bar(
            fixture_counts,
            x="Date",
            y="Num Fixtures",
            text="Num Fixtures",
            title="Number of Fixtures per Date (Filtered)",
            color_discrete_sequence=["#EB89B5"],
            labels={"Date": "Match Date", "Num Fixtures": "Count"}
        )
        fig_counts.update_layout(template="plotly_dark")
        fig_counts.update_traces(textposition="outside")
        st.plotly_chart(fig_counts)

        st.write("### Filtered Fixtures Table")
        st.dataframe(filtered_df, width=1200, height=500)

    except requests.RequestException as e:
        st.error(f"Cannot load fixtures: {e}")

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
    fig.update_layout(title=f"{x_metric} vs {y_metric}")
    st.plotly_chart(fig)

# --- 4g. Best XI ---
def tab_best_xi(players_df):
    st.markdown("## Best XI (1-4-3-3) by Points & Form")
    if players_df.empty or "position" not in players_df.columns:
        st.warning("No player data or missing 'position' info.")
        return

    # Weighted formula: total_points + 2×form
    players_df["score_for_best_xi"] = players_df["total_points"] + 2.0 * players_df["form"]

    # 1 GK, 4 Def, 3 Mid, 3 Fwd
    gk = players_df[players_df["position"] == "Goalkeeper"]\
        .sort_values("score_for_best_xi", ascending=False).head(1)
    defenders = players_df[players_df["position"] == "Defender"]\
        .sort_values("score_for_best_xi", ascending=False).head(4)
    mids = players_df[players_df["position"] == "Midfielder"]\
        .sort_values("score_for_best_xi", ascending=False).head(3)
    fwds = players_df[players_df["position"] == "Forward"]\
        .sort_values("score_for_best_xi", ascending=False).head(3)

    best_11 = pd.concat([gk, defenders, mids, fwds]).copy()

    fig = px.bar(
        best_11,
        x="last_name",
        y="score_for_best_xi",
        color="club",
        color_discrete_sequence=px.colors.qualitative.Pastel2,
        title="Recommended XI (Weighted by total_points + 2×form)"
    )
    fig.update_layout(template="plotly_dark", xaxis_title="Player", yaxis_title="Score")
    st.plotly_chart(fig)

    st.write("### Detailed Best XI Table")
    columns_to_show = [
        "first_name","last_name","club","position","total_points","form",
        "score_for_best_xi","goals_scored","assists","clean_sheets","cost"
    ]
    st.dataframe(best_11[columns_to_show])

# ------------------------------------------------------------------------------
# 5. MAIN APP
# ------------------------------------------------------------------------------
# 5a. Ensure data is loaded
if st.session_state["players"].empty or st.session_state["clubs"].empty:
    refresh_data()

# 5b. Hero Banner & Intro
hero_banner()
instructions_expander()

# 5c. Tabs
tab_labels = [
    "Overview", 
    "Search Player", 
    "Compare Clubs", 
    "Fixtures", 
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
    tab_fixtures(st.session_state["clubs"])
with tabs[4]:
    tab_best_players(st.session_state["players"])
with tabs[5]:
    tab_advanced(st.session_state["players"])
with tabs[6]:
    tab_best_xi(st.session_state["players"])

# 5d. Floating Refresh Button
st.markdown(
    """
    <button class="floating-btn" onclick="window.location.reload();">
        &#x21bb;
    </button>
    """,
    unsafe_allow_html=True
)
