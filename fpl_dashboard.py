# ---------------------------------------------------------------------------
# 5. MAIN APP
# ---------------------------------------------------------------------------
if "players" not in st.session_state or st.session_state["players"].empty:
    with st.spinner("Fetching and processing data..."):
        refresh_data()

hero_banner()
instructions_expander()

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
    tab_best_players(st.session_state["players"], st.session_state["club_difficulty"])
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
