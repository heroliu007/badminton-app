import streamlit as st
import pandas as pd
import random
import itertools
import graphviz # 新增這個庫來畫關係圖

# =======================
# 設定與 CSS 優化
# =======================
st.set_page_config(page_title="互動式循環賽系統", layout="wide", page_icon="🏸")

st.markdown("""
<style>
    .stDataFrame { margin: 0 auto; }
    div[data-testid="stMetricValue"] { font-size: 1.5rem; }
    h3 { color: #2c3e50; }
</style>
""", unsafe_allow_html=True)

# =======================
# 1. 核心邏輯區
# =======================

def generate_schedule(players):
    """產生單循環賽程的初始資料結構"""
    matches = []
    for p1, p2 in itertools.combinations(players, 2):
        matches.append({
            "隊伍 A": p1,
            "隊伍 B": p2,
            "A 得分": None,
            "B 得分": None
        })
    return pd.DataFrame(matches)

def calculate_rankings(df_matches, players):
    """計算積分與排名"""
    stats = {p: {"勝": 0, "敗": 0, "得失分": 0, "總得分": 0} for p in players}
    
    for index, row in df_matches.iterrows():
        p1 = row["隊伍 A"]
        p2 = row["隊伍 B"]
        s1 = row["A 得分"]
        s2 = row["B 得分"]
        
        if pd.notna(s1) and pd.notna(s2):
            stats[p1]["總得分"] += s1
            stats[p2]["總得分"] += s2
            stats[p1]["得失分"] += (s1 - s2)
            stats[p2]["得失分"] += (s2 - s1)
            
            if s1 > s2:
                stats[p1]["勝"] += 1
                stats[p2]["敗"] += 1
            elif s2 > s1:
                stats[p2]["勝"] += 1
                stats[p1]["敗"] += 1

    df_rank = pd.DataFrame.from_dict(stats, orient='index')
    df_rank.index.name = "隊伍"
    df_rank.reset_index(inplace=True)
    df_rank = df_rank.sort_values(by=["勝", "得失分", "總得分"], ascending=False)
    df_rank.reset_index(drop=True, inplace=True)
    df_rank.index += 1 
    return df_rank

def create_cross_table(df_matches, players):
    """產生交叉勝敗表"""
    cross_df = pd.DataFrame("-", index=players, columns=players)
    for p in players: cross_df.at[p, p] = "❌"

    for index, row in df_matches.iterrows():
        p1 = row["隊伍 A"]
        p2 = row["隊伍 B"]
        s1 = row["A 得分"]
        s2 = row["B 得分"]
        
        if pd.notna(s1) and pd.notna(s2):
            cross_df.at[p1, p2] = f"{int(s1)}:{int(s2)}"
            cross_df.at[p2, p1] = f"{int(s2)}:{int(s1)}"
    return cross_df

# =======================
# 2. 圖表繪製區 (新增功能)
# =======================

def draw_network(df_matches):
    """繪製勝敗關係圖 (五角形/四角形)"""
    # 建立一個有向圖 (Directed Graph)
    graph = graphviz.Digraph()
    graph.attr(rankdir='LR', layout='circo') # layout='circo' 會讓圖變成圓形/多邊形
    graph.attr('node', shape='ellipse', style='filled', color='lightblue')
    
    has_result = False
    for index, row in df_matches.iterrows():
        p1 = row["隊伍 A"]
        p2 = row["隊伍 B"]
        s1 = row["A 得分"]
        s2 = row["B 得分"]
        
        # 確保節點存在
        graph.node(p1)
        graph.node(p2)

        # 如果有比分，畫出箭頭 (贏 -> 輸)
        if pd.notna(s1) and pd.notna(s2):
            has_result = True
            if s1 > s2:
                graph.edge(p1, p2, label=f"{int(s1)}:{int(s2)}", color='green')
            elif s2 > s1:
                graph.edge(p2, p1, label=f"{int(s2)}:{int(s1)}", color='green')
    
    if not has_result:
        graph.attr(label='(輸入比分後，箭頭會自動出現)')
        
    return graph

# =======================
# 3. 網頁介面區 (UI)
# =======================

st.title("🏸 循環賽視覺化系統")

# --- 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 設定")
    default_players = "張三/李四\n王五/趙六\nTeam A\nTeam B\nTeam C"
    raw_text = st.text_area("參賽名單", default_players, height=150)
    players_list = [p.strip() for p in raw_text.split('\n') if p.strip()]
    if st.button("🔄 重置賽程"): st.session_state.clear()

if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = generate_schedule(players_list)
if set(st.session_state.schedule_df["隊伍 A"].unique()).union(set(st.session_state.schedule_df["隊伍 B"].unique())) != set(players_list):
     st.session_state.schedule_df = generate_schedule(players_list)

# --- 主畫面 ---
if len(players_list) < 2:
    st.error("請輸入至少兩隊！")
else:
    # 第一區：輸入
    st.subheader("1️⃣ 輸入比分")
    edited_df = st.data_editor(
        st.session_state.schedule_df,
        column_config={
            "A 得分": st.column_config.NumberColumn(min_value=0, max_value=100),
            "B 得分": st.column_config.NumberColumn(min_value=0, max_value=100),
        },
        hide_index=True,
        use_container_width=True,
        num_rows="fixed"
    )

    # 計算資料
    rank_df = calculate_rankings(edited_df, players_list)
    cross_df = create_cross_table(edited_df, players_list)

    # 第二區：表格與圖表
    st.divider()
    
    # 使用 Tabs 分頁來切換不同視角
    tab1, tab2, tab3 = st.tabs(["📊 排名與統計圖", "🕸️ 勝敗關係圖", "🔢 交叉勝敗表"])

    with tab1:
        col_rank, col_chart = st.columns([1, 1.5])
        with col_rank:
            st.markdown("#### 目前排名")
            st.dataframe(rank_df.style.highlight_max(axis=0, color="#d1e7dd"), use_container_width=True)
        with col_chart:
            st.markdown("#### 得失分統計 (Bar Chart)")
            # 畫長條圖：顯示每隊的得失分
            st.bar_chart(rank_df.set_index("隊伍")["得失分"], color="#3498db")

    with tab2:
        st.markdown("#### 🔄 對戰食物鏈 (誰贏了誰)")
        st.caption("這就是您要的五角形/多邊形圖：箭頭從贏家指向輸家")
        # 呼叫畫圖函數
        try:
            st.graphviz_chart(draw_network(edited_df))
        except Exception:
            st.warning("請確保輸入比分後圖表會自動產生")

    with tab3:
        st.markdown("#### ❌ 傳統交叉表")
        st.dataframe(cross_df, use_container_width=True)
