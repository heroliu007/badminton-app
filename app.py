import streamlit as st
import pandas as pd
import itertools
import graphviz
from io import BytesIO

# =======================
# 設定與 CSS
# =======================
st.set_page_config(page_title="多場地循環賽系統", layout="wide", page_icon="🏆")

st.markdown("""
<style>
    .stDataFrame { margin: 0 auto; }
    h3 { color: #2c3e50; }
    /* 讓 Tabs 字體大一點，方便手機點擊 */
    button[data-baseweb="tab"] { font-size: 1.2rem; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# =======================
# 核心邏輯函數
# =======================

def generate_schedule(players):
    """產生初始賽程"""
    matches = []
    # 移除空白行並去重
    clean_players = list(set([p.strip() for p in players if p.strip()]))
    if len(clean_players) < 2:
        return pd.DataFrame()
        
    for p1, p2 in itertools.combinations(clean_players, 2):
        matches.append({
            "隊伍 A": p1,
            "隊伍 B": p2,
            "A 得分": None,
            "B 得分": None
        })
    return pd.DataFrame(matches)

def calculate_rankings(df_matches):
    """計算積分"""
    # 取得所有隊伍名單
    players = list(set(df_matches["隊伍 A"]).union(set(df_matches["隊伍 B"])))
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

def draw_network(df_matches):
    """繪製關係圖"""
    graph = graphviz.Digraph()
    graph.attr(rankdir='LR', layout='circo')
    graph.attr('node', shape='ellipse', style='filled', color='lightblue')
    
    # 確保所有隊伍都有節點
    players = list(set(df_matches["隊伍 A"]).union(set(df_matches["隊伍 B"])))
    for p in players:
        graph.node(p)

    has_result = False
    for index, row in df_matches.iterrows():
        p1 = row["隊伍 A"]
        p2 = row["隊伍 B"]
        s1 = row["A 得分"]
        s2 = row["B 得分"]
        
        if pd.notna(s1) and pd.notna(s2):
            has_result = True
            if s1 > s2:
                graph.edge(p1, p2, label=f"{int(s1)}:{int(s2)}", color='green')
            elif s2 > s1:
                graph.edge(p2, p1, label=f"{int(s2)}:{int(s1)}", color='green')
    
    if not has_result:
        graph.attr(label='(比賽開始後顯示勝敗走向)')
    return graph

def convert_df_to_csv(df):
    """將 DataFrame 轉為 CSV 下載用"""
    return df.to_csv(index=False).encode('utf-8-sig')

# =======================
# 單一賽程管理介面 (封裝成函數以重複使用)
# =======================

def render_tournament_group(group_name):
    """渲染單一組別的完整介面"""
    st.header(f"🏟️ {group_name} 賽程管理")
    
    # Session State Key 的唯一識別碼 (避免 A 組跟 B 組資料打架)
    ss_key = f"df_{group_name}"
    
    # 1. 初始化資料
    if ss_key not in st.session_state:
        st.session_state[ss_key] = pd.DataFrame()

    # 2. 設定區域 (側邊欄縮進去太擠，改用 Expander)
    with st.expander(f"⚙️ {group_name} 設定 (名單/上傳)", expanded=False):
        col_input, col_upload = st.columns(2)
        
        with col_input:
            default_text = "隊伍1\n隊伍2\n隊伍3"
            raw_text = st.text_area(f"{group_name} 參賽名單 (一行一隊)", default_text, height=100, key=f"text_{group_name}")
            if st.button(f"✨ 產生 {group_name} 新賽程", key=f"btn_gen_{group_name}"):
                players = raw_text.split('\n')
                st.session_state[ss_key] = generate_schedule(players)
                st.rerun()

        with col_upload:
            uploaded_file = st.file_uploader(f"或是上傳 Excel/CSV ({group_name})", type=['xlsx', 'csv'], key=f"up_{group_name}")
            if uploaded_file is not None:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        df_upload = pd.read_csv(uploaded_file)
                    else:
                        df_upload = pd.read_excel(uploaded_file)
                    
                    # 簡單檢查欄位
                    required_cols = {"隊伍 A", "隊伍 B"}
                    if required_cols.issubset(df_upload.columns):
                        st.session_state[ss_key] = df_upload
                        st.success("✅ 匯入成功！")
                    else:
                        st.error("❌ 格式錯誤！請包含：'隊伍 A', '隊伍 B'")
                except Exception as e:
                    st.error(f"讀取失敗: {e}")

    # 3. 取得目前資料
    df = st.session_state[ss_key]

    if df.empty:
        st.info("👈 請先在設定區輸入名單或上傳檔案")
        return

    # 4. 比分輸入區 (Data Editor)
    st.subheader("📝 輸入比分")
    edited_df = st.data_editor(
        df,
        column_config={
            "A 得分": st.column_config.NumberColumn(min_value=0, max_value=200),
            "B 得分": st.column_config.NumberColumn(min_value=0, max_value=200),
        },
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic", # 允許新增刪除行
        key=f"editor_{group_name}"
    )
    
    # ⚠️ 重要：手動更新 session state，確保切換 Tab 時資料還在
    # Streamlit 的 data_editor 自動會更新 key 對應的 state，但為了保險起見或做額外處理，有時需手動
    # 但在此例中，data_editor 的 key 機制已經足夠維持編輯狀態

    # 5. 安全備份下載 (因為沒有連雲端資料庫)
    csv = convert_df_to_csv(edited_df)
    st.download_button(
        label=f"💾 下載 {group_name} 賽程與比分備份 (CSV)",
        data=csv,
        file_name=f'{group_name}_schedule.csv',
        mime='text/csv',
        key=f"dl_{group_name}"
    )

    # 6. 統計與圖表
    if not edited_df.empty:
        rank_df = calculate_rankings(edited_df)
        
        t1, t2 = st.tabs(["📊 排名", "🕸️ 關係圖"])
        
        with t1:
            st.dataframe(rank_df.style.highlight_max(axis=0, color="#d1e7dd"), use_container_width=True)
        with t2:
            try:
                st.graphviz_chart(draw_network(edited_df))
            except:
                st.write("圖表繪製中...")

# =======================
# 主程式入口
# =======================

st.title("🏆 多場地循環賽系統 (手機暫存版)")
st.caption("⚠️ 注意：本模式資料暫存於瀏覽器，**重新整理或關閉網頁會導致資料遺失**，請善用「下載備份」按鈕。")

# 建立四個主分頁
tab_a, tab_b, tab_c, tab_d = st.tabs(["🅰️ 第一場地", "🅱️ 第二場地", "©️ 第三場地", "🇩 第四場地"])

with tab_a:
    render_tournament_group("Group_A")
with tab_b:
    render_tournament_group("Group_B")
with tab_c:
    render_tournament_group("Group_C")
with tab_d:
    render_tournament_group("Group_D")
