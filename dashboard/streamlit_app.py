import streamlit as st

st.set_page_config(
    page_title="SEMS Dashboard",
    page_icon="🎓",
    layout="wide"
)

st.title("🎓 SEMS Dashboard")

st.markdown("""
Welcome to the AI-Based Education Recommendation System.

Use the sidebar to navigate between modules.
""")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Study Hours", "32 hrs")

with col2:
    st.metric("Current Streak", "5 Days 🔥")

with col3:
    st.metric("Productivity", "87%")