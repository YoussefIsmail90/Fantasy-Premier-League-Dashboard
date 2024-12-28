import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import numpy as np
import random

# ----------------------------------------------------------------------
# 1. Page Configuration
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="Premier League Dashboard - New Look",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------------------------------------------------
# 2. Session State Setup
# ----------------------------------------------------------------------
if "raw_fpl_data" not in st.session_state:
    st.session_state["raw_fpl_data"] = {}
if "players" not in st.session_state:
    st.session_state["players"] = pd.DataFrame()
if "clubs" not in st.session_state:  # 'teams' -> 'clubs'
    st.session_state["clubs"] = pd.DataFrame()

# ----------------------------------------------------------------------
# 3. Data Fetching & Preparation
# ----------------------------------------------------------------------
@st.cache_data(ttl=60 * 60)
def fetch_fpl_data():
    """Fetch raw JSON data from the official FPL 'bootstrap-static' endpoint."""
    try:
        url = "https://fantasy.premierleague.com/api/bootstrap-static/"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Error fetching FPL data: {e}")
        return {}

@st.cache_data(ttl=60 * 60)
def prepare_data(data):
    """
    Transform raw JSON data into structured DataFrames for players & clubs.
    We rename some columns to give the app a fresh look:
     - 'team' -> 'club_id'
     - 'second_name' -> 'last_name'
     - 'now_cost' -> 'cost'
     - 'minutes' -> 'minutes_played'
     - 'selected_by_percent' -> 'popularity'
    """
    if not data:
        return pd.DataFrame(), pd.DataFrame()

    players_df = pd.DataFrame(data.get("elements", []))
    clubs_df = pd.DataFrame(data.get("teams", []))
    positions_df = pd.DataFrame(data.get("element_types", []))

    if players_df.empty or clubs_df.empty:
        return players_df, clubs_df

    # Rename columns for a new feel
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

    # Merge to replace 'club_id' with actual club names
    players_df = players_df.merge(
        clubs_df[["id", "name"]], left_on="club_id", right_on="id", how="left"
    )
    # Use 'club' to refer to the team's name
    players_df.rename(columns={"name": "club"}, inplace=True)

    # Convert cost to decimal
    players_df["cost"] = players_df["cost"] / 10.0

    # Convert minutes -> hours
    players_df["hours_played"] = players_df["minutes_played"] / 60.0

    # Convert popularity to numeric
    players_df["popularity"] = pd.to_numeric(players_df["popularity"], errors="coerce")

    # Map element_type to position
    if not positions_df.empty:
        id_to_position = dict(zip(positions_df["id"], positions_df["singular_name"]))
        players_df["position"] = players_df["element_type"].map(id_to_position)

    return players_df, clubs_df

def refresh_data():
    """Fetch new data and re-assign DataFrames in session state."""
    data = fetch_fpl_data()
    st.session_state["raw_fpl_data"] = data
    p_df, c_df = prepare_data(data)
    st.session_state["players"], st.session_state["clubs"] = p_df, c_df

# ----------------------------------------------------------------------
# 4. Tabs / Page Functions
# ----------------------------------------------------------------------
def tab_overview(players_df):
    """Overview tab: Top 30 players by total_points, with a Pastel color scheme."""
    st.subheader("Premier League Overview")

    if players_df.empty:
        st.warning("No player data available.")
        return

    st.write("### Top 30 Players (By Total Points)")
    top_players = players_df.sort_values("total_points", ascending=False).head(30)

    # Use a pastel color palette for better aesthetics
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

    st.write("### Quick Stats Table")
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


def tab_search_player(players_df):
    """Search for a specific player by last name."""
    st.subheader("Find a Player")
    name_query = st.text_input("Type part of a last name (e.g. 'Rashford'):")
    if name_query:
        results = players_df[players_df["last_name"].str.contains(name_query, case=False, na=False)]
        if results.empty:
            st.write("No matching players.")
        else:
            st.dataframe(
                results[
                    [
                        "first_name", "last_name", "club", "position", 
                        "total_points", "goals_scored", "assists", 
                        "clean_sheets", "cost", "popularity"
                    ]
                ]
            )


def tab_team_comparison(players_df, clubs_df):
    """Compare two clubs based on aggregated stats like points, goals, assists."""
    st.subheader("Compare Two Clubs")

    if clubs_df.empty or players_df.empty:
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

import datetime  # Make sure to import datetime

