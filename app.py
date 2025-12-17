import streamlit as st
import pandas as pd
import google.generativeai as genai
import matplotlib.pyplot as plt
from PIL import Image
from streamlit_paste_button import paste_image_button
import io

# -----------------------------------------------------------------------------
# 1. 基礎設定 (Page Config & Fonts)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="JAMOVI 智能助手 V2",
    page_icon="📊",
    layout="wide"
)

# 設定 Matplotlib 中文字型 (Windows 專用)
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei'] 
plt.rcParams['axes.unicode_minus'] = False 

# -----------------------------------------------------------------------------
# 2. Session State 初始化
# -----------------------------------------------------------------------------
if 'curr_df' not in st.session_state:
    st.session_state['curr_df'] = None
if 'df_name' not in st.session_state:
    st.session_state['df_name'] = ""
if 'research_q' not in st.session_state:
    st.session_state['research_q'] = ""
if 'analysis_result' not in st.session_state:
    st.session_state['analysis_result'] = None
if 'messages' not in st.session_state:
    st.session_state['messages'] = []

# -----------------------------------------------------------------------------
# 3. API 連線設定
# -----------------------------------------------------------------------------
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    # 設定候補模型清單 (優先使用驗證過的 2.5-flash，並加入實驗版作為備援)
    candidate_models = [
        "gemini-2.5-flash", 
        "gemini-2.5-pro",
        "gemini-2.0-flash-exp",
        "gemini-flash-latest",
        "gemini-pro-latest"
    ]
    model = None
    
    # 嘗試建立模型物件 (這裡主要設定物件，真正連線會在 generate_content 時發生)
    # 但為了確保穩定，我們預設選用列表中的第一個
    model = genai.GenerativeModel(candidate_models[0])
    
except Exception as e:
    st.error(f"API Key 設定錯誤：{e}")
    st.stop()


# -----------------------------------------------------------------------------
# 4. 介面主架構 (Title & Tabs)
# -----------------------------------------------------------------------------
st.title("📊 JAMOVI 量化研究智能助手 V2")
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["📂 1. 數據上傳", "📝 2. 統計分析與 APA 報告", "💬 3. 自由咨詢室", "⚡ 4. Python 自動運算"])

