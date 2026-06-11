import streamlit as st
import pandas as pd

st.title("📈 Analytics")

data = pd.DataFrame({
    "Day": ["Mon", "Tue", "Wed", "Thu", "Fri"],
    "Hours": [2, 4, 5, 3, 6]
})

st.line_chart(data.set_index("Day"))