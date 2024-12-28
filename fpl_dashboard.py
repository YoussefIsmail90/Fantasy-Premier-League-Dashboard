import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import numpy as np

# ------------------------------------------------------------------------------
# 1. Page Configuration & Initialization
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="FPL Dashboard: Enhanced Edition",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ensure these session variables exist
if "fpl_data" not in st.session_state:
    st.session_state["fpl_data"] = {}
if "players" not in st.session_state:
    st.session_state["players"] = pd.DataFrame()
if "teams" not in st.session_state:
    st.session_state["teams"] = pd.DataFrame()
if "team_colors" not in st.session_state:
    st.session_state["team_colors"] = {}

# ------------------------------------------------------------------------------
# 2. Fetch & Prepare Data
# ------------------------------------------------------------------------------
@st.cache_data(ttl=60 * 60)  # cache for 1 hour
def fetch_fpl_data():
    """Fetches raw JSON data from the FPL's 'bootstrap-static' endpoint."""
    try:
        url = "https://fantasy.premierleague.com/api/bootstrap-static/"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Failed to fetch data from FPL: {e}")
        return {}

@st.cache_data(ttl=60 * 60)
def prepare_data(data):
    """
    Converts raw JSON data into structured DataFrames for players and teams.
    Adds a 'position' column to players by mapping 'element_type'.
    """
    if not data:
        return pd.DataFrame(), pd.DataFrame()

    players_df = pd.DataFrame(data.get("elements", []))
    teams_df = pd.DataFrame(data.get("teams", []))
    positions_df = pd.DataFrame(data.get("element_types", []))

    # Merge players with teams (to get team names)
    if not players_df.empty:
        players_df = players_df.merge(
            teams_df[["id", "name"]], left_on="team", right_on="id", how="left"
        )
        players_df.drop(columns=["id", "team_x"], errors="ignore", inplace=True)
        players_df.rename(columns={"team_y": "team"}, inplace=True)

        # Rename and adjust columns
        players_df.rename(columns={"now_cost": "Price", "minutes": "Minutes"}, inplace=True)
        players_df["Price"] = players_df["Price"] / 10.0
        players_df["Hours"] = players_df["Minutes"] / 60.0
        players_df["Ownership"] = pd.to_numeric(players_df["selected_by_percent"], errors="coerce")

        # Map element_type to position
        if not positions_df.empty:
            map_pos = dict(zip(positions_df["id"], positions_df["singular_name"]))
            players_df["position"] = players_df["element_type"].map(map_pos)

    return players_df, teams_df

def assign_team_colors(players_df, color_list):
    """
    Generates a color map for each unique team in the 'players' DataFrame,
    using the provided color palette.
    
    We assume the players DataFrame has a column 'team' with the team names.
    """
    if "team" not in players_df.columns or players_df.empty:
        # If the DataFrame is empty or missing 'team', return an empty dict
        return {}

    unique_teams = players_df["team"].unique()
    return {
        team: color_list[i % len(color_list)]
        for i, team in enumerate(unique_teams)
    }

# ------------------------------------------------------------------------------
# 3. Data Refresh & Initialization
# ------------------------------------------------------------------------------
def refresh_data():
    """Refreshes data in session state."""
    st.session_state["fpl_data"] = fetch_fpl_data()
    p, t = prepare_data(st.session_state["fpl_data"])
    st.session_state["players"], st.session_state["teams"] = p, t

    # Assign default color palette to players
    default_palette = px.colors.sequential.Plasma
    st.session_state["team_colors"] = assign_team_colors(p, default_palette)

# ------------------------------------------------------------------------------
# 4. Page Sections
# ------------------------------------------------------------------------------

# --- 4a. Home Page ---
def page_home():
    st.markdown("## Welcome to the Enhanced FPL Dashboard")
    st.write(
        "This app provides in-depth insights and interactive visuals for all your **Fantasy Premier League** needs.\n\n"
        "Explore players, compare teams, track fixtures, and more!"
    )
    
    # Color palette selection
    st.write("---")
    st.subheader("Pick Your Color Palette")
    palette_options = {
        "Plasma": px.colors.sequential.Plasma,
        "Viridis": px.colors.sequential.Viridis,
        "Magma": px.colors.sequential.Magma,
        "Reds": px.colors.sequential.Reds,
        "Blues": px.colors.sequential.Blues,
        "Greens": px.colors.sequential.Greens,
    }
    chosen_palette_name = st.selectbox("Palette", list(palette_options.keys()))
    chosen_palette = palette_options[chosen_palette_name]
    
    # Assign colors to the players DataFrame
    if not st.session_state["players"].empty:
        st.session_state["team_colors"] = assign_team_colors(st.session_state["players"], chosen_palette)

    st.write("---")
    st.subheader("Top 50 Players by Total Points")

    players_df = st.session_state["players"]
    if not players_df.empty:
        # Sort players by total_points
        top_50 = players_df.sort_values("total_points", ascending=False).head(50)

        # Plot bar chart
        fig = px.bar(
            top_50,
            x="second_name",
            y="total_points",
            color="team",
            title="Top Scoring Players",
            color_discrete_map=st.session_state["team_colors"] if st.session_state["team_colors"] else {}
        )
        fig.update_layout(
            template="plotly_dark",
            xaxis_title="Player",
            yaxis_title="Points",
            hovermode="x unified"
        )
        st.plotly_chart(fig)
    else:
        st.warning("No player data available.")

