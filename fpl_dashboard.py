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
    players = players[['first_name', 'second_name', 'team', 'total_points', 'goals_scored', 'assists', 'clean_sheets', 
                       'now_cost', 'minutes', 'yellow_cards', 'red_cards', 'form', 'bonus', 'event_points', 
                       'selected_by_percent', 'influence', 'creativity', 'threat', 'expected_goals', 'expected_assists', 
                       'expected_goals_conceded', 'saves']]
    players = players.merge(teams[['id', 'name']], left_on='team', right_on='id')
    players.drop(columns=['id', 'team'], inplace=True)
    players.rename(columns={'name': 'team'}, inplace=True)
    players.rename(columns={'now_cost': 'Price'}, inplace=True)
    players.rename(columns={'minutes': 'Hours'}, inplace=True)
    players['Hours'] = players['Hours'] / 60
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
col1, col2, col3, col4, col5, col6  = st.columns([1, 1, 1, 1, 1, 1])

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
    st.write("Real-time data updates from the Fantasy Premier League.")
    
    # Check if player data is available
    if 'players' not in st.session_state or st.session_state.players.empty:
        st.error("No player data available. Please check the data loading process.")
        st.stop()
    
    st.subheader("Top Players by Total Points")
    
    fig = px.bar(
        st.session_state.players.sort_values(by='total_points', ascending=False).head(50),
        x='second_name',
        y='total_points',
        color='team',
        color_discrete_map=st.session_state.team_colors,
        title="Top Players by Total Points",
        labels={'second_name': 'Player', 'total_points': 'Total Points'},
        height=500
    )
    fig.update_layout(template="plotly_dark")
    st.plotly_chart(fig)
    
    st.subheader("Player Detailed Statistics")

    num_players = st.slider("Number of Players to Display:", min_value=5, max_value=total_players, value=10)
    sort_by = st.selectbox("Sort By:", options=['Hours', 'Total Points', 'Goals Scored', 'Assists', 'Clean Sheets', 'Ownership', 'Price'])

    detailed_players = st.session_state.players[['first_name', 'second_name', 'team', 'total_points', 'goals_scored', 'assists', 'clean_sheets', 'Hours', 'yellow_cards', 'red_cards', 'form', 'bonus', 'event_points', 'Ownership', 'Price']]
    
    if sort_by == 'Hours':
        detailed_players = detailed_players.sort_values(by='Hours', ascending=False)
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

    price_form_df = st.session_state.players[['second_name', 'bonus', 'Ownership', 'Price']].sort_values(by='Ownership', ascending=False).head(top_n)
    st.write("Top 20 players based on Ownership:")
    st.write(price_form_df)
    
    st.subheader("Team Performance")
    
    team_performance = st.session_state.players.groupby('team').agg({
        'total_points': 'sum',
        'goals_scored': 'sum',
        'assists': 'sum',
        'clean_sheets': 'sum',
        'Price': 'mean'
    }).reset_index()

    fig = px.bar(
        team_performance,
        x='team',
        y=['total_points', 'goals_scored', 'assists', 'clean_sheets'],
        title="Team Performance Overview",
        labels={'value': 'Count', 'team': 'Team'},
        height=500,
        color_discrete_map=st.session_state.team_colors
    )
    fig.update_layout(template="plotly_dark")
    st.plotly_chart(fig)

    # Fetch injury and suspension data
def fetch_injury_data():
    # This is a mockup URL; replace with actual API endpoint
    url = "https://fantasy.premierleague.com/api/injury-data/"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.RequestException as e:
        st.error(f"Error fetching injury data: {e}")
        return {}

# Display injury and suspension data
st.sidebar.header("Injury and Suspension Updates")
injury_data = fetch_injury_data()

if injury_data:
    st.write("Injury and Suspension Updates")
    st.dataframe(pd.DataFrame(injury_data))
else:
    st.write("No injury data available.")


elif st.session_state.page == 'Compare Players':
    st.subheader("Compare Players")
    
    if 'comparison_players' not in st.session_state or len(st.session_state.comparison_players) < 2:
        st.warning("Select at least two players to compare.")
    else:
        comparison_df = st.session_state.players[st.session_state.players['second_name'].isin(st.session_state.comparison_players)]
        
        fig = px.bar(
            comparison_df,
            x='second_name',
            y=['total_points', 'goals_scored', 'assists', 'clean_sheets'],
            title="Player Comparison",
            color='team',
            color_discrete_map=st.session_state.team_colors,
            height=500
        )
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig)

elif st.session_state.page == 'Search for a Player':
    st.subheader("Search for a Player")
    
    search_term = st.text_input("Enter player name:")
    if search_term:
        search_results = st.session_state.players[st.session_state.players['second_name'].str.contains(search_term, case=False)]
        if search_results.empty:
            st.warning("No players found.")
        else:
            st.write(search_results)
            st.write(f"Total players found: {len(search_results)}")
    
elif st.session_state.page == 'Compare Teams':
    st.subheader("Compare Teams")
    
    teams_to_compare = st.multiselect("Select Teams to Compare:", options=st.session_state.teams['name'].tolist())
    
    if len(teams_to_compare) < 2:
        st.warning("Select at least two teams to compare.")
    else:
        team_comparison_df = st.session_state.players[st.session_state.players['team'].isin(teams_to_compare)]
        
        fig = px.bar(
            team_comparison_df,
            x='team',
            y=['total_points', 'goals_scored', 'assists', 'clean_sheets'],
            title="Team Comparison",
            color='team',
            color_discrete_map=st.session_state.team_colors,
            height=500
        )
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig)

elif st.session_state.page == 'Search for a Team':
    st.subheader("Search for a Team")
    
    search_term = st.text_input("Enter team name:")
    if search_term:
        search_results = st.session_state.teams[st.session_state.teams['name'].str.contains(search_term, case=False)]
        if search_results.empty:
            st.warning("No teams found.")
        else:
            st.write(search_results)
            st.write(f"Total teams found: {len(search_results)}")

elif st.session_state.page == 'Fixtures':
    st.subheader("Fixtures")
    
    # Fetch fixtures data
    url = "https://fantasy.premierleague.com/api/fixtures/"
    response = requests.get(url)
    fixtures_data = response.json()
    
    fixtures_df = pd.DataFrame(fixtures_data)
    
    if not fixtures_df.empty:
        fixtures_df['event_date'] = pd.to_datetime(fixtures_df['event_date'], format='%Y-%m-%dT%H:%M:%S')
        fixtures_df['date'] = fixtures_df['event_date'].dt.date
        fixtures_df['time'] = fixtures_df['event_date'].dt.time
        fixtures_df = fixtures_df[['date', 'time', 'team_a', 'team_h']]
        fixtures_df.columns = ['Date', 'Time', 'Home Team', 'Away Team']
        
        st.write(fixtures_df)
    else:
        st.warning("No fixtures data available.")