# =============================================================================
# Tab 1: 數據上傳與預覽
# =============================================================================
with tab1:
    st.header("數據檔案上傳")
    uploaded_file = st.file_uploader("請上傳 CSV 或 Excel 檔案", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            # 讀取檔案
            if uploaded_file.name != st.session_state['df_name']:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                st.session_state['curr_df'] = df
                st.session_state['df_name'] = uploaded_file.name
                # 清空舊的對話與分析結果，因為資料換了
                st.session_state['analysis_result'] = None
                st.session_state['messages'] = []
                st.toast("✅ 資料已更新！")
            
            df = st.session_state['curr_df']
            
            st.success(f"目前檔案：{st.session_state['df_name']}")
            
            # --- 自動判讀變項類型 ---
            def detect_variable_type(series):
                """
                簡易判斷規則：
                1. 字串/Object -> 名義變項
                2. 數值型且不重複值少於 15 (通常是 Likert 量表或分組) -> 次序變項 (或名義)
                3. 其餘數值型 -> 連續變項
                """
                if pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
                    return "名義變項"
                elif pd.api.types.is_numeric_dtype(series):
                    # 判斷是否為「類別/次序」性質的數值
                    n_unique = series.nunique()
                    if n_unique <= 15: 
                        return "次序變項"  # 或是名義變項，這裡簡化歸類為次序/分組
                    else:
                        return "連續變項"
                return "未知"

            # 建立變項資訊表
            var_info = []
            for col in df.columns:
                dtype = str(df[col].dtype)
                n_unique = df[col].nunique()
                var_type = detect_variable_type(df[col])
                # 簡單範例值 (取前 3 個不重複值)
                examples = str(df[col].dropna().unique()[:3])
                
                var_info.append({
                    "欄位名稱": col,
                    "推測變項類型": var_type,
                    "資料型態": dtype,
                    "不重複值數量": n_unique,
                    "範例值": examples
                })
            
            df_info = pd.DataFrame(var_info)

            col_a, col_b = st.columns([1, 1])
            with col_a:
                st.subheader("1. 數據預覽")
                st.dataframe(df.head(), use_container_width=True)
            with col_b:
                st.subheader("2. 變項類型自動偵測")
                st.dataframe(
                    df_info.style.map(
                        lambda x: 'background-color: #d4edda' if x == '連續變項' else 
                                  ('background-color: #fff3cd' if x == '次序變項' else ''),
                        subset=['推測變項類型']
                    ),
                    use_container_width=True,
                    hide_index=True
                )
                
        except Exception as e:
            st.error(f"檔案讀取失敗：{e}")
    else:
        st.info("👋 請先上傳資料以開始分析。")

# =============================================================================
# Tab 2: 統計分析與教學 (核心功能)
# =============================================================================
with tab2:
    st.header("智能統計分析 & APA 報告生成")
    
    # 檢查是否有資料
    if st.session_state['curr_df'] is None:
        st.warning("⚠️ 請先至「Tab 1 數據上傳」載入資料檔案。")
    else:
        # 輸入研究問題
        q_input = st.text_area(
            "請描述您的研究問題或假設：",
            value=st.session_state['research_q'],
            height=150,
            placeholder="範例：我想探討「性別」(Gender) 對於「工作滿意度」(Satisfaction) 是否有顯著差異？"
        )
        st.session_state['research_q'] = q_input
        
        analyze_btn = st.button("🚀 開始智能分析 (JAMOVI 指引)", type="primary")
        
        if analyze_btn and q_input:
            with st.spinner("🤖 AI 正在思考統計策略、撰寫 JAMOVI 教學並生成 APA 報告..."):
                try:
                    df = st.session_state['curr_df']
                    # 準備 PromptContext
                    # 將自動判讀的變項類型也提供給 AI
                    var_desc_list = []
                    for col in df.columns:
                        v_type = "名義變項"
                        if pd.api.types.is_numeric_dtype(df[col]):
                            if df[col].nunique() <= 15:
                                v_type = "次序變項"
                            else:
                                v_type = "連續變項"
                        var_desc_list.append(f"- {col}: {v_type} ({str(df[col].dtype)})")
                    
                    columns_info = "\n".join(var_desc_list)
                    data_head = df.head().to_markdown(index=False)
                    
                    system_prompt = f"""
                    你是一位精通統計學與 JAMOVI 軟體操作的學術顧問，同時也是 APA 第七版格式的寫作專家。
                    
                    【使用者資料背景】
                    - 變數名稱與型態：{columns_info}
                    - 資料預覽：\n{data_head}
                    
                    【使用者研究問題】
                    {q_input}
                    
                    【任務要求】
                    請根據資料特性與研究問題，輸出以下三個部分的內容（請用繁體中文）：
                    
                    ### 1. 統計方法建議
                    - 建議使用的統計檢定方法（如：獨立樣本 t 檢定、One-way ANOVA、Pearson 相關等）。
                    - 簡短說明選擇理由（例如：自變項是二分名義，依變項是連續變數...）。

                    ### 2. JAMOVI 操作教學 (Step-by-Step)
                    - 詳細列出 JAMOVI 軟體的操作路徑（例如：點選 Analysis > T-Tests > ...）。
                    - 明確指出應將哪個欄位放入 Dependent Variable，哪個放入 Grouping Variable。
                    - 提醒需勾選的必要選項（如：Effect Size, Homogeneity test, Descriptives）。
                    
                    ### 3. APA 第七版結果報告 (Results)
                    - **結果敘述**：提供一段完整的學術結果寫作範本。包含解釋統計顯著性、假設檢定結果（支持或拒絕）。
                    - **統計數據填空**：請在文中使用標準符號，如 *t*(df) = value, *p* = .xxx, *d* = .xx。若無法計算精確值，請用 `[數值]` 標示。
                    - **APA 表格**：請用 Markdown Table 製作一個符合 APA 三線表格式（只有頂線、底線、標題下線）的表格範例。標題需如：**Table 1** *Means and Standard Deviations...*
                    """
                    
                    # 嘗試呼叫 API，若失敗則嘗試其他模型
                    response = None
                    tab2_errors = []
                    
                    import time
                    for m_name in candidate_models:
                        # Retry logic for each model
                        success = False
                        last_error = None
                        for attempt in range(3):
                            try:
                                temp_model = genai.GenerativeModel(m_name)
                                response = temp_model.generate_content(system_prompt)
                                success = True
                                break # break retry loop
                            except Exception as e:
                                last_error = e
                                err_msg = str(e)
                                if "429" in err_msg or "Quota" in err_msg or "limit" in err_msg:
                                    time.sleep(5)
                                    continue # retry same model
                                else:
                                    # Non-recoverable error
                                    break 
                        
                        if success:
                            break # break model loop
                        else:
                            # Model failed after retries
                            if last_error:
                                tab2_errors.append(f"{m_name}: {last_error}")
                    
                    if response:
                        st.session_state['analysis_result'] = response.text
                    else:
                        st.error("分析過程發生錯誤 (所有模型皆失敗)。詳細原因：")
                        for err in tab2_errors:
                            st.error(err)
                        if not tab2_errors:
                            st.error(f"Debug: 錯誤列表為空。模型清單長度: {len(candidate_models)}")

                except Exception as e:
                    st.error(f"分析過程發生未知錯誤：{e}")
        
        # 顯示結果
        if st.session_state['analysis_result']:
            st.markdown(st.session_state['analysis_result'])
            st.success("✅ 分析完成！您可以切換到 Tab 3 進行進一步諮詢，或到 Tab 4 查看 Python 實作結果。")

# =============================================================================
# Tab 3: 自由諮詢室 (Chat)
# =============================================================================
with tab3:
    st.header("💬 統計自由諮詢室")
    
    if st.session_state['curr_df'] is None:
        st.info("💡 上傳資料後，AI 將能根據您的變數進行更精準的回答。目前僅提供通用諮詢。")
        context_str = "使用者尚未上傳資料，請回答一般統計問題。"
    else:
        df = st.session_state['curr_df']
        context_str = f"""
        【目前資料背景】
        - 欄位資訊：{str(df.dtypes.to_dict())}
        - 使用者目前的研究問題：{st.session_state.get('research_q', '尚未設定')}
        """

    # 0. 圖片上傳區 (放在對話框上方)
    with st.expander("📸 上傳圖片佐證 (選填)"):
        col_img1, col_img2 = st.columns(2)
        with col_img1:
            uploaded_img = st.file_uploader("1. 上傳檔案", type=["png", "jpg", "jpeg"], key="chat_img_uploader")
        
        with col_img2:
            st.write("2. 或直接貼上截圖 (Ctrl+V)")
            paste_result = paste_image_button(
                label="📋 點此後按 Ctrl+V 貼上",
                background_color="#FF4B4B",
                hover_background_color="#FF0000",
                text_color="#FFFFFF",
                key="paste_btn"
            )
        
        image_content = None
        
        # 優先處理貼上的圖片
        if paste_result.image_data is not None:
            image_content = paste_result.image_data
            st.success("已成功貼上截圖！")
            st.image(image_content, caption="剪貼簿圖片", width=300)
        # 其次處理上傳的圖片 (若使用者同時操作，這裡邏輯是後者蓋前者，或可並存，此處先擇一)
        elif uploaded_img:
            image_content = Image.open(uploaded_img)
            st.image(image_content, caption="已上傳檔案", width=300)

    # 顯示歷史訊息
    for msg in st.session_state['messages']:
        st.chat_message(msg["role"]).write(msg["content"])

    # 處理使用者輸入
    if prompt := st.chat_input("請輸入您的問題... (例如：這筆資料適合做因素分析嗎？)"):
        # 1. 顯示使用者訊息
        st.session_state['messages'].append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)
        if image_content:
             # 若有圖片，也存入紀錄以便顯示
             st.chat_message("user").image(image_content, caption="User Uploaded Image", width=300)
        
        # 2. 呼叫 AI (含 retry 機制)
        try:
            full_prompt = f"""
            你是一個專業的統計助教。請用繁體中文回答。
            {context_str}
            
            【使用者提問】
            {prompt}
            """
            
            # 準備輸入內容 (有圖就傳圖)
            input_content = full_prompt
            if image_content:
                input_content = [full_prompt, image_content]

            ai_reply = None
            chat_error_details = []
            
            for m_name in candidate_models:
                # Retry logic for chat
                success = False
                last_error = None
                for attempt in range(3):
                    try:
                        chat_model = genai.GenerativeModel(m_name)
                        # 聊天用 stream=True 體驗較好，但這裡用一次性生成比較簡單
                        response = chat_model.generate_content(input_content)
                        ai_reply = response.text
                        success = True
                        break # break retry loop
                    except Exception as e:
                        last_error = e
                        err_msg = str(e)
                        if "429" in err_msg or "Quota" in err_msg or "limit" in err_msg:
                            import time
                            time.sleep(5)
                            continue # retry same model
                        else:
                            break # break retry loop
                
                if success:
                    break # break model loop
                else:
                    if last_error:
                         chat_error_details.append(f"{m_name}: {last_error}")
            
            if ai_reply:
                # 3. 顯示與儲存 AI 回覆
                st.session_state['messages'].append({"role": "assistant", "content": ai_reply})
                st.chat_message("assistant").write(ai_reply)
            else:
                st.error("所有模型嘗試皆失敗。詳細錯誤：")
                st.json(chat_error_details)
            
        except Exception as e:
            st.error(f"未知錯誤：{e}")

