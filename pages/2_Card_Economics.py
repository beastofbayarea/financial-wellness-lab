"""Dedicated Streamlit page for card-program strategy."""

import streamlit as st

from dashboard import apply_dashboard_styles, render_card_economics, render_footer, render_navigation


st.set_page_config(page_title="Card Economics · Financial Wellness Lab", page_icon="📊", layout="wide")
apply_dashboard_styles()
render_navigation("Card strategy")
st.title("Card program strategy")
st.markdown(
    "Compare issuance models against your portfolio assumptions, economics, and "
    "investment criteria."
)
render_card_economics()
render_footer()
