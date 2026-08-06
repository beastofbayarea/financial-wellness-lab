"""Dedicated Streamlit page for the card-economics MVP."""

import streamlit as st

from dashboard import apply_dashboard_styles, render_card_economics, render_footer


st.set_page_config(page_title="Card Economics · Financial Wellness Lab", page_icon="📊", layout="wide")
apply_dashboard_styles()
st.title("Card Economics MVP")
st.markdown(
    "Change a synthetic portfolio and its walk-away gates, then trace how the "
    "deterministic model ranks viable issuance paths."
)
render_card_economics()
render_footer()
