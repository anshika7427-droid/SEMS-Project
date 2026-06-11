import streamlit as st

st.title("🗓️ Smart Scheduler")

subject = st.text_input("Enter Subject")

hours = st.slider("Study Hours", 1, 10)

if st.button("Generate Schedule"):
    st.success(f"{subject} scheduled for {hours} hours.")