def tab_fixtures(clubs_df):
    """
    Enhanced Fixtures Tab:
    - Team filter
    - Status filter (Upcoming / Finished / All)
    - Date range filter
    - Date-grouped bar chart
    - Detailed fixtures table
    """
    st.subheader("Upcoming & Recent Fixtures - Enhanced")

    try:
        # Fetch fixtures
        resp = requests.get("https://fantasy.premierleague.com/api/fixtures/")
        resp.raise_for_status()
        fixtures_json = resp.json()
        fix_df = pd.DataFrame(fixtures_json)

        # If no data, bail out
        if fix_df.empty:
            st.write("No fixture data found.")
            return

        # Convert to datetime & split date/time
        fix_df["kickoff_time"] = pd.to_datetime(fix_df["kickoff_time"], errors="coerce")
        fix_df["Date"] = fix_df["kickoff_time"].dt.date
        fix_df["Time"] = fix_df["kickoff_time"].dt.strftime("%H:%M")

        # Map team IDs to names if clubs are available
        if not clubs_df.empty:
            id_map = dict(zip(clubs_df["id"], clubs_df["name"]))
            fix_df["Home"] = fix_df["team_h"].map(id_map)
            fix_df["Away"] = fix_df["team_a"].map(id_map)
        else:
            fix_df["Home"] = fix_df["team_h"]
            fix_df["Away"] = fix_df["team_a"]

        # Scores & Status
        fix_df["Home Score"] = fix_df.get("team_h_score", None)
        fix_df["Away Score"] = fix_df.get("team_a_score", None)

        # Determine match status
        fix_df["Status"] = fix_df.apply(lambda x: "Finished" if x["finished"] else "Upcoming", axis=1)

        # Basic columns to show
        show_cols = ["Date", "Time", "Home", "Away", "Home Score", "Away Score", "Status"]
        fix_df = fix_df[show_cols]

        # ----------------------------
        # Sidebar-like filters
        # ----------------------------
        st.write("### Filter Options")

        # 1) Filter by Team
        filter_club = st.selectbox(
            "Filter by Club:",
            ["All"] + sorted(clubs_df["name"].unique()) if not clubs_df.empty else ["All"]
        )

        # 2) Filter by Status
        filter_status = st.selectbox("Filter by Status:", ["All", "Upcoming", "Finished"])

        # 3) Filter by Date Range
        min_date = fix_df["Date"].min()
        max_date = fix_df["Date"].max()

        # Let user pick a start and end date
        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input(
                "Start Date", 
                value=min_date, 
                min_value=min_date, 
                max_value=max_date
            )
        with col_end:
            end_date = st.date_input(
                "End Date",
                value=max_date,
                min_value=min_date,
                max_value=max_date
            )
        
        # Ensure start_date <= end_date
        if start_date > end_date:
            st.warning("Start Date cannot be after End Date.")
            return

        # ----------------------------
        # Apply Filters
        # ----------------------------
        filtered_df = fix_df.copy()

        # (a) Team
        if filter_club != "All":
            filtered_df = filtered_df[
                (filtered_df["Home"] == filter_club) | (filtered_df["Away"] == filter_club)
            ]

        # (b) Status
        if filter_status != "All":
            filtered_df = filtered_df[filtered_df["Status"] == filter_status]

        # (c) Date range
        filtered_df = filtered_df[
            (filtered_df["Date"] >= start_date) & 
            (filtered_df["Date"] <= end_date)
        ]

        # ----------------------------
        # Quick Stats: Group by Date
        # ----------------------------
        if not filtered_df.empty:
            st.write("### Fixtures by Date")
            fixture_counts = filtered_df.groupby("Date").size().reset_index(name="Num Fixtures")
            # Sort by date
            fixture_counts.sort_values("Date", inplace=True)

            fig_counts = px.bar(
                fixture_counts,
                x="Date",
                y="Num Fixtures",
                title="Number of Fixtures per Date (Filtered)",
                text="Num Fixtures",
                color_discrete_sequence=["#EB89B5"],  # Example color
                labels={"Date": "Match Date", "Num Fixtures": "Count"}
            )
            fig_counts.update_layout(template="plotly_dark")
            fig_counts.update_traces(textposition="outside")
            st.plotly_chart(fig_counts)
        else:
            st.info("No fixtures match your filters.")
            return

        # ----------------------------
        # Show Detailed Table
        # ----------------------------
        st.write("### Filtered Fixtures Table")
        st.dataframe(filtered_df, width=1200, height=500)

    except requests.RequestException as e:
        st.error(f"Cannot load fixtures: {e}")




