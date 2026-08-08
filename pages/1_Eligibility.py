"""Dedicated Streamlit page for advance eligibility."""

import streamlit as st

from dashboard import apply_dashboard_styles, render_eligibility, render_footer, render_navigation


st.set_page_config(page_title="Eligibility · Financial Wellness Lab", page_icon="✅", layout="wide")
apply_dashboard_styles()
render_navigation("Advance eligibility")
st.markdown('<div class="hero-kicker">Policy Evaluation</div>', unsafe_allow_html=True)
st.title("Advance eligibility review")
st.markdown(
    '<div class="hero-copy">Review an applicant scenario against policy rules '
    'and receive a complete, explainable decision with deterministic audit details.</div>',
    unsafe_allow_html=True,
)
render_eligibility()
render_footer()
