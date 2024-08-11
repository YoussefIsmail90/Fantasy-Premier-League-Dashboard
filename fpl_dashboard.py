import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import streamlit as st

# Set page configuration
st.set_page_config(page_title="Fantasy Premier League Dashboard", layout="wide")

# Initialize session state for navigation and search
if 'page' not in st.session_state:
    st.session_state.page = 'Home'
if 'comparison_players' not in st.session_state:
    st.session_state.comparison_players = []
if 'search_team' not in st.session_state:
    st.session_state.search_team = ""
if 'team_colors' not in st.session_state:
    st.session_state.team_colors = {}

# Fetch FPL data from the API with loading indicator
@st.cache_data(ttl=3600)
def fetch_fpl_data():
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

# Convert data to DataFrames
def prepare_data(data):
    players = pd.DataFrame(data['elements'])
    teams = pd.DataFrame(data['teams'])
    players = players[['first_name', 'second_name', 'team', 'total_points', 'goals_scored', 'assists', 'clean_sheets', 'now_cost', 'minutes', 'yellow_cards', 'red_cards', 'form', 'bonus', 'event_points', 'selected_by_percent']]
    players = players.merge(teams[['id', 'name']], left_on='team', right_on='id')
    players.drop(columns=['id', 'team'], inplace=True)
    players.rename(columns={'name': 'team'}, inplace=True)
    players.rename(columns={'now_cost': 'Price'}, inplace=True)
    players['Price'] = players['Price'] / 10
    players['selected_by_percent'] = pd.to_numeric(players['selected_by_percent'], errors='coerce')
    players.rename(columns={'selected_by_percent': 'Ownership'}, inplace=True)
    return players, teams

# Define color palettes
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

# Define color for teams
def get_team_colors(players, color_palette):
    return {team: color_palette[i % len(color_palette)] for i, team in enumerate(players['team'].unique())}

# Define navigation and refresh functions
def navigate_to(page_name):
    st.session_state.page = page_name

def refresh_data():
    st.session_state.fpl_data = fetch_fpl_data()
    st.session_state.players, st.session_state.teams = prepare_data(st.session_state.fpl_data)
    st.session_state.team_colors = get_team_colors(st.session_state.players, color_palette)

# Refresh Button
st.sidebar.button("Refresh Data", on_click=refresh_data)

# Load and prepare data
if 'fpl_data' not in st.session_state:
    st.session_state.fpl_data = fetch_fpl_data()
    st.session_state.players, st.session_state.teams = prepare_data(st.session_state.fpl_data)
    color_palette = color_palettes.get('Plasma', px.colors.sequential.Plasma)
    st.session_state.team_colors = get_team_colors(st.session_state.players, color_palette)
else:
    players, teams = st.session_state.players, st.session_state.teams
    color_palette = color_palettes.get('Plasma', px.colors.sequential.Plasma)
    st.session_state.team_colors = get_team_colors(st.session_state.players, color_palette)

# Calculate total number of players
total_players = len(st.session_state.players)

# Navigation Buttons
st.title("Fantasy Premier League Dashboard")

# Create layout for navigation buttons
col1, col2, col3, col4, col5, col6 = st.columns([1, 1, 1, 1, 1, 1])

with col1:
    if st.button("Home"):
        navigate_to("Home")
with col2:
    if st.button("Compare Players"):
        navigate_to("Compare Players")
with col3:
    if st.button("Search for a Player"):
        navigate_to("Search for a Player")
with col4:
    if st.button("Compare Teams"):
        navigate_to("Compare Teams")
with col5:
    if st.button("Search for a Team"):
        navigate_to("Search for a Team")
with col6:
    if st.button("Fixtures"):
        navigate_to("Fixtures")

