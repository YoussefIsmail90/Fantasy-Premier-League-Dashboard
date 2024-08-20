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
    element_types = pd.DataFrame(data['element_types'])  # Fetch element types

    players = players[['first_name', 'second_name', 'team', 'total_points', 'goals_scored', 'assists', 'clean_sheets', 
                       'now_cost', 'minutes', 'yellow_cards', 'red_cards', 'form', 'bonus', 'event_points', 
                       'selected_by_percent', 'influence', 'creativity', 'threat', 'expected_goals', 
                       'expected_assists', 'expected_goals_conceded', 'saves', 'element_type']]
    players = players.merge(teams[['id', 'name']], left_on='team', right_on='id')
    players.drop(columns=['id', 'team'], inplace=True)
    players.rename(columns={'name': 'team'}, inplace=True)
    players.rename(columns={'now_cost': 'Price'}, inplace=True)
    players.rename(columns={'minutes': 'Hours'}, inplace=True)
    players['Hours'] = players['Hours'] / 60
    players['Price'] = players['Price'] / 10
    players['selected_by_percent'] = pd.to_numeric(players['selected_by_percent'], errors='coerce')
    players.rename(columns={'selected_by_percent': 'Ownership'}, inplace=True)

    # Map element_type to readable position names
    element_types_map = dict(zip(element_types['id'], element_types['singular_name']))
    players['position'] = players['element_type'].map(element_types_map)

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
col1, col2, col3, col4, col5, col6 , col7 = st.columns([1, 1, 1, 1, 1, 1, 1])


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
with col7:
    if st.button("Best Players"):
        navigate_to("Best Players")



# Page content based on navigation state
if st.session_state.page == 'Home':
    st.write("Real-time data updates from the Fantasy Premier League.")
    
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
    price_form_df = price_form_df.rename(columns={'Ownership': 'ownership'})
    price_colors = '#1f77b4'
    bonus_colors = '#ff7f0e'
    ownership_colors = '#2ca02c'

    fig_combined = go.Figure()

    fig_combined.add_trace(go.Bar(
        x=price_form_df['second_name'],
        y=price_form_df['ownership'],
        name='Ownership',
        marker_color=ownership_colors
    ))

    fig_combined.add_trace(go.Bar(
        x=price_form_df['second_name'],
        y=price_form_df['bonus'],
        name='Bonus Points',
        marker_color=bonus_colors
    ))

    fig_combined.add_trace(go.Bar(
        x=price_form_df['second_name'],
        y=price_form_df['Price'],
        name='Price',
        marker_color=price_colors
    ))

    fig_combined.update_layout(
        barmode='group',
        title='Top Players by Ownership, Bonus Points, and Price',
        xaxis_title='Player',
        yaxis_title='Value',
        template='plotly_dark'
    )

    st.plotly_chart(fig_combined)



elif st.session_state.page == 'Compare Players':
    st.header("Compare Players")

    player1_name = st.selectbox("Select Player 1", options=players['second_name'].unique())
    player2_name = st.selectbox("Select Player 2", options=players['second_name'].unique())

    if player1_name and player2_name:
        player1_data = players[players['second_name'] == player1_name].iloc[0]
        player2_data = players[players['second_name'] == player2_name].iloc[0]

        metrics = ['total_points', 'goals_scored', 'assists', 'clean_sheets', 'Hours', 'yellow_cards', 'red_cards','Ownership','Price']
        player1_values = [player1_data[metric] for metric in metrics]
        player2_values = [player2_data[metric] for metric in metrics]

        comparison_df = pd.DataFrame({
            'Metric': metrics,
            player1_name: player1_values,
            player2_name: player2_values
        })

        fig_comparison = px.bar(comparison_df, x='Metric', y=[player1_name, player2_name],
                               title=f'Comparison between {player1_name} and {player2_name}',
                               labels={'Metric': 'Metric', 'value': 'Value'},
                               height=500,
                               color_discrete_sequence=['#ef2213', '#20ef13'])
        
        fig_comparison.update_layout(template="plotly_dark")

        st.plotly_chart(fig_comparison)

elif st.session_state.page == 'Search for a Player':
    st.header("Search for a Player")

    search_query = st.text_input("Enter Player Name")
    if search_query:
        search_results = players[players['second_name'].str.contains(search_query, case=False, na=False)]
        if not search_results.empty:
            st.write(search_results)
        else:
            st.write("No players found.")

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

        fig_team_comparison = px.bar(stats_df, x='Metric', y=[team1_name, team2_name],
                                    title=f'Comparison between {team1_name} and {team2_name}',
                                    labels={'Metric': 'Metric', 'value': 'Value'},
                                    height=500,
                                    color_discrete_sequence=['#ef2213', '#20ef13'])
        fig_team_comparison.update_layout(template="plotly_dark")

        st.plotly_chart(fig_team_comparison)

elif st.session_state.page == 'Search for a Team':
    st.header("Search for a Team")

    search_query = st.text_input("Enter Team Name")
    if search_query:
        search_results = teams[teams['name'].str.contains(search_query, case=False, na=False)]
        if not search_results.empty:
            st.write(search_results)
        else:
            st.write("No teams found.")

