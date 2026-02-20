import streamlit as st
import requests
import plotly.io as pio
import plotly.graph_objs as go
from collections import defaultdict
import json

BACKEND_URL = "http://localhost:8000"

# --- Modern Page Config ---
st.set_page_config(page_title="Insight Orchestra 2.0", layout="wide", page_icon="🎻")

# --- Session State Initialization ---
if 'nlq_history' not in st.session_state:
    st.session_state['nlq_history'] = []
if 'session_id' not in st.session_state:
    st.session_state['session_id'] = None
if 'edited_code' not in st.session_state:
    st.session_state['edited_code'] = {}

# --- Custom CSS for Modern Look ---
st.markdown("""
    <style>
    .main { background-color: #f4f6fa; }
    .block-container { padding-top: 2rem; }
    h1, h2, h3, h4 { color: #1a2233; }
    .stButton>button { background: linear-gradient(90deg, #2c3e50 0%, #4ca1af 100%); color: white; border-radius: 8px; font-weight: 600; }
    .stFileUploader { background: #fff; border-radius: 10px; }
    .stTextInput>div>div>input { border-radius: 6px; }
    .stSelectbox>div>div { border-radius: 6px; }
    .stExpanderHeader { font-weight: 600; }
    .stAlert { border-radius: 8px; }
    .code-block {
        background: #1e1e1e;
        color: #d4d4d4;
        padding: 1em;
        border-radius: 8px;
        font-family: 'Courier New', monospace;
        overflow-x: auto;
    }
    .transparent-code {
        background: #282c34;
        color: #abb2bf;
        padding: 1em;
        border-radius: 8px;
        font-family: 'Courier New', monospace;
        font-size: 0.9em;
    }
    .session-context {
        background: #e8f4fd;
        border-left: 4px solid #4ca1af;
        padding: 0.5em 1em;
        border-radius: 0 8px 8px 0;
        margin-bottom: 0.5em;
    }
    </style>
""", unsafe_allow_html=True)

# --- Sidebar Navigation ---
st.sidebar.markdown("""
    <div style='text-align:center; margin-bottom:1.5em;'>
        <img src="https://img.icons8.com/ios-filled/100/2c3e50/orchestra.png" width="70" style="margin-bottom:0.5em;"/>
        <div style='font-size:1.5em; font-weight:700; color:#1a2233; letter-spacing:0.5px;'>Insight Orchestra</div>
        <div style='font-size:0.95em; color:#4ca1af; font-weight:500;'>Multi-Agent Data Analysis</div>
    </div>
""", unsafe_allow_html=True)

