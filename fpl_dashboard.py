import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import streamlit as st

# Set page configuration
st.set_page_config(page_title="Fantasy Premier League Dashboard", layout="wide")

# Initialize session state for navigation
if 'page' not in st.session_state:
    st.session_state.page = 'Home'

# Initialize session state for player comparison
if 'comparison_players' not in st.session_state:
    st.session_state.comparison_players = []

# Initialize session state for team search
if 'search_team' not in st.session_state:
    st.session_state.search_team = ""

# Fetch FPL data from the API
@st.cache_data(ttl=3600)
def fetch_fpl_data():
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
    players = players[['first_name', 'second_name', 'team', 'total_points', 'goals_scored', 'assists', 'clean_sheets', 'now_cost', 'minutes', 'yellow_cards', 'red_cards']]
    players = players.merge(teams[['id', 'name']], left_on='team', right_on='id')
    players.drop(columns=['id', 'team'], inplace=True)
    players.rename(columns={'name': 'team'}, inplace=True)
    return players, teams

# Load and prepare data
fpl_data = fetch_fpl_data()
players, teams = prepare_data(fpl_data)

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

# Initialize color_palette
color_palette = color_palettes.get('Plasma', px.colors.sequential.Plasma)

# Define navigation buttons
def navigate_to(page_name):
    st.session_state.page = page_name

# Navigation Buttons
st.title("Fantasy Premier League Dashboard")

# Create layout for navigation buttons
col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 2])

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


# Page content based on navigation state
if st.session_state.page == 'Home':
    # Home Page
    st.write("Real-time data updates from the Fantasy Premier League (FPL) API.")
    
    # Create layout for top options
    col1, col2 = st.columns([2, 2])
    
    with col1:
        # Top: Color Palette Selection
        st.subheader("Select Color Palette")
        selected_palette_name = st.selectbox("Select Color Palette:", options=list(color_palettes.keys()))
        color_palette = color_palettes.get(selected_palette_name, px.colors.sequential.Plasma)
    
    # Display top players
    st.subheader("Top Players by Total Points")
    
    # Create a dictionary to map team names to colors
    team_colors = {team: color_palette[i % len(color_palette)] for i, team in enumerate(players['team'].unique())}
    
    fig = px.bar(
        players.sort_values(by='total_points', ascending=False).head(10),
        x='second_name',
        y='total_points',
        color='team',
        color_discrete_map=team_colors,
        title="Top 10 Players by Total Points",
        labels={'second_name': 'Player', 'total_points': 'Total Points'},
        height=500
    )
    fig.update_layout(template="plotly_dark")
    st.plotly_chart(fig)
    
    # Player Detailed Statistics
    st.subheader("Player Detailed Statistics")
    detailed_players = players[['first_name', 'second_name', 'team', 'total_points', 'goals_scored', 'assists', 'clean_sheets', 'minutes', 'yellow_cards', 'red_cards']]
    
    # Apply formatting and styling
    styled_players = detailed_players.style \
        .background_gradient(cmap='plasma') \
        .format(precision=2)
    
    st.dataframe(styled_players)
    
    # Team Performance Comparison
    st.subheader("Extended Team Performance Comparison")
    team_perf_ext = players.groupby('team').agg({
        'total_points': 'sum',
        'goals_scored': 'sum',
        'assists': 'sum',
        'clean_sheets': 'sum',
        'minutes': 'sum',
        'yellow_cards': 'sum',
        'red_cards': 'sum'
    }).reset_index()
    
    team_perf_sorted_ext = team_perf_ext.sort_values(by='total_points', ascending=False)
    team_perf_fig_ext = go.Figure()
    team_perf_fig_ext.add_trace(go.Bar(x=team_perf_sorted_ext['team'], y=team_perf_sorted_ext['total_points'], name='Total Points', marker_color=color_palette[3]))
    team_perf_fig_ext.add_trace(go.Bar(x=team_perf_sorted_ext['team'], y=team_perf_sorted_ext['goals_scored'], name='Goals Scored', marker_color=color_palette[4]))
    team_perf_fig_ext.add_trace(go.Bar(x=team_perf_sorted_ext['team'], y=team_perf_sorted_ext['yellow_cards'], name='Yellow Cards', marker_color=color_palette[5]))
    team_perf_fig_ext.update_layout(title="Extended Team Performance Comparison", barmode='group', xaxis_title="Team", yaxis_title="Count", height=500)
    st.plotly_chart(team_perf_fig_ext)

    st.markdown("##")
    st.markdown("**For more apps ideas, visit [my Kaggle profile](https://www.kaggle.com/youssefismail20)**")