def tab_best_players(players_df):
    """Best players by position, using a 'combined_score' approach."""
    st.subheader("Best Players by Position")

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

    st.write(f"**Detailed {chosen_position} Stats**")
    st.dataframe(top_10[["first_name", "last_name", "club", "position"] + relevant_metrics])


def tab_advanced(players_df):
    """Advanced scatter plot explorer: pick any two numeric metrics to analyze."""
    st.subheader("Advanced Explorer (Scatter Plot)")

    if players_df.empty:
        st.warning("No data to explore.")
        return

    numeric_cols = [
        "total_points","goals_scored","assists","clean_sheets","influence",
        "creativity","threat","expected_goals","expected_assists","cost",
        "popularity","hours_played","yellow_cards","red_cards"
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
        hover_data=["last_name","club","position","cost","popularity","hours_played"],
        color=color_by,
        template="plotly_dark"
    )
    if size_metric != "None":
        scatter_config["size"] = size_metric
        scatter_config["size_max"] = 25
    
    fig = px.scatter(**scatter_config)
    fig.update_layout(title=f"{x_metric} vs {y_metric}")
    st.plotly_chart(fig)


def tab_best_xi(players_df):
    """
    Select a standard 1-4-4-2 Best XI based on highest total_points so far.
    For a more advanced approach, you could incorporate upcoming fixtures,
    difficulty ratings, or other metrics.
    """
    st.subheader("Best XI for Next Week (1-4-4-2)")

    if players_df.empty or "position" not in players_df.columns:
        st.warning("No data or missing position info.")
        return

    # Pick 1 GK, 4 Defenders, 4 Midfielders, 2 Forwards
    gk = players_df[players_df["position"] == "Goalkeeper"].sort_values("total_points", ascending=False).head(1)
    defenders = players_df[players_df["position"] == "Defender"].sort_values("total_points", ascending=False).head(4)
    mids = players_df[players_df["position"] == "Midfielder"].sort_values("total_points", ascending=False).head(4)
    fwds = players_df[players_df["position"] == "Forward"].sort_values("total_points", ascending=False).head(2)

    best_11 = pd.concat([gk, defenders, mids, fwds])

    fig = px.bar(
        best_11,
        x="last_name",
        y="total_points",
        color="club",
        color_discrete_sequence=px.colors.qualitative.Pastel2,
        title="Recommended XI (by total_points)"
    )
    fig.update_layout(template="plotly_dark", xaxis_title="Player", yaxis_title="Points")
    st.plotly_chart(fig)

    st.write("### Detailed Best XI Table")
    st.dataframe(
        best_11[
            [
                "first_name","last_name","club","position","total_points",
                "goals_scored","assists","clean_sheets","cost","popularity"
            ]
        ]
    )

# ----------------------------------------------------------------------
# 5. Run App
# ----------------------------------------------------------------------
# Refresh if data is missing
if st.session_state["players"].empty or st.session_state["clubs"].empty:
    refresh_data()

st.title("Premier League Dashboard (Fresh Redesign)")

# Create tabs across the top
tab_labels = [
    "Overview", 
    "Search Player", 
    "Compare Clubs", 
    "Fixtures", 
    "Best Players", 
    "Advanced", 
    "Best XI"
]
tabs = st.tabs(tab_labels)

# Tab 0: Overview
with tabs[0]:
    tab_overview(st.session_state["players"])

# Tab 1: Search a Player
with tabs[1]:
    tab_search_player(st.session_state["players"])

# Tab 2: Team Comparison
with tabs[2]:
    tab_team_comparison(st.session_state["players"], st.session_state["clubs"])

# Tab 3: Fixtures
with tabs[3]:
    tab_fixtures(st.session_state["clubs"])

# Tab 4: Best Players
with tabs[4]:
    tab_best_players(st.session_state["players"])

# Tab 5: Advanced Explorer
with tabs[5]:
    tab_advanced(st.session_state["players"])

# Tab 6: Best XI
with tabs[6]:
    tab_best_xi(st.session_state["players"])

# A button at the bottom to reload the data
st.write("---")
if st.button("Refresh All Data"):
    refresh_data()
    st.experimental_rerun()
