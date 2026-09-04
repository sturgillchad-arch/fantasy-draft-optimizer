import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import requests

st.set_page_config(
    page_title="War Room Terminal • Draft Optimizer",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 1. ADAPTIVE LIGHT/DARK DUAL-THEME TERMINAL CSS
st.markdown("""
<style>
    :root {
        --war-bg-card: #ffffff;
        --war-border: #cbd5e1;
        --war-border-darker: #94a3b8;
        --war-text-main: #0f172a;
        --war-text-sub: #475569;
        --war-subtle-bg: #f8fafc;
        --war-row-hover: #e2e8f0;
    }

    @media (prefers-color-scheme: dark) {
        :root {
            --war-bg-card: #111827;
            --war-border: #1f2937;
            --war-border-darker: #374151;
            --war-text-main: #f9fafb;
            --war-text-sub: #9ca3af;
            --war-subtle-bg: #1f2937;
            --war-row-hover: #1e293b;
        }
    }

    [data-theme="light"] {
        --war-bg-card: #ffffff;
        --war-border: #cbd5e1;
        --war-border-darker: #94a3b8;
        --war-text-main: #0f172a;
        --war-text-sub: #475569;
        --war-subtle-bg: #f8fafc;
        --war-row-hover: #e2e8f0;
    }

    [data-theme="dark"] {
        --war-bg-card: #111827;
        --war-border: #1f2937;
        --war-border-darker: #374151;
        --war-text-main: #f9fafb;
        --war-text-sub: #9ca3af;
        --war-subtle-bg: #1f2937;
        --war-row-hover: #1e293b;
    }

    .metric-card {
        background-color: var(--war-bg-card);
        border: 2px solid var(--war-border);
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .hud-title {
        color: var(--war-text-sub);
        font-size: 0.74rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
        font-weight: 700;
    }
    .hud-value {
        color: var(--war-text-main);
        font-size: 1.35rem;
        font-weight: 800;
        line-height: 1.2;
    }
    .hud-sub {
        color: #059669;
        font-size: 0.75rem;
        font-weight: 600;
    }

    .prio-row-container {
        background-color: var(--war-bg-card);
        border: 1px solid var(--war-border);
        border-radius: 6px;
        padding: 4px 10px;
        margin-bottom: 4px;
    }
    .prio-row-container:hover {
        background-color: var(--war-row-hover);
    }

    .stButton.sort-hdr > button {
        background: transparent !important;
        border: none !important;
        color: var(--war-text-sub) !important;
        font-size: 0.72rem !important;
        font-weight: 800 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.03em !important;
        padding: 4px 2px !important;
        box-shadow: none !important;
    }
    .stButton.sort-hdr > button:hover {
        color: #2563eb !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        border-bottom: 2px solid var(--war-border);
    }
    .stTabs [data-baseweb="tab"] {
        padding: 6px 16px;
        font-size: 0.88rem;
        font-weight: 700;
        border-radius: 6px 6px 0 0;
    }

    .badge-pos {
        font-size: 0.75rem;
        font-weight: 700;
        padding: 2px 7px;
        border-radius: 4px;
        letter-spacing: 0.02em;
    }
    .badge-rb { background-color: #2563eb; color: #ffffff; }
    .badge-wr { background-color: #059669; color: #ffffff; }
    .badge-qb { background-color: #ea580c; color: #ffffff; }
    .badge-te { background-color: #d97706; color: #ffffff; }
    .badge-other { background-color: #475569; color: #ffffff; }
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

if 'sort_col' not in st.session_state:
    st.session_state.sort_col = 'VORP'
if 'sort_asc' not in st.session_state:
    st.session_state.sort_asc = False

def set_sort(col, default_asc=False):
    if st.session_state.sort_col == col:
        st.session_state.sort_asc = not st.session_state.sort_asc
    else:
        st.session_state.sort_col = col
        st.session_state.sort_asc = default_asc

def reset_entire_board():
    st.session_state.draft_history = []
    st.session_state.my_roster = []
    st.session_state.my_ir = []
    st.session_state.current_pick = 1
    st.session_state.sort_col = 'VORP'
    st.session_state.sort_asc = False
    st.rerun()

# 3. ACTIVE NFL FRANCHISES LIST
NFL_TEAMS = {
    'ARI', 'ATL', 'BAL', 'BUF', 'CAR', 'CHI', 'CIN', 'CLE', 'DAL', 'DEN',
    'DET', 'GB', 'HOU', 'IND', 'JAX', 'KC', 'LV', 'LAC', 'LAR', 'MIA',
    'MIN', 'NE', 'NO', 'NYG', 'NYJ', 'PHI', 'PIT', 'SF', 'SEA', 'TB', 'TEN', 'WAS'
}

# 4. ROBUST DATA ENGINE (15-Min TTL + Granular Injury Mapping)
@st.cache_data(ttl=900)
def fetch_player_pool():
    try:
        url = "https://api.sleeper.app/v1/players/nfl"
        res = requests.get(url, timeout=12).json()
        pool = []
        for p_id, p in res.items():
            pos = 'DST' if p.get('position') == 'DEF' else p.get('position')
            team = p.get('team')
            rank = p.get('search_rank')
            is_active = p.get("active", False)

            if is_active and pos in ['QB', 'RB', 'WR', 'TE', 'DST', 'K'] and team in NFL_TEAMS and rank is not None and rank > 0:
                rank = float(rank)
                
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
                
                inj_status = p.get("injury_status") or "Healthy"
                inj_body = p.get("injury_body_part")
                inj_notes = p.get("injury_notes") or p.get("news_updated") or "Active"
                detailed_notes = f"{inj_body}: {inj_notes}" if inj_body else inj_notes

                pool.append({
                    "Name": p.get("full_name") or f"{p.get('first_name')} {p.get('last_name')}",
                    "Pos": pos,
                    "Team": team,
                    "ADP": rank,
                    "ProjPts": round(proj, 1),
                    "Status": inj_status,
                    "Notes": detailed_notes
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

# 5. SIDEBAR CONFIGURATION (ACCORDIONS)
with st.sidebar.expander("⏱️ Draft Clock & Audio Settings", expanded=False):
    clock_seconds = st.number_input("Clock Duration (Seconds):", min_value=15, max_value=300, value=60, step=5)
    enable_sound = st.toggle("Enable Audio Warnings", value=True, help="Plays countdown beeps at 10s and an alarm at 0s using Web Audio API.")

with st.sidebar.expander("⚙️ League Settings", expanded=False):
    num_teams = st.number_input("League Size (Teams):", 6, 16, 10, 1)
    total_rounds = st.number_input("Total Rounds:", 10, 25, 16, 1)
    my_slot = st.selectbox("Draft Position:", list(range(1, num_teams + 1)), index=min(8, num_teams - 1))

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
    
    if st.button("🔄 Sync Fresh NFL Wire Data", help="Clears cache and forces an immediate reload of player depth charts and injury wires."):
        fetch_player_pool.clear()
        st.rerun()

    if st.button("Reset Entire Draft Board", type="secondary"):
        reset_entire_board()

TOTAL_PICKS = num_teams * total_rounds

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

raw_df = pd.read_csv(uploaded) if uploaded else fetch_player_pool()

# 6. AI BOT SIMULATION FUNCTION
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

if st.session_state.practice_mode and st.session_state.auto_advance and st.session_state.current_pick not in my_picks and st.session_state.current_pick <= TOTAL_PICKS:
    next_user_pick = [p for p in my_picks if p >= st.session_state.current_pick]
    target = next_user_pick[0] if next_user_pick else TOTAL_PICKS + 1
    simulate_bot_picks(target)

drafted_names = [d['name'] for d in st.session_state.draft_history]

# 7. DYNAMIC VORP ENGINE
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

# 8. TURN CADENCE & SIMULATION
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
        return "⏳ Safe"
    elif row['Survival %'] <= 25:
        return "⚡ Draft"
    return "⚖️ Mid"

scored_df['Action'] = scored_df.apply(strategy_tag, axis=1)

def execute_pick(player_name, is_my_pick, stash_to_ir=False):
    match = raw_df[raw_df['Name'] == player_name]
    p_pos = match.iloc[0]['Pos'] if not match.empty else "FLEX"
    p_team = match.iloc[0]['Team'] if not match.empty else ""

    st.session_state.draft_history.append({
        'pick': st.session_state.current_pick,
        'name': player_name,
        'pos': p_pos,
        'team': p_team,
        'is_mine': is_my_pick,
        'is_ir': (is_my_pick and stash_to_ir and len(st.session_state.my_ir) == 0)
    })

    if is_my_pick:
        if stash_to_ir and len(st.session_state.my_ir) == 0:
            st.session_state.my_ir.append(player_name)
        else:
            st.session_state.my_roster.append(player_name)

    st.session_state.current_pick += 1

    if st.session_state.practice_mode and st.session_state.auto_advance:
        next_user_pick = [p for p in my_picks if p >= st.session_state.current_pick]
        if next_user_pick:
            simulate_bot_picks(next_user_pick[0])
        else:
            simulate_bot_picks(TOTAL_PICKS + 1)
    st.rerun()

# 9. EXECUTIVE HUD
curr_round = min(((curr_p - 1) // num_teams) + 1, total_rounds)
next_picks = [p for p in my_picks if p >= curr_p]

h1, h2, h3, h4 = st.columns([1.2, 1.4, 1.6, 1.8])

with h1:
    mode_label = "🎮 PRACTICE (AUTO-ADV)" if (st.session_state.practice_mode and st.session_state.auto_advance) else ("🎮 PRACTICE" if st.session_state.practice_mode else "LIVE WAR ROOM")
    remaining_picks = max(0, TOTAL_PICKS - curr_p + 1)
    st.markdown(f"""
    <div class="metric-card">
        <div class="hud-title">{mode_label}</div>
        <div class="hud-value">R{curr_round} • P#{min(curr_p, TOTAL_PICKS)}</div>
        <div class="hud-sub">{remaining_picks} picks remaining</div>
    </div>
    """, unsafe_allow_html=True)

with h2:
    if curr_p > TOTAL_PICKS:
        status_text = "🏁 DRAFT COMPLETED"
        status_color = "#059669"
    else:
        status_text = "🚨 ON THE CLOCK" if is_turn else f"In Queue ({gap} picks away)"
        status_color = "#dc2626" if is_turn else "#2563eb"
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
        <div class="hud-value">{team_roster_count}/{total_rounds} Active <span style="font-size:0.9rem; color: var(--war-text-sub);">(+{ir_count} IR)</span></div>
        <div class="hud-sub">{(total_rounds - team_roster_count)} open spots</div>
    </div>
    """, unsafe_allow_html=True)

# 10. DRAFT COUNTDOWN CLOCK COMPONENT (AUTO-RESETS ON ANY PICK)
clock_html = f"""
<div id="clock-container" data-pick="{curr_p}" style="
    background: var(--war-bg-card, #ffffff);
    border: 2px solid {'#dc2626' if is_turn else '#cbd5e1'};
    border-radius: 8px;
    padding: 10px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
">
    <div style="display: flex; align-items: center; gap: 14px;">
        <span style="font-size: 0.85rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; color: {'#dc2626' if is_turn else '#475569'};">
            {'🚨 ON THE CLOCK TIMER' if is_turn else '⏱️ DRAFT CLOCK'}
        </span>
        <div id="timer-display" style="
            font-size: 1.6rem;
            font-weight: 800;
            font-variant-numeric: tabular-nums;
            color: #059669;
            min-width: 70px;
        ">00:{clock_seconds:02d}</div>
    </div>
    <div style="display: flex; align-items: center; gap: 8px;">
        <button id="btn-toggle" onclick="toggleClock()" style="
            background: #2563eb;
            color: #ffffff;
            border: none;
            border-radius: 5px;
            padding: 6px 14px;
            font-size: 0.82rem;
            font-weight: 700;
            cursor: pointer;
        ">Pause</button>
        <button onclick="resetClock()" style="
            background: #64748b;
            color: #ffffff;
            border: none;
            border-radius: 5px;
            padding: 6px 14px;
            font-size: 0.82rem;
            font-weight: 700;
            cursor: pointer;
        ">Reset</button>
    </div>
</div>

<script>
    const currentPickInstance = {curr_p};
    let duration = {clock_seconds};
    let remaining = duration;
    let isRunning = true;
    let soundEnabled = {'true' if enable_sound else 'false'};
    let timerInterval = null;
    let audioCtx = null;

    function getAudioCtx() {{
        if (!audioCtx) {{
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            audioCtx = new AudioContext();
        }}
        if (audioCtx.state === 'suspended') {{
            audioCtx.resume();
        }}
        return audioCtx;
    }}

    function playTone(freq, dur, type = 'sine') {{
        if (!soundEnabled) return;
        try {{
            const ctx = getAudioCtx();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = type;
            osc.frequency.setValueAtTime(freq, ctx.currentTime);
            gain.gain.setValueAtTime(0.12, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + dur);
        }} catch(e) {{}}
    }}

    function updateDisplay() {{
        const el = document.getElementById('timer-display');
        if (!el) return;
        const mins = Math.floor(remaining / 60);
        const secs = remaining % 60;
        el.innerText = (mins < 10 ? '0' : '') + mins + ':' + (secs < 10 ? '0' : '') + secs;

        if (remaining <= 5) {{
            el.style.color = '#dc2626';
        }} else if (remaining <= 15) {{
            el.style.color = '#d97706';
        }} else {{
            el.style.color = '#059669';
        }}
    }}

    function tick() {{
        if (remaining > 0) {{
            remaining--;
            updateDisplay();

            if (remaining <= 10 && remaining > 0) {{
                playTone(880, 0.08, 'triangle');
            }} else if (remaining === 0) {{
                playTone(440, 0.4, 'sawtooth');
                setTimeout(() => playTone(330, 0.6, 'sawtooth'), 200);
            }}
        }} else {{
            clearInterval(timerInterval);
            isRunning = false;
            const btn = document.getElementById('btn-toggle');
            if (btn) btn.innerText = 'Start';
        }}
    }}

    function startTimer() {{
        clearInterval(timerInterval);
        timerInterval = setInterval(tick, 1000);
        isRunning = true;
        const btn = document.getElementById('btn-toggle');
        if (btn) btn.innerText = 'Pause';
    }}

    function toggleClock() {{
        getAudioCtx();
        if (isRunning) {{
            clearInterval(timerInterval);
            isRunning = false;
            const btn = document.getElementById('btn-toggle');
            if (btn) btn.innerText = 'Start';
        }} else {{
            if (remaining <= 0) remaining = duration;
            startTimer();
        }}
    }}

    function resetClock() {{
        getAudioCtx();
        clearInterval(timerInterval);
        remaining = duration;
        updateDisplay();
        startTimer();
    }}

    // Clean reset triggered on every instance mount / pick progression
    resetClock();
</script>
"""
components.html(clock_html, height=72)

# 11. IN-LINE ACTION CONSOLE + PROMINENT RESET CONTROLS
if curr_p > TOTAL_PICKS:
    st.success("🎉 **DRAFT COMPLETE! All rounds have concluded.**")
    if st.button("🚀 Start New Draft / Reset Board", type="primary", use_container_width=True):
        reset_entire_board()
else:
    with st.container():
        act_col1, act_col2, act_col3, act_col4, act_col5, act_col6 = st.columns([2.6, 1.0, 0.9, 1.2, 0.8, 0.8])
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
                    execute_pick(selected_player, mine, send_to_ir)

        with act_col5:
            if st.button("↩ Undo", help="Revert the last pick logged", use_container_width=True):
                if st.session_state.draft_history:
                    if st.session_state.practice_mode and st.session_state.auto_advance:
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

        with act_col6:
            if st.button("🔄 Reset", help="Reset all picks and rosters back to Pick #1", use_container_width=True):
                reset_entire_board()

st.markdown("---")

# 12. TIER 1: SPLIT WORKSPACE (PRIORITY TARGETS LEFT • ROSTER RIGHT)
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
    ctrl_title_col, ctrl_filter_col, ctrl_count_col = st.columns([1.6, 2.0, 1.4])
    
    with ctrl_title_col:
        st.markdown("##### 🎯 Priority Targets")
        
    with ctrl_filter_col:
        prio_pos_filter = st.pills(
            "Filter by Position",
            options=["ALL", "RB", "WR", "TE", "QB", "FLEX", "DST/K"],
            default="ALL",
            label_visibility="collapsed"
        )
        
    with ctrl_count_col:
        prio_limit = st.selectbox(
            "Show Count",
            options=[5, 8, 10, 15],
            index=2,
            format_func=lambda x: f"Top {x} Available",
            label_visibility="collapsed"
        )

    if prio_pos_filter == "ALL":
        target_pool = display_scored[~display_scored['Pos'].isin(['K', 'DST'])]
    elif prio_pos_filter == "FLEX":
        target_pool = display_scored[display_scored['Pos'].isin(['RB', 'WR', 'TE'])]
    elif prio_pos_filter == "DST/K":
        target_pool = display_scored[display_scored['Pos'].isin(['DST', 'K'])]
    else:
        target_pool = display_scored[display_scored['Pos'] == prio_pos_filter]

    # DYNAMIC MULTI-COLUMN SORTING LOGIC
    sort_col = st.session_state.sort_col
    sort_asc = st.session_state.sort_asc

    if sort_col == 'VORP':
        priority_display = target_pool.sort_values(
            by=['VORP', 'ADP'], ascending=[sort_asc, True]
        ).head(prio_limit).reset_index(drop=True)
    elif sort_col == 'ADP':
        priority_display = target_pool.sort_values(
            by=['ADP', 'VORP'], ascending=[sort_asc, False]
        ).head(prio_limit).reset_index(drop=True)
    else:
        priority_display = target_pool.sort_values(
            by=[sort_col, 'VORP'], ascending=[sort_asc, False]
        ).head(prio_limit).reset_index(drop=True)

    def sort_indicator(col_name):
        if st.session_state.sort_col == col_name:
            return " ▲" if st.session_state.sort_asc else " ▼"
        return ""

    # CLICKABLE SORTABLE HEADER ROW
    h_act, h_name, h_pos, h_team, h_proj, h_vorp, h_adp, h_surv, h_verd = st.columns(
        [1.2, 3.5, 1.0, 1.0, 1.4, 1.4, 1.2, 1.8, 1.4]
    )

    with h_act:
        st.markdown("<div style='font-size:0.72rem; font-weight:800; color:var(--war-text-sub); padding:4px 0;'>ACTION</div>", unsafe_allow_html=True)
    with h_name:
        if st.button(f"PLAYER{sort_indicator('Name')}", key="hdr_sort_name", use_container_width=True):
            set_sort('Name', default_asc=True)
            st.rerun()
    with h_pos:
        if st.button(f"POS{sort_indicator('Pos')}", key="hdr_sort_pos", use_container_width=True):
            set_sort('Pos', default_asc=True)
            st.rerun()
    with h_team:
        if st.button(f"NFL{sort_indicator('Team')}", key="hdr_sort_team", use_container_width=True):
            set_sort('Team', default_asc=True)
            st.rerun()
    with h_proj:
        if st.button(f"PROJ{sort_indicator('ProjPts')}", key="hdr_sort_proj", use_container_width=True):
            set_sort('ProjPts', default_asc=False)
            st.rerun()
    with h_vorp:
        if st.button(f"VORP{sort_indicator('VORP')}", key="hdr_sort_vorp", use_container_width=True):
            set_sort('VORP', default_asc=False)
            st.rerun()
    with h_adp:
        if st.button(f"ADP{sort_indicator('ADP')}", key="hdr_sort_adp", use_container_width=True):
            set_sort('ADP', default_asc=True)
            st.rerun()
    with h_surv:
        if st.button(f"SURVIVAL{sort_indicator('Survival %')}", key="hdr_sort_surv", use_container_width=True):
            set_sort('Survival %', default_asc=False)
            st.rerun()
    with h_verd:
        st.markdown("<div style='font-size:0.72rem; font-weight:800; color:var(--war-text-sub); text-align:right; padding:4px 0;'>VERDICT</div>", unsafe_allow_html=True)

    st.markdown("<div style='border-bottom: 2px solid var(--war-border); margin-bottom: 6px;'></div>", unsafe_allow_html=True)

    if priority_display.empty:
        st.info("No available players matching this positional filter.")
    else:
        for idx, row in priority_display.iterrows():
            st.markdown("<div class='prio-row-container'>", unsafe_allow_html=True)
            c_btn, c_name, c_pos, c_team, c_proj, c_vorp, c_adp, c_surv, c_act = st.columns(
                [1.2, 3.5, 1.0, 1.0, 1.4, 1.4, 1.2, 1.8, 1.4]
            )

            with c_btn:
                if st.button("Draft", key=f"btn_prio_draft_{row['Name']}_{idx}", type="secondary", use_container_width=True):
                    execute_pick(row['Name'], is_my_pick=True)

            with c_name:
                health_icon = "🚨 " if row['Status'] in ["IR", "Out", "Suspended"] else ("⚠️ " if row['Status'] in ["Questionable", "Doubtful", "PUP"] else "")
                st.markdown(f"<div style='font-size: 0.88rem; font-weight: 700; color: var(--war-text-main); padding-top: 4px;'>{health_icon}{row['Name']}</div>", unsafe_allow_html=True)

            with c_pos:
                badge_class = f"badge-{row['Pos'].lower()}" if row['Pos'] in ['RB', 'WR', 'QB', 'TE'] else "badge-other"
                st.markdown(f"<div style='padding-top: 4px;'><span class='badge-pos {badge_class}'>{row['Pos']}</span></div>", unsafe_allow_html=True)

            with c_team:
                st.markdown(f"<div style='font-size: 0.82rem; font-weight: 600; color: var(--war-text-sub); padding-top: 4px;'>{row['Team']}</div>", unsafe_allow_html=True)

            with c_proj:
                st.markdown(f"<div style='font-size: 0.85rem; font-weight: 700; color: var(--war-text-main); text-align: right; padding-top: 4px;'>{row['ProjPts']:.1f}</div>", unsafe_allow_html=True)

            with c_vorp:
                st.markdown(f"<div style='font-size: 0.85rem; font-weight: 800; color: #2563eb; text-align: right; padding-top: 4px;'>+{row['VORP']:.1f}</div>", unsafe_allow_html=True)

            with c_adp:
                st.markdown(f"<div style='font-size: 0.82rem; font-weight: 600; color: var(--war-text-sub); text-align: right; padding-top: 4px;'>{row['ADP']:.0f}</div>", unsafe_allow_html=True)

            with c_surv:
                surv_color = "#059669" if row['Survival %'] >= 70 else ("#d97706" if row['Survival %'] >= 35 else "#dc2626")
                st.markdown(f"<div style='font-size: 0.85rem; font-weight: 800; color: {surv_color}; text-align: right; padding-top: 4px;'>{row['Survival %']}%</div>", unsafe_allow_html=True)

            with c_act:
                act_color = "#2563eb" if "Safe" in row['Action'] else ("#dc2626" if "Draft" in row['Action'] else "#64748b")
                st.markdown(f"<div style='font-size: 0.8rem; font-weight: 700; color: {act_color}; text-align: right; padding-top: 4px;'>{row['Action']}</div>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

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
    
    bench_names = [p for p in roster_pool['Name'].tolist() if p not in taken and p != "—"]
    
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

    st.dataframe(
        starter_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Slot": st.column_config.TextColumn("Slot", width="small"),
            "Player": st.column_config.TextColumn("Starter")
        }
    )

    st.markdown(f"###### 🪑 Bench ({len(bench_names)} Reserves)")
    if bench_names:
        bench_df = roster_pool[roster_pool['Name'].isin(bench_names)][['Name', 'Pos', 'Team', 'ProjPts', 'Status']].copy()
        bench_df.insert(0, "Slot", [f"BN{i+1}" for i in range(len(bench_df))])
        st.dataframe(
            bench_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Slot": st.column_config.TextColumn("Slot", width="small"),
                "Name": st.column_config.TextColumn("Player"),
                "Pos": st.column_config.TextColumn("Pos", width="small"),
                "Team": st.column_config.TextColumn("NFL", width="small"),
                "ProjPts": st.column_config.NumberColumn("Proj", format="%.1f"),
                "Status": st.column_config.TextColumn("Health", width="small")
            }
        )
    else:
        st.caption("No bench reserves drafted yet.")

    if st.session_state.my_ir:
        st.markdown(f"###### 🏥 IR Slot")
        ir_df = raw_df[raw_df['Name'].isin(st.session_state.my_ir)][['Name', 'Pos', 'Team', 'Status', 'Notes']].copy()
        st.dataframe(
            ir_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Name": st.column_config.TextColumn("Player"),
                "Pos": st.column_config.TextColumn("Pos", width="small"),
                "Team": st.column_config.TextColumn("NFL", width="small"),
                "Status": st.column_config.TextColumn("Health", width="small"),
                "Notes": st.column_config.TextColumn("Report")
            }
        )

    st.markdown("---")
    st.markdown("##### ⚡ Tier Scarcity Cliff")
    cliff_cols = st.columns(4)
    for i, p in enumerate(['RB', 'WR', 'TE', 'QB']):
        top_tier = scored_df[scored_df['Pos'] == p].head(3)
        cliff_val = (top_tier.iloc[0]['VORP'] - top_tier.iloc[-1]['VORP']) if len(top_tier) >= 2 else 0.0
        with cliff_cols[i]:
            st.metric(label=f"{p} Cliff", value=f"-{cliff_val:.1f}")