# --- 4b. Compare Players ---
def page_compare_players():
    st.markdown("## Compare Two Players")
    players_df = st.session_state["players"]
    if players_df.empty:
        st.warning("No player data available.")
        return

    # side-by-side selectors
    col1, col2 = st.columns(2)
    with col1:
        p1 = st.selectbox("Player 1", players_df["second_name"].dropna().unique())
    with col2:
        p2 = st.selectbox("Player 2", players_df["second_name"].dropna().unique())

    if p1 and p2:
        data1 = players_df.loc[players_df["second_name"] == p1].iloc[0]
        data2 = players_df.loc[players_df["second_name"] == p2].iloc[0]

        metrics = ["total_points", "goals_scored", "assists", "clean_sheets", 
                   "Hours", "Ownership", "Price"]
        comp_data = {
            "Metric": metrics,
            p1: [data1.get(m, 0) for m in metrics],
            p2: [data2.get(m, 0) for m in metrics]
        }
        comp_df = pd.DataFrame(comp_data)
        fig = px.bar(comp_df, x="Metric", y=[p1, p2], barmode="group", title=f"{p1} vs {p2}")
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig)

# --- 4c. Search Player ---
def page_search_player():
    st.markdown("## Search for a Player")
    players_df = st.session_state["players"]
    query = st.text_input("Enter a player's surname (e.g., 'Haaland'):")
    if query:
        results = players_df[players_df["second_name"].str.contains(query, case=False, na=False)]
        if results.empty:
            st.write("No matching players found.")
        else:
            st.dataframe(results, height=600)

# --- 4d. Compare Teams ---
def page_compare_teams():
    st.markdown("## Compare Two Teams")
    players_df = st.session_state["players"]
    teams_df = st.session_state["teams"]
    if players_df.empty or teams_df.empty:
        st.warning("No data available.")
        return

    team_list = sorted(teams_df["name"].dropna().unique().tolist())
    col1, col2 = st.columns(2)
    with col1:
        t1 = st.selectbox("Team 1", team_list)
    with col2:
        t2 = st.selectbox("Team 2", team_list)

    if t1 and t2:
        team1_stats = players_df[players_df["team"] == t1][
            ["total_points", "goals_scored", "assists", "clean_sheets"]
        ].sum()
        team2_stats = players_df[players_df["team"] == t2][
            ["total_points", "goals_scored", "assists", "clean_sheets"]
        ].sum()
        comp_df = pd.DataFrame({
            "Metric": ["Total Points", "Goals Scored", "Assists", "Clean Sheets"],
            t1: team1_stats.values,
            t2: team2_stats.values
        })
        fig = px.bar(
            comp_df,
            x="Metric",
            y=[t1, t2],
            barmode="group",
            title=f"{t1} vs {t2}",
            color_discrete_sequence=px.colors.qualitative.Prism
        )
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig)

# --- 4e. Search Team ---
def page_search_team():
    st.markdown("## Search for a Team")
    teams_df = st.session_state["teams"]
    query = st.text_input("Enter a Team's name (e.g., 'Arsenal'):")
    if query:
        results = teams_df[teams_df["name"].str.contains(query, case=False, na=False)]
        if results.empty:
            st.write("No matching teams found.")
        else:
            st.dataframe(results)

