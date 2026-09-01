import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Draft War Room (Slot 9)", layout="wide")

# 1. BASELINE DATA & CONFIGURATION
MY_PICKS = [9, 12, 29, 32, 49, 52, 69, 72, 89, 92, 109, 112, 129, 132, 149, 152]
BASELINES = {'QB': 10, 'RB': 30, 'WR': 30, 'TE': 10, 'DST': 10, 'K': 10}

DEFAULT_ROSTER_LIMITS = {
    'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'FLEX': 1, 'DST': 1, 'K': 1, 'BENCH': 7, 'IR': 1
}

# 2. DATA FETCHER (Sleeper Public Feed / Fallback Projections)
@st.cache_data(ttl=3600)
def fetch_live_player_pool():
    try:
        url = "https://api.sleeper.app/v1/players/nfl"
        res = requests.get(url, timeout=10).json()
        pool = []
        for p_id, p in res.items():
            if p.get("active") and p.get("position") in ['QB', 'RB', 'WR', 'TE', 'DEF', 'K']:
                pos = 'DST' if p.get('position') == 'DEF' else p.get('position')
                # Approximate baseline fantasy points from rank for demo / CSV fallback
                rank = p.get('search_rank') or 999
                proj = max(350 - (rank * 1.5), 20.0) if pos == 'QB' else max(280 - (rank * 1.2), 15.0)
                pool.append({
                    "Name": p.get("full_name"),
                    "Pos": pos,
                    "Team": p.get("team") or "FA",
                    "ADP": rank,
                    "ProjPts": round(proj, 1),
                    "Status": p.get("injury_status") or "Healthy",
                    "Notes": p.get("injury_notes") or "Active"
                })
        df = pd.DataFrame(pool)
        return df.sort_values(by="ADP").reset_index(drop=True)
    except Exception:
        # Fallback starter set if offline
        data = [
            {"Name": "Jahmyr Gibbs", "Pos": "RB", "Team": "DET", "ADP": 1, "ProjPts": 330.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Bijan Robinson", "Pos": "RB", "Team": "ATL", "ADP": 2, "ProjPts": 314.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Ja'Marr Chase", "Pos": "WR", "Team": "CIN", "ADP": 3, "ProjPts": 277.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Puka Nacua", "Pos": "WR", "Team": "LAR", "ADP": 4, "ProjPts": 275.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Jonathan Taylor", "Pos": "RB", "Team": "IND", "ADP": 6, "ProjPts": 265.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Amon-Ra St. Brown", "Pos": "WR", "Team": "DET", "ADP": 8, "ProjPts": 270.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "James Cook", "Pos": "RB", "Team": "BUF", "ADP": 9, "ProjPts": 258.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "A.J. Brown", "Pos": "WR", "Team": "PHI", "ADP": 10, "ProjPts": 255.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Saquon Barkley", "Pos": "RB", "Team": "PHI", "ADP": 11, "ProjPts": 256.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Garrett Wilson", "Pos": "WR", "Team": "NYJ", "ADP": 12, "ProjPts": 248.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "De'Von Achane", "Pos": "RB", "Team": "MIA", "ADP": 14, "ProjPts": 245.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Brock Bowers", "Pos": "TE", "Team": "LV", "ADP": 20, "ProjPts": 210.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Josh Allen", "Pos": "QB", "Team": "BUF", "ADP": 22, "ProjPts": 375.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Drake London", "Pos": "WR", "Team": "ATL", "ADP": 25, "ProjPts": 230.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Lamar Jackson", "Pos": "QB", "Team": "BAL", "ADP": 31, "ProjPts": 348.0, "Status": "Healthy", "Notes": "Active"},
        ]
        return pd.DataFrame(data)

def compute_vorp(df):
    df_calc = df.copy()
    for pos, rank in BASELINES.items():
        pos_pool = df_calc[df_calc['Pos'] == pos].sort_values(by='ProjPts', ascending=False)
        rep_val = pos_pool.iloc[rank-1]['ProjPts'] if len(pos_pool) >= rank else (pos_pool.iloc[-1]['ProjPts'] if len(pos_pool) > 0 else 0)
        df_calc.loc[df_calc['Pos'] == pos, 'VORP'] = round(df_calc['ProjPts'] - rep_val, 1)
    return df_calc

# 3. STATE INITIALIZATION
if 'drafted' not in st.session_state:
    st.session_state.drafted = []
if 'my_roster' not in st.session_state:
    st.session_state.my_roster = []
if 'current_pick' not in st.session_state:
    st.session_state.current_pick = 1

# Data Import Handler
st.sidebar.header("Data Sources")
uploaded = st.sidebar.file_uploader("Upload Projections CSV", type=["csv"])
if uploaded:
    raw_df = pd.read_csv(uploaded)
else:
    raw_df = fetch_live_player_pool()

available_df = raw_df[~raw_df['Name'].isin(st.session_state.drafted)].copy()
scored_df = compute_vorp(available_df)

# 4. SIDEBAR NAVIGATION
st.sidebar.markdown("---")
curr_round = ((st.session_state.current_pick - 1) // 10) + 1
st.sidebar.subheader(f"Round {curr_round} • Overall #{st.session_state.current_pick} / 160")

is_turn = st.session_state.current_pick in MY_PICKS
if is_turn:
    st.sidebar.success("🚨 **ON THE CLOCK (PICK NOW)**")
else:
    upcoming = [p for p in MY_PICKS if p > st.session_state.current_pick]
    if upcoming:
        st.sidebar.info(f"Picks until your turn: **{upcoming[0] - st.session_state.current_pick}** (#{upcoming[0]})")
    else:
        st.sidebar.success("🏁 Draft Complete!")

# Draft Input Form
with st.sidebar.form("pick_form"):
    chosen_player = st.selectbox("Select Picked Player:", scored_df['Name'].tolist() if not scored_df.empty else ["Empty"])
    my_pick = st.checkbox("Drafted to My Team", value=is_turn)
    btn_draft = st.form_submit_button("Record Pick")

    if btn_draft and not scored_df.empty:
        st.session_state.drafted.append(chosen_player)
        if my_pick:
            st.session_state.my_roster.append(chosen_player)
        st.session_state.current_pick += 1
        st.rerun()

if st.sidebar.button("Reset Entire Draft"):
    st.session_state.drafted = []
    st.session_state.my_roster = []
    st.session_state.current_pick = 1
    st.rerun()

# 5. MAIN BOARD & METRICS
st.title("Draft War Room — Slot 9 (10-Team Half-PPR)")

# Turn Gap calculation
is_short_gap = st.session_state.current_pick in [9, 29, 49, 69, 89, 109, 129, 149]
gap = 2 if is_short_gap else 16

c1, c2 = st.columns([3, 2])

with c1:
    st.subheader(f"Available Targets (Sorted by VORP • Next Gap: {gap} picks)")
    
    def assess_survival(adp, pick, g):
        cliff = (pick + g) - adp
        if cliff > 4:
            return "🔴 Gone before return"
        elif cliff >= -2:
            return "🟡 50/50 Survival"
        else:
            return "🟢 Safe to wait"

    display_df = scored_df.copy()
    display_df['Turn Risk'] = display_df['ADP'].apply(lambda x: assess_survival(x, st.session_state.current_pick, gap))
    
    st.dataframe(
        display_df[['Name', 'Pos', 'Team', 'ProjPts', 'VORP', 'ADP', 'Turn Risk', 'Status', 'Notes']]
        .sort_values(by='VORP', ascending=False),
        use_container_width=True,
        hide_index=True
    )

with c2:
    st.subheader(f"My Roster ({len(st.session_state.my_roster)}/16 + 1 IR)")
    if st.session_state.my_roster:
        roster_view = raw_df[raw_df['Name'].isin(st.session_state.my_roster)]
        st.dataframe(roster_view[['Name', 'Pos', 'Team', 'ProjPts', 'Status']], use_container_width=True, hide_index=True)
        st.metric("Total Projected Points", f"{roster_view['ProjPts'].sum():.1f}")
    else:
        st.info("No players drafted yet.")

    st.markdown("---")
    st.subheader("Positional Run Tracker")
    for p in ['RB', 'WR', 'TE', 'QB']:
        top_3 = scored_df[scored_df['Pos'] == p].head(3)
        if len(top_3) >= 2:
            drop = top_3.iloc[0]['VORP'] - top_3.iloc[-1]['VORP']
            st.caption(f"**{p} Tier Drop-off:** -{drop:.1f} VORP across next 3 available")