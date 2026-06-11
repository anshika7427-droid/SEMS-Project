import streamlit as st

st.title("📊 Dashboard")

st.subheader("Student Overview")

col1, col2 = st.columns(2)

with col1:
    st.info("Current CGPA: 8.5")

with col2:
    st.success("Target Study Hours Completed")

st.progress(75)

st.write("Weekly performance tracking coming soon...")