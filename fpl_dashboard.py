import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import numpy as np
import datetime

# ----------------------------------------------------------------------
# 1. Page Configuration
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="Premier League Dashboard - Enhanced Fixtures & Best XI",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------------------------------------------------
# 2. Session State Initialization
# ----------------------------------------------------------------------
if "raw_fpl_data" not in st.session_state:
    st.session_state["raw_fpl_data"] = {}
if "players" not in st.session_state:
    st.session_state["players"] = pd.DataFrame()
if "clubs" not in st.session_state:
    st.session_state["clubs"] = pd.DataFrame()

# ----------------------------------------------------------------------
# 3. Data Fetching & Preparation
# ----------------------------------------------------------------------
@st.cache_data(ttl=60 * 60)
def fetch_fpl_data():
    """
    Fetch raw JSON from the official FPL 'bootstrap-static' endpoint.
    Cached for 1 hour to reduce repeated calls.
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
    Renames columns for a fresh look (e.g., 'team' -> 'club_id', etc.).
    Adds 'hours_played' & 'popularity' columns, maps 'element_type' to 'position'.
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

    # Merge to replace 'club_id' with actual club names
    players_df = players_df.merge(
        clubs_df[["id", "name"]], left_on="club_id", right_on="id", how="left"
    )
    players_df.drop(columns=["id", "club_id"], inplace=True, errors="ignore")
    players_df.rename(columns={"name": "club"}, inplace=True)

    # Convert cost -> decimal
    players_df["cost"] = players_df["cost"] / 10.0

    # Convert minutes -> hours
    players_df["hours_played"] = players_df["minutes_played"] / 60.0

    # Convert popularity -> numeric
    players_df["popularity"] = pd.to_numeric(players_df["popularity"], errors="coerce")

    # Convert form -> numeric (for Best XI scoring)
    players_df["form"] = pd.to_numeric(players_df["form"], errors="coerce").fillna(0.0)

    # Map element_type -> position
    if not positions_df.empty:
        id_to_position = dict(zip(positions_df["id"], positions_df["singular_name"]))
        players_df["position"] = players_df["element_type"].map(id_to_position)

    return players_df, clubs_df

def refresh_data():
    """
    Fetch new data & reassign DataFrames in session state.
    """
    raw_data = fetch_fpl_data()
    st.session_state["raw_fpl_data"] = raw_data
    p_df, c_df = prepare_data(raw_data)
    st.session_state["players"], st.session_state["clubs"] = p_df, c_df

# ----------------------------------------------------------------------
# 4. Tabs / Page Functions
# ----------------------------------------------------------------------

# --- 4a. Overview ---
def tab_overview(players_df):
    """
    Shows a bar chart of the top 30 players by total_points
    (using a pastel color palette) plus a quick stats table.
    """
    st.subheader("Premier League Overview")

    if players_df.empty:
        st.warning("No player data available.")
        return

    st.write("### Top 30 Players (By Total Points)")
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

# --- 4b. Search Player ---
def tab_search_player(players_df):
    """
    Allows a user to search for a player by last name substring.
    """
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

# --- 4c. Compare Clubs ---
def tab_team_comparison(players_df, clubs_df):
    """
    Compare two clubs by aggregated stats (Points, Goals, Assists, Clean Sheets).
    """
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
            color_discrete_sequence=["#FFC107", "#03A9F4"],  # Example custom colors
            title=f"{c1} vs {c2}"
        )
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig)

# --- 4d. Fixtures (Enhanced) ---
def tab_fixtures(clubs_df):
    """
    Enhanced Fixtures Tab:
    - Team filter
    - Status filter (All / Upcoming / Finished)
    - Date range filter
    - Bar chart (fixtures per date)
    - Detailed fixture table
    """
    st.subheader("Upcoming & Recent Fixtures")

    try:
        # Fetch
        resp = requests.get("https://fantasy.premierleague.com/api/fixtures/")
        resp.raise_for_status()
        fix_df = pd.DataFrame(resp.json())

        if fix_df.empty:
            st.info("No fixture data found.")
            return

        # Convert times -> datetime
        fix_df["kickoff_time"] = pd.to_datetime(fix_df["kickoff_time"], errors="coerce")
        fix_df["Date"] = fix_df["kickoff_time"].dt.date
        fix_df["Time"] = fix_df["kickoff_time"].dt.strftime("%H:%M")

        # If all invalid
        if fix_df["Date"].dropna().empty:
            st.info("No valid fixture dates found.")
            return

        # Map club IDs if clubs data is available
        if not clubs_df.empty and "id" in clubs_df.columns and "name" in clubs_df.columns:
            id_map = dict(zip(clubs_df["id"], clubs_df["name"]))
            fix_df["Home"] = fix_df["team_h"].map(id_map)
            fix_df["Away"] = fix_df["team_a"].map(id_map)
        else:
            fix_df["Home"] = fix_df["team_h"]
            fix_df["Away"] = fix_df["team_a"]

        # Scores & Status
        fix_df["Home Score"] = fix_df.get("team_h_score", None)
        fix_df["Away Score"] = fix_df.get("team_a_score", None)
        fix_df["Status"] = fix_df.apply(lambda x: "Finished" if x["finished"] else "Upcoming", axis=1)

        keep_cols = ["Date", "Time", "Home", "Away", "Home Score", "Away Score", "Status"]
        fix_df = fix_df[keep_cols]

        # Safely compute min/max date
        min_date = fix_df["Date"].min()
        max_date = fix_df["Date"].max()

        st.write("### Filter Options")

        # Team filter
        if not clubs_df.empty:
            club_list = sorted(clubs_df["name"].dropna().unique().tolist())
            filter_club = st.selectbox("Filter by Club:", ["All"] + club_list)
        else:
            filter_club = "All"

        # Status filter
        filter_status = st.selectbox("Filter by Status:", ["All","Upcoming","Finished"])

        # Date range filter
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

        # (a) Club
        if filter_club != "All":
            filtered_df = filtered_df[
                (filtered_df["Home"] == filter_club) | (filtered_df["Away"] == filter_club)
            ]
        # (b) Status
        if filter_status != "All":
            filtered_df = filtered_df[filtered_df["Status"] == filter_status]
        # (c) Date Range
        filtered_df = filtered_df[
            (filtered_df["Date"] >= start_date) & (filtered_df["Date"] <= end_date)
        ]

        if filtered_df.empty:
            st.info("No fixtures match your filters.")
            return

        # Quick bar chart of fixture counts by date
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
    """
    Displays the top players by 'combined_score' for each position,
    where the 'combined_score' is sum of relevant metrics.
    """
    st.subheader("Best Players by Position")

    if players_df.empty or "position" not in players_df.columns:
        st.warning("No players or missing 'position' info.")
        return

    # Metrics for each position
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

# --- 4f. Advanced Explorer ---
def tab_advanced(players_df):
    """
    Lets the user pick any two numeric columns for a scatter plot,
    with optional bubble sizing.
    """
    st.subheader("Advanced Explorer (Scatter Plot)")

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
    """
    Enhanced Best XI feature:
    - Formation: 1-4-3-3
    - Score formula: total_points + 2 * form
    - Select top players in each position group based on that scoring
    """
    st.subheader("Best XI (1-4-3-3) by Points & Form")

    if players_df.empty or "position" not in players_df.columns:
        st.warning("No player data or missing 'position' info.")
        return

    # Create a custom 'score_for_best_xi' = total_points + 2×form
    # This gives extra weight to current form
    players_df["score_for_best_xi"] = players_df["total_points"] + 2.0 * players_df["form"]

    # We'll pick:
    # 1 GK, 4 Def, 3 Mid, 3 Fwd
    # Sort each subset by 'score_for_best_xi' descending
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

# ----------------------------------------------------------------------
# 5. Main App
# ----------------------------------------------------------------------
if st.session_state["players"].empty or st.session_state["clubs"].empty:
    refresh_data()

st.title("Premier League Dashboard (Enhanced Fixtures & Best XI)")

# Create tabs across the top
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

# Tab 0: Overview
with tabs[0]:
    tab_overview(st.session_state["players"])

# Tab 1: Search Player
with tabs[1]:
    tab_search_player(st.session_state["players"])

# Tab 2: Compare Clubs
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

# A refresh button at the bottom
st.write("---")
if st.button("Refresh All Data"):
    refresh_data()
    st.experimental_rerun()
