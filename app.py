import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="Draft Optimizer (Slot 9)", layout="wide")

# 1. LEAGUE CONFIGURATION
NUM_TEAMS = 10
TOTAL_ROUNDS = 16
MY_SLOT = 9

MY_PICKS = [9, 12, 29, 32, 49, 52, 69, 72, 89, 92, 109, 112, 129, 132, 149, 152]
STARTER_LIMITS = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'DST': 1, 'K': 1, 'FLEX': 1}
BASELINES = {'QB': 10, 'RB': 30, 'WR': 30, 'TE': 10, 'DST': 10, 'K': 10}

# 2. DATA FETCHER (Sleeper Public API with Fallback)
@st.cache_data(ttl=3600)
def fetch_player_pool():
    try:
        url = "https://api.sleeper.app/v1/players/nfl"
        res = requests.get(url, timeout=12).json()
        pool = []
        for p_id, p in res.items():
            if p.get("active") and p.get("position") in ['QB', 'RB', 'WR', 'TE', 'DEF', 'K']:
                pos = 'DST' if p.get('position') == 'DEF' else p.get('position')
                rank = float(p.get('search_rank') or 999)
                
                # Baseline scoring curves
                if pos == 'QB':
                    proj = max(380.0 - (rank * 1.8), 120.0)
                elif pos in ['RB', 'WR']:
                    proj = max(295.0 - (rank * 1.3), 35.0)
                elif pos == 'TE':
                    proj = max(215.0 - (rank * 1.4), 25.0)
                elif pos == 'K':
                    proj = max(135.0 - (rank * 0.15), 90.0)
                else:
                    proj = max(125.0 - (rank * 0.15), 75.0)
                    
                pool.append({
                    "Name": p.get("full_name") or f"{p.get('first_name')} {p.get('last_name')}",
                    "Pos": pos,
                    "Team": p.get("team") or "FA",
                    "ADP": rank,
                    "ProjPts": round(proj, 1),
                    "Status": p.get("injury_status") or "Healthy",
                    "Notes": p.get("injury_notes") or "Active"
                })
        df = pd.DataFrame(pool).sort_values(by="ADP").reset_index(drop=True)
        return df
    except Exception:
        data = [
            {"Name": "Jahmyr Gibbs", "Pos": "RB", "Team": "DET", "ADP": 1.0, "ProjPts": 330.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Bijan Robinson", "Pos": "RB", "Team": "ATL", "ADP": 2.0, "ProjPts": 314.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Ja'Marr Chase", "Pos": "WR", "Team": "CIN", "ADP": 3.0, "ProjPts": 277.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Puka Nacua", "Pos": "WR", "Team": "LAR", "ADP": 4.0, "ProjPts": 275.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Jonathan Taylor", "Pos": "RB", "Team": "IND", "ADP": 6.0, "ProjPts": 265.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Amon-Ra St. Brown", "Pos": "WR", "Team": "DET", "ADP": 8.0, "ProjPts": 270.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "A.J. Brown", "Pos": "WR", "Team": "PHI", "ADP": 10.0, "ProjPts": 255.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Saquon Barkley", "Pos": "RB", "Team": "PHI", "ADP": 11.0, "ProjPts": 256.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Brock Bowers", "Pos": "TE", "Team": "LV", "ADP": 20.0, "ProjPts": 210.0, "Status": "Healthy", "Notes": "Active"},
            {"Name": "Josh Allen", "Pos": "QB", "Team": "BUF", "ADP": 22.0, "ProjPts": 375.0, "Status": "Healthy", "Notes": "Active"},
        ]
        return pd.DataFrame(data)

# 3. STATE INITIALIZATION
if 'draft_history' not in st.session_state:
    st.session_state.draft_history = []  # Stores list of dicts: {'pick': N, 'name': str, 'pos': str, 'team': str}
if 'my_roster' not in st.session_state:
    st.session_state.my_roster = []
if 'my_ir' not in st.session_state:
    st.session_state.my_ir = []
if 'current_pick' not in st.session_state:
    st.session_state.current_pick = 1

# Load Data
st.sidebar.header("Data Feeds")
uploaded = st.sidebar.file_uploader("Upload Projections CSV (Optional)", type=["csv"])
if uploaded:
    raw_df = pd.read_csv(uploaded)
else:
    raw_df = fetch_player_pool()

drafted_names = [d['name'] for d in st.session_state.draft_history]

# 4. VORP ENGINE
def calculate_dynamic_vorp(df, my_roster_names):
    df_calc = df.copy()
    my_players = df_calc[df_calc['Name'].isin(my_roster_names)]
    qb_count = len(my_players[my_players['Pos'] == 'QB'])
    te_count = len(my_players[my_players['Pos'] == 'TE'])
    
    for pos, rank in BASELINES.items():
        pos_pool = df_calc[df_calc['Pos'] == pos].sort_values(by='ProjPts', ascending=False)
        rep_val = pos_pool.iloc[rank-1]['ProjPts'] if len(pos_pool) >= rank else (pos_pool.iloc[-1]['ProjPts'] if len(pos_pool) > 0 else 0)
        df_calc.loc[df_calc['Pos'] == pos, 'VORP'] = round(df_calc['ProjPts'] - rep_val, 1)

    if qb_count >= 1:
        df_calc.loc[df_calc['Pos'] == 'QB', 'VORP'] = round(df_calc['VORP'] * 0.4, 1)
    if te_count >= 1:
        df_calc.loc[df_calc['Pos'] == 'TE', 'VORP'] = round(df_calc['VORP'] * 0.4, 1)
    df_calc.loc[df_calc['Pos'].isin(['K', 'DST']), 'VORP'] = round(df_calc['VORP'] * 0.2, 1)

    return df_calc

available_df = raw_df[~raw_df['Name'].isin(drafted_names)].copy()
scored_df = calculate_dynamic_vorp(available_df, st.session_state.my_roster)

# 5. TURN GAP & MONTE CARLO
curr_p = st.session_state.current_pick
is_turn = curr_p in MY_PICKS

if is_turn:
    idx = MY_PICKS.index(curr_p)
    gap = 2 if (idx % 2 == 0) else 16
else:
    upcoming = [p for p in MY_PICKS if p > curr_p]
    gap = (upcoming[0] - curr_p) if upcoming else 0

def simulate_survival(adp, current_pick, target_gap, n_sims=300):
    simulated_picks = np.random.normal(loc=adp, scale=4.0, size=n_sims)
    threshold = current_pick + max(target_gap, 1)
    survived = np.sum(simulated_picks > threshold)
    return int(round((survived / n_sims) * 100, 0))

scored_df['Survival %'] = scored_df['ADP'].apply(lambda x: simulate_survival(x, curr_p, gap))

# 6. SIDEBAR CONTROLS
st.sidebar.markdown("---")
curr_round = ((curr_p - 1) // 10) + 1
st.sidebar.subheader(f"Round {curr_round} • Pick #{curr_p} / 160")

if is_turn:
    st.sidebar.success("🚨 **YOU ARE ON THE CLOCK**")
else:
    upcoming = [p for p in MY_PICKS if p > curr_p]
    if upcoming:
        st.sidebar.info(f"Picks until next turn: **{upcoming[0] - curr_p}** (Pick #{upcoming[0]})")
    else:
        st.sidebar.success("Draft Complete!")

with st.sidebar.form("draft_action_form"):
    selected_player = st.selectbox("Record Draft Pick:", scored_df['Name'].tolist() if not scored_df.empty else ["Pool Empty"])
    mine = st.checkbox("Drafted to My Team", value=is_turn)
    send_to_ir = st.checkbox("Direct to IR Slot", value=False)
    btn_submit = st.form_submit_button("Confirm Pick")

    if btn_submit and not scored_df.empty:
        # Look up player details
        match = raw_df[raw_df['Name'] == selected_player]
        p_pos = match.iloc[0]['Pos'] if not match.empty else "FLEX"
        p_team = match.iloc[0]['Team'] if not match.empty else ""

        st.session_state.draft_history.append({
            'pick': curr_p,
            'name': selected_player,
            'pos': p_pos,
            'team': p_team,
            'is_mine': mine
        })

        if mine:
            if send_to_ir and len(st.session_state.my_ir) == 0:
                st.session_state.my_ir.append(selected_player)
            else:
                st.session_state.my_roster.append(selected_player)
        st.session_state.current_pick += 1
        st.rerun()

if st.sidebar.button("Reset Draft Board"):
    st.session_state.draft_history = []
    st.session_state.my_roster = []
    st.session_state.my_ir = []
    st.session_state.current_pick = 1
    st.rerun()

# 7. MAIN INTERFACE
st.title("Draft War Room — Slot 9 (10-Team Half-PPR)")

c_main, c_team = st.columns([3, 2])

with c_main:
    tab_board, tab_all, tab_rb, tab_wr, tab_te, tab_qb, tab_dst_k, tab_injury = st.tabs(
        ["📋 Draft Board", "🔥 Best VORP", "🏃 Running Backs", "🙌 Wide Receivers", "🧱 Tight Ends", "🎯 Quarterbacks", "🛡️ D/ST & K", "🏥 Injury Hub"]
    )

    # VISUAL DRAFT BOARD BUILDER
    with tab_board:
        # Build 16-round x 10-team snake grid
        grid_data = {f"Team {i+1}": ["—"] * TOTAL_ROUNDS for i in range(NUM_TEAMS)}
        
        # Populate drafted picks
        for item in st.session_state.draft_history:
            p_num = item['pick']
            r_idx = (p_num - 1) // NUM_TEAMS
            p_in_round = (p_num - 1) % NUM_TEAMS
            
            # Snake routing: Even rounds (0, 2, 4...) 1->10; Odd rounds (1, 3, 5...) 10->1
            col_idx = p_in_round if (r_idx % 2 == 0) else (NUM_TEAMS - 1 - p_in_round)
            col_name = f"Team {col_idx + 1}"
            grid_data[col_name][r_idx] = f"{item['name']} ({item['pos']})"

        board_df = pd.DataFrame(grid_data, index=[f"Round {r+1}" for r in range(TOTAL_ROUNDS)])

        # Highlighting Slot 9 & Positional Styling
        def style_draft_grid(val):
            if "—" in val:
                return "color: #555; background-color: #111;"
            if "(RB)" in val:
                return "background-color: #1e3a5f; color: #a5d8ff; font-weight: bold;"
            if "(WR)" in val:
                return "background-color: #1a4329; color: #b2f2bb; font-weight: bold;"
            if "(QB)" in val:
                return "background-color: #5c2c16; color: #ffc9c9; font-weight: bold;"
            if "(TE)" in val:
                return "background-color: #4f3a12; color: #ffec99; font-weight: bold;"
            return "background-color: #2b2b2b; color: #fff;"

        try:
    styled_board = board_df.style.map(style_draft_grid)
except AttributeError:
    styled_board = board_df.style.applymap(style_draft_grid)
        st.dataframe(styled_board, use_container_width=True, height=520)

    def format_status_badge(val):
        if val in ["IR", "Out", "Suspended"]:
            return f"🚨 {val}"
        elif val in ["Questionable", "Doubtful", "PUP"]:
            return f"⚠️ {val}"
        return "✅ Healthy"

    display_scored = scored_df.copy()
    display_scored['Status Badge'] = display_scored['Status'].apply(format_status_badge)

    def render_position_table(df_subset):
        st.dataframe(
            df_subset[['Name', 'Pos', 'Team', 'ProjPts', 'VORP', 'ADP', 'Survival %', 'Status Badge', 'Notes']]
            .sort_values(by=['VORP', 'ADP'], ascending=[False, True]),
            use_container_width=True,
            hide_index=True
        )

    with tab_all:
        render_position_table(display_scored[~display_scored['Pos'].isin(['K', 'DST'])])
    with tab_rb:
        render_position_table(display_scored[display_scored['Pos'] == 'RB'])
    with tab_wr:
        render_position_table(display_scored[display_scored['Pos'] == 'WR'])
    with tab_te:
        render_position_table(display_scored[display_scored['Pos'] == 'TE'])
    with tab_qb:
        render_position_table(display_scored[display_scored['Pos'] == 'QB'])
    with tab_dst_k:
        render_position_table(display_scored[display_scored['Pos'].isin(['DST', 'K'])])
    with tab_injury:
        injured_only = display_scored[display_scored['Status'] != 'Healthy']
        st.caption("Target late-round injured players here to draft directly into your IR spot.")
        st.dataframe(
            injured_only[['Name', 'Pos', 'Team', 'ADP', 'Status', 'Notes']].sort_values(by='ADP'),
            use_container_width=True,
            hide_index=True
        )

with c_team:
    st.subheader(f"My Team ({len(st.session_state.my_roster)}/16 Active + {len(st.session_state.my_ir)}/1 IR)")
    
    if st.session_state.my_roster:
        team_df = raw_df[raw_df['Name'].isin(st.session_state.my_roster)]
        st.dataframe(team_df[['Name', 'Pos', 'Team', 'ProjPts', 'Status']], use_container_width=True, hide_index=True)
        st.metric("Total Projected Starter Output", f"{team_df['ProjPts'].sum():.1f} pts")
    else:
        st.info("No active selections yet.")

    if st.session_state.my_ir:
        st.markdown("#### 🏥 IR Slot")
        ir_df = raw_df[raw_df['Name'].isin(st.session_state.my_ir)]
        st.dataframe(ir_df[['Name', 'Pos', 'Team', 'Status', 'Notes']], use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Tier Scarcity Monitor")
    for p in ['RB', 'WR', 'TE', 'QB']:
        top_tier = scored_df[scored_df['Pos'] == p].head(3)
        if len(top_tier) >= 2:
            drop = top_tier.iloc[0]['VORP'] - top_tier.iloc[-1]['VORP']
            st.caption(f"**{p} Scarcity Cliff:** -{drop:.1f} VORP across top 3 available")