# Page content based on navigation state
if st.session_state.page == 'Home':
    st.write("Real-time data updates from the Fantasy Premier League (FPL) API.")
    
    # Create layout for top options
    col1, col2 = st.columns([2, 2])
    
    with col1:
        st.subheader("Select Color Palette")
        selected_palette_name = st.selectbox("Select Color Palette:", options=list(color_palettes.keys()))
        color_palette = color_palettes.get(selected_palette_name, px.colors.sequential.Plasma)
        st.session_state.team_colors = get_team_colors(st.session_state.players, color_palette)
    
    st.subheader("Top Players by Total Points")
    
    fig = px.bar(
        st.session_state.players.sort_values(by='total_points', ascending=False).head(50),
        x='second_name',
        y='total_points',
        color='team',
        color_discrete_map=st.session_state.team_colors,
        title="Top 50 Players by Total Points",
        labels={'second_name': 'Player', 'total_points': 'Total Points'},
        height=500
    )
    fig.update_layout(template="plotly_dark")
    st.plotly_chart(fig)
    
    st.subheader("Player Detailed Statistics")

    num_players = st.slider("Number of Players to Display:", min_value=5, max_value=total_players, value=10)
    sort_by = st.selectbox("Sort By:", options=['Minutes', 'Total Points', 'Goals Scored', 'Assists', 'Clean Sheets', 'Ownership', 'Price'])

    detailed_players = st.session_state.players[['first_name', 'second_name', 'team', 'total_points', 'goals_scored', 'assists', 'clean_sheets', 'minutes', 'yellow_cards', 'red_cards', 'form', 'bonus', 'event_points', 'Ownership', 'Price']]
    
    if sort_by == 'Minutes':
        detailed_players = detailed_players.sort_values(by='minutes', ascending=False)
    elif sort_by == 'Total Points':
        detailed_players = detailed_players.sort_values(by='total_points', ascending=False)
    elif sort_by == 'Goals Scored':
        detailed_players = detailed_players.sort_values(by='goals_scored', ascending=False)
    elif sort_by == 'Assists':
        detailed_players = detailed_players.sort_values(by='assists', ascending=False)
    elif sort_by == 'Clean Sheets':
        detailed_players = detailed_players.sort_values(by='clean_sheets', ascending=False)
    elif sort_by == 'Ownership':
        detailed_players = detailed_players.sort_values(by='Ownership', ascending=False)
    elif sort_by == 'Price':
        detailed_players = detailed_players.sort_values(by='Price', ascending=False)
    
    top_players_df = detailed_players.head(num_players)

    styled_players = top_players_df.style \
        .background_gradient(cmap='plasma') \
        .format(precision=2)

    st.dataframe(styled_players)

    st.subheader("Players Info")
    
    top_n = 20

    price_form_df = st.session_state.players[['second_name', 'bonus', 'Ownership', 'Price']].sort_values(by='Price', ascending=False).head(top_n)
    price_form_df = price_form_df.rename(columns={'Ownership': 'ownership'})
    price_colors = '#1f77b4'
    bonus_colors = '#ff7f0e'
    ownership_colors = '#2ca02c'

    fig_combined = go.Figure()

    fig_combined.add_trace(go.Bar(
        x=price_form_df['second_name'],
        y=price_form_df['Price'],
        name='Price',
        marker_color=price_colors
    ))

    fig_combined.add_trace(go.Bar(
        x=price_form_df['second_name'],
        y=price_form_df['bonus'],
        name='Bonus Points',
        marker_color=bonus_colors
    ))

    fig_combined.add_trace(go.Bar(
        x=price_form_df['second_name'],
        y=price_form_df['ownership'],
        name='Ownership',
        marker_color=ownership_colors
    ))

    fig_combined.update_layout(
        barmode='group',
        title='Top Players by Price, Bonus Points, and Ownership',
        xaxis_title='Player',
        yaxis_title='Value',
        template='plotly_dark'
    )

    st.plotly_chart(fig_combined)

elif st.session_state.page == 'Compare Players':
    st.header("Compare Players")
    st.write("Compare the statistics of different players.")

    player_options = st.session_state.players['second_name'].tolist()
    selected_players = st.multiselect("Select Players to Compare:", options=player_options, default=st.session_state.comparison_players)
    st.session_state.comparison_players = selected_players

    if len(selected_players) >= 2:
        comparison_df = st.session_state.players[st.session_state.players['second_name'].isin(selected_players)]

        fig_comp = px.line(
            comparison_df,
            x='second_name',
            y=['total_points', 'goals_scored', 'assists', 'clean_sheets', 'minutes'],
            color='second_name',
            markers=True,
            title='Player Comparison'
        )
        fig_comp.update_layout(template="plotly_dark")
        st.plotly_chart(fig_comp)
    else:
        st.warning("Please select at least two players for comparison.")

elif st.session_state.page == 'Search for a Player':
    st.header("Search for a Player")
    player_name = st.text_input("Enter Player Name:")
    
    if player_name:
        search_df = st.session_state.players[st.session_state.players['second_name'].str.contains(player_name, case=False)]
        
        if not search_df.empty:
            st.write("Search Results:")
            st.dataframe(search_df)
        else:
            st.write("No players found.")

elif st.session_state.page == 'Compare Teams':
    st.header("Compare Teams")
    st.write("Compare team statistics.")
    
    team_options = st.session_state.teams['name'].tolist()
    selected_teams = st.multiselect("Select Teams to Compare:", options=team_options)
    
    if len(selected_teams) >= 2:
        team_stats = st.session_state.players[st.session_state.players['team'].isin(selected_teams)]
        team_stats_summary = team_stats.groupby('team').agg({
            'total_points': 'sum',
            'goals_scored': 'sum',
            'assists': 'sum',
            'clean_sheets': 'sum'
        }).reset_index()
        
        fig_team_comp = px.bar(
            team_stats_summary,
            x='team',
            y=['total_points', 'goals_scored', 'assists', 'clean_sheets'],
            title='Team Comparison'
        )
        fig_team_comp.update_layout(template="plotly_dark")
        st.plotly_chart(fig_team_comp)
    else:
        st.warning("Please select at least two teams for comparison.")

elif st.session_state.page == 'Search for a Team':
    st.header("Search for a Team")
    team_name = st.text_input("Enter Team Name:")
    
    if team_name:
        search_teams_df = st.session_state.teams[st.session_state.teams['name'].str.contains(team_name, case=False)]
        
        if not search_teams_df.empty:
            st.write("Search Results:")
            st.dataframe(search_teams_df)
        else:
            st.write("No teams found.")

elif st.session_state.page == 'Fixtures':
    st.header("Fixtures")
    
    try:
        fixtures_url = "https://fantasy.premierleague.com/api/fixtures/"
        response = requests.get(fixtures_url)
        response.raise_for_status()
        fixtures = response.json()
        fixtures_df = pd.DataFrame(fixtures)
        
        fixtures_df['kickoff_time'] = pd.to_datetime(fixtures_df['kickoff_time'])
        fixtures_df['week'] = fixtures_df['kickoff_time'].dt.isocalendar().week
        fixtures_df['year'] = fixtures_df['kickoff_time'].dt.year
        fixtures_df = fixtures_df[['week', 'year', 'team_a', 'team_h', 'kickoff_time']]
        
        st.write("Fixtures Calendar:")
        st.dataframe(fixtures_df)
    
    except requests.RequestException as e:
        st.error(f"Error fetching fixtures: {e}")