# --- 4f. Fixtures ---
def page_fixtures():
    st.markdown("## Upcoming & Finished Fixtures")
    try:
        resp = requests.get("https://fantasy.premierleague.com/api/fixtures/")
        resp.raise_for_status()
        fixtures_data = resp.json()
        fix_df = pd.DataFrame(fixtures_data)
        if fix_df.empty:
            st.write("No fixture data found.")
            return

        # Convert to datetime
        fix_df["kickoff_time"] = pd.to_datetime(fix_df["kickoff_time"], errors="coerce")
        fix_df["Date"] = fix_df["kickoff_time"].dt.date
        fix_df["Time"] = fix_df["kickoff_time"].dt.strftime("%H:%M")

        teams_df = st.session_state["teams"]
        if not teams_df.empty:
            id_map = dict(zip(teams_df["id"], teams_df["name"]))
            fix_df["Home"] = fix_df["team_h"].map(id_map)
            fix_df["Away"] = fix_df["team_a"].map(id_map)

        fix_df["Home Score"] = fix_df["team_h_score"]
        fix_df["Away Score"] = fix_df["team_a_score"]
        fix_df["Status"] = fix_df.apply(lambda x: "Finished" if x["finished"] else "Upcoming", axis=1)

        keep_cols = ["Date", "Time", "Home", "Away", "Home Score", "Away Score", "Status"]
        fix_df = fix_df[keep_cols]

        # Team filter
        filter_team = st.selectbox("Filter by Team:", ["All"] + sorted(teams_df["name"].unique()))
        if filter_team != "All":
            fix_df = fix_df[(fix_df["Home"] == filter_team) | (fix_df["Away"] == filter_team)]

        st.dataframe(fix_df, height=700, width=1200)
    except requests.RequestException as e:
        st.error(f"Cannot load fixtures: {e}")

# --- 4g. Best Players ---
def page_best_players():
    st.markdown("## Best Players by Position")
    players_df = st.session_state["players"]
    if "position" not in players_df.columns or players_df.empty:
        st.error("Position data is unavailable.")
        return

    # Define metrics per position
    metrics_map = {
        "Goalkeeper": ["saves", "clean_sheets", "form"],
        "Defender": ["expected_goals", "expected_assists", "clean_sheets", "influence", "creativity", "threat", "form"],
        "Midfielder": ["expected_goals", "expected_assists", "influence", "creativity", "threat", "form"],
        "Forward": ["expected_goals", "expected_assists", "influence", "creativity", "threat", "form"]
    }

    positions = sorted(players_df["position"].dropna().unique().tolist())
    chosen_position = st.selectbox("Position", positions)

    subset = players_df[players_df["position"] == chosen_position].copy()
    used_metrics = metrics_map.get(chosen_position, [])

    # Summation of relevant metrics
    for m in used_metrics:
        subset[m] = pd.to_numeric(subset[m], errors="coerce")
    subset["score_sum"] = subset[used_metrics].sum(axis=1)
    top_players = subset.sort_values("score_sum", ascending=False).head(10)

    st.write(f"### Top 10 {chosen_position}s (by combined stats)")
    fig = px.bar(
        top_players.sort_values("score_sum", ascending=False),
        x="web_name",
        y="score_sum",
        color="team",
        color_discrete_map=st.session_state["team_colors"] if st.session_state["team_colors"] else {},
        title=f"Best {chosen_position}s"
    )
    fig.update_layout(template="plotly_dark", xaxis_title="Player", yaxis_title="Score Sum")
    st.plotly_chart(fig)

    st.dataframe(top_players[["first_name", "web_name", "team", "position"] + used_metrics])

# --- 4h. Advanced Explorer ---
def page_advanced_explorer():
    """
    Provides an interactive scatter plot where users can pick any two stats
    to explore among players (e.g., Price vs. Ownership).
    """
    st.markdown("## Advanced Explorer")
    st.write("Choose any **two metrics** to explore a scatter plot of all players.")

    players_df = st.session_state["players"].copy()
    if players_df.empty:
        st.warning("No player data available.")
        return

    numeric_cols = [
        "total_points", "goals_scored", "assists", "clean_sheets", 
        "Hours", "Ownership", "Price", "yellow_cards", "red_cards", 
        "saves", "influence", "creativity", "threat", "expected_goals", 
        "expected_assists"
    ]
    x_col = st.selectbox("X-axis", numeric_cols, index=numeric_cols.index("Price"))
    y_col = st.selectbox("Y-axis", numeric_cols, index=numeric_cols.index("Ownership"))
    color_choice = st.selectbox("Color By", ["team", "position"])
    size_choice = st.selectbox("Bubble Size", ["None"] + numeric_cols, index=0)

    scatter_kwargs = dict(
        data_frame=players_df,
        x=x_col,
        y=y_col,
        hover_data=["second_name", "team", "position", "Price", "Ownership"],
        color=color_choice,
        template="plotly_dark"
    )
    if size_choice != "None":
        scatter_kwargs["size"] = size_choice
        scatter_kwargs["size_max"] = 25

    fig = px.scatter(**scatter_kwargs)
    fig.update_layout(title=f"{x_col} vs. {y_col}", hovermode="closest")
    st.plotly_chart(fig)

