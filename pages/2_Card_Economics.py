"""Dedicated Streamlit page for card-program strategy."""

import streamlit as st

from dashboard import apply_dashboard_styles, render_card_economics, render_footer, render_navigation


st.set_page_config(page_title="Card Economics · Financial Wellness Lab", page_icon="📊", layout="wide")
apply_dashboard_styles()
render_navigation("Card strategy")
st.markdown('<div class="hero-kicker">Portfolio strategy</div>', unsafe_allow_html=True)
st.title("Select the card model that creates the strongest risk-adjusted contribution")
st.markdown(
    "A conclusion-led comparison of partner and direct-issuance models across "
    "economics, launch speed, and balance-sheet exposure."
)
render_card_economics()
render_footer()
