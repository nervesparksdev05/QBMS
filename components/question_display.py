import streamlit as st

# Function to display questions with diagrams
def display_questions_with_selection(questions, show_diagrams=True, enable_selection=False, context_prefix=""):
    selected_questions = []
    
    for i, question in enumerate(questions):
        question_id = question.get('id', f'q{i+1}')
        
        # Use context_prefix to make checkbox keys unique across different contexts
        unique_key = f"{context_prefix}_select_{question_id}" if context_prefix else f"select_{question_id}"
        
        with st.expander(f"Question {i+1} ({question.get('difficulty', 'medium').capitalize()})"):
            if enable_selection:
                has_diagram = question.get('requires_diagram', False)
                checkbox_label = "Generate diagram for this question" if not has_diagram else "Regenerate diagram"
                is_selected = st.checkbox(checkbox_label, key=unique_key)  # Use the unique key here
                if is_selected:
                    selected_questions.append(question_id)
            
            # Rest of your function remains the same
            st.markdown(f"**{question['question']}**")
            
            # ... (rest of the function)
    
    return selected_questions