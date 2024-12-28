import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import streamlit as st

# Set page configuration
st.set_page_config(
    page_title="Fantasy Premier League Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------------------------------------------------------
# Session State Initialization
# ------------------------------------------------------------------------------
if 'page' not in st.session_state:
    st.session_state.page = 'Home'
if 'comparison_players' not in st.session_state:
    st.session_state.comparison_players = []
if 'search_team' not in st.session_state:
    st.session_state.search_team = ""
if 'team_colors' not in st.session_state:
    st.session_state.team_colors = {}

# ------------------------------------------------------------------------------
# Data Fetching & Preparation
# ------------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def fetch_fpl_data():
    """
    Fetches data from the official Fantasy Premier League API.

    Returns:
        dict: JSON-decoded data from the FPL bootstrap-static endpoint.
    """
    with st.spinner("Fetching data..."):
        try:
            url = "https://fantasy.premierleague.com/api/bootstrap-static/"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return data
        except requests.RequestException as e:
            st.error(f"Error fetching data: {e}")
            return {}

@st.cache_data(ttl=3600)
def prepare_data(data):
    """
    Transforms raw JSON data into structured pandas DataFrames for players and teams.

    Args:
        data (dict): Raw data from the FPL API.

    Returns:
        players (pd.DataFrame): Processed players data
        teams (pd.DataFrame): Teams data
    """
    if not data:
        return pd.DataFrame(), pd.DataFrame()

    players = pd.DataFrame(data['elements'])
    teams = pd.DataFrame(data['teams'])
    element_types = pd.DataFrame(data['element_types'])

    # Select relevant columns
    players = players[
        [
            'first_name', 'second_name', 'web_name', 'team', 'total_points', 
            'goals_scored', 'assists', 'clean_sheets', 'now_cost', 'minutes', 
            'yellow_cards', 'red_cards', 'form', 'bonus', 'event_points', 
            'selected_by_percent', 'influence', 'creativity', 'threat', 
            'expected_goals', 'expected_assists', 'expected_goals_conceded', 
            'saves', 'element_type'
        ]
    ]

    # Merge with team names
    players = players.merge(teams[['id', 'name']], left_on='team', right_on='id')
    players.drop(columns=['id', 'team'], inplace=True)
    players.rename(columns={'name': 'team'}, inplace=True)
    players.rename(columns={'now_cost': 'Price'}, inplace=True)
    players.rename(columns={'minutes': 'Hours'}, inplace=True)
    
    # Convert minutes to hours
    players['Hours'] = players['Hours'] / 60.0
    
    # Convert price to a decimal
    players['Price'] = players['Price'] / 10.0
    
    # Convert ownership to numeric
    players['selected_by_percent'] = pd.to_numeric(players['selected_by_percent'], errors='coerce')
    players.rename(columns={'selected_by_percent': 'Ownership'}, inplace=True)

    # Map element_type to readable position names
    element_types_map = dict(zip(element_types['id'], element_types['singular_name']))
    players['position'] = players['element_type'].map(element_types_map)

    return players, teams

def get_team_colors(players_df, color_palette):
    """
    Assigns a color from the specified palette to each unique team.

    Args:
        players_df (pd.DataFrame): Players DataFrame
        color_palette (list): List of color hex strings

    Returns:
        dict: Mapping of team name to color
    """
    unique_teams = players_df['team'].unique()
    return {team: color_palette[i % len(color_palette)] for i, team in enumerate(unique_teams)}

# ------------------------------------------------------------------------------
# Global Color Palettes
# ------------------------------------------------------------------------------
color_palettes = {
    'Plasma': px.colors.sequential.Plasma,
    'Viridis': px.colors.sequential.Viridis,
    'Cividis': px.colors.sequential.Cividis,
    'Inferno': px.colors.sequential.Inferno,
    'Magma': px.colors.sequential.Magma,
    'Blues': px.colors.sequential.Blues,
    'Greens': px.colors.sequential.Greens,
    'Oranges': px.colors.sequential.Oranges,
    'Reds': px.colors.sequential.Reds,
    'BuPu': px.colors.sequential.BuPu,
    'BuGn': px.colors.sequential.BuGn,
    'YlGn': px.colors.sequential.YlGn,
    'YlOrRd': px.colors.sequential.YlOrRd,
}

# ------------------------------------------------------------------------------
# Navigation Helpers
# ------------------------------------------------------------------------------
def navigate_to(page_name):
    """
    Updates session state to change the current page.

    Args:
        page_name (str): Name of the page to navigate to.
    """
    st.session_state.page = page_name

def refresh_data():
    """
    Refreshes the data by fetching and preparing the FPL data again
    and updates session state variables accordingly.
    """
    st.session_state.fpl_data = fetch_fpl_data()
    st.session_state.players, st.session_state.teams = prepare_data(st.session_state.fpl_data)
    st.session_state.team_colors = get_team_colors(st.session_state.players, color_palette)

# ------------------------------------------------------------------------------
# Reusable Plot Function
# ------------------------------------------------------------------------------
def plot_bar_chart(data, x, y, color, color_map, title, labels=None, height=500, template="plotly_dark"):
    """
    Creates a Plotly bar chart.

    Args:
        data (pd.DataFrame): Data to plot
        x (str): Column name for x-axis
        y (str): Column name for y-axis
        color (str): Column to map color to
        color_map (dict): Map of categories to colors
        title (str): Chart title
        labels (dict): Axis labels mapping
        height (int): Chart height
        template (str): Plotly template name

    Returns:
        go.Figure: Plotly figure object
    """
    fig = px.bar(
        data,
        x=x,
        y=y,
        color=color,
        color_discrete_map=color_map,
        title=title,
        labels=labels or {},
        height=height
    )
    fig.update_layout(template=template)
    return fig

# ------------------------------------------------------------------------------
# Main App
# ------------------------------------------------------------------------------
# Fetch and prepare data (once at startup or if not in session_state)
if 'fpl_data' not in st.session_state:
    st.session_state.fpl_data = fetch_fpl_data()
    st.session_state.players, st.session_state.teams = prepare_data(st.session_state.fpl_data)
    # Default palette
    color_palette = color_palettes.get('Plasma', px.colors.sequential.Plasma)
    st.session_state.team_colors = get_team_colors(st.session_state.players, color_palette)
else:
    # Reassign for easy reference
    color_palette = color_palettes.get('Plasma', px.colors.sequential.Plasma)
    st.session_state.team_colors = get_team_colors(st.session_state.players, color_palette)

# ------------------------------------------------------------------------------
# Sidebar Navigation
# ------------------------------------------------------------------------------
st.sidebar.title("Navigation")

# Instead of multiple buttons, let's use radio buttons for a cleaner interface
page_choice = st.sidebar.radio(
    "Go to Page:",
    ("Home", "Compare Players", "Search for a Player",
     "Compare Teams", "Search for a Team", "Fixtures", "Best Players")
)

# Refresh button
st.sidebar.button("Refresh Data", on_click=refresh_data)

# Set the current page based on radio selection
navigate_to(page_choice)

# ------------------------------------------------------------------------------
# Main Page Content
# ------------------------------------------------------------------------------
st.title("Fantasy Premier League Dashboard")

players = st.session_state.players
teams = st.session_state.teams

# Guard clauses if data is empty
if players.empty or teams.empty:
    st.error("No data available. Please refresh the page.")
    st.stop()

total_players = len(players)

# ==============================================================================
# HOME PAGE
# ==============================================================================
if st.session_state.page == 'Home':
    st.write("Real-time data updates from the Fantasy Premier League. Explore players, compare teams, and more!")

    # Color palette selection
    st.subheader("Select Color Palette")
    selected_palette_name = st.selectbox("Select Color Palette:", options=list(color_palettes.keys()))
    color_palette = color_palettes.get(selected_palette_name, px.colors.sequential.Plasma)
    st.session_state.team_colors = get_team_colors(players, color_palette)

    st.subheader("Top Players by Total Points (Top 50)")
    top_players_figure = plot_bar_chart(
        data=players.sort_values(by='total_points', ascending=False).head(50),
        x='second_name',
        y='total_points',
        color='team',
        color_map=st.session_state.team_colors,
        title="Top Players by Total Points",
        labels={'second_name': 'Player', 'total_points': 'Total Points'},
        height=500,
        template="plotly_dark"
    )
    st.plotly_chart(top_players_figure)

    st.subheader("Player Detailed Statistics")
    num_players = st.slider("Number of Players to Display:", min_value=5, max_value=total_players, value=10)
    sort_options = {
        'Hours': 'Hours',
        'Total Points': 'total_points',
        'Goals Scored': 'goals_scored',
        'Assists': 'assists',
        'Clean Sheets': 'clean_sheets',
        'Ownership': 'Ownership',
        'Price': 'Price'
    }
    sort_by_display = st.selectbox("Sort By:", options=list(sort_options.keys()))
    sort_by = sort_options[sort_by_display]

    detailed_players = players[
        [
            'first_name', 'second_name', 'team', 'total_points', 'goals_scored',
            'assists', 'clean_sheets', 'Hours', 'yellow_cards', 'red_cards', 'form', 
            'bonus', 'event_points', 'Ownership', 'Price'
        ]
    ]

    # Sort the DataFrame based on user choice
    detailed_players = detailed_players.sort_values(by=sort_by, ascending=False)
    top_players_df = detailed_players.head(num_players)

    styled_players = top_players_df.style \
        .background_gradient(cmap='plasma') \
        .format(precision=2)

    st.dataframe(styled_players, height=600)

    st.subheader("Players Info - Ownership, Bonus, and Price")
    top_n = 20
    price_form_df = players[['second_name', 'bonus', 'Ownership', 'Price']]\
        .sort_values(by='Ownership', ascending=False)\
        .head(top_n)

    price_form_df = price_form_df.rename(columns={'Ownership': 'ownership'})

    fig_combined = go.Figure()
    fig_combined.add_trace(go.Bar(
        x=price_form_df['second_name'],
        y=price_form_df['ownership'],
        name='Ownership',
        marker_color='#2ca02c'  # Green
    ))
    fig_combined.add_trace(go.Bar(
        x=price_form_df['second_name'],
        y=price_form_df['bonus'],
        name='Bonus Points',
        marker_color='#ff7f0e'  # Orange
    ))
    fig_combined.add_trace(go.Bar(
        x=price_form_df['second_name'],
        y=price_form_df['Price'],
        name='Price',
        marker_color='#1f77b4'  # Blue
    ))

    fig_combined.update_layout(
        barmode='group',
        title='Top 20 Players by Ownership',
        template="plotly_dark",
        yaxis=dict(title='Value'),
        xaxis=dict(title='Player'),
        height=500
    )
    st.plotly_chart(fig_combined)

# ==============================================================================
# COMPARE PLAYERS PAGE
# ==============================================================================
elif st.session_state.page == 'Compare Players':
    st.header("Compare Players")

    player1_name = st.selectbox("Select Player 1", options=players['second_name'].unique())
    player2_name = st.selectbox("Select Player 2", options=players['second_name'].unique())

    if player1_name and player2_name:
        player1_data = players[players['second_name'] == player1_name].iloc[0]
        player2_data = players[players['second_name'] == player2_name].iloc[0]

        metrics = [
            'total_points', 'goals_scored', 'assists', 'clean_sheets', 
            'Hours', 'yellow_cards', 'red_cards', 'Ownership', 'Price'
        ]
        player1_values = [player1_data[metric] for metric in metrics]
        player2_values = [player2_data[metric] for metric in metrics]

        comparison_df = pd.DataFrame({
            'Metric': metrics,
            player1_name: player1_values,
            player2_name: player2_values
        })

        fig_comparison = px.bar(
            comparison_df,
            x='Metric',
            y=[player1_name, player2_name],
            title=f'Comparison between {player1_name} and {player2_name}',
            labels={'Metric': 'Metric', 'value': 'Value'},
            height=500,
            color_discrete_sequence=['#ef2213', '#20ef13']
        )
        fig_comparison.update_layout(template="plotly_dark")

        st.plotly_chart(fig_comparison)

# ==============================================================================
# SEARCH FOR A PLAYER PAGE
# ==============================================================================
elif st.session_state.page == 'Search for a Player':
    st.header("Search for a Player")

    search_query = st.text_input("Enter Player Name (e.g., 'Kane')")
    if search_query:
        search_results = players[players['second_name'].str.contains(search_query, case=False, na=False)]
        if not search_results.empty:
            st.write(search_results)
        else:
            st.write("No players found.")

# ==============================================================================
# COMPARE TEAMS PAGE
# ==============================================================================
elif st.session_state.page == 'Compare Teams':
    st.header("Compare Teams")

    team1_name = st.selectbox("Select Team 1", options=teams['name'].unique())
    team2_name = st.selectbox("Select Team 2", options=teams['name'].unique())

    if team1_name and team2_name:
        team1_players = players[players['team'] == team1_name]
        team2_players = players[players['team'] == team2_name]

        team1_stats = team1_players[['total_points', 'goals_scored', 'assists', 'clean_sheets']].sum()
        team2_stats = team2_players[['total_points', 'goals_scored', 'assists', 'clean_sheets']].sum()

        stats_df = pd.DataFrame({
            'Metric': ['Total Points', 'Goals Scored', 'Assists', 'Clean Sheets'],
            team1_name: team1_stats.values,
            team2_name: team2_stats.values
        })

        fig_team_comparison = px.bar(
            stats_df,
            x='Metric',
            y=[team1_name, team2_name],
            title=f'Comparison between {team1_name} and {team2_name}',
            labels={'Metric': 'Metric', 'value': 'Value'},
            height=500,
            color_discrete_sequence=['#ef2213', '#20ef13']
        )
        fig_team_comparison.update_layout(template="plotly_dark")

        st.plotly_chart(fig_team_comparison)

# ==============================================================================
# SEARCH FOR A TEAM PAGE
# ==============================================================================
elif st.session_state.page == 'Search for a Team':
    st.header("Search for a Team")

    search_query = st.text_input("Enter Team Name (e.g., 'Arsenal')")
    if search_query:
        search_results = teams[teams['name'].str.contains(search_query, case=False, na=False)]
        if not search_results.empty:
            st.write(search_results)
        else:
            st.write("No teams found.")

# ==============================================================================
# FIXTURES PAGE
# ==============================================================================
elif st.session_state.page == 'Fixtures':
    st.header("Fixtures")

    fixtures_url = "https://fantasy.premierleague.com/api/fixtures/"
    try:
        response = requests.get(fixtures_url)
        response.raise_for_status()
        fixtures = response.json()
        fixtures_df = pd.DataFrame(fixtures)

        if not fixtures_df.empty:
            # Convert kickoff_time to datetime
            fixtures_df['kickoff_time'] = pd.to_datetime(fixtures_df['kickoff_time'], errors='coerce')

            # Extract date and time
            fixtures_df['Date'] = fixtures_df['kickoff_time'].dt.date
            fixtures_df['Time'] = fixtures_df['kickoff_time'].dt.strftime('%H:%M')  # Format as HH:MM

            # Map team IDs to names
            team_id_to_name = dict(teams[['id', 'name']].values)
            fixtures_df['team_h'] = fixtures_df['team_h'].map(team_id_to_name)
            fixtures_df['team_a'] = fixtures_df['team_a'].map(team_id_to_name)

            # Rename columns for clarity
            fixtures_df = fixtures_df.rename(columns={'team_h': 'Home', 'team_a': 'Away'})

            # Add scores if available
            fixtures_df['Home Score'] = fixtures_df.get('team_h_score', '-')
            fixtures_df['Away Score'] = fixtures_df.get('team_a_score', '-')

            # Convert to numeric (some may still be '-')
            fixtures_df['Home Score'] = pd.to_numeric(fixtures_df['Home Score'], errors='coerce')
            fixtures_df['Away Score'] = pd.to_numeric(fixtures_df['Away Score'], errors='coerce')

            # Determine match status
            fixtures_df['Status'] = fixtures_df.apply(
                lambda row: 'Finished' if row.get('finished') else 'Upcoming', axis=1
            )

            # Filter final display columns
            display_columns = ['Date', 'Time', 'Home', 'Away', 'Home Score', 'Away Score', 'Status']
            fixtures_df = fixtures_df[display_columns]

            # Team filter
            st.subheader("Filter by Team")
            all_teams_list = ['All'] + sorted(teams['name'].unique())
            selected_team = st.selectbox("Select Team:", options=all_teams_list)

            # Apply team filter
            if selected_team != 'All':
                filtered_fixtures = fixtures_df[
                    (fixtures_df['Home'] == selected_team) | 
                    (fixtures_df['Away'] == selected_team)
                ]
            else:
                filtered_fixtures = fixtures_df

            st.write("*Fixtures Table*")
            st.dataframe(filtered_fixtures, height=650, width=1400)
        else:
            st.write("No fixture data available.")

    except requests.RequestException as e:
        st.error(f"Error fetching fixtures: {e}")  

# ==============================================================================
# BEST PLAYERS PAGE
# ==============================================================================
elif st.session_state.page == 'Best Players':
    st.header("Best Players by Position")

    metrics_by_position = {
        'Goalkeeper': ['saves', 'clean_sheets', 'form'],
        'Defender': ['expected_goals', 'expected_assists', 'clean_sheets', 'influence', 'creativity', 'threat', 'form'],
        'Midfielder': ['expected_goals', 'expected_assists', 'influence', 'creativity', 'threat', 'form'],
        'Forward': ['expected_goals', 'expected_assists', 'influence', 'creativity', 'threat', 'form']
    }

    # Position selection (only those available)
    if 'position' in players.columns:
        unique_positions = list(players['position'].unique())
        # If "All" is needed, you can insert it: unique_positions.insert(0, "All")

        # Default selection to 'Forward' if present in the DataFrame
        default_index = 0
        if 'Forward' in unique_positions:
            default_index = unique_positions.index('Forward')

        position = st.selectbox("Select Position", options=unique_positions, index=default_index)

        filtered_players = players[players['position'] == position]

        # Ensure metrics columns are numeric
        for metric in metrics_by_position.get(position, []):
            if metric in filtered_players.columns:
                filtered_players[metric] = pd.to_numeric(filtered_players[metric], errors='coerce')

        selected_metrics = metrics_by_position.get(position, [])
        missing_metrics = [m for m in selected_metrics if m not in filtered_players.columns]

        if missing_metrics:
            st.error(f"Missing columns in data: {', '.join(missing_metrics)}")
        else:
            # Calculate a total score across the relevant metrics
            filtered_players['total_score'] = filtered_players[selected_metrics].sum(axis=1)

            # Sort and get the top 11
            top_11_players = filtered_players.sort_values(by='total_score', ascending=False).head(11)

            st.write(f"Top {len(top_11_players)} Players for '{position}'")

            # Create a bar chart to show these players
            fig_best_players = plot_bar_chart(
                data=top_11_players.sort_values(by='total_score', ascending=False),
                x='web_name',
                y='total_score',
                color='team',
                color_map=st.session_state.team_colors,
                title="Best Players by Selected Metrics",
                labels={'web_name': 'Player', 'total_score': 'Total Score'},
                height=500,
                template="plotly_dark"
            )
            # Sort x-axis by total_score
            fig_best_players.update_xaxes(title_text='Player', categoryorder='total descending')
            st.plotly_chart(fig_best_players)

            st.subheader("Detailed Player Information")
            st.dataframe(
                top_11_players[['first_name', 'web_name', 'team', 'position'] + selected_metrics],
                height=425,
                width=1200
            )
    else:
        st.error("The 'position' column is missing in the players DataFrame.")