# =============================================================================
# Tab 4: Python 自動運算結果
# =============================================================================
with tab4:
    st.header("⚡ Python 自動運算結果 (Beta)")
    st.markdown("""
    此功能會讓 AI 嘗試為您的研究問題**撰寫並執行 Python 程式碼**（使用 scipy/statsmodels/pandas），
    直接計算出 P 值與統計檢定量，填補 APA 報告中的數值空白。
    """)
    
    if st.session_state['curr_df'] is None:
        st.warning("⚠️ 請先至「Tab 1 數據上傳」載入資料檔案。")
    elif not st.session_state['research_q']:
        st.warning("⚠️ 請先在「Tab 2」輸入您的研究問題。")
    else:
        # 使用者確認執行
        if st.button("▶️ 執行 Python 自動分析", key="run_python"):
            df = st.session_state['curr_df']
            
            with st.spinner("🤖 正在生成並執行 Python 統計腳本..."):
                try:
                     # 1. 生成程式碼
                    code_prompt = f"""
                    You are a Python Data Analyst Expert.
                    
                    【Goal】
                    Write a Python script to perform statistical analysis based on the user's dataframe and question.
                    
                    【Data Context】
                    - Columns: {list(df.columns)}
                    - Data Sample (first 5 rows):
                    {df.head().to_string()}
                    
                    【User Question】
                    {st.session_state['research_q']}
                    
                    【Requirements】
                    1. Assume the dataframe is already loaded in a variable named `df`. DO NOT read any file.
                    2. Use `scipy.stats` or `statsmodels` or `pandas` for analysis.
                    3. Use `st.write()`, `st.dataframe()`, or `st.metric()` to display the results clearly. 
                    4. Check for missing values causing errors, simple dropna if needed.
                    5. Output the p-value clearly.
                    6. The code should be executable in Streamlit environment.
                    7. Do not import streamlit or pandas inside the code (assume `st`, `pd`, `plt`, `np` are available), but DO import `scipy.stats` etc.
                    8. Wrap the output in NO specific function, just plain script.
                    
                    Reply ONLY with the python code block.
                    """
                    
                    generated_code = ""
                    tab4_errors = []
                    
                    import time
                    for m_name in candidate_models:
                        # Retry logic for code generation
                        success = False
                        last_error = None
                        for attempt in range(3):
                            try:
                                # 為了程式碼生成精準度，將 temperature 調低
                                gen_config = genai.GenerationConfig(temperature=0.1)
                                code_model = genai.GenerativeModel(m_name, generation_config=gen_config)
                                resp = code_model.generate_content(code_prompt)
                                generated_code = resp.text
                                success = True
                                break # break retry loop
                            except Exception as e:
                                last_error = e
                                err_msg = str(e)
                                if "429" in err_msg or "Quota" in err_msg or "limit" in err_msg:
                                    time.sleep(5)
                                    continue # retry same model
                                else:
                                    break # break retry loop
                        
                        if success:
                            break # break model loop
                        else:
                            if last_error:
                                tab4_errors.append(f"{m_name}: {last_error}")
                    
                    if not generated_code:
                        st.error("無法生成程式碼，可能是所有模型連線失敗。詳細錯誤如下：")
                        st.json(tab4_errors)
                    else:
                        # 2. 清理程式碼
                        cleaned_code = generated_code.replace("```python", "").replace("```", "").strip()
                        
                        st.subheader("📝 生成的分析程式碼：")
                        with st.expander("點擊查看原始碼"):
                            st.code(cleaned_code, language="python")
                            
                        # 3. 執行程式碼
                        st.subheader("📊 運算結果：")
                        local_vars = {
                            'df': df,
                            'st': st,
                            'pd': pd,
                            'plt': plt,
                            'scipy': __import__('scipy'),
                            'statsmodels': __import__('statsmodels')
                        }
                        
                        exec(cleaned_code, globals(), local_vars)
                        
                except Exception as e:
                    st.error(f"程式執行發生錯誤：{e}")
                    st.warning("建議檢查變項名稱是否含特殊字元，或嘗試簡化研究問題。")