# --- 4i. Player Radar Chart ---
def page_player_radar():
    """
    Radar (Spider) Chart allows comparing a single player's selected metrics 
    in a radial layout.
    """
    st.markdown("## Player Radar Chart")
    st.write(
        "Select a single **player** and choose which metrics to plot in a Radar Chart. "
        "This can highlight their strengths and weaknesses at a glance!"
    )

    players_df = st.session_state["players"]
    if players_df.empty:
        st.warning("No player data available.")
        return

    player_name = st.selectbox("Choose Player:", players_df["second_name"].dropna().unique())
    if not player_name:
        return

    metrics_choices = [
        "total_points", "goals_scored", "assists", "clean_sheets", "Hours", 
        "Ownership", "Price", "influence", "creativity", "threat", 
        "expected_goals", "expected_assists"
    ]
    default_selection = ["total_points", "goals_scored", "assists"]
    selected_metrics = st.multiselect("Select Radar Metrics", metrics_choices, default=default_selection)

    player_data = players_df[players_df["second_name"] == player_name].iloc[0]
    radar_values = []
    for metric in selected_metrics:
        val = player_data.get(metric, 0)
        val = float(val) if pd.notna(val) else 0.0
        radar_values.append(val)

    if len(selected_metrics) < 3:
        st.warning("Radar charts typically need 3 or more metrics to display effectively!")
        return

    # We'll close the polygon by repeating the first metric at the end
    r_values = radar_values + [radar_values[0]]
    theta_values = selected_metrics + [selected_metrics[0]]

    fig = go.Figure(
        data=go.Scatterpolar(
            r=r_values,
            theta=theta_values,
            fill='toself',
            name=player_name,
            marker=dict(size=8),
            line=dict(color='cyan', width=2)
        )
    )
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, linewidth=2, gridcolor="gray", gridwidth=0.5),
            angularaxis=dict(showline=True, linewidth=2, linecolor='gray')
        ),
        showlegend=False,
        template="plotly_dark",
        title=f"Radar Chart: {player_name}"
    )
    st.plotly_chart(fig)

# --- 4j. Team-Level Summary ---
def page_team_summary():
    """
    Aggregates stats at the team level and provides a quick view of
    average or sum of metrics for each team in a bar chart.
    """
    st.markdown("## Team-Level Summary Stats")
    st.write(
        "This page calculates **average** or **total** stats for each team to give "
        "you a sense of overall team performance."
    )

    players_df = st.session_state["players"]
    if players_df.empty:
        st.warning("No player data available.")
        return

    possible_stats = [
        "goals_scored", "assists", "clean_sheets", "total_points", 
        "expected_goals", "expected_assists", "Minutes"
    ]
    chosen_stat = st.selectbox("Choose Stat to Summarize", possible_stats, index=0)
    agg_type = st.radio("Aggregation Type", ["Sum", "Average"], index=1)

    if agg_type == "Sum":
        agg_df = players_df.groupby("team")[chosen_stat].sum().reset_index()
    else:
        agg_df = players_df.groupby("team")[chosen_stat].mean().reset_index()

    agg_df = agg_df.sort_values(chosen_stat, ascending=False)

    fig = px.bar(
        agg_df,
        x="team",
        y=chosen_stat,
        color="team",
        title=f"{agg_type} {chosen_stat.capitalize()} by Team",
        color_discrete_map=st.session_state["team_colors"] if st.session_state["team_colors"] else {}
    )
    fig.update_layout(template="plotly_dark", xaxis_title="Team", yaxis_title=f"{chosen_stat} ({agg_type})")
    st.plotly_chart(fig)

    st.dataframe(agg_df, height=500)

# ------------------------------------------------------------------------------
# 5. Main App
# ------------------------------------------------------------------------------
# If data is missing, fetch it now
if st.session_state["players"].empty or st.session_state["teams"].empty:
    refresh_data()

# Sidebar Navigation
st.sidebar.title("FPL Dashboard")
page_options = [
    "Home",
    "Compare Players",
    "Search a Player",
    "Compare Teams",
    "Search a Team",
    "Fixtures",
    "Best Players",
    "Advanced Explorer",
    "Player Radar Chart",
    "Team Summary"
]
choice = st.sidebar.radio("Go to:", page_options)
st.sidebar.button("Refresh Data", on_click=refresh_data)

# Page Routing
if choice == "Home":
    page_home()
elif choice == "Compare Players":
    page_compare_players()
elif choice == "Search a Player":
    page_search_player()
elif choice == "Compare Teams":
    page_compare_teams()
elif choice == "Search a Team":
    page_search_team()
elif choice == "Fixtures":
    page_fixtures()
elif choice == "Best Players":
    page_best_players()
elif choice == "Advanced Explorer":
    page_advanced_explorer()
elif choice == "Player Radar Chart":
    page_player_radar()
elif choice == "Team Summary":
    page_team_summary()
