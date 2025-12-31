import streamlit as st
import pandas as pd
import itertools
import graphviz
from io import BytesIO

# =======================
# 1. CSS 強力優化 (黑底螢光風 + 底部導航)
# =======================
st.set_page_config(page_title="賽程控制台", layout="wide", page_icon="⚡")

st.markdown("""
<style>
    /* 全局背景：深黑 */
    .stApp {
        background-color: #000000;
        color: #FFFFFF;
    }
    
    /* 標題與強調色：螢光綠 */
    h1, h2, h3, h4, h5, h6, .stMarkdown {
        color: #00FF00 !important;
        font-weight: 800 !important;
    }
    
    /* 輸入框優化：白底黑字，字體超大 */
    input[type="number"] {
        font-size: 28px !important;
        background-color: #FFFFFF !important;
        color: #000000 !important;
        font-weight: bold;
        height: 60px !important;
        border-radius: 10px;
    }
    
    /* 下拉選單優化 */
    div[data-baseweb="select"] > div {
        background-color: #333333;
        color: white;
        font-size: 20px;
    }

    /* 按鈕：高亮橘色，方便點擊 */
    .stButton button {
        background-color: #FF5722 !important;
        color: white !important;
        border: none;
        border-radius: 12px;
        font-size: 24px !important;
        padding: 15px 0px;
        font-weight: bold;
        width: 100%;
        margin-top: 10px;
    }

    /* =========== 底部導航列黑科技 =========== */
    /* 隱藏原本 Tabs 上方的線條 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        background-color: #111;
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        z-index: 9999;
        padding-bottom: 10px; /* 避開 iPhone 底部橫條 */
        padding-top: 5px;
        border-top: 2px solid #00FF00;
    }

    /* Tab 按鈕樣式 */
    .stTabs [data-baseweb="tab"] {
        height: 60px;
        white-space: pre-wrap;
        background-color: #222;
        border-radius: 5px;
        color: #888;
        flex: 1; /* 平均分配寬度 */
        font-size: 1.2rem;
    }

    /* 被選中的 Tab */
    .stTabs [aria-selected="true"] {
        background-color: #00FF00 !important;
        color: #000000 !important;
        font-weight: bold;
    }
    
    /* 為了不讓內容被底部導航擋住，增加底部留白 */
    .main .block-container {
        padding-bottom: 100px;
    }
    
    /* 隱藏不需要的裝飾 */
    header {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# =======================
# 2. 核心邏輯 (與之前相同)
# =======================

def generate_schedule(players):
    matches = []
    clean_players = list(set([p.strip() for p in players if p.strip()]))
    if len(clean_players) < 2: return pd.DataFrame()
    for p1, p2 in itertools.combinations(clean_players, 2):
        matches.append({"隊伍 A": p1, "隊伍 B": p2, "A 得分": None, "B 得分": None})
    return pd.DataFrame(matches)

def calculate_rankings(df_matches):
    players = list(set(df_matches["隊伍 A"]).union(set(df_matches["隊伍 B"])))
    stats = {p: {"勝": 0, "敗": 0, "得失分": 0, "總得分": 0} for p in players}
    for _, row in df_matches.iterrows():
        p1, p2, s1, s2 = row["隊伍 A"], row["隊伍 B"], row["A 得分"], row["B 得分"]
        if pd.notna(s1) and pd.notna(s2):
            stats[p1]["總得分"] += s1; stats[p2]["總得分"] += s2
            stats[p1]["得失分"] += (s1 - s2); stats[p2]["得失分"] += (s2 - s1)
            if s1 > s2: stats[p1]["勝"] += 1; stats[p2]["敗"] += 1
            elif s2 > s1: stats[p2]["勝"] += 1; stats[p1]["敗"] += 1
    df_rank = pd.DataFrame.from_dict(stats, orient='index')
    df_rank.reset_index(inplace=True); df_rank.rename(columns={'index': '隊伍'}, inplace=True)
    return df_rank.sort_values(by=["勝", "得失分"], ascending=False).reset_index(drop=True)

def draw_network(df_matches):
    graph = graphviz.Digraph()
    graph.attr(rankdir='LR', layout='circo', bgcolor='black') # 黑底圖表
    graph.attr('node', shape='ellipse', style='filled', color='white', fontcolor='black')
    graph.attr('edge', color='white', fontcolor='white')
    
    players = list(set(df_matches["隊伍 A"]).union(set(df_matches["隊伍 B"])))
    for p in players: graph.node(p)
    
    for _, row in df_matches.iterrows():
        if pd.notna(row["A 得分"]) and pd.notna(row["B 得分"]):
            s1, s2 = row["A 得分"], row["B 得分"]
            lbl = f"{int(s1)}:{int(s2)}"
            if s1 > s2: graph.edge(row["隊伍 A"], row["隊伍 B"], label=lbl, color='#00FF00', penwidth='2')
            elif s2 > s1: graph.edge(row["隊伍 B"], row["隊伍 A"], label=lbl, color='#00FF00', penwidth='2')
    return graph

# =======================
# 3. 介面模組
# =======================

def render_tournament_group(group_name, icon):
    st.markdown(f"### {icon} {group_name}")
    ss_key = f"df_{group_name}"
    
    # 初始化
    if ss_key not in st.session_state:
        st.session_state[ss_key] = pd.DataFrame()

    # --- 設定區 (折疊起來省空間) ---
    with st.expander("🛠️ 設定名單 / 上傳 / 下載", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            raw = st.text_area("名單 (一行一隊)", "A隊\nB隊\nC隊", key=f"txt_{group_name}")
            if st.button("重置賽程", key=f"btn_{group_name}"):
                st.session_state[ss_key] = generate_schedule(raw.split('\n'))
                st.rerun()
        with c2:
            up = st.file_uploader("上傳 Excel", key=f"up_{group_name}")
            if up:
                try:
                    df = pd.read_excel(up) if up.name.endswith('.xlsx') else pd.read_csv(up)
                    st.session_state[ss_key] = df
                except: pass
            
            # 下載按鈕放在這
            if not st.session_state[ss_key].empty:
                csv = st.session_state[ss_key].to_csv(index=False).encode('utf-8-sig')
                st.download_button("💾 下載備份", csv, f"{group_name}.csv", "text/csv")

    df = st.session_state[ss_key]
    if df.empty:
        st.info("請先設定名單")
        return

    # --- 🚀 重點：快速輸入介面 ---
    # 邏輯：建立一個下拉選單選擇比賽，下方出現兩個大框框
    
    # 1. 製作下拉選單的選項 (例如: "1. Team A vs Team B")
    match_options = []
    for idx, row in df.iterrows():
        status = "✅" if pd.notna(row['A 得分']) else "⬜"
        label = f"{status} 場次{idx+1}: {row['隊伍 A']} 🆚 {row['隊伍 B']}"
        match_options.append(label)

    st.markdown("---")
    st.markdown("#### ⚡ 快速比分輸入")
    
    # 選擇場次
    selected_match_label = st.selectbox("選擇場次", match_options, key=f"sel_{group_name}")
    selected_idx = match_options.index(selected_match_label)
    
    # 取得該場次的目前比分
    current_a = df.at[selected_idx, "A 得分"]
    current_b = df.at[selected_idx, "B 得分"]
    val_a = int(current_a) if pd.notna(current_a) else 0
    val_b = int(current_b) if pd.notna(current_b) else 0

    # 顯示兩個超大輸入框
    col_input_1, col_input_2 = st.columns(2)
    
    with col_input_1:
        st.markdown(f"<div style='text-align:center; font-size:20px; color:#aaa;'>{df.at[selected_idx, '隊伍 A']}</div>", unsafe_allow_html=True)
        # 使用 form 讓手機輸入時更好操作，且有 Submit 按鈕
        new_score_a = st.number_input("A得分", value=val_a, min_value=0, max_value=200, key=f"in_a_{group_name}_{selected_idx}", label_visibility="collapsed")
    
    with col_input_2:
        st.markdown(f"<div style='text-align:center; font-size:20px; color:#aaa;'>{df.at[selected_idx, '隊伍 B']}</div>", unsafe_allow_html=True)
        new_score_b = st.number_input("B得分", value=val_b, min_value=0, max_value=200, key=f"in_b_{group_name}_{selected_idx}", label_visibility="collapsed")

    # 確認按鈕 (一鍵更新)
    if st.button(f"確認登錄：{df.at[selected_idx, '隊伍 A']} vs {df.at[selected_idx, '隊伍 B']}", key=f"save_{group_name}"):
        df.at[selected_idx, "A 得分"] = new_score_a
        df.at[selected_idx, "B 得分"] = new_score_b
        st.session_state[ss_key] = df # 存回 Session
        st.success("已更新！")
        st.rerun()

    # --- 顯示結果 (排名與圖表) ---
    st.markdown("---")
    t1, t2, t3 = st.tabs(["📊 即時排名", "🕸️ 對戰圖", "📋 完整賽表"])
    
    with t1:
        rank = calculate_rankings(df)
        st.dataframe(rank, use_container_width=True, hide_index=True)
    with t2:
        try: st.graphviz_chart(draw_network(df))
        except: st.write("無資料")
    with t3:
        # 顯示唯讀的完整表格供查閱
        st.dataframe(df, use_container_width=True, hide_index=True)

# =======================
# 4. 主程式架構
# =======================

# 雖然 Tabs 在 HTML 結構是上面，但透過 CSS 我們把它搬到了下面
tab1, tab2, tab3, tab4 = st.tabs(["1️⃣ 場地一", "2️⃣ 場地二", "3️⃣ 場地三", "4️⃣ 場地四"])

with tab1: render_tournament_group("場地 A", "🅰️")
with tab2: render_tournament_group("場地 B", "🅱️")
with tab3: render_tournament_group("場地 C", "©️")
with tab4: render_tournament_group("場地 D", "🇩")
