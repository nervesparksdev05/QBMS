import requests
import json
import os
import re
from pathlib import Path
import traceback
from utils.generate_diagram import extract_and_render_diagrams

def load_prompt_template(template_file):
    """Load prompt template from file"""
    template_path = os.path.join("prompts", template_file)
    try:
        with open(template_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        # If template file doesn't exist yet, return a default template
        if template_file == "question_gen.txt":
            return """You are an expert question generator for educational purposes.
Generate {num_questions} questions based on the provided content.
The questions should be of varying difficulty: {difficulty_distribution}
Subject: {subject}

Content:
{content}

Generate questions in the following JSON format:
{
  "questions": [
    {
      "id": "q1",
      "question": "Question text here",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "Option A",
      "difficulty": "easy|medium|hard",
      "source": "Chapter 1",
      "requires_diagram": true , it will always true,
      "diagram_description": "Detailed description of what the diagram should show "
    }
  ]
}

IMPORTANT GUIDELINES:
1. By default, set requires_diagram to true for all questions
2. Include detailed and clear diagram_description fields even if requires_diagram is false - these will be used later if the user chooses to add a diagram
3. For physics and math questions, include coordinate systems, measurements, and specific details in the diagram_description
4. Format your response as a valid JSON object as shown above

Respond ONLY with the JSON, no explanations or additional text.
"""
        elif template_file == "diagram_gen.txt":
            return """Generate Python matplotlib code for a diagram with the following description:
Description: {description}
Subject area: {subject}
Question context: {question}

Return Python code using matplotlib that creates an educational-quality diagram matching the description. The code should:
- Use appropriate figure size (e.g., plt.figure(figsize=(3, 2))) suitable for exam papers.
- Include clear labels for axes, titles, and key elements (e.g., plt.xlabel(), plt.ylabel(), plt.title()).
- Use numpy for any necessary calculations (e.g., data points, scales).
- Add grid lines (plt.grid(True)) where relevant to aid understanding.
- Use distinct colors and line styles for different elements to enhance clarity.
- Include legends if multiple data series or elements are present (plt.legend()).
- Ensure all text (labels, titles) is legible with appropriate font sizes (e.g., 10-12 pt).
- Avoid unnecessary complexity; focus on essential elements described.
- Optimize for a small size (e.g., 30-150 pixel width when rendered) while maintaining readability.

Example structure:
```python
import matplotlib.pyplot as plt
import numpy as np

# Set up figure
plt.figure(figsize=(3, 2))

# Plot data or elements
# (e.g., plt.plot(), plt.hlines(), etc.)

# Add labels and annotations
plt.xlabel('X-axis label')
plt.ylabel('Y-axis label')
plt.title('Diagram Title')
plt.grid(True)

# Save or display (handled by rendering function)
"""

def generate_questions(content, subject, num_questions, difficulty_distribution):
    try:
        # Format difficulty distribution for prompt
        difficulty_format = ", ".join([f"{count} {level}" for level, count in difficulty_distribution.items()])
        
        # Format content for prompt
        content_formatted = "\n\n".join([f"--- {('Chapter' if len(content) > 1 else 'Page')} {num} ---\n{text}" 
                                      for num, text in content.items()])
        
        # Load question generation prompt template
        template = load_prompt_template("question_gen.txt")
        
        # Format prompt
        prompt = template.format(
            num_questions=num_questions,
            difficulty_distribution=difficulty_format,
            subject=subject,
            content=content_formatted
        )

        print("prompt ->", prompt)
        
        # Call Ollama API
        response = requests.post('http://192.168.31.137:11434/api/generate', 
                               json={
                                   "model": "gemme3:4b",
                                   "prompt": prompt,
                                   "stream": False
                               })
        
        if response.status_code == 200:
            response_data = response.json()
            # Extract JSON from response
            print("response_data", response_data)
            generated_text = response_data.get('response', '')
            
            json_match = re.search(r'```json\s*(.+?)\s*```', generated_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON without code blocks
                json_match = re.search(r'(\{.*"questions":\s*\[.+?\]\s*\})', generated_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = generated_text
            
            try:
                # Parse JSON
                result = json.loads(json_str)
                questions = result.get('questions', [])
                print("questions", questions)
                
                # Ensure each question has required fields
                for i, question in enumerate(questions):
                    if 'id' not in question:
                        question['id'] = f"q{i+1}"
                    if 'requires_diagram' not in question:
                        question['requires_diagram'] = False
                    if 'diagram_description' not in question:
                        question['diagram_description'] = f"Diagram for question: {question['question']}"
                    # Add a new field to track if user has selected this question for diagram generation
                    question['user_selected_for_diagram'] = False
                
                return questions
            except json.JSONDecodeError:
                print("Failed to parse JSON from model response")
                print("Response:", generated_text[:500])  # Print part of the response for debugging
                return []
        
        else:
            print(f"Error calling Ollama API: {response.status_code}")
            print(response.text)
            return []
            
    except Exception as e:
        print(f"Error generating questions: {str(e)}")
        traceback.print_exc()
        return []

def update_questions_with_user_selections(questions, selected_question_ids):
    for question in questions:
        question_id = question.get('id')
        if question_id in selected_question_ids:
            question['user_selected_for_diagram'] = True
        else:
            question['user_selected_for_diagram'] = False
    
    return questions

def generate_diagrams_for_selected_questions(questions):
    """
    Generate diagrams only for questions that have been selected by the user
    
    Args:
        questions (list): List of question dictionaries
        
    Returns:
        dict: Dictionary mapping question IDs to LaTeX diagram code
    """
    diagrams = {}
    
    for question in questions:
        if question.get('user_selected_for_diagram', False):
            question_id = question.get('id')
            latex_code = generate_diagram_for_question(question)
            if latex_code:
                diagrams[question_id] = latex_code
    
    return diagrams

def generate_diagram_for_question(question):
    """
    Generate matplotlib Python code for a single question
    
    Args:
        question (dict): Question dictionary with diagram description
        
    Returns:
        str: Python matplotlib code for the diagram
    """
    try:
        description = question.get('diagram_description', '')
        q_text = question.get('question', '')
        subject = question.get('subject', 'Physics')
        
        template = load_prompt_template("diagram_gen.txt")
        
        prompt = template.format(
            description=description,
            subject=subject,
            question=q_text
        )
        
        print(f"Generating diagram for question {question.get('id')}: {q_text[:50]}...")
        
        response = requests.post('http://192.168.31.137:11434/api/generate', 
                               json={
                                   "model": "gemme3:4b",
                                   "prompt": prompt,
                                   "stream": False
                               })
        
        if response.status_code == 200:
            response_data = response.json()
            matplotlib_code = response_data.get('response', '')
            
            # Remove any code block markers if present
            matplotlib_code = re.sub(r'```python\s*|\s*```', '', matplotlib_code)
            matplotlib_code = matplotlib_code.strip()
            
            return matplotlib_code
        else:
            print(f"Error calling Ollama API: {response.status_code}")
            print(response.text)
            return ""
            
    except Exception as e:
        print(f"Error generating diagram: {str(e)}")
        traceback.print_exc()
        return ""

def render_diagrams_for_questions(questions, diagrams):
    """
    Render generated LaTeX diagrams for questions
    
    Args:
        questions (list): List of question dictionaries
        diagrams (dict): Dictionary mapping question IDs to LaTeX code
        
    Returns:
        dict: Dictionary mapping question IDs to rendered diagram paths
    """
    rendered_diagrams = {}
    
    for question_id, latex_code in diagrams.items():
        try:
            # Create a temporary file with the LaTeX code
            diagram_path = extract_and_render_diagrams(latex_code, question_id)
            if diagram_path:
                rendered_diagrams[question_id] = diagram_path
        except Exception as e:
            print(f"Error rendering diagram for question {question_id}: {str(e)}")
            traceback.print_exc()
    
    return rendered_diagrams

def generate_solutions(questions):
    """
    Generate solutions for questions using Gemma 3:27b model via Ollama
    
    Args:
        questions (list): List of question dictionaries
    
    Returns:
        dict: Dictionary mapping question IDs to solutions
    """
    try:
        # Format questions for prompt
        questions_formatted = json.dumps(questions, indent=2)
        
        # Load solution generation prompt template
        template = load_prompt_template("solution_gen.txt")
        
        # Check if the template contains tikzpicture placeholder
        if "{tikzpicture}" in template:
            # Format prompt with both placeholders
            prompt = template.format(questions=questions_formatted, tikzpicture="\\begin{tikzpicture}...\\end{tikzpicture}")
        else:
            # Format prompt with just the questions
            prompt = template.format(questions=questions_formatted)
        
        # Print debug info
        print(f"=================================================> solutions generation")
        
        # Call Ollama API with timeout
        response = requests.post('http://192.168.31.137:11434/api/generate', 
                               json={
                                   "model": "gemme3:4b",
                                   "prompt": prompt,
                                   "stream": False
                               },
                               timeout=60)  # Add timeout
        
        if response.status_code == 200:
            response_data = response.json()
            # Process response and return solutions
            generated_text = response_data.get('response', '')
            
            # Extract JSON from response
            json_match = re.search(r'```json\s*(.+?)\s*```', generated_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON without code blocks
                json_match = re.search(r'(\{.+\})', generated_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = generated_text
            
            try:
                solutions = json.loads(json_str)
                return solutions
            except json.JSONDecodeError:
                print("Failed to parse JSON from model response for solutions")
                print("Response:", generated_text[:500])  # Print part of the response for debugging
                return {}
        else:
            print(f"Error calling Ollama API for solutions: {response.status_code}")
            print(response.text)
            return {}
            
    except Exception as e:
        print(f"Error generating solutions: {str(e)}")
        traceback.print_exc()
        return {}