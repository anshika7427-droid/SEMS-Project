import streamlit as st

st.title("⏳ Focus Timer")

minutes = st.number_input("Pomodoro Minutes", 1, 60, 25)

if st.button("Start Session"):
    st.success(f"Focus session started for {minutes} minutes.")