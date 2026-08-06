"""Dedicated Streamlit page for the eligibility MVP."""

import streamlit as st

from dashboard import apply_dashboard_styles, render_eligibility, render_footer, render_navigation


st.set_page_config(page_title="Eligibility · Financial Wellness Lab", page_icon="✅", layout="wide")
apply_dashboard_styles()
render_navigation("Advance eligibility")
st.title("Advance eligibility")
st.markdown(
    "Review an applicant scenario against the current advance policy and receive "
    "a complete, explainable decision."
)
render_eligibility()
render_footer()
