import streamlit as st

def create_difficulty_selector(total_questions):
    st.subheader("Difficulty Distribution")

    # Initialize difficulty counts in session state if not already present
    if "easy_count" not in st.session_state:
        st.session_state.easy_count = 0
    if "medium_count" not in st.session_state:
        st.session_state.medium_count = 0
    if "hard_count" not in st.session_state:
        st.session_state.hard_count = total_questions
    
    # Define callback functions to maintain consistent state
    def update_easy():
        # When easy count changes, adjust other counts
        medium = st.session_state.medium_count_input
        easy = st.session_state.easy_count_input
        
        # Ensure we don't exceed total
        if easy + medium > total_questions:
            medium = total_questions - easy
        
        # Update session state
        st.session_state.easy_count = easy
        st.session_state.medium_count = medium
        st.session_state.hard_count = total_questions - easy - medium

    def update_medium():
        # When medium count changes, adjust hard count
        easy = st.session_state.easy_count
        medium = st.session_state.medium_count_input
        
        # Ensure we don't exceed total
        if easy + medium > total_questions:
            medium = total_questions - easy
        
        # Update session state
        st.session_state.medium_count = medium
        st.session_state.hard_count = total_questions - easy - medium

    # Create three columns for inputs
    col1, col2, col3 = st.columns(3)

    with col1:
        easy_count = st.number_input(
            "Easy Questions",
            min_value=0,
            max_value=total_questions,
            value=st.session_state.easy_count,
            key="easy_count_input",
            on_change=update_easy,
            help="Questions that test recall and basic understanding"
        )

    with col2:
        medium_max = total_questions - st.session_state.easy_count
        medium_count = st.number_input(
            "Medium Questions",
            min_value=0,
            max_value=medium_max,
            value=min(st.session_state.medium_count, medium_max),
            key="medium_count_input",
            on_change=update_medium,
            help="Questions that test application and analytical skills"
        )

    with col3:
        hard_count = total_questions - st.session_state.easy_count - st.session_state.medium_count
        hard_count = max(0, hard_count)  # Ensure non-negative
        st.number_input(
            "Hard Questions",
            min_value=0,
            max_value=total_questions,
            value=hard_count,
            key="hard_count_display",
            help="Questions that test evaluation and creation skills",
            disabled=True
        )

    # Update session state with the final values
    st.session_state.hard_count = hard_count

    return {
        "easy": st.session_state.easy_count,
        "medium": st.session_state.medium_count,
        "hard": st.session_state.hard_count
    }