import streamlit as st
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from sympy import symbols, Eq, plot as symplot
import numpy as np
import io
import re
import math

def render_matplotlib_image(code, question_id, block_id):
    plt.close('all')
    code = re.sub(r"plt\.show\(\)", "", code)

    # Prepare execution environment
    exec_globals = {
        "plt": plt,
        "np": np,
        "math": math,
        "io": io,
        "__builtins__": __builtins__,
    }

    try:
        exec(code, exec_globals)
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=200, bbox_inches='tight')
        buffer.seek(0)
        st.image(buffer, caption=f"Diagram for {question_id} - Block {block_id}", use_container_width=True)
    except Exception as e:
        st.error(f"Matplotlib rendering failed: {e}")


def render_plotly_image(code, question_id, block_id):
    try:
        exec_globals = {
            "go": go,
            "np": np,
            "__builtins__": __builtins__,
        }
        local_vars = {}
        exec(code, exec_globals, local_vars)
        fig = local_vars.get("fig")
        if isinstance(fig, go.Figure):
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No Plotly figure (fig) found.")
    except Exception as e:
        st.error(f"Plotly rendering failed: {e}")

def extract_and_render_diagrams(json_data):
    st.title("Generated Diagrams")

    for item in json_data:
        question_id = item.get('question_id')
        generated_prompt = item.get('generated_prompt', '')

        # Multiple language block styles supported
        blocks = re.findall(r"```(python|plotly)(.*?)```", generated_prompt, re.DOTALL)
        if not blocks:
            st.warning(f"No valid code found for question ID: {question_id}")
            continue

        st.subheader(f"Diagram for {question_id}")
        for i, (lang, code) in enumerate(blocks):
            code = code.strip()
            if lang == "plotly":
                render_plotly_image(code, question_id, i+1)
            else:
                render_matplotlib_image(code, question_id, i+1)
