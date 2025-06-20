import streamlit as st
import requests
import plotly.io as pio
import plotly.graph_objs as go
from collections import defaultdict

BACKEND_URL = "http://localhost:8000"

# --- Modern Page Config ---
st.set_page_config(page_title="Insight Orchestra 2.0", layout="wide", page_icon="🎻")

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
    </style>
""", unsafe_allow_html=True)

# --- Hero Section ---
st.markdown("""
<div style='padding:2.5rem 0 1.5rem 0; text-align:center; background: linear-gradient(90deg, #e0eafc 0%, #cfdef3 100%); border-radius: 18px; margin-bottom: 2rem;'>
    <h1 style='font-size:2.8rem; margin-bottom:0.2em;'>Insight Orchestra 2.0 🎻</h1>
    <span style='font-size:1.3rem; color:#2c3e50;'>AI-powered, multi-agent data analysis for everyone.<br>Upload, explore, ask, and understand your data—instantly.</span>
</div>
""", unsafe_allow_html=True)

# --- Sidebar Navigation ---
st.sidebar.image("https://img.icons8.com/ios-filled/100/2c3e50/orchestra.png", width=80)
st.sidebar.title("Navigation")
section = st.sidebar.radio(
    "Go to section:",
    ["Upload & Status", "Agent Feed", "Summary & Q&A", "Visualizations", "Download Report"],
    index=0,
    key="nav_radio"
)

# --- Upload & Status Section ---
if section == "Upload & Status":
    st.header("1. Upload your CSV 🗂️")
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
                st.success("File uploaded! Ready to analyze.")
            else:
                st.error(f"Upload failed: {resp.text}")
    else:
        st.info("Awaiting file upload.")
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

# --- Summary & Q&A Section ---
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
    st.info(st.session_state.get("insight_summary", "Click 'Generate Summary' to see insights."))
    st.divider()
    st.header("💬 Ask a Question About Your Data")
    if "nlq_history" not in st.session_state:
        st.session_state["nlq_history"] = []
    nlq_input = st.text_input("Type your question and press Enter", key="nlq_input")
    if nlq_input:
        with st.spinner("Thinking..."):
            resp = requests.post(f"{BACKEND_URL}/nlq", json={"file_path": st.session_state['file_path'], "question": nlq_input})
            if resp.status_code == 200:
                answer = resp.json().get("answer", "No answer.")
            else:
                answer = "Sorry, I couldn't answer that."
            st.session_state["nlq_history"].append((nlq_input, answer))
    for q, a in reversed(st.session_state["nlq_history"]):
        st.markdown(f"<div style='margin-bottom:0.5em;'><b style='color:#2c3e50;'>You:</b> {q}<br><b style='color:#4ca1af;'>Orchestra:</b> {a}</div>", unsafe_allow_html=True)
    st.divider()

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
            if st.button("Explain This", key=f"explain_{selected_type}_{selected_plot_idx}"):
                with st.spinner("Explaining..."):
                    resp = requests.post(f"{BACKEND_URL}/explain", json={"plot": plot})
                    if resp.status_code == 200:
                        st.session_state["explanation"] = resp.json().get("explanation", "No explanation available.")
                    else:
                        st.session_state["explanation"] = "Explanation failed."
            if "explanation" in st.session_state:
                st.info(st.session_state["explanation"])
        with meta_col:
            st.markdown("#### ℹ️ Plot Details")
            st.write(f"**Type:** {plot.get('type', 'Chart').capitalize()}")
            st.write(f"**Title:** {plot.get('title', plot.get('type', 'Chart'))}")
            if 'x' in plot:
                st.write(f"**X:** {plot['x']}")
            if 'y' in plot:
                st.write(f"**Y:** {plot['y']}")
            st.write(f"**Index:** {plot_list[selected_plot_idx][0]+1} of {len(plots)}")
            with st.expander("Show full plot metadata", expanded=False):
                st.json({k: v for k, v in plot.items() if k != 'plotly_json'})
        st.divider()
    else:
        st.warning(chart_info.get('error', "No chart could be generated for the selected hypothesis. This may be due to insufficient data, an unsupported hypothesis, or a data processing error."))

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