elif st.session_state.page == 'Compare Players':
    # Compare Players Page
    st.title("Compare Players")
    st.write("Use this section to compare players based on various metrics.")
    
    # Player comparison functionality
    st.session_state.comparison_players = st.multiselect("Select Players to Compare:", options=players['second_name'].unique())
    comparison_players = st.session_state.comparison_players
    
    if len(comparison_players) > 1:
        comp_df = players[players['second_name'].isin(comparison_players)]
        
        # 1. Combined Metrics Bar Chart
        metrics = ['total_points', 'goals_scored', 'assists', 'clean_sheets']
        combined_metrics_df = comp_df.melt(id_vars=['second_name', 'team'], value_vars=metrics, var_name='Metric', value_name='Value')
        
        combined_metrics_fig = px.bar(
            combined_metrics_df,
            x='second_name',
            y='Value',
            color='Metric',
            facet_col='Metric',
            facet_col_wrap=3,
            title="Combined Metrics Comparison",
            labels={'second_name': 'Player', 'Value': 'Metric Value'},
            height=600
        )
        combined_metrics_fig.update_layout(
            template="plotly_dark",
            xaxis_title="Player",
            yaxis_title="Metric Value",
            barmode='group'
        )
        st.plotly_chart(combined_metrics_fig)
        
        # 2. Enhanced Performance Radar Chart
        radar_df = comp_df.set_index('second_name')[['goals_scored', 'assists', 'clean_sheets']]
        radar_df = radar_df.fillna(0)  # Fill NaN values with 0
        
        radar_fig = go.Figure()
        for player in radar_df.index:
            radar_fig.add_trace(go.Scatterpolar(
                r=radar_df.loc[player],
                theta=radar_df.columns,
                fill='toself',
                name=player
            ))
        
        radar_fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 30],
                    showticklabels=True
                ),
                angularaxis=dict(
                    tickmode='array',
                    tickvals=list(range(len(radar_df.columns))),
                    ticktext=radar_df.columns
                )
            ),
            showlegend=True,
            title="Player Performance Radar Chart",
            title_font_size=18,
            margin=dict(t=50, b=0, l=0, r=0)
        )
        radar_fig.update_layout(template="plotly_dark")
        st.plotly_chart(radar_fig)
    else:
        st.write("Please select more than one player to compare.")





elif st.session_state.page == 'Search for a Player':
    # Search for a Player Page
    st.title("Search for a Player")
    st.write("Enter a player's name to search and view their performance metrics.")
    
    player_name = st.text_input("Enter player's name:", "")
    
    if player_name:
        player_search = players[(players['first_name'].str.contains(player_name, case=False)) | (players['second_name'].str.contains(player_name, case=False))]
        
        if not player_search.empty:
            st.subheader(f"{player_name} Performance Metrics")
            
            # Aggregating metrics
            metrics = ['goals_scored', 'assists', 'clean_sheets', 'total_points']
            player_metrics = player_search[metrics].sum()

            # Data Preparation for Stacked Bar Chart
            df = pd.DataFrame({
                'Metric': metrics,
                'Value': player_metrics
            })

            # Create Stacked Bar Chart
            fig = px.bar(
                df,
                x='Metric',
                y='Value',
                title=f"Performance Metrics Breakdown for {player_name}",
                labels={'Value': 'Total Value', 'Metric': 'Metric'},
                color='Metric',
                color_discrete_sequence=px.colors.sequential.Plasma,
                height=500
            )
            
            fig.update_layout(
                barmode='stack',
                template="plotly_dark"
            )
            
            st.plotly_chart(fig)
            
        else:
            st.write("Player not found.")
    else:
        st.write("Please enter a player name.")


elif st.session_state.page == 'Compare Teams':
    # Compare Teams Page
    st.title("Compare Teams")
    st.write("Compare teams based on various metrics.")
    
    teams_comparison = st.multiselect("Select Teams to Compare:", options=teams['name'].unique())
    
    if len(teams_comparison) > 1:
        team_comparison_df = players[players['team'].isin(teams_comparison)]
        
        # 1. Team Performance Overview
        overview_df = team_comparison_df.groupby('team').agg({
            'total_points': 'sum',
            'goals_scored': 'sum',
            'assists': 'sum',
            'clean_sheets': 'sum',
            'minutes': 'sum',
            'yellow_cards': 'sum',
            'red_cards': 'sum'
        }).reset_index()
        
        # Create a combined bar chart for multiple metrics
        fig_overview = px.bar(
            overview_df,
            x='team',
            y=['total_points', 'goals_scored', 'assists', 'clean_sheets'],
            title="Team Performance Overview",
            labels={'value': 'Count', 'team': 'Team'},
            height=500
        )
        fig_overview.update_layout(
            barmode='group',
            template="plotly_dark"
        )
        st.plotly_chart(fig_overview)
        
        
    else:
        st.write("Please select more than one team to compare.")


elif st.session_state.page == 'Search for a Team':
    # Search for a Team Page
    st.title("Search for a Team")
    st.write("Enter a team's name to search and view their performance metrics.")
    
    search_team = st.text_input("Enter team name:", "")
    
    if search_team:
        team_search = players[players['team'].str.contains(search_team, case=False)]
        
        if not team_search.empty:
            st.subheader(f"{search_team} Performance Metrics")
            
            # Aggregating metrics
            metrics = ['goals_scored', 'assists', 'clean_sheets', 'yellow_cards', 'red_cards']
            team_metrics = team_search[metrics].sum()
            
            # Create a DataFrame for the multi-metric bar chart
            metrics_df = pd.DataFrame({
                'Metric': metrics,
                'Value': team_metrics
            })

            # Create a bar chart with stacked bars for better comparison
            fig = px.bar(
                metrics_df,
                x='Metric',
                y='Value',
                title=f"Performance Metrics for {search_team}",
                labels={'Value': 'Total Value', 'Metric': 'Metric'},
                color='Metric',
                color_discrete_map={
                    'goals_scored': color_palette[0],
                    'assists': color_palette[1],
                    'clean_sheets': color_palette[2],
                    'yellow_cards': color_palette[3],
                    'red_cards': color_palette[4]
                },
                height=500
            )
            fig.update_layout(
                template="plotly_dark",
                xaxis_title="Metric",
                yaxis_title="Total Value"
            )
            st.plotly_chart(fig)
            
        else:
            st.write("Team not found.")
    else:
        st.write("Please enter a team name.")


