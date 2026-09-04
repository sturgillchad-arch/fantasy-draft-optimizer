import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(
    page_title="War Room Terminal • Draft Optimizer",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 1. MODERN TERMINAL CSS INJECTION
st.markdown("""
<style>
    .metric-card {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 8px;
    }
    .hud-title {
        color: #9ca3af;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
        font-weight: 600;
    }
    .hud-value {
        color: #f9fafb;
        font-size: 1.3rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .hud-sub {
        color: #10b981;
        font-size: 0.75rem;
        font-weight: 500;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 6px 14px;
        font-size: 0.85rem;
        border-radius: 6px 6px 0 0;
    }
    thead tr th {
        font-size: 0.78rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.03em !important;
    }
</style>
""", unsafe_allow_html=True)

# 2. STATE MANAGEMENT
if 'draft_history' not in st.session_state:
    st.session_state.draft_history = []
if 'my_roster' not in st.session_state:
    st.session_state.my_roster = []
if 'my_ir' not in st.session_state:
    st.session_state.my_ir = []
if 'current_pick' not in st.session_state:
    st.session_state.current_pick = 1
if 'practice_mode' not in st.session_state:
    st.session_state.practice_mode = False
if 'auto_advance' not in st.session_state:
    st.session_state.auto_advance = True

# 3. SIDEBAR CONFIGURATION (ACCORDIONS)
with st.sidebar.expander("⚙️ League Settings", expanded=False):
    num_teams = st.number_input("League Size (Teams):", 6, 16, 10, 1)
    total_rounds = st.number_input("Total Rounds:", 10, 25, 16, 1)
    my_slot = st.selectbox("Draft Position:", list(range(1, num_teams + 1)), index=min(8, num_teams - 1))
    top_n = st.slider("Top Recommendations Count:", 5, 10, 6)

with st.sidebar.expander("🎮 Practice Draft Simulation", expanded=True):
    practice_toggle = st.toggle("Enable Practice Mode", value=st.session_state.practice_mode)
    st.session_state.practice_mode = practice_toggle
    auto_adv_toggle = st.toggle("Auto-Fast-Forward to My Pick", value=st.session_state.auto_advance,
                                help="When enabled, opponents auto-pick immediately after you confirm your turn.")
    st.session_state.auto_advance = auto_adv_toggle
    ai_randomness = st.select_slider(
        "AI Draft Tendencies:",
        options=["Strict ADP", "Realistic Variance", "Chaotic Reach"],
        value="Realistic Variance",
        help="Controls how strictly simulated opponents draft according to consensus ADP."
    )

with st.sidebar.expander("📂 Data Feeds & Backup", expanded=False):
    uploaded = st.file_uploader("Upload Projections CSV", type=["csv"])
    if st.button("Reset Entire Draft Board", type="secondary"):
        st.session_state.draft_history = []
        st.session_state.my_roster = []
        st.session_state.my_ir = []
        st.session_state.current_pick = 1
        st.rerun()

TOTAL_PICKS = num_teams * total_rounds

# Generate dynamic snake pick schedule
def generate_my_picks(slot, teams, rounds):
    picks = []
    for r in range(rounds):
        if r % 2 == 0:
            p = (r * teams) + slot
        else:
            p = (r * teams) + (teams - slot + 1)
        picks.append(p)
    return picks

my_picks = generate_my_picks(my_slot, num_teams, total_rounds)
BASELINES = {'QB': num_teams, 'RB': int(num_teams * 3.0), 'WR': int(num_teams * 3.0), 'TE': num_teams, 'DST': num_teams, 'K': num_teams}

# 4. DATA ENGINE (Sleeper Public API)
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
        return pd.DataFrame(pool).sort_values(by="ADP").reset_index(drop=True)
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

raw_df = pd.read_csv(uploaded) if uploaded else fetch_player_pool()

# 5. AI BOT SIMULATION FUNCTION
def simulate_bot_picks(target_pick):
    scale_dict = {"Strict ADP": 0.8, "Realistic Variance": 3.0, "Chaotic Reach": 6.5}
    curr_scale = scale_dict.get(ai_randomness, 3.0)
    
    while st.session_state.current_pick < target_pick and st.session_state.current_pick <= TOTAL_PICKS:
        p_idx = st.session_state.current_pick
        d_names = [d['name'] for d in st.session_state.draft_history]
        pool = raw_df[~raw_df['Name'].isin(d_names)].copy()
        
        if pool.empty:
            break
            
        pool['sim_val'] = pool['ADP'] + np.random.normal(0, curr_scale, size=len(pool))
        bot_choice = pool.sort_values(by='sim_val').iloc[0]
        
        st.session_state.draft_history.append({
            'pick': p_idx,
            'name': bot_choice['Name'],
            'pos': bot_choice['Pos'],
            'team': bot_choice['Team'],
            'is_mine': False,
            'is_ir': False
        })
        st.session_state.current_pick += 1

# Auto-advance bots at the start of draft if needed
if st.session_state.practice_mode and st.session_state.auto_advance and st.session_state.current_pick not in my_picks and st.session_state.current_pick <= TOTAL_PICKS:
    next_user_pick = [p for p in my_picks if p >= st.session_state.current_pick]
    target = next_user_pick[0] if next_user_pick else TOTAL_PICKS + 1
    simulate_bot_picks(target)

drafted_names = [d['name'] for d in st.session_state.draft_history]

# 6. DYNAMIC VORP ENGINE
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

# 7. TURN CADENCE & SIMULATION
curr_p = st.session_state.current_pick
is_turn = curr_p in my_picks

if is_turn:
    curr_idx = my_picks.index(curr_p)
    gap = (my_picks[curr_idx + 1] - curr_p) if curr_idx < len(my_picks) - 1 else 0
else:
    upcoming = [p for p in my_picks if p > curr_p]
    gap = (upcoming[0] - curr_p) if upcoming else 0

def simulate_survival(adp, current_pick, target_gap, n_sims=300):
    simulated_picks = np.random.normal(loc=adp, scale=4.0, size=n_sims)
    threshold = current_pick + max(target_gap, 1)
    return int(round((np.sum(simulated_picks > threshold) / n_sims) * 100, 0))

scored_df['Survival %'] = scored_df['ADP'].apply(lambda x: simulate_survival(x, curr_p, gap))

def strategy_tag(row):
    if row['Survival %'] >= 80:
        return "⏳ Safe to Wait"
    elif row['Survival %'] <= 25:
        return "⚡ Draft Now"
    return "⚖️ Moderate"

scored_df['Action'] = scored_df.apply(strategy_tag, axis=1)

# 8. EXECUTIVE HUD
curr_round = ((curr_p - 1) // num_teams) + 1
next_picks = [p for p in my_picks if p >= curr_p]

h1, h2, h3, h4 = st.columns([1.2, 1.4, 1.6, 1.8])

with h1:
    mode_label = "🎮 PRACTICE (AUTO-ADV)" if (st.session_state.practice_mode and st.session_state.auto_advance) else ("🎮 PRACTICE" if st.session_state.practice_mode else "LIVE WAR ROOM")
    st.markdown(f"""
    <div class="metric-card">
        <div class="hud-title">{mode_label}</div>
        <div class="hud-value">R{curr_round} • P#{curr_p}</div>
        <div class="hud-sub">{TOTAL_PICKS - curr_p + 1} picks remaining</div>
    </div>
    """, unsafe_allow_html=True)

with h2:
    status_text = "🚨 ON THE CLOCK" if is_turn else f"In Queue ({gap} picks away)"
    status_color = "#ef4444" if is_turn else "#3b82f6"
    st.markdown(f"""
    <div class="metric-card">
        <div class="hud-title">Clock Status</div>
        <div class="hud-value" style="color: {status_color};">{status_text}</div>
        <div class="hud-sub">Position: Slot {my_slot}</div>
    </div>
    """, unsafe_allow_html=True)

with h3:
    if len(next_picks) >= 2:
        flow_text = f"#{next_picks[0]} ➔ #{next_picks[1]}"
        sub_text = f"Turn Gap: {next_picks[1] - next_picks[0]} picks"
    elif len(next_picks) == 1:
        flow_text = f"Final Pick: #{next_picks[0]}"
        sub_text = "Draft Wrap-Up"
    else:
        flow_text = "Draft Completed"
        sub_text = "All rounds logged"

    st.markdown(f"""
    <div class="metric-card">
        <div class="hud-title">Turn Package Rhythm</div>
        <div class="hud-value">{flow_text}</div>
        <div class="hud-sub">{sub_text}</div>
    </div>
    """, unsafe_allow_html=True)

with h4:
    team_roster_count = len(st.session_state.my_roster)
    ir_count = len(st.session_state.my_ir)
    st.markdown(f"""
    <div class="metric-card">
        <div class="hud-title">Roster Allocation</div>
        <div class="hud-value">{team_roster_count}/{total_rounds} Active <span style="font-size:0.9rem; color:#9ca3af;">(+{ir_count} IR)</span></div>
        <div class="hud-sub">{(total_rounds - team_roster_count)} open spots</div>
    </div>
    """, unsafe_allow_html=True)

# 9. IN-LINE ACTION CONSOLE
with st.container():
    act_col1, act_col2, act_col3, act_col4, act_col5 = st.columns([2.8, 1.1, 1.0, 1.3, 0.9])
    with act_col1:
        selected_player = st.selectbox(
            "Quick Log Draft Pick:",
            options=scored_df['Name'].tolist() if not scored_df.empty else ["Pool Empty"],
            label_visibility="collapsed",
            help="Search and log any drafted player."
        )
    with act_col2:
        mine = st.checkbox("Draft to My Team", value=is_turn)
    with act_col3:
        send_to_ir = st.checkbox("Send to IR", value=False)
    with act_col4:
        if st.button("Confirm Pick ↵", type="primary", use_container_width=True):
            if not scored_df.empty:
                match = raw_df[raw_df['Name'] == selected_player]
                p_pos = match.iloc[0]['Pos'] if not match.empty else "FLEX"
                p_team = match.iloc[0]['Team'] if not match.empty else ""

                st.session_state.draft_history.append({
                    'pick': curr_p,
                    'name': selected_player,
                    'pos': p_pos,
                    'team': p_team,
                    'is_mine': mine,
                    'is_ir': (mine and send_to_ir and len(st.session_state.my_ir) == 0)
                })

                if mine:
                    if send_to_ir and len(st.session_state.my_ir) == 0:
                        st.session_state.my_ir.append(selected_player)
                    else:
                        st.session_state.my_roster.append(selected_player)
                
                st.session_state.current_pick += 1
                
                # AUTO-ADVANCE TRIGGER: Fast-forward bots automatically to your next turn
                if st.session_state.practice_mode and st.session_state.auto_advance:
                    next_user_pick = [p for p in my_picks if p >= st.session_state.current_pick]
                    if next_user_pick:
                        simulate_bot_picks(next_user_pick[0])
                    else:
                        simulate_bot_picks(TOTAL_PICKS + 1)
                        
                st.rerun()

    with act_col5:
        if st.button("↩ Undo", help="Revert the last pick logged (or user pick in practice mode)", use_container_width=True):
            if st.session_state.draft_history:
                if st.session_state.practice_mode and st.session_state.auto_advance:
                    # Pop bot picks until we undo the user's pick
                    while st.session_state.draft_history:
                        last = st.session_state.draft_history.pop()
                        st.session_state.current_pick = max(1, st.session_state.current_pick - 1)
                        if last['is_mine']:
                            p_name = last['name']
                            if last['is_ir'] and p_name in st.session_state.my_ir:
                                st.session_state.my_ir.remove(p_name)
                            elif p_name in st.session_state.my_roster:
                                st.session_state.my_roster.remove(p_name)
                            break
                else:
                    last_pick = st.session_state.draft_history.pop()
                    p_name = last_pick['name']
                    if last_pick['is_mine']:
                        if last_pick['is_ir'] and p_name in st.session_state.my_ir:
                            st.session_state.my_ir.remove(p_name)
                        elif p_name in st.session_state.my_roster:
                            st.session_state.my_roster.remove(p_name)
                    st.session_state.current_pick = max(1, st.session_state.current_pick - 1)
                st.rerun()

st.markdown("---")

# 10. TERMINAL SPLIT: WORKSPACE & ROSTER
c_board, c_roster = st.columns([3.1, 1.9])

TABLE_CONFIG = {
    "Name": st.column_config.TextColumn("Player"),
    "Pos": st.column_config.TextColumn("Pos", width="small"),
    "Team": st.column_config.TextColumn("NFL", width="small"),
    "ProjPts": st.column_config.NumberColumn("Proj", format="%.1f"),
    "VORP": st.column_config.NumberColumn("VORP", format="%.1f"),
    "ADP": st.column_config.NumberColumn("ADP", format="%.0f"),
    "Survival %": st.column_config.ProgressColumn("Survival Odds", format="%d%%", min_value=0, max_value=100),
    "Action": st.column_config.TextColumn("Verdict", width="small"),
    "Status Badge": st.column_config.TextColumn("Health", width="small"),
    "Notes": st.column_config.TextColumn("Report")
}

def format_status_badge(val):
    if val in ["IR", "Out", "Suspended"]:
        return f"🚨 {val}"
    elif val in ["Questionable", "Doubtful", "PUP"]:
        return f"⚠️ {val}"
    return "✅ Healthy"

display_scored = scored_df.copy()
display_scored['Status Badge'] = display_scored['Status'].apply(format_status_badge)

with c_board:
    st.markdown(f"##### 🎯 Priority Targets Available Now (Top {top_n})")
    priority_pool = display_scored[~display_scored['Pos'].isin(['K', 'DST'])].sort_values(
        by=['VORP', 'ADP'], ascending=[False, True]
    ).head(top_n)

    st.dataframe(
        priority_pool[['Name', 'Pos', 'Team', 'ProjPts', 'VORP', 'ADP', 'Survival %', 'Action', 'Status Badge']],
        use_container_width=True,
        hide_index=True,
        column_config=TABLE_CONFIG
    )

    tab_board, tab_all, tab_rb, tab_wr, tab_te, tab_qb, tab_dst_k, tab_injury = st.tabs(
        ["📋 Visual Grid", "🔥 All VORP", "🏃 RB", "🙌 WR", "🧱 TE", "🎯 QB", "🛡️ D/ST & K", "🏥 IR Hub"]
    )

    def render_pos_table(df_sub):
        st.dataframe(
            df_sub[['Name', 'Pos', 'Team', 'ProjPts', 'VORP', 'ADP', 'Survival %', 'Action', 'Status Badge', 'Notes']]
            .sort_values(by=['VORP', 'ADP'], ascending=[False, True]),
            use_container_width=True,
            hide_index=True,
            column_config=TABLE_CONFIG
        )

    with tab_board:
        grid_data = {f"Team {i+1}": ["—"] * total_rounds for i in range(num_teams)}
        for item in st.session_state.draft_history:
            p_num = item['pick']
            r_idx = (p_num - 1) // num_teams
            p_in_round = (p_num - 1) % num_teams
            col_idx = p_in_round if (r_idx % 2 == 0) else (num_teams - 1 - p_in_round)
            col_name = f"Team {col_idx + 1}"
            grid_data[col_name][r_idx] = f"{item['name']} ({item['pos']})"

        board_df = pd.DataFrame(grid_data, index=[f"R{r+1}" for r in range(total_rounds)])

        def style_draft_grid(val):
            if "—" in val:
                return "color: #4b5563; background-color: #0f172a;"
            if "(RB)" in val:
                return "background-color: #1e3a8a; color: #bfdbfe; font-weight: 600;"
            if "(WR)" in val:
                return "background-color: #064e3b; color: #a7f3d0; font-weight: 600;"
            if "(QB)" in val:
                return "background-color: #7c2d12; color: #fed7aa; font-weight: 600;"
            if "(TE)" in val:
                return "background-color: #713f12; color: #fef08a; font-weight: 600;"
            return "background-color: #374151; color: #f3f4f6;"

        try:
            styled_board = board_df.style.map(style_draft_grid)
        except AttributeError:
            styled_board = board_df.style.applymap(style_draft_grid)

        st.dataframe(styled_board, use_container_width=True, height=460)

    with tab_all:
        render_pos_table(display_scored[~display_scored['Pos'].isin(['K', 'DST'])])
    with tab_rb:
        render_pos_table(display_scored[display_scored['Pos'] == 'RB'])
    with tab_wr:
        render_pos_table(display_scored[display_scored['Pos'] == 'WR'])
    with tab_te:
        render_pos_table(display_scored[display_scored['Pos'] == 'TE'])
    with tab_qb:
        render_pos_table(display_scored[display_scored['Pos'] == 'QB'])
    with tab_dst_k:
        render_pos_table(display_scored[display_scored['Pos'].isin(['DST', 'K'])])
    with tab_injury:
        injured_only = display_scored[display_scored['Status'] != 'Healthy']
        st.dataframe(
            injured_only[['Name', 'Pos', 'Team', 'ADP', 'Status', 'Notes']].sort_values(by='ADP'),
            use_container_width=True,
            hide_index=True,
            column_config=TABLE_CONFIG
        )

with c_roster:
    st.markdown("##### 🛡️ Lineup Depth Chart")
    
    roster_pool = raw_df[raw_df['Name'].isin(st.session_state.my_roster)].copy()
    
    def get_slot_assignment(pos, taken_slots):
        return [p for p in roster_pool[roster_pool['Pos'] == pos]['Name'].tolist() if p not in taken_slots]

    taken = []
    qb = (get_slot_assignment('QB', taken) + ["—"])[0]
    taken.append(qb)
    
    rbs = get_slot_assignment('RB', taken)
    rb1 = rbs[0] if len(rbs) > 0 else "—"
    rb2 = rbs[1] if len(rbs) > 1 else "—"
    taken.extend([rb1, rb2])
    
    wrs = get_slot_assignment('WR', taken)
    wr1 = wrs[0] if len(wrs) > 0 else "—"
    wr2 = wrs[1] if len(wrs) > 1 else "—"
    taken.extend([wr1, wr2])
    
    te = (get_slot_assignment('TE', taken) + ["—"])[0]
    taken.append(te)
    
    flex_candidates = [p for p in roster_pool[roster_pool['Pos'].isin(['RB', 'WR', 'TE'])]['Name'].tolist() if p not in taken and p != "—"]
    flex = flex_candidates[0] if flex_candidates else "—"
    taken.append(flex)
    
    dst = (get_slot_assignment('DST', taken) + ["—"])[0]
    taken.append(dst)
    
    k = (get_slot_assignment('K', taken) + ["—"])[0]
    taken.append(k)
    
    bench = [p for p in roster_pool['Name'].tolist() if p not in taken and p != "—"]
    
    starter_df = pd.DataFrame([
        {"Slot": "QB", "Player": qb},
        {"Slot": "RB1", "Player": rb1},
        {"Slot": "RB2", "Player": rb2},
        {"Slot": "WR1", "Player": wr1},
        {"Slot": "WR2", "Player": wr2},
        {"Slot": "TE", "Player": te},
        {"Slot": "FLEX", "Player": flex},
        {"Slot": "D/ST", "Player": dst},
        {"Slot": "K", "Player": k},
    ])

    st.dataframe(starter_df, use_container_width=True, hide_index=True)

    if bench:
        st.caption(f"**Bench ({len(bench)}):** " + ", ".join(bench))
    else:
        st.caption("**Bench:** No reserves yet.")

    if st.session_state.my_ir:
        st.markdown(f"🏥 **IR Slot:** {', '.join(st.session_state.my_ir)}")

    st.markdown("---")
    st.markdown("##### ⚡ Tier Scarcity Cliff")
    cliff_cols = st.columns(4)
    for i, p in enumerate(['RB', 'WR', 'TE', 'QB']):
        top_tier = scored_df[scored_df['Pos'] == p].head(3)
        cliff_val = (top_tier.iloc[0]['VORP'] - top_tier.iloc[-1]['VORP']) if len(top_tier) >= 2 else 0.0
        with cliff_cols[i]:
            st.metric(label=f"{p} Cliff", value=f"-{cliff_val:.1f}")