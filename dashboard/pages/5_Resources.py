import streamlit as st

st.title("📚 Resources")

uploaded_file = st.file_uploader("Upload Notes/PDF")

if uploaded_file:
    st.success("File uploaded successfully")