with st.sidebar:
    # --- Session Context Card ---
    st.markdown("### 💬 Session Context")
    if st.session_state.get('file_path'):
        file_name = st.session_state.get('file_path').split('/')[-1]
        st.markdown(f"""
            <div class='session-context'>
                <b>File:</b> {file_name}<br>
                <b>Messages:</b> {len(st.session_state.get('nlq_history', []))}
            </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.get('nlq_history'):
            with st.expander("📜 Conversation History", expanded=False):
                for i, (q, a) in enumerate(st.session_state['nlq_history']):
                    st.markdown(f"**Q{i+1}:** {q[:50]}...")
    
    st.markdown("---")
    
    # --- Navigation ---
    section = st.radio(
        "Navigation",
        ["Upload & Status", "Agent Feed", "Summary & Q&A", "Visualizations", "Download Report"],
        index=0,
        key="nav_radio",
        help="Navigate between workflow steps.",
        label_visibility="collapsed",
    )
    
    st.markdown("---")
    
    # --- Help Section ---
    with st.expander("❓ Help & Guide", expanded=False):
        st.markdown("""
        **How to use:**
        1. Upload a CSV or connect to BigQuery.
        2. Run analysis.
        3. Ask questions in natural language.
        4. Toggle "Show Code" to see generated Python.
        5. Edit code and re-run for custom queries.
        """)
    
    # --- Clear Session ---
    if st.button("🗑️ Clear Session"):
        st.session_state['nlq_history'] = []
        st.session_state['session_id'] = None
        st.session_state['edited_code'] = {}
        st.rerun()
    
    st.markdown("---")
    
    # --- Sidebar Footer ---
    st.markdown("""
        <div style='text-align:center; color:#bbb; font-size:0.93em;'>
            Made with ♥ by the Insight Orchestra team<br>
            <a href='https://github.com/laban254' target='_blank' style='color:#4ca1af;'>GitHub</a>
        </div>
    """)

# --- Hero Section ---
st.markdown("""
<div style='padding:2.5rem 0 1.5rem 0; text-align:center; background: linear-gradient(90deg, #e0eafc 0%, #cfdef3 100%); border-radius: 18px; margin-bottom: 2rem;'>
    <h1 style='font-size:2.8rem; margin-bottom:0.2em;'>Insight Orchestra 2.0 🎻</h1>
    <span style='font-size:1.3rem; color:#2c3e50;'>AI-powered, multi-agent data analysis for everyone.<br>Upload, explore, ask, and understand your data—instantly.</span>
</div>
""", unsafe_allow_html=True)

# --- Progress Bar ---
progress_steps = ["Upload", "Analyze", "Agent Feed", "Summary & Q&A", "Visualizations", "Download"]
progress_idx = progress_steps.index(section.split(" & ")[0]) if section.split(" & ")[0] in progress_steps else 0
st.markdown(f"""
    <style>
    .progress-container {{display: flex; justify-content: space-between; margin-bottom: 1.5em;}}
    .progress-step {{flex: 1; text-align: center; font-weight: 600; color: #4ca1af;}}
    .progress-step.active {{color: #fff; background: #4ca1af; border-radius: 8px; padding: 0.3em 0;}}
    </style>
""", unsafe_allow_html=True)
progress_html = "<div class='progress-container'>"
for i, step in enumerate(progress_steps):
    cls = "progress-step active" if i == progress_idx else "progress-step"
    progress_html += f"<div class='{cls}'>{step}</div>"
progress_html += "</div>"
st.markdown(progress_html, unsafe_allow_html=True)

# --- Upload & Status Section ---
if section == "Upload & Status":
    st.header("1. Choose Data Source 🗂️")
    data_source = st.radio(
        "Select data source:",
        ["CSV Upload", "Google BigQuery"],
        horizontal=True,
        key="data_source_radio"
    )
    
    if data_source == "CSV Upload":
        uploaded_file = st.file_uploader(
            "Drag and drop file here",
            type=["csv"],
            help="Limit 200MB per file • CSV"
        )
        if uploaded_file is not None:
            with st.spinner("Uploading file to backend..."):
                files = {"file": (uploaded_file.name, uploaded_file, "text/csv")}
                resp = requests.post(f"{BACKEND_URL}/upload", files=files)
                if resp.status_code == 200:
                    st.session_state['file_path'] = resp.json()['file_path']
                    st.session_state['nlq_history'] = []  # Reset chat history
                    st.success("File uploaded! Ready to analyze.")
                else:
                    st.error(f"Upload failed: {resp.text}")
        else:
            st.info("Awaiting file upload.")
    else:
        st.markdown("""
        **Connect to Google BigQuery**
        Paste your [service account JSON](https://console.cloud.google.com/apis/credentials/serviceaccountkey) and enter your SQL query below.
        """, unsafe_allow_html=True)
        credentials_json = st.text_area("Service Account JSON", height=150, key="bq_creds")
        bq_query = st.text_area("BigQuery SQL Query", key="bq_query")
        if st.button("Fetch from BigQuery", use_container_width=True):
            if not credentials_json.strip() or not bq_query.strip():
                st.error("Please provide both credentials and a query.")
            else:
                with st.spinner("Querying BigQuery and loading data..."):
                    resp = requests.post(f"{BACKEND_URL}/bigquery", json={"credentials_json": credentials_json, "query": bq_query})
                    if resp.status_code == 200:
                        data = resp.json()
                        st.session_state['file_path'] = data['file_path']
                        st.session_state['nlq_history'] = []
                        st.success(f"BigQuery data loaded! {data['row_count']} rows, {len(data['columns'])} columns. Ready to analyze.")
                    else:
                        st.error(f"BigQuery fetch failed: {resp.text}")
    
    if st.session_state.get('file_path'):
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Run Analysis 🎬", use_container_width=True):
            with st.spinner("Agents are working their magic..."):
                resp = requests.post(f"{BACKEND_URL}/process", json={"file_path": st.session_state['file_path']})
                if resp.status_code == 200:
                    st.session_state['results'] = resp.json()
                    st.success("Analysis complete! Switch to Agent Feed or Visualizations.")
                else:
                    st.error(f"Analysis failed: {resp.text}")

# --- Agent Feed Section ---
if section == "Agent Feed" and st.session_state.get('results'):
    results = st.session_state['results']
    st.header("Agent Feed 🧑‍💻")
    with st.expander("Data Janitor 🧹", expanded=True):
        st.json(results['cleaner']['report'])
    with st.expander("Hypothesis Bot 🤔", expanded=False):
        st.json(results['hypothesis']['hypotheses'])
    with st.expander("Debate Manager 🗣️", expanded=False):
        debate = results['debate']['summary']
        st.markdown(f"""
            <div style='background: linear-gradient(90deg, #e0eafc 0%, #cfdef3 100%); border-radius: 12px; padding: 1.2em 1em; margin-bottom: 1em; box-shadow: 0 2px 8px #e0eafc;'>
                <h4 style='margin-bottom:0.5em;'>Consensus Hypothesis 🏆</h4>
                <span style='font-size:1.1em; color:#2c3e50;'><b>{debate['consensus']['hypothesis']}</b></span><br>
                <span style='color:#888;'>Business Value:</span> <b>{debate['consensus']['business_value']:.2f}</b><br>
                <span style='color:#888;'>Confidence:</span> <b>{debate['consensus']['confidence']*100:.1f}%</b>
            </div>
        """, unsafe_allow_html=True)
        st.progress(debate['consensus']['confidence'], text="Consensus Confidence")
        st.caption("Business value and confidence are scored from 0 to 1.")
        st.markdown("---")
        st.json(debate)

# --- Summary & Q&A Section (With Transparent Code) ---
if section == "Summary & Q&A" and st.session_state.get('results'):
    results = st.session_state['results']
    st.header("📝 Automated Insight Summary")
    if st.button("Generate Summary", key="summary_btn") or "insight_summary" not in st.session_state:
        with st.spinner("Summarizing insights..."):
            resp = requests.post(f"{BACKEND_URL}/summarize", json={"workflow_results": results})
            if resp.status_code == 200:
                st.session_state["insight_summary"] = resp.json().get("summary", "No summary available.")
            else:
                st.session_state["insight_summary"] = "Summary generation failed."
    
    if st.session_state.get("insight_summary"):
        st.markdown(f"""
            <div style='background:#fff; border-radius:12px; box-shadow:0 2px 8px #e0eafc; padding:1.2em 1em; margin-bottom:1em;'>
                <b>Summary:</b> {st.session_state.get("insight_summary")}
            </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    st.header("💬 Ask a Question About Your Data")
    
    # --- NLQ Input with Transparent Code ---
    nlq_input = st.text_input("Type your question and press Enter", key="nlq_input", 
                              placeholder="e.g., Show me sales trends by region...")
    
    if nlq_input:
        with st.spinner("Generating code and executing..."):
            payload = {
                "file_path": st.session_state['file_path'],
                "question": nlq_input,
                "session_id": st.session_state.get('session_id')
            }
            resp = requests.post(f"{BACKEND_URL}/nlq", json=payload)
            
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("answer", "No answer.")
                code = data.get("code", "")
                reasoning = data.get("reasoning", "")
                plot_json = data.get("plot_json")
                
                # Store in history
                st.session_state["nlq_history"].append({
                    "question": nlq_input,
                    "answer": answer,
                    "code": code,
                    "reasoning": reasoning,
                    "plot_json": plot_json
                })
                
                # Update session ID if provided
                if data.get("session_id"):
                    st.session_state['session_id'] = data["session_id"]
            else:
                st.error(f"Query failed: {resp.text}")
    
    # --- Display Conversation with Transparent Code ---
    for i, item in enumerate(reversed(st.session_state.get("nlq_history", []))):
        st.markdown(f"""
            <div style='background:#fff; border-radius:10px; box-shadow:0 2px 8px #e0eafc; padding:1em; margin-bottom:1em;'>
                <b style='color:#2c3e50;'>You:</b> {item['question']}<br><br>
                <b style='color:#4ca1af;'>🤖 Orchestra:</b> {item['answer']}
            </div>
        """, unsafe_allow_html=True)
        
        # --- Transparent Code Toggle ---
        if item.get('code'):
            with st.expander("🔧 Show Generated Code", expanded=False):
                st.markdown(f"""
                    <div class='transparent-code'>{item['code']}</div>
                    <button onclick="navigator.clipboard.writeText({json.dumps(item['code'])})" 
                            style='background:#4ca1af; color:#fff; border:none; border-radius:6px; padding:0.5em 1em; margin-top:0.5em; cursor:pointer;'>
                        📋 Copy Code
                    </button>
                """, unsafe_allow_html=True)
                
                # --- Edit & Re-run ---
                st.markdown("### ✏️ Edit & Re-run")
                edited_code = st.text_area(
                    "Edit the code below:",
                    value=item['code'],
                    height=150,
                    key=f"edit_code_{i}"
                )
                
                if st.button("▶️ Run Edited Code", key=f"run_edited_{i}"):
                    st.info("Code execution from frontend coming soon!")
        
        # --- Render Plot if available ---
        if item.get('plot_json'):
            try:
                fig = pio.from_json(item['plot_json'])
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.warning(f"Could not render chart: {e}")
        
        st.markdown("<hr style='margin:1em 0;'>", unsafe_allow_html=True)

# --- Visualizations Section ---
if section == "Visualizations" and st.session_state.get('results'):
    results = st.session_state['results']
    st.header("Viz Whiz 📊")
    viz = results['viz']
    chart_info = viz.get('chart_info', {})
    
    if chart_info.get('success') and chart_info.get('plots'):
        plots = chart_info['plots']
        st.subheader(f"Auto-generated Visualizations ({len(plots)})")
        
        plot_type_icons = {
            'scatter': '🔵',
            'density_heatmap': '🌡️',
            'box': '📦',
            'violin': '🎻',
            'histogram': '📊',
            'bar': '🟩',
            'line': '📈',
            'pie': '🥧',
            'area': '⛰️',
        }
        
        grouped = defaultdict(list)
        for i, plot in enumerate(plots):
            grouped[plot.get('type', 'Other')].append((i, plot))
        
        available_types = list(grouped.keys())
        type_labels = [f"{plot_type_icons.get(pt, '📈')} {pt.capitalize()}" for pt in available_types]
        
        selected_type_idx = st.selectbox(
            "Select plot type:",
            options=range(len(available_types)),
            format_func=lambda i: type_labels[i],
            key="plot_type_selectbox"
        )
        
        selected_type = available_types[selected_type_idx]
        plot_list = grouped[selected_type]
        plot_titles = [f"{plot_type_icons.get(selected_type, '📈')} {plot[1].get('title', selected_type)}" for plot in plot_list]
        
        selected_plot_idx = st.selectbox(
            f"Select a {selected_type} plot:",
            options=range(len(plot_list)),
            format_func=lambda i: plot_titles[i],
            key=f"{selected_type}_plot_selectbox"
        )
        
        plot = plot_list[selected_plot_idx][1]
        icon = plot_type_icons.get(selected_type, '📈')
        
        plot_col, meta_col = st.columns([3, 1])
        with plot_col:
            st.markdown(f"""
                <div style='background: #fff; border-radius: 12px; box-shadow: 0 2px 12px #e0eafc; padding: 1.5em 1.5em 1em 1.5em; margin-bottom: 1em;'>
                    <h3 style='margin-bottom:0.5em;'>{icon} {plot.get('title', plot.get('type', 'Chart'))}</h3>
                    <span style='color:#888;font-size:1em;'>Type: <b>{plot.get('type', 'Chart').capitalize()}</b></span>
                </div>
            """, unsafe_allow_html=True)
            
            fig = pio.from_json(plot['plotly_json'])
            st.plotly_chart(fig, use_container_width=True)
            
            # --- Chart Recommendations ---
            recs = {
                'scatter': "Best for showing relationships between two numeric variables.",
                'density_heatmap': "Great for visualizing the concentration of data points.",
                'box': "Ideal for comparing distributions and spotting outliers.",
                'violin': "Shows distribution shape and spread across categories.",
                'histogram': "Best for understanding the distribution of a single variable.",
                'bar': "Great for comparing quantities across categories.",
                'line': "Best for trends over time or ordered data.",
                'pie': "Good for showing proportions (use sparingly).",
                'area': "Useful for showing cumulative totals over time."
            }
            st.info(recs.get(selected_type, "This chart type helps you explore your data."))
            
            # --- Explain Chart ---
            if st.button("Explain This Chart", key=f"explain_{selected_type}_{selected_plot_idx}"):
                with st.spinner("Explaining..."):
                    resp = requests.post(f"{BACKEND_URL}/explain", json={"plot": plot})
                    if resp.status_code == 200:
                        st.session_state["explanation"] = resp.json().get("explanation", "No explanation.")
                    else:
                        st.session_state["explanation"] = "Explanation failed."
            
            if "explanation" in st.session_state:
                st.info(st.session_state["explanation"])
            
            st.markdown("**Next step:** Ask a question about this chart in the 'Summary & Q&A' section!")
        
        with meta_col:
            st.markdown("#### ℹ️ Plot Details")
            st.write(f"**Type:** {plot.get('type', 'Chart').capitalize()}")
            st.write(f"**Title:** {plot.get('title', plot.get('type', 'Chart'))}")
            if 'x' in plot:
                st.write(f"**X:** {plot['x']}")
            if 'y' in plot:
                st.write(f"**Y:** {plot['y']}")
            st.write(f"**Index:** {plot_list[selected_plot_idx][0]+1} of {len(plots)}")
            
            with st.expander("Show full metadata", expanded=False):
                st.json({k: v for k, v in plot.items() if k != 'plotly_json'})
        
        st.divider()
    else:
        st.warning(chart_info.get('error', "No chart could be generated. Try uploading different data."))

# --- Download Report Section ---
if section == "Download Report" and st.session_state.get('results'):
    st.header("📥 Download Full Report")
    
    if st.button("Generate & Download Report (HTML)", key="download_report_btn"):
        with st.spinner("Generating report..."):
            resp = requests.post(f"{BACKEND_URL}/report", json={"workflow_results": st.session_state['results']})
            if resp.status_code == 200:
                url = resp.json().get("report_url")
                if url:
                    st.success("Report ready! Click the link below to download.")
                    st.markdown(f"[Download Report]({url})", unsafe_allow_html=True)
                else:
                    st.error("Report generation failed.")
            else:
                st.error("Report generation failed.")
    
    st.info("The report includes all insights, hypotheses, and visualizations from your session.")