# 13. TIER 2: FULL-WIDTH 100% ACROSS DRAFT BOARD & POSITIONAL TABS
st.markdown("---")
st.markdown("#### 📋 Full League Draft Board & Positional Depth")

tab_board, tab_all, tab_rb, tab_wr, tab_te, tab_qb, tab_dst_k, tab_injury = st.tabs(
    ["📋 Full Visual Board", "🔥 All VORP", "🏃 Running Backs", "🙌 Wide Receivers", "🧱 Tight Ends", "🎯 Quarterbacks", "🛡️ D/ST & K", "🏥 IR Hub"]
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

    board_df = pd.DataFrame(grid_data, index=[f"Round {r+1}" for r in range(total_rounds)])

    def style_draft_grid(val):
        if "—" in val:
            return "color: #94a3b8; background-color: var(--war-subtle-bg);"
        if "(RB)" in val:
            return "background-color: #2563eb; color: #ffffff; font-weight: 700;"
        if "(WR)" in val:
            return "background-color: #059669; color: #ffffff; font-weight: 700;"
        if "(QB)" in val:
            return "background-color: #ea580c; color: #ffffff; font-weight: 700;"
        if "(TE)" in val:
            return "background-color: #d97706; color: #ffffff; font-weight: 700;"
        return "background-color: #475569; color: #ffffff; font-weight: 700;"

    try:
        styled_board = board_df.style.map(style_draft_grid)
    except AttributeError:
        styled_board = board_df.style.applymap(style_draft_grid)

    st.dataframe(styled_board, use_container_width=True, height=520)

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