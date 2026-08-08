"""Dedicated Streamlit page for card-program strategy."""

import streamlit as st

from dashboard import apply_dashboard_styles, render_card_economics, render_footer, render_navigation


st.set_page_config(page_title="Card Economics · Financial Wellness Lab", page_icon="📊", layout="wide")
apply_dashboard_styles()
render_navigation("Card strategy")
st.markdown('<div class="hero-kicker">Portfolio Strategy & Economics</div>', unsafe_allow_html=True)
st.title("Card program issuance strategy")
st.markdown(
    '<div class="hero-copy">Compare operating models across annual contribution, launch velocity, '
    'balance sheet exposure, and strategic criteria.</div>',
    unsafe_allow_html=True,
)
render_card_economics()
render_footer()