elif st.session_state.page == 'Fixtures':
    st.header("Fixtures")

    # Fetch and display fixtures
    fixtures_url = "https://fantasy.premierleague.com/api/fixtures/"
    try:
        response = requests.get(fixtures_url)
        response.raise_for_status()
        fixtures = response.json()
        fixtures_df = pd.DataFrame(fixtures)

        # Convert datetime and add date and time columns
        fixtures_df['kickoff_time'] = pd.to_datetime(fixtures_df['kickoff_time'])
        fixtures_df['Date'] = fixtures_df['kickoff_time'].dt.date
        fixtures_df['Time'] = fixtures_df['kickoff_time'].dt.strftime('%H:%M')  # Format time as HH:MM

        # Map team IDs to team names using the teams DataFrame
        team_id_to_name = dict(teams[['id', 'name']].values)
        fixtures_df['team_h'] = fixtures_df['team_h'].map(team_id_to_name)
        fixtures_df['team_a'] = fixtures_df['team_a'].map(team_id_to_name)

        # Rename columns
        fixtures_df = fixtures_df.rename(columns={'team_h': 'Home', 'team_a': 'Away'})
        
        # Add useful columns
        fixtures_df['Home Score'] = fixtures_df.get('team_h_score', '-').fillna('-')
        fixtures_df['Away Score'] = fixtures_df.get('team_a_score', '-').fillna('-')
        fixtures_df['Home Score'] = pd.to_numeric(fixtures_df['Home Score'], errors='coerce')
        fixtures_df['Away Score'] = pd.to_numeric(fixtures_df['Away Score'], errors='coerce')

        # Add status column based on 'finished' and 'finished_provisional'
        fixtures_df['Status'] = fixtures_df['finished'].apply(lambda x: 'Finished' if x else 'Upcoming')
        fixtures_df['Status'] = fixtures_df['Status'].fillna('Provisional' if fixtures_df['finished_provisional'].any() else 'Upcoming')

        # Select columns to display
        fixtures_df = fixtures_df[['Date', 'Time', 'Home', 'Away', 'Home Score', 'Away Score', 'Status']]

        # Team filter
        st.subheader("Filter by Team")
        selected_team = st.selectbox("Select Team:", options=['All'] + sorted(teams['name'].unique()))

        # Apply team filter
        if selected_team != 'All':
            filtered_fixtures = fixtures_df[(fixtures_df['Home'] == selected_team) | (fixtures_df['Away'] == selected_team)]
        else:
            filtered_fixtures = fixtures_df

        # Display filtered fixtures in a table
        st.write("*Fixtures Table*")
        st.dataframe(filtered_fixtures, width=1200)  # Adjust the width as needed

    except requests.RequestException as e:
        st.error(f"Error fetching fixtures: {e}")  

elif st.session_state.page == 'Best Players':
    st.header("Best Players")

    # Define metrics for each position
    metrics_by_position = {
        'Goalkeeper': ['saves', 'clean_sheets'],
        'Defender': ['expected_goals', 'expected_assists', 'clean_sheets', 'influence', 'creativity', 'threat'],
        'Midfielder': ['expected_goals', 'expected_assists', 'influence', 'creativity', 'threat'],
        'Forward': ['expected_goals', 'expected_assists', 'influence', 'creativity', 'threat']
    }

    # Check if 'position' column exists
    if 'position' in players.columns:
        # Set default position to 'Forward' and remove 'All'
        position = st.selectbox("Select Position", options=list(players['position'].unique()), index=list(players['position'].unique()).index('Forward'))
        
        # Filter by position
        filtered_players = players[players['position'] == position]

        # Ensure metrics columns are numeric
        for metric in metrics_by_position.get(position, []):
            if metric in filtered_players.columns:
                filtered_players[metric] = pd.to_numeric(filtered_players[metric], errors='coerce')
        
        # Determine metrics to use based on position
        selected_metrics = metrics_by_position.get(position, [])
        
        # Handle missing metrics columns
        missing_metrics = [metric for metric in selected_metrics if metric not in filtered_players.columns]
        if missing_metrics:
            st.error(f"Missing columns: {', '.join(missing_metrics)}")
        else:
            # Calculate total score based on selected metrics
            filtered_players['total_score'] = filtered_players[selected_metrics].sum(axis=1)

            # Sort by total score
            top_11_players = filtered_players.sort_values(by='total_score', ascending=False).head(11)

            st.write(f"Top 11 Players based on selected metrics for position '{position}'")
            
            # Display top players sorted by total score
            fig = px.bar(
                top_11_players,
                x='second_name',
                y='total_score',
                color='team',
                color_discrete_map=st.session_state.team_colors,
                title="Best 11 Players by Metrics",
                labels={'second_name': 'Player', 'total_score': 'Total Score'},
                height=500
            )
            fig.update_layout(template="plotly_dark")
            fig.update_xaxes(title_text='Player', categoryorder='total descending')  # Ensure x-axis is sorted by total_score
            st.plotly_chart(fig)
            
            st.subheader("Detailed Player Information")
            st.write(top_11_players[['first_name', 'second_name', 'team', 'position'] + selected_metrics])
    else:
        st.error("The 'position' column is missing in the data.")





