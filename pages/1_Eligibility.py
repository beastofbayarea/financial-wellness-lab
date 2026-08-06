"""Dedicated Streamlit page for the eligibility MVP."""

import streamlit as st

from dashboard import apply_dashboard_styles, render_eligibility, render_footer


st.set_page_config(page_title="Eligibility · Financial Wellness Lab", page_icon="✅", layout="wide")
apply_dashboard_styles()
st.title("Eligibility MVP")
st.markdown(
    "Build a synthetic applicant scenario and trace the deterministic rule workflow "
    "from input facts to an approval limit or actionable denial reasons."
)
render_eligibility()
render_footer()
