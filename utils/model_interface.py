from dotenv import load_dotenv
import requests
import json
import os
import re
import traceback
from utils.generate_diagram import extract_and_render_diagrams
import google.generativeai as genai
import uuid
import subprocess
from together import Together
from collections import Counter
import time
import openai as OpenAI
import random

load_dotenv()

gemma_api_key = os.getenv("GOOGLE_API_KEY")
chatgpt_api_key = os.getenv("CHATGPT_API_KEY")
genai.configure(api_key=gemma_api_key)

DIAGRAM_FOLDER = os.path.join(os.getcwd(), "temp_diagrams")
os.makedirs(DIAGRAM_FOLDER, exist_ok=True)

def load_prompt_template(template_file):
    """Load prompt template from file"""
    # template_path = os.path.join("prompts", template_file)
    # try:
    #     with open(template_path, "r") as f:
    #         return f.read()
    # except FileNotFoundError:
        # If template file doesn't exist yet, return a default template
    if template_file == "question_gen.txt":
            return """You are an expert multiple-choice question (MCQ) generator for educational exams in mathematics and physics.
Generate {num_questions} MCQ questions based on the provided content.
The questions should be of varying difficulty according to Bloom's Taxonomy: {difficulty_distribution}

DIFFICULTY LEVELS (BLOOM'S TAXONOMY):
1. EASY (Remember & Understand): Questions that test recall and basic comprehension of mathematical/physics facts, formulas, and concepts.
   - Remember: Recall formulas, laws, theorems, or basic concepts without applying them
   - Understand: Demonstrate understanding of principles by explaining relationships or giving examples
   - EXAMPLES:
     * "What is the formula for the volume of a sphere?"
     * "Which physical quantity is measured in joules?"
     * "What is the relationship between velocity and acceleration?"
     * "The SI unit for electric current is:"
   - AVOID requiring any complex analysis, interpretation, or multi-step application for EASY questions

2. MEDIUM (Apply & Analyze): Questions that require application of formulas and analytical problem-solving.
   - Apply: Solve problems using equations, formulas, laws and theorems in straightforward applications
   - Analyze: Break down problems into components, determine relationships, and solve multi-step problems
   - EXAMPLES:
     * "A car traveling at 60 km/h accelerates uniformly to 90 km/h in 5 seconds. What is its acceleration?"
     * "If the lateral surface area of a cone is 44π cm² and its radius is 4 cm, what is its height?"
     * "When a force of 20 N is applied to an object with mass 4 kg, what is its acceleration?"
     * "The frequency of a simple pendulum depends on which of the following factors?"
   - MUST involve application of formulas or principles to solve a problem
   - MUST require mathematical calculations or logical reasoning

3. HARD (Evaluate & Create): Questions that require advanced problem-solving, synthesis of multiple concepts, or evaluation of complex scenarios.
   - Evaluate: Make judgments based on criteria, compare solutions, or determine optimal approaches
   - Create: Combine multiple concepts to solve novel problems or derive new formulas/relationships
   - EXAMPLES:
     * "A rocket ejects gas at a rate of 50 kg/s with a velocity of 3000 m/s. If the rocket's initial mass is 10,000 kg, how long will it take to reach 80% of its escape velocity?"
     * "Which combination of materials would create the most efficient heat transfer in this multi-layer insulation system?"
     * "Given that a satellite orbits Earth at 400 km above the surface, calculate the minimum energy required to transfer it to a geosynchronous orbit."
     * "Which of the following modifications to this circuit design would maximize power output while minimizing heat loss?"
   - MUST require synthesis of multiple formulas or concepts
   - MUST involve complex calculations, non-obvious relationships, or multi-step problem-solving
   - Should require deep conceptual understanding and critical thinking

Subject: {subject}

Content:
{content}

MATHEMATICS AND PHYSICS QUESTION GUIDELINES:
1. FOCUS on numerical problems with clear-cut answers (especially for medium and hard questions)
2. INCLUDE all necessary information in the question statement
3. AVOID ambiguous wording or unclear problem statements
4. ENSURE units are consistent and clearly specified
5. PROVIDE sufficient context for the problem without referencing external examples
6. SPECIFY all relevant constraints and conditions
7. CREATE complete, self-contained problems that don't require additional information
8. MAKE diagram descriptions extremely detailed when diagrams are required
9. CALCULATE problems thoroughly to ensure correct answers and distractors

QUESTION INDEPENDENCE GUIDELINES:
1. Each question must be completely standalone and self-contained
2. NEVER reference "examples," "problems," or any external material in the question text
3. NEVER use phrases like "In Example 1" or "From the diagram"
4. REWRITE any problem that depends on external reference as a complete scenario
5. INCLUDE all necessary variables, values, and conditions within the question text
6. ENSURE questions contain all required information to solve them
7. ADDRESS different concepts or applications in each question
8. TRANSFORM problems from the content into new, self-contained scenarios
9. AVOID any implication that the question relates to a previously referenced example

CONTENT RELEVANCE RULES:
1. Questions must be directly related to the concepts in the provided content
2. Questions should test understanding of the same principles covered in the content
3. ADAPT examples from the content into new problems that apply the same concepts
4. ENSURE questions align with the specific field (mathematics/physics) of the content
5. TRANSFORM specific examples from content into general principles
6. CREATE new scenarios that test the same underlying mathematical/physical concepts
7. USE similar complexity/difficulty levels as examples in the content

Generate questions in the following JSON format:
{{
  "questions": [
    {{
      "id": "q1",
      "question": "Complete problem statement including all necessary information",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "Option A",
      "difficulty": "easy" | "medium" | "hard",
      "source_concept": "Mathematical/physical concept from content",
      "diagram_required": true,
      "diagram_description": "Child-friendly, step-by-step drawing instructions with all measurements and details (see ENHANCED DIAGRAM DESCRIPTION GUIDELINES)",
      "bloom_level": "Remember" | "Understand" | "Apply" | "Analyze" | "Evaluate" | "Create",
      "confidence_score": 0.95
    }}
  ]
}}

ENHANCED DIAGRAM DESCRIPTION GUIDELINES:
1. CREATE STEP-BY-STEP DRAWING INSTRUCTIONS that a child could follow:
   - Start with the basic shape or framework (e.g., "First, draw a large circle in the middle of your paper")
   - Add elements one at a time in logical order (e.g., "Next, draw a straight line from the top of the circle to the bottom")
   - Use simple, everyday objects for comparison (e.g., "Draw a triangle about the size of your thumb")

2. USE CHILD-FRIENDLY MEASUREMENTS AND REFERENCES:
   - Relate sizes to common objects (e.g., "Draw a circle about the size of a quarter")
   - Use finger widths or hand spans for approximations (e.g., "Make the line about three finger-widths long")
   - Suggest using everyday tools (e.g., "You can use the bottom of a cup to trace the circle")

3. INCLUDE CLEAR POSITIONING INSTRUCTIONS:
   - Reference parts of the paper (e.g., "Place this in the upper left corner of your paper")
   - Use body-centered directions (e.g., "Draw the square to the right, about as far as your thumb and pointer finger when spread apart")
   - Use clock positions (e.g., "Draw a small circle at the 3 o'clock position of the larger circle")

4. SPECIFY SIMPLE LABELING INSTRUCTIONS:
   - Give clear directions for adding labels (e.g., "Write a big letter A next to the triangle")
   - Suggest using different colors if helpful (e.g., "Color the circle blue and the square red")
   - Keep text simple and minimal (e.g., "Write the number 5 inside the square")

5. INCLUDE ALL MATHEMATICAL DETAILS but explain them simply:
   - Explain angles in relatable terms (e.g., "Make a corner that looks like the corner of a book")
   - Describe mathematical concepts using everyday language (e.g., "The lines should never touch, like train tracks")
   - Include precise measurements but with simple explanations (e.g., "Make the line 5 cm long - that's about the width of three fingers")

6. PROVIDE VERIFICATION STEPS:
   - Include simple checks to ensure accuracy (e.g., "When you're done, you should have 4 circles that are all the same size")
   - Suggest ways to check measurements (e.g., "The triangle should be tall enough to reach from your thumb to your pinky when you spread your fingers")
   - Add confirmation details (e.g., "Your finished drawing should look a bit like a flower with 5 petals")

7. FOR SPECIFIC DIAGRAM TYPES:
   - For geometric shapes: Start with the outline or framework, then add internal elements
   - For graphs: Begin with drawing the axes like a big plus sign, then add points step-by-step
   - For physics diagrams: Start with the main object, then add arrows for forces or motion
   - For circuits: Start with a big loop, then add the battery, then add other components

8. BALANCE SIMPLICITY WITH PRECISION:
   - Include all necessary mathematical information (angles, lengths, coordinates)
   - But express these in child-accessible language and comparisons
   - Always include both the precise measurement AND a child-friendly reference

9. ADD CHECKPOINTS AND ENCOURAGEMENT:
   - Insert verification steps throughout (e.g., "At this point, your drawing should have 3 circles")
   - Include simple encouragement (e.g., "This part might look tricky, but just take it step by step")
   - Provide alternatives for difficult elements (e.g., "If drawing a perfect circle is hard, you can trace something round")

DIAGRAM DESCRIPTION EXAMPLE:
BAD: "A right triangle with sides 3cm, 4cm and 5cm with angle 90° between sides 3cm and 4cm."

GOOD: "Let's draw a special triangle step by step:
1. First, draw a flat line from left to right about as long as your pointer finger (that's 4 cm).
2. At the left end of this line, draw a straight line going up about the size of your thumb (that's 3 cm).
3. Now connect the top point to the right end of the bottom line to finish your triangle.
4. The corner where the bottom and left lines meet should be a perfect square corner, like the corner of a book or sheet of paper (that's 90 degrees).
5. Label the bottom line '4 cm', the left side line '3 cm', and the slanted line '5 cm'.
6. When you're finished, your triangle should look like half a square that's been cut diagonally.
7. Double-check: The bottom line is horizontal, the left line is vertical, and they meet at a square corner."

QUESTION FORMULATION PRINCIPLES FOR MATHEMATICS/PHYSICS:
1. CREATE complete problem statements with all necessary variables and conditions
2. INCLUDE all relevant numeric values and units within the question
3. ENSURE that all information needed to solve the problem is provided
4. FORMULATE questions as stand-alone problems that don't reference external examples
5. ENSURE all required formulas can be applied directly to the information in the question
6. PROVIDE sufficient context without making the question dependent on external information
7. CHECK that the mathematical calculations yield a unique, correct answer
8. VERIFY that distractors are plausible but mathematically incorrect

PROHIBITED PHRASINGS:
1. DO NOT use "In Example X..."
2. DO NOT use "From the diagram..."
3. DO NOT use "In the figure above..."
4. DO NOT use "As shown in the previous problem..."
5. DO NOT use "According to the content..."
6. DO NOT use "As mentioned in the chapter..."
7. DO NOT use "Referring to the given scenario..."
8. DO NOT begin with "Which of the following..."
9. DO NOT use "Based on the information provided..."
10. DO NOT use "In the context of..."

EXAM QUESTION TRANSFORMATION EXAMPLES:
BAD: "In Example 1, what is the height of the conical portion of the playing top?"
GOOD: "A playing top has a conical portion with a base radius of 2 cm and slant height of 6 cm. What is the height of this conical portion?"

BAD: "In Example 2, what area is not included in the surface area calculation of the decorative block?"
GOOD: "A decorative block consists of a cube with a hemisphere mounted on one face. When calculating the total surface area, which part is NOT included?"

BAD: "In Example 3, what color is used to paint the cylindrical portion of the toy rocket?"
GOOD: "A toy rocket has cylindrical body and conical nose. What color is traditionally used to paint the cylindrical portion of model rockets?"

MCQ OPTION GUIDELINES:
1. Include exactly 4 options (A, B, C, D) for each question
2. Ensure all options are plausible but only one is mathematically correct
3. For numerical answers, create distractors from common calculation errors
4. Include distractors that would result from misapplying relevant formulas
5. For conceptual questions, create distractors with plausible but incorrect principles
6. Ensure distractors are within a reasonable range of the correct answer
7. AVOID options that are obviously incorrect or absurd
8. ENSURE correct answers are derived from proper application of mathematical/physical principles
9. DISTRIBUTE correct answers approximately evenly among options A, B, C, and D

CORRECT ANSWER DETERMINATION INSTRUCTIONS:
1. You MUST CALCULATE the answer for every question by working through the complete mathematical solution
2. NEVER guess or estimate the correct answer - always solve the problem completely
3. Verify your calculations to ensure the correct answer is accurate
4. Make sure the correct answer appears among the four options
5. For numerical problems, calculate the exact answer using appropriate formulas and mathematics
6. For conceptual questions, apply relevant principles correctly to determine the answer
7. Double-check that your reasoning follows mathematical/physical laws accurately
8. If the correct answer differs from all four options after calculation, revise the options to include it

IMPORTANT REMINDERS:
1. Questions must be COMPLETELY SELF-CONTAINED with all necessary information
2. Questions should NEVER reference external examples, figures, or content
3. Mathematical and physics problems must be SOLVABLE using only the information provided
4. All measurements, values, and conditions must be EXPLICITLY STATED in the question
5. Diagram descriptions must follow the ENHANCED DIAGRAM DESCRIPTION GUIDELINES for child-friendly instructions
6. Carefully calculate all numerical answers and create plausible distractors
7. Verify that each question tests concepts from the content but stands entirely on its own
8. DO NOT include solution explanations in the output, but ensure correct answers are properly calculated

Respond ONLY with the JSON, no explanations or additional text.
"""
    elif template_file == "question_gen_non_math.txt":
            return """You are an expert multiple-choice question (MCQ) generator for educational exams in humanities and social sciences.
Generate {num_questions} MCQ questions based on the provided content.
The questions should be of varying difficulty according to Bloom's Taxonomy: {difficulty_distribution}

DIFFICULTY LEVELS (BLOOM'S TAXONOMY):
1. EASY (Remember & Understand): Questions that test recall and basic comprehension of facts, definitions, and concepts.
   - Remember: Recall facts, terms, basic concepts, or answers without understanding their meaning
   - Understand: Demonstrate understanding of facts and ideas by organizing, comparing, interpreting, and stating main ideas
   - EXAMPLES:
     * "Which definition best describes democracy?"
     * "What were the primary causes of World War I?"
     * "Which literary device is exemplified by 'all the world's a stage'?"
     * "The United Nations was primarily established to:"
   - AVOID requiring any analysis, interpretation, or application for EASY questions

2. MEDIUM (Apply & Analyze): Questions that require application of knowledge and analytical thinking.
   - Apply: Solve problems by applying acquired knowledge, facts, techniques and rules in a different way
   - Analyze: Examine and break information into parts by identifying motives or causes; make inferences and find evidence
   - EXAMPLES:
     * "How do economic policies of socialism and capitalism fundamentally differ?"
     * "What conclusion can be drawn from the events of the Industrial Revolution?"
     * "How does symbolism affect the central theme in 'To Kill a Mockingbird'?"
     * "Which evidence most strongly supports the theory of continental drift?"
   - MUST involve interpretation, application of concepts, or detailed analysis
   - MUST go beyond simple recall and require deeper engagement with the content

3. HARD (Evaluate & Create): Questions that require evaluation of information and creation of new ideas.
   - Evaluate: Present and defend opinions by making judgments about information, validity of ideas, or quality of work based on a set of criteria
   - Create: Compile information together in a different way by combining elements in a new pattern or proposing alternative solutions
   - EXAMPLES:
     * "Which economic proposal would most effectively address income inequality?"
     * "How would modern African nations likely differ if colonialism had never occurred?"
     * "Which interpretation most comprehensively addresses the symbolism in Robert Frost's poetry?"
     * "Which theoretical framework best explains the sociological phenomenon of urbanization?"
   - MUST require synthesis of multiple concepts or critical evaluation
   - MUST involve evaluating perspectives or applying concepts to new situations
   - Should require deep conceptual understanding and critical thinking

Subject: {subject}

Content:
{content}

HUMANITIES AND SOCIAL SCIENCES QUESTION GUIDELINES:
1. FOCUS on testing understanding of concepts, theories, and factual knowledge
2. INCLUDE all necessary information and context in the question statement
3. AVOID ambiguous wording or unclear statements
4. ENSURE questions are culturally and historically accurate
5. PROVIDE sufficient context for the problem without referencing external examples
6. SPECIFY all relevant details needed to answer the question
7. CREATE complete, self-contained questions that don't require additional information
8. MAKE map or diagram descriptions extremely detailed when such visuals are required
9. VERIFY answers thoroughly to ensure accuracy and plausibility of distractors

QUESTION INDEPENDENCE GUIDELINES:
1. Each question must be completely standalone and self-contained
2. NEVER reference "passages," "texts," or any external material in the question text
3. NEVER use phrases like "In the passage" or "From the excerpt"
4. REWRITE any question that depends on external reference as a complete scenario
5. INCLUDE all necessary context, quotes, or historical details within the question text
6. ENSURE questions contain all required information to answer them
7. ADDRESS different concepts or applications in each question
8. TRANSFORM information from the content into new, self-contained questions
9. AVOID any implication that the question relates to a previously referenced text

CONTENT RELEVANCE RULES:
1. Questions must be directly related to the concepts in the provided content
2. Questions should test understanding of the same principles covered in the content
3. ADAPT examples from the content into new questions that test the same concepts
4. ENSURE questions align with the specific field (literature/history/social science) of the content
5. TRANSFORM specific examples from content into questions about general principles
6. CREATE new scenarios that test the same underlying concepts
7. USE similar complexity/difficulty levels as examples in the content

Generate questions in the following JSON format:
{{
  "questions": [
    {{
      "id": "q1",
      "question": "Complete question including all necessary context and information",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "Option A",
      "difficulty": "easy" | "medium" | "hard",
      "source_concept": "Concept from content being tested",
      "diagram_required": false,
      "diagram_description": "ONLY IF NEEDED: DETAILED description of map/diagram/chart including ALL labels, elements, regions, time periods, relationships, and essential visual information that must be represented.",
      "bloom_level": "Remember" | "Understand" | "Apply" | "Analyze" | "Evaluate" | "Create",
      "confidence_score": 0.95
    }}
  ]
}}

QUESTION FORMULATION PRINCIPLES FOR HUMANITIES/SOCIAL SCIENCES:
1. CREATE complete question statements with all necessary context
2. INCLUDE all relevant quotes, historical details, or theoretical frameworks within the question
3. ENSURE that all information needed to answer the question is provided
4. FORMULATE questions as stand-alone problems that don't reference external sources
5. ENSURE questions can be answered using general knowledge that matches the content
6. PROVIDE sufficient context without making the question dependent on external information
7. CHECK that the question leads to a unique, correct answer
8. VERIFY that distractors are plausible but incorrect

PROHIBITED PHRASINGS:
1. DO NOT use "In the text..."
2. DO NOT use "From the passage..."
3. DO NOT use "In the excerpt above..."
4. DO NOT use "According to the author..."
5. DO NOT use "Based on the reading..."
6. DO NOT use "As mentioned in the chapter..."
7. DO NOT use "Referring to the given material..."
8. DO NOT begin with "Which of the following..."
9. DO NOT use "Based on the information provided..."
10. DO NOT use "In the context of..."
11. DO NOT use "As shown in the image..."
12. DO NOT use "According to the map/chart/diagram..."

QUESTION TRANSFORMATION EXAMPLES:
BAD: "According to the passage, what was Gandhi's primary strategy for Indian independence?"
GOOD: "What was Mahatma Gandhi's primary strategy for achieving Indian independence during the early 20th century?"

BAD: "In the text, which literary device does Shakespeare use most frequently?"
GOOD: "Which literary device does Shakespeare use most frequently in his tragedy 'Hamlet'?"

BAD: "Based on the historical account provided, what caused the Great Depression?"
GOOD: "What economic factors primarily caused the Great Depression in the United States during the late 1920s?"

BAD: "In the map shown, which region had the highest population density?"
GOOD: "Which region of India had the highest population density according to the 2011 census?"

MCQ OPTION GUIDELINES:
1. Include exactly 4 options (A, B, C, D) for each question
2. Ensure all options are plausible but only one is clearly correct
3. Create distractors using common misconceptions or partial understandings
4. Include distractors that represent incorrect interpretations or applications
5. For factual questions, create distractors with similar but incorrect facts
6. Ensure distractors have similar length and complexity as the correct answer
7. AVOID options that are obviously incorrect or absurd
8. ENSURE correct answers are derived from proper application of concepts from the content
9. DISTRIBUTE correct answers approximately evenly among options A, B, C, and D

DIAGRAM/MAP/CHART GUIDELINES FOR HUMANITIES/SOCIAL SCIENCES:
1. Set diagram_required to true ONLY when a visual is ESSENTIAL for answering the question
2. Provide EXTREMELY DETAILED diagram descriptions including:
   - For maps: all regions, boundaries, labels, legends, and relevant geographical features
   - For timelines: all dates, events, periods, and chronological relationships
   - For charts: all data points, categories, relationships, and trends
   - For diagrams: all components, relationships, labels, and connections
3. Specify the exact scale, time period, and scope when relevant
4. Include all text labels that should appear on the visual
5. Describe the visual as if instructing someone to create it precisely
6. For complex visuals, specify the organization and layout
7. For historical maps or diagrams, specify the time period and relevant historical context

CORRECT ANSWER DETERMINATION INSTRUCTIONS:
1. You MUST CAREFULLY ANALYZE all possible answers to determine which is correct
2. NEVER guess or arbitrarily select a correct answer - always base it on evidence
3. For factual questions, verify facts against the source content
4. For interpretive questions, apply proper theories, frameworks, and principles
5. Make sure the correct answer appears among the four options
6. For conceptual questions, apply relevant principles correctly to determine the answer
7. Double-check that your reasoning follows established theories and facts accurately
8. If none of the options seem correct after analysis, revise the options to include the correct answer

IMPORTANT REMINDERS:
1. Questions must be COMPLETELY SELF-CONTAINED with all necessary information
2. Questions should NEVER reference external texts, passages, or visuals
3. Humanities and social science questions must be ANSWERABLE using only the information provided
4. All quotes, historical details, or theoretical frameworks must be EXPLICITLY STATED in the question when needed
5. Diagram/map descriptions must be EXTREMELY DETAILED to enable accurate reproduction when required
6. Carefully verify all factual information and create plausible distractors
7. Verify that each question tests concepts from the content but stands entirely on its own
8. Questions should appear to test general knowledge while still being based on the provided content
9. Students should be able to understand and answer questions without ever seeing the original content
10. DO NOT include explanations in the output, but ensure correct answers are properly determined

Respond ONLY with the JSON, no explanations or additional text.
"""

    elif template_file == "diagram_gen.txt":
            return """Generate Python matplotlib code for a diagram with the following description:
Description: {description}
Subject area: {subject}
Question context: {question}

Generate a simple, high-quality 2D educational diagram using matplotlib in Python. The diagram should clearly and accurately represent the described physical or conceptual scenario. Follow these guidelines:

Simplicity: Keep the diagram minimal and focused. Only include elements necessary to represent the concept or situation.

Spacing: Ensure there is a clear visual gap between different objects or labels to maintain readability.

Object Clarity: All visual elements (e.g., person, block, ball, arrow, plane) must be easily identifiable using clear shapes (e.g., circles, rectangles, lines).

Instructional Labels: Label all key objects and forces with concise text to aid understanding, without solving or explaining the scenario.

No Solution or Answer: The diagram must only depict the scenario; do not include any answers, calculations, or results.

Orientation: Use 2D Cartesian plane with appropriate coordinate axes or reference lines if needed.

Matplotlib only: Use Python's matplotlib library exclusively to draw the diagram. Avoid 3D or external rendering libraries.

Clean Aesthetics: Use light colors, solid lines, and consistent font size for a visually appealing and accessible layout.

Example structure:
```python
import matplotlib.pyplot as plt
import numpy as np
# import y4 # Remove or ensure y4 exists if needed

# Set up figure
plt.figure(figsize=(3, 2))

# Plot data or elements
# (e.g., plt.plot(), plt.hlines(), etc.)

# Add labels and annotations
# plt.xlabel('X-axis label') # Often not needed for simple diagrams
# plt.ylabel('Y-axis label') # Often not needed for simple diagrams
# plt.title('Diagram Title') # Optional title
plt.grid(False) # Usually False for cleaner exam diagrams
plt.xticks([]) # Remove x-axis ticks
plt.yticks([]) # Remove y-axis ticks
plt.gca().spines['top'].set_visible(False) # Remove top border
plt.gca().spines['right'].set_visible(False) # Remove right border
plt.gca().spines['left'].set_visible(False) # Remove left border
plt.gca().spines['bottom'].set_visible(False) # Remove bottom border

# Save or display (handled by rendering function)
"""
    elif template_file == "solution_gen.txt":
            return """You are an expert solution provider for educational questions.
Your task is to generate ACCURATE and DETAILED solutions for the following questions. 
The correct answer has already been provided - your job is to explain WHY it's correct.

Questions:
{questions}

For EACH question provided, you MUST generate:
1. **Detailed Explanation:** A step-by-step explanation justifying why the given correct answer is right. Explain the core concepts, formulas, and calculations needed.
2. **Key Insights:** Highlight the main principles or knowledge needed to solve this type of problem.

**CRITICAL REQUIREMENTS:**
* **ACCURACY IS PARAMOUNT:** Your explanation MUST be factually correct and logically sound based on the subject matter.
* **STEP-BY-STEP REASONING:** Break down the solution process clearly so students can follow the logic.
* **CLEAR CONNECTIONS:** Connect your explanation directly to why the provided correct answer is the right one.
* **EDUCATIONAL VALUE:** Your explanation should teach the underlying concepts, not just give the answer.
* **FORMAT CORRECT ANSWER:** In the "correct_answer" field, always format your answer as "Option X: [answer text]" where X is the letter (A, B, C, or D) and [answer text] is the full text of that option. For example, if "Determining the surface area and volume" is option B, the correct_answer should be "Option B: Determining the surface area and volume".

**Output Format (Strict JSON ONLY):**
Format your response as a valid JSON object containing a list named "solutions". Do NOT include any text before or after the JSON object.
```json
{{
  "solutions": [
    {{
      "id": "q1",
      "correct_answer": "Option B: The same correct answer string that was provided to you",
      "explanation": "Detailed, step-by-step explanation proving why the given correct answer is right.",
    }}
    // ... more solutions for other questions
  ]
}}
"""
    else:
        return ""

def verify_questions(questions, subject, content):
    print(f"Starting verification of {len(questions)} questions for subject: {subject}")
    
    valid_questions = []
    for q in questions:
        required_fields = ['question', 'options', 'id']
        
        has_correct_answer = 'correct_answer' in q
        has_answer = 'answer' in q
        
        if not all(field in q for field in required_fields) or not (has_correct_answer or has_answer):
            print(f"Skipping question due to missing required fields: {q.get('id', 'Unknown')}")
            continue
            
        if not isinstance(q.get('options'), (list, dict)):
            print(f"Skipping question due to invalid options format: {q.get('id', 'Unknown')}")
            continue
            
        valid_questions.append(q)
    
    if not valid_questions:
        print("No valid questions to verify")
        return []
    
    solved_answers = solve_all_questions(valid_questions, subject, content)

    print("sol", solved_answers)
    
    verified_results = verify_all_questions(valid_questions, solved_answers, subject, content)
    print("veri", verified_results)
    return verified_results

def solve_all_questions(questions, subject, content):
    print(f"Solving {len(questions)} questions...")
    
    formatted_questions = []
    for i, q in enumerate(questions):
        question_id = q.get('id', i)
        question_text = q['question'].strip()
        options = q.get('options', [])
        
        options_text = ""
        for j, option in enumerate(options):
            if isinstance(option, dict) and 'text' in option:
                label = option.get('label', chr(65 + j))
                options_text += f"{label}. {option['text']}\n"
            else:
                label = chr(65 + j)
                options_text += f"{label}. {option}\n"
        
        formatted_questions.append({
            "id": question_id,
            "question": question_text,
            "options": options_text
        })
    
    solve_prompt = f"""
You are solving {subject} multiple-choice questions with scientific rigor. Follow this EXACT protocol:

1. PROBLEM-SOLVING PHASE (OPTIONS BLIND):
   - Analyze using ONLY: a) Your expert knowledge, b) Provided content: {content}
   - COMPLETELY IGNORE all options during this phase
   - Derive solution step-by-step with logical reasoning
   - Calculate confidence based on:
     • Solution clarity (100% if certain, <50% if uncertain steps exist)
     • Content alignment (higher if matches provided content perfectly)
     • Mathematical certainty (100% for exact calculations, lower for estimates)

2. ANSWER FORMATTING PHASE:
   - Only AFTER solving, briefly view options to match your answer's format to the options format
   - Do NOT change your answer to match an option - your answer must be based ONLY on your independent solution
   - Format your answer to use the same style/units/precision as the options (e.g., "2.5A" not "2.50 volts")

3. OUTPUT FORMAT (STRICT ADHERENCE):
QUESTION ID: [id]
SOLUTION: [Complete derivation with all reasoning steps]
INDEPENDENT_ANSWER: [Your raw solution before formatting]
ANSWER: [Your same solution, formatted to match option style but NOT changing the actual answer]
CONFIDENCE_SCORE: [0-100 based SOLELY on:
   • 100 = Perfect certainty (exact calculation/proven fact)
   • 80-99 = High confidence (minor assumptions)
   • 50-79 = Moderate confidence (some estimation)
   • <50 = Low confidence (significant uncertainty)]

CRITICAL RULES:
■ NEVER reference options during solution phase
■ Confidence reflects SOLUTION certainty, not option matching
■ If conflicted between methods, use LOWER confidence
■ Document all assumptions affecting confidence
■ The ANSWER must contain the same answer as INDEPENDENT_ANSWER, just formatted to match option style

Example Output:
QUESTION ID: q12
SOLUTION: "Using Ohm's Law (V=IR)... calculated current = 2.5A"
INDEPENDENT_ANSWER: "2.5 amperes"
ANSWER: "2.5A"
CONFIDENCE_SCORE: 95 (exact calculation with verified formula)

Now solve these questions:
"""
    
    for q in formatted_questions:
        solve_prompt += f"""
    QUESTION ID: {q['id']}
    Question: {q['question']}
    Options:
    {q['options']}
    
    """
    
    try:
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {os.getenv('CHATGPT_API_KEY')}"
            },
            json={
                "model": "gpt-4.1",
                "messages": [{"role": "user", "content": solve_prompt}],
                "temperature": 0.3,
                "stream": False 
            },
            timeout=180
        )

        if response.status_code != 200:
            print(f"Error calling API: {response.status_code}")
            print(response.text)
            return {}
        
        response_json = response.json()
        solutions_text = response_json['choices'][0]['message']['content']
        
        solutions = parse_solutions_with_required_keys(solutions_text)
        
        print(f"Successfully solved {len(solutions)} questions independently")
        return solutions
        
    except Exception as e:
        print(f"Error while solving questions: {str(e)}")
        return {}

def parse_solutions_with_required_keys(solutions_text):
    solutions = {}
    current_id = None
    current_section = None
    current_solution = {
        "solution": "",
        "independent_answer": "",
        "answer": "",
        "confidence_score": ""
    }
    
    for line in solutions_text.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        if line.startswith("QUESTION ID:"):
            # Save previous solution if exists
            if current_id is not None:
                solutions[current_id] = current_solution.copy()
            
            current_id = line.replace("QUESTION ID:", "").strip()
            current_solution = {
                "solution": "",
                "independent_answer": "",
                "answer": "",
                "confidence_score": ""
            }
            current_section = None
            
        elif line.startswith("SOLUTION:"):
            current_section = "solution"
            current_solution["solution"] = line.replace("SOLUTION:", "").strip()
            
        elif line.startswith("INDEPENDENT_ANSWER:"):
            current_section = "independent_answer"
            current_solution["independent_answer"] = line.replace("INDEPENDENT_ANSWER:", "").strip()
            
        elif line.startswith("ANSWER:"):
            current_section = "answer"
            current_solution["answer"] = line.replace("ANSWER:", "").strip()
            
        elif line.startswith("CONFIDENCE_SCORE:"):
            current_section = None  
            score_text = line.replace("CONFIDENCE_SCORE:", "").strip()
            try:
                score = int(score_text.split()[0])  
                current_solution["confidence_score"] = score
            except (ValueError, IndexError):
                current_solution["confidence_score"] = score_text
            
        elif current_section and current_section != "confidence_score" and current_id is not None:
            current_solution[current_section] += " " + line
    
    if current_id is not None:
        solutions[current_id] = current_solution
    
    return solutions

def format_options_for_prompt(options):
    if isinstance(options, dict):
        return "\n".join([f"{option_key}: {option_value}" for option_key, option_value in options.items()])
    elif isinstance(options, list):
        return "\n".join([f"{chr(65 + i)}: {option}" for i, option in enumerate(options)])
    return ""

def clean_option_text(option_text):
    if '(' in option_text:
        cleaned = option_text.split('(')[0].strip()
        return cleaned
    
    return option_text.strip()

def verify_all_questions(questions, solved_answers, subject, content):
    print(f"Verifying {len(questions)} questions...")
    
    verified_questions = []
    
    for q in questions:
        question_id = q.get('id', '')
        if question_id not in solved_answers:
            print(f"Skipping question {question_id} - no solution provided")
            continue
            
        question_text = q['question'].strip()
        options = q.get('options', [])
        
        # Clean option texts to remove explanations
        if isinstance(options, list):
            options = [clean_option_text(str(option)) for option in options]
        elif isinstance(options, dict):
            options = {k: clean_option_text(str(v)) for k, v in options.items()}
        
        current_answer = q.get('correct_answer', '')
        solution_info = solved_answers[question_id]
        solved_answer = solution_info.get('answer', '')
        solved_confidence = solution_info.get('confidence_score', 0)
        question_confidence = q.get('confidence_score', 0)
        
        verification_prompt = f"""
        Subject: {subject}
        Content: {content}
        
        Please verify this question:
        
        Question: {question_text}
        Options: {options}
        Current answer: {current_answer}
        Solved answer: {solved_answer}
        
        IMPORTANT: Answer each question with ONLY a single word 'yes' or 'no' - no explanation, no additional text:
        1. Is the question valid, well-formed, and directly related to the content?
        2. Is the question self-contained without requiring external information?
        3. Does the current answer match the solved answer?
        
        Format your response exactly like this:
        1. yes/no
        2. yes/no
        3. yes/no
        """
        
        try:
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f"Bearer {os.getenv('CHATGPT_API_KEY')}"
                },
                json={
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": verification_prompt}],
                    "temperature": 0.3
                },
                timeout=60
            )
            
            if response.status_code != 200:
                print(f"Error verifying question {question_id}")
                continue
                
            verification_response = response.json()['choices'][0]['message']['content']
            lines = [line.strip().lower() for line in verification_response.split('\n') if line.strip()]
            
            valid_question = "yes" in lines[0] if len(lines) > 0 else False
            self_contained = "yes" in lines[1] if len(lines) > 1 else False
            answers_match = "yes" in lines[2] if len(lines) > 2 else False
            
            if not valid_question or not self_contained:
                print(f"Question {question_id} failed validation - skipping")
                continue
                
            if answers_match:
                accepted_answer = current_answer
            else:
                if solved_confidence >= question_confidence:
                    accepted_answer = solved_answer
                    q['correct_answer'] = solved_answer
                else:
                    accepted_answer = current_answer
            
            accepted_answer = clean_option_text(str(accepted_answer))
            
            answer_in_options = any(
                str(option).strip().lower() == str(accepted_answer).strip().lower() 
                for option in options
            )
            
            if not answer_in_options and options:
                replace_index = random.randint(0, len(options)-1)
                options[replace_index] = accepted_answer
                print(f"Updated options for question {question_id} - added correct answer")
            
            verified_question = q.copy()
            verified_question['options'] = options
            verified_question['correct_answer'] = accepted_answer
            verified_question['verification_status'] = "verified"
            verified_question['solved_confidence'] = solved_confidence
            verified_questions.append(verified_question)
            
        except Exception as e:
            print(f"Error processing question {question_id}: {str(e)}")
            continue
    
    print(f"Successfully verified {len(verified_questions)} questions")
    return verified_questions

def generate_questions(content, subject, num_questions, difficulty_distribution, conversation_data=None):
    try:
        # Format difficulty distribution for prompt - ensure we're using the correct counts
        difficulty_format = ", ".join([f"{count} {level}" for level, count in difficulty_distribution.items() if count > 0])

        # Validate that the sum of difficulties equals num_questions
        total_difficulty_count = sum(difficulty_distribution.values())
        if total_difficulty_count != num_questions:
            # Adjust the hard difficulty to make the total match
            difficulty_distribution["hard"] = max(0, num_questions - difficulty_distribution["easy"] - difficulty_distribution["medium"])
            # Re-format with adjusted values
            difficulty_format = ", ".join([f"{count} {level}" for level, count in difficulty_distribution.items() if count > 0])

        # Format content for prompt
        content_formatted = "\n\n".join([f"--- {('Chapter' if len(content) > 1 else 'Page')} {num} ---\n{text}"
                                      for num, text in content.items()])
        
        conversation_context = ""
        if conversation_data:
            topic = conversation_data.get('topic', 'the topic')
            conversation_context = "\n\n### Conversation Context:\n"
            conversation_context += f"These questions should be based on the learning session about: {topic}\n"
            conversation_context += "Here's the conversation between the student and AI tutor:\n\n"
            
            for msg in conversation_data.get('messages', []):
                role = "Student" if msg.get('sender') == 'user' else "Tutor"
                conversation_context += f"{role}: {msg.get('message', '')}\n\n"
            
            conversation_context += "\nPay special attention to questions the student asked and concepts the tutor emphasized."

        # Load question generation prompt template
        if subject == "Physics" or subject == "Maths":
            template = load_prompt_template("question_gen.txt")
        else:
            template = load_prompt_template("question_gen_non_math.txt")

        # Format prompt with stronger emphasis on question count and difficulty distribution
        prompt = template.format(
            num_questions=num_questions,
            difficulty_distribution=difficulty_format,
            subject=subject,
            content=content_formatted
        )

        # Add explicit instructions about question count and difficulty distribution
        prompt = prompt.replace("Generate {num_questions} questions",
                               f"Generate EXACTLY {num_questions} questions. This is a requirement, not a suggestion.")
        prompt = prompt.replace("of varying difficulty: {difficulty_distribution}",
                               f"with EXACTLY this difficulty distribution: {difficulty_format}. Do not deviate from this distribution.")
        # Call Ollama API
        # response = requests.post('http://192.168.31.137:11434/api/generate',
        #                        json={
        #                            "model": "gemma3:27b",
        #                            "prompt": prompt,
        #                            "stream": False
        #                        })

        reasoning_prefix = """You are an expert mathematics and physics educator with deep subject knowledge. 
    Your task is to generate accurate, self-contained multiple-choice questions that test understanding of mathematical and physical concepts.

    I want you to think carefully and follow these steps when creating the MCQs:
    
    Step 1: Analyze the content thoroughly and identify key concepts, formulas, and principles that can be tested.
    Step 2: For each concept, create self-contained questions that don't reference external materials.
    Step 3: Ensure mathematical/physics accuracy by working through each problem step by step.
    Step 4: Create plausible distractors based on common misconceptions or calculation errors.
    Step 5: Verify that each question is completely self-contained with all necessary information.
    Step 6: Double-check your work to ensure only one answer is correct.
    
    Now, using the following instructions, generate high-quality MCQs:
    """
        
        enhanced_prompt = reasoning_prefix + prompt + conversation_context

        print("generating.........")

        # model = genai.GenerativeModel('gemma-3-27b-it')
        model = genai.GenerativeModel(
            model_name='gemma-3-27b-it',
            generation_config={
                'temperature': 0.2,
                'top_p': 0.95, 
                'top_k': 40,
                'max_output_tokens': 8192,
            }
        )
        response = model.generate_content(enhanced_prompt)

        if not response.text:
            return {"error": "Generation failed: No response from model in Step 1."}

        # if response.status_code == 200:
            # response_data = response.json()
            # Extract JSON from response
            # generated_text = response_data.get('response', '')
        generated_text = response.text
        print("==================================> generated text")
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
            print("<><><><><><><><><><><><>Question generated")
            # Ensure exactly num_questions are returned
            if len(questions) < num_questions:
                # If too few questions, try a second request for the remaining questions
                print(f"Model returned only {len(questions)} questions. Requesting {num_questions - len(questions)} more...")

                # Request for remaining questions
                remaining_prompt = prompt.replace(
                    f"Generate EXACTLY {num_questions} questions",
                    f"Generate EXACTLY {num_questions - len(questions)} additional questions"
                )

                additional_questions = request_additional_questions(
                    remaining_prompt,
                    num_questions - len(questions)
                )

                # Combine questions
                questions.extend(additional_questions)

            # If still too many or too few, adjust the list
            if len(questions) > num_questions:
                questions = questions[:num_questions]  # Truncate if too many

            # Ensure each question has required fields
            for i, question in enumerate(questions):
                if 'id' not in question:
                    question['id'] = f"q{i+1}"
                if 'requires_diagram' not in question:
                    question['requires_diagram'] = True
                if 'diagram_description' not in question:
                    question['diagram_description'] = f"Diagram for question: {question['question']}"
                if 'confidence_score' not in question:
                    question['confidence_score'] = 0.8  # Default confidence score
                # Add a new field to track if user has selected this question for diagram generation
                question['user_selected_for_diagram'] = False
                # Add subject field for later use
                question['subject'] = subject

            return questions
        except json.JSONDecodeError:
            print("Failed to parse JSON from model response")
            print("Response:", generated_text[:500])  # Print part of the response for debugging
            return []

        # else:
        #     print(f"Error calling Ollama API: {response.status_code}")
        #     print(response.text)
        #     return []

    except Exception as e:
        print(f"Error generating questions: {str(e)}")
        traceback.print_exc()
        return []

def convert_question_difficulty(question, content, subject, new_difficulty):
    try:
        if question.get('difficulty', 'medium') == new_difficulty:
            return question
            
        modified_question = question.copy()
        
        content_formatted = "\n\n".join([f"--- {('Chapter' if len(content) > 1 else 'Page')} {num} ---\n{text}"
                                      for num, text in content.items()])
        
        prompt = f"""
You are an expert educational content creator specializing in {subject}. 
You have been asked to convert the following question from {question.get('difficulty', 'medium')} difficulty to {new_difficulty} difficulty.

Original Question:
Question: {question['question']}
Options: {question.get('options', [])}
Correct Answer: {question.get('correct_answer', '')}
Current Difficulty: {question.get('difficulty', 'medium')}

Consider these difficulty level criteria:
- Easy: Basic recall of facts, simple application of formulas, straightforward concepts.
- Medium: Understanding of relationships between concepts, moderate analysis required, may involve multiple steps.
- Hard: Advanced application, synthesis of multiple concepts, critical thinking required, may involve rare edge cases or exceptions.

Here is the relevant content for this question:
{content_formatted}

Create a new version of this question at {new_difficulty} difficulty level while preserving the core concept.

Return your response in this JSON format:
```json
{{
  "question": "The rewritten question text",
  "options": ["Option A", "Option B", "Option C", "Option D"],
  "correct_answer": "The correct option",
  "diagram_description": "Description of the diagram needed for this question",
  "difficulty": "{new_difficulty}",
  "explanation": "Explanation of why this question is now at {new_difficulty} difficulty level"
}}
```
"""
        

        model = genai.GenerativeModel('gemma-3-27b-it')
        response = model.generate_content(prompt)
        
        if not response.text:
            raise Exception("No response from model when converting question difficulty")
            
        generated_text = response.text

        json_match = re.search(r'```json\s*(.+?)\s*```', generated_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'(\{.*"question":.+?\})', generated_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = generated_text
                
        converted_data = json.loads(json_str)
        
        for key in ['question', 'options', 'correct_answer', 'diagram_description', 'explanation']:
            if key in converted_data:
                modified_question[key] = converted_data[key]
                
        modified_question['difficulty'] = new_difficulty
        
        if 'diagram_matplotlib' in modified_question:
            modified_question['requires_diagram'] = True
        
        return modified_question
        
    except Exception as e:
        print(f"Error converting question difficulty: {str(e)}")
        traceback.print_exc()
        return question


def batch_solve_questions(questions):
    try:        
        formatted_questions = "\n\n".join([
            f"Question ID: {q['id']}\nQuestion: {q['question']}\nDifficulty: {q.get('difficulty', 'medium')}"
            for q in questions
        ])

        template = load_prompt_template("solution_gen.txt")

        prompt = template.format(questions=formatted_questions)

        prompt += """
        CRITICAL REQUIREMENTS:
        1. Do NOT generate new options - just explain the given correct answer
        2. Provide a detailed, step-by-step explanation for why the provided correct answer is correct
        3. Include key concepts and formulas that apply to the question
        4. Your explanation should be clear enough for educational purposes
        
        RESPOND WITH VALID JSON ONLY - NO ADDITIONAL TEXT!
        """

        print(f"Generating solutions for {len(questions)} questions...")
        
        models = ["gemma", "gpt"] 
        
        model_solutions = []
        
        for model in models:
            try:
                print(f"Generating solutions using model: {model}")
                
                if model == "gemma":
                    gemma_model = genai.GenerativeModel('gemma-3-27b-it')
                    response = gemma_model.generate_content(prompt)
                    
                    if not response.text:
                        print("Generation failed: No response from Gemma model")
                        continue
                    
                    generated_text = response.text
                    
                elif model == "gpt":
                    gpt_response = requests.post(
                        'https://api.openai.com/v1/chat/completions',
                        headers={
                            'Content-Type': 'application/json',
                            'Authorization': f"Bearer {os.getenv('CHATGPT_API_KEY')}"
                        },
                        json={
                            "model": "gpt-4.1",
                            "messages": [{"role": "user", "content": prompt}]
                        },
                        timeout=180
                    )

                    if gpt_response.status_code != 200:
                        print(f"Error calling GPT-4.1 API: {gpt_response.status_code}")
                        print(gpt_response.text)
                        continue
                
                    generated_text = gpt_response.json()['choices'][0]['message']['content']
                
                result = extract_json_from_text(generated_text)
                
                if result and "solutions" in result and isinstance(result["solutions"], list):
                    solutions_dict = {sol.get('id'): sol for sol in result["solutions"] if sol.get('id')}
                    model_solutions.append(solutions_dict)
                    print(f"Successfully extracted {len(solutions_dict)} solutions from {model}")
                else:
                    print(f"Failed to extract valid solutions from {model}")
            except Exception as e:
                print(f"Error with model {model}: {str(e)}")
        
        consensus_solutions = {}
        
        for q in questions:
            question_id = q['id']
            
            model_answers = []
            for solution_dict in model_solutions:
                if question_id in solution_dict:
                    solution = solution_dict[question_id]
                    if 'correct_answer' in solution:
                        model_answers.append(solution)
            
            if len(model_answers) >= 2:
                answer_counts = {}
                for sol in model_answers:
                    answer = sol.get('correct_answer', '')
                    answer_counts[answer] = answer_counts.get(answer, 0) + 1
                
                most_common = max(answer_counts.items(), key=lambda x: x[1], default=(None, 0))
                most_common_answer = most_common[0]
                
                consensus_solution = next((sol for sol in model_answers if sol.get('correct_answer') == most_common_answer), 
                                        model_answers[0] if model_answers else None)
                
                if consensus_solution:
                    consensus_solution['consensus_count'] = most_common[1]
                    consensus_solution['total_models'] = len(model_answers)
                    
                    ensure_valid_solution(consensus_solution, question_id)
                    
                    consensus_solutions[question_id] = consensus_solution
            
            elif len(model_answers) == 1:
                solution = model_answers[0]
                solution['consensus_count'] = 1
                solution['total_models'] = 1
                
                ensure_valid_solution(solution, question_id)
                
                consensus_solutions[question_id] = solution

        return consensus_solutions

    except Exception as e:
        print(f"Error generating solutions in batch: {str(e)}")
        traceback.print_exc()
        return {}

def ensure_valid_solution_simple(solution, question_id):
    """
    Ensure the solution has all required fields
    
    Args:
        solution (dict): Solution dictionary
        question_id (str): Question ID
    """
    # Make sure solution has the required fields
    if 'explanation' not in solution:
        solution['explanation'] = "No explanation provided."
    
    # Ensure the correct_answer field exists
    if 'correct_answer' not in solution:
        solution['correct_answer'] = "Unknown"
    
    # Add the question ID if not present
    if 'id' not in solution:
        solution['id'] = question_id

def ensure_valid_solution(solution, question_id):
    """Helper function to ensure a solution has all required fields with valid values"""
    # Ensure correct_answer is present
    if 'correct_answer' not in solution:
        solution['correct_answer'] = f"Answer for question {question_id}"

    # Ensure options list exists and has exactly 4 options
    if 'options' not in solution or not isinstance(solution['options'], list):
        solution['options'] = [
            solution['correct_answer'],
            f"Incorrect option 1 for {question_id}",
            f"Incorrect option 2 for {question_id}",
            f"Incorrect option 3 for {question_id}"
        ]

    # Ensure options are unique and include correct answer
    unique_options = []
    seen = set()

    # First ensure correct answer is in the list
    correct_answer = solution['correct_answer']
    unique_options.append(correct_answer)
    seen.add(correct_answer)

    # Then add other unique options
    for option in solution['options']:
        if option not in seen and len(unique_options) < 4:
            unique_options.append(option)
            seen.add(option)

    # If we don't have 4 unique options, add new ones
    while len(unique_options) < 4:
        new_option = f"Additional option {len(unique_options)} for {question_id}"
        if new_option not in seen:
            unique_options.append(new_option)
            seen.add(new_option)

    # Update solution with fixed options
    solution['options'] = unique_options[:4]
    
    # Ensure explanation exists
    if 'explanation' not in solution or not solution['explanation']:
        solution['explanation'] = f"Explanation for answer to question {question_id}"

def solve_questions(questions):
    # Try batch solution generation first
    solutions_dict = batch_solve_questions(questions)

    # For any questions without solutions, try individual generation
    missing_ids = [q['id'] for q in questions if q['id'] not in solutions_dict]
    if missing_ids:
        print(f"Missing solutions for {len(missing_ids)} questions. Trying to generate them individually...")

        for q in questions:
            if q['id'] in missing_ids:
                print(f"Generating individual solution for question {q['id']}...")
                individual_solution = generate_individual_solution(q)
                if individual_solution:
                    solutions_dict[q['id']] = individual_solution
                    print(f"Successfully generated solution for {q['id']}")
                else:
                    print(f"Failed to generate solution for {q['id']}, creating fallback solution")

    return solutions_dict

def update_questions_with_solutions(questions, solutions):
    """
    Update question objects with solution data

    Args:
        questions (list): List of question dictionaries
        solutions (dict): Dictionary of solutions keyed by question ID

    Returns:
        list: Updated questions with solution data
    """
    for question in questions:
        question_id = question.get('id')
        if question_id in solutions:
            solution = solutions[question_id]
            # Add solution data to the question
            question['correct_answer'] = solution.get('correct_answer', '')
            question['options'] = solution.get('options', [])
            question['explanation'] = solution.get('explanation', '')
            # Update confidence score if available in solution
            if 'confidence_score' in solution:
                question['solution_confidence'] = solution.get('confidence_score', 0.8)

    return questions

def request_additional_questions(prompt, num_needed):
    """Request additional questions if initial response had too few"""
    try:
        # response = requests.post('http://192.168.31.137:11434/api/generate',
        #                       json={
        #                           "model": "gemma3:27b",
        #                           "prompt": prompt,
        #                           "stream": False
                            #   })
        
        model = genai.GenerativeModel('gemma-3-27b-it')
        response = model.generate_content(prompt)
            
        if not response.text:
            return {"error": "Generation failed: No response from model in Step 1."}
        
        generated_text = response.text

        # if response.status_code == 200:
        #     response_data = response.json()
        #     generated_text = response_data.get('response', '')
        print("_______________________________________> modified code", generated_text)
        # Extract JSON using the same pattern as the main function
        json_match = re.search(r'```json\s*(.+?)\s*```', generated_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'(\{.*"questions":\s*\[.+?\]\s*\})', generated_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = generated_text

        try:
            result = json.loads(json_str)
            return result.get('questions', [])[:num_needed]  # Only take what's needed
        except json.JSONDecodeError:
            print("Failed to parse JSON from additional questions response")
            return []

        return []
    except Exception as e:
        print(f"Error getting additional questions: {str(e)}")
        return []

def load_previous_questions():
    """Load all previously generated questions from the data/generated folder"""
    previous_questions = []
    generated_dir = "data/generated"

    if not os.path.exists(generated_dir):
        return previous_questions

    for filename in os.listdir(generated_dir):
        if filename.endswith("_questions.json") or filename.endswith("_questions_with_diagrams.json"):
            try:
                with open(os.path.join(generated_dir, filename), 'r') as f:
                    data = json.load(f)
                    if "questions" in data and isinstance(data["questions"], list):
                        previous_questions.extend(data["questions"])
            except Exception as e:
                print(f"Error loading {filename}: {e}")

    return previous_questions

def is_duplicate_question(question, existing_questions, similarity_threshold=0.8):
    """
    Check if a question is too similar to any existing questions

    Args:
        question (dict): The new question to check
        existing_questions (list): List of existing question dictionaries
        similarity_threshold (float): Threshold for considering questions similar (0-1)

    Returns:
        bool: True if the question is a duplicate, False otherwise
    """
    from difflib import SequenceMatcher

    question_text = question.get('question', '').lower()
    if not question_text:
        return False

    for existing in existing_questions:
        existing_text = existing.get('question', '').lower()
        if not existing_text:
            continue

        # Calculate similarity ratio
        similarity = SequenceMatcher(None, question_text, existing_text).ratio()
        if similarity >= similarity_threshold:
            print(f"Duplicate found ({similarity:.2f}): {question_text[:50]}... vs {existing_text[:50]}...")
            return True

    return False

def filter_out_duplicates(new_questions, existing_questions):
    """Filter out duplicate questions from a list of new questions"""
    unique_questions = []

    for question in new_questions:
        if not is_duplicate_question(question, existing_questions):
            unique_questions.append(question)
        else:
            print(f"Filtered out duplicate: {question.get('question', '')[:50]}...")

    return unique_questions

def generate_questions_with_duplicate_check(content, subject, num_questions, difficulty_distribution, conversation_data=None):
    """Generate questions while checking for duplicates against previously generated questions"""
    # Load existing questions
    existing_questions = load_previous_questions()
    print(f"Loaded {len(existing_questions)} previously generated questions for duplicate checking.")

    # First attempt to generate the requested number of questions
    questions = generate_questions(content, subject, num_questions, difficulty_distribution, conversation_data=conversation_data)

    # Filter out any duplicates
    unique_questions = filter_out_duplicates(questions, existing_questions)
    print("que", questions)

    verified_questions = verify_questions(questions, subject, content)
    
    # Continue with the verified questions
    unique_questions = verified_questions

    # If we filtered out duplicates, we need to generate more to meet the target
    if len(unique_questions) < num_questions:
        additional_needed = num_questions - len(unique_questions)
        print(f"Need {additional_needed} more questions after filtering duplicates.")

        # Generate extra questions (request more than needed to account for possible duplicates)
        extra_questions = generate_questions(content, subject, additional_needed * 2, difficulty_distribution, conversation_data=conversation_data)

        # Filter duplicates from extra questions (against both existing and already-accepted questions)
        extra_unique = filter_out_duplicates(extra_questions, existing_questions + unique_questions)

        # Add just enough of the extra questions to reach the target
        unique_questions.extend(extra_unique[:additional_needed])

    # Final trim to the exact number requested
    return unique_questions[:num_questions]

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
    """
    diagrams = {}

    for question in questions:
        if question.get('user_selected_for_diagram', False):
            question_id = question.get('id')
            latex_code = generate_diagram_for_question(question)
            if latex_code:
                diagrams[question_id] = latex_code

    return diagrams


def extract_json_from_text(text):
    """Extract JSON from text with more robust patterns"""
    # Try direct JSON parsing first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try various regex patterns
        patterns = [
            r'```json\s*(.+?)\s*```',  # Code block with json tag
            r'```\s*(.+?)\s*```',       # Any code block
            r'(\{.*"solutions":\s*\[.+?\]\s*\})',  # Solutions JSON pattern
            r'(\{.*"id":\s*".+?"\s*,.+?\})'  # Single solution JSON
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue

    # If all else fails, try to clean and fix the JSON
    cleaned_text = re.sub(r'[^\x00-\x7F]+', '', text)  # Remove non-ASCII chars
    try:
        return json.loads(cleaned_text)
    except:
        return None

def generate_diagram_for_question(question, max_retries=2):
    try:
        description = question.get('diagram_description', '')
        q_text = question.get('question', '')
        subject = question.get('subject', 'Physics')
        
        retry_count = 0
        previous_error_info = ""
        
        while retry_count < max_retries:
            try:
                print(f"Diagram generation attempt {retry_count + 1}/{max_retries}")
                
                if retry_count > 0:
                    error_feedback = f"""
IMPORTANT CORRECTION NEEDED:
Previous attempt failed with issues: {previous_error_info}

Please fix by:
1. Using ONLY basic TikZ commands (no libraries)
2. Using ONLY absolute positioning with coordinates
3. Ensuring all elements are properly enclosed in begin/end tags
4. Using thicker lines for better visibility
5. Avoiding overlapping elements
"""
                else:
                    error_feedback = ""
                
                prompt = f"""
You are tasked with creating a precise TikZ diagram for the following {subject} question:

QUESTION TEXT: {q_text}

DIAGRAM DESCRIPTION: {description}

{error_feedback}

PROCESS TO FOLLOW:

STEP 1 - COMPREHENSIVE ANALYSIS: 
First, thoroughly analyze the question to determine:
1. The exact physical or mathematical scenario being described
2. All key elements that must be visualized (objects, forces, dimensions, etc.)
3. Precise numerical values and measurements that must appear in the diagram
4. Appropriate dimensionality (2D is preferred unless 3D is explicitly needed)
5. Required notation, labels, and mathematical symbols
6. Specific relationships or transformations that need to be depicted

STEP 2 - PRECISE DIAGRAM DESIGN: 
Based on the analysis, design a clear, accurate diagram that:
1. Faithfully represents the physical/mathematical situation with correct proportions
2. Shows all relevant objects with proper scaling and orientation
3. Displays all numerical values mentioned in the question in appropriate positions
4. Uses clear, consistent labels that exactly match notation in the question
5. Employs standard notation for vectors, angles, coordinates, etc.
6. Maintains visual clarity through appropriate spacing and organization

STEP 3 - VERIFICATION:
Before proceeding to code generation, verify that:
1. All elements from the question are accurately represented
2. The diagram correctly illustrates the mathematical/physical principles involved
3. No contradictions or inaccuracies exist in the visualization
4. The diagram would be clear to a student trying to understand the problem
5. Any specific requirements mentioned in the error feedback are addressed

STEP 4 - LATEX CODE GENERATION: 
Create compilable LaTeX code that:
1. Uses ONLY basic TikZ commands (no additional libraries)
2. Uses absolute positioning only (no relative positioning)
3. Has proper line thickness for visibility (line width=1pt for main elements)
4. Includes all labels and numerical values from the question
5. Shows a clear, properly scaled representation
6. Uses appropriate mathematical notation through LaTeX math mode
7. Is organized with clear commenting

DO NOT output any explanations, analysis, or comments - PROVIDE ONLY THE COMPILABLE LATEX CODE in this exact format:

\\documentclass[tikz,border=5mm]{{standalone}}
\\usepackage{{tikz,amsmath,amssymb}}
\\begin{{document}}
\\begin{{tikzpicture}}[scale=1.0]
    % TikZ code here
\\end{{tikzpicture}}
\\end{{document}}
"""
                
                api_key = os.getenv('CHATGPT_API_KEY')
                if not api_key:
                    raise ValueError("API key not found. Set CHATGPT_API_KEY environment variable.")
                
                gpt_response = requests.post(
                    'https://api.openai.com/v1/chat/completions',
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f"Bearer {api_key}"
                    },
                    json={
                        "model": "gpt-4.1",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2 
                    }
                )
                
                if gpt_response.status_code != 200:
                    print(f"API error: {gpt_response.status_code}")
                    print(gpt_response.text)
                    retry_count += 1
                    previous_error_info = "API communication error"
                    continue
                
                response = gpt_response.json()['choices'][0]['message']['content']
                
                latex_patterns = [
                    r"```latex\n(.*?)\n```", 
                    r"```\n(.*?)\n```",   
                    r"`{3}(.*?)`{3}"  
                ]
                
                latex_content = None
                for pattern in latex_patterns:
                    matches = re.findall(pattern, response, re.DOTALL)
                    if matches:
                        latex_content = matches[0].strip()
                        break
                
                if not latex_content:
                    latex_content = response.strip()
                
                required_elements = [
                    "\\documentclass",
                    "\\begin{document}",
                    "\\begin{tikzpicture}",
                    "\\end{tikzpicture}",
                    "\\end{document}"
                ]
                
                missing_elements = []
                for element in required_elements:
                    if element not in latex_content:
                        missing_elements.append(element)
                
                if missing_elements:
                    print(f"Missing LaTeX elements: {', '.join(missing_elements)}")
                    retry_count += 1
                    previous_error_info = f"Missing LaTeX elements: {', '.join(missing_elements)}"
                    continue
                
                disallowed_features = [
                    "\\usetikzlibrary",
                    "arrows.meta",
                    "positioning",
                    "[right of=",
                    "[left of=",
                    "[above of=",
                    "[below of=",
                    "node[right of=",
                    "node[left of=",
                    "node[above of=",
                    "node[below of="
                ]
                
                found_disallowed = []
                for feature in disallowed_features:
                    if feature in latex_content:
                        found_disallowed.append(feature)
                
                if found_disallowed:
                    print(f"Disallowed TikZ features: {', '.join(found_disallowed)}")
                    retry_count += 1
                    previous_error_info = f"Disallowed TikZ features: {', '.join(found_disallowed)}"
                    continue
                
                file_base = str(uuid.uuid4())
                tex_path = os.path.join(DIAGRAM_FOLDER, f"{file_base}.tex")
                pdf_path = os.path.join(DIAGRAM_FOLDER, f"{file_base}.pdf")
                log_path = os.path.join(DIAGRAM_FOLDER, f"{file_base}.log")
                aux_path = os.path.join(DIAGRAM_FOLDER, f"{file_base}.aux")
                
                temp_files = [tex_path, pdf_path, log_path, aux_path]
                
                try:
                    with open(tex_path, "w", encoding="utf-8") as f:
                        f.write(latex_content)
                    
                    result = subprocess.run(
                        ["pdflatex", "-interaction=nonstopmode", "-output-directory", DIAGRAM_FOLDER, tex_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=30 
                    )
                    
                    if result.returncode != 0:
                        error_info = ""
                        lines = result.stdout.split('\n')
                        for i, line in enumerate(lines):
                            if any(err in line.lower() for err in ["error:", "emergency stop", "undefined control", "fatal error"]):
                                error_info += line.strip() + "\n"
                                for j in range(1, 3):
                                    if i + j < len(lines) and lines[i + j].strip():
                                        error_info += lines[i + j].strip() + "\n"
                        
                        print(f"LaTeX compilation failed: {error_info}")
                        retry_count += 1
                        previous_error_info = f"Compilation errors: {error_info[:200]}..."
                        continue
                    
                    print("Successfully compiled LaTeX code")
                    return latex_content
                    
                finally:
                    for file_path in temp_files:
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                        except Exception as cleanup_error:
                            print(f"Warning: Could not delete {file_path}: {str(cleanup_error)}")
                
            except Exception as e:
                print(f"Error during attempt {retry_count + 1}: {str(e)}")
                retry_count += 1
                previous_error_info = str(e)
        
        print(f"Failed to generate valid LaTeX code after {max_retries} attempts")
        return None
        
    except Exception as e:
        print(f"Error generating LaTeX code: {str(e)}")
        traceback.print_exc()
        return None

def generate_diagram_with_instructions(question, instructions, max_retries=2):
    try:
        description = question.get('diagram_description', '')
        q_text = question.get('question', '')
        subject = question.get('subject', 'Physics')
        original_code = question.get('diagram_matplotlib', '')
        
        retry_count = 0
        previous_error_info = ""
        
        while retry_count < max_retries:
            try:
                print(f"Diagram modification attempt {retry_count + 1}/{max_retries}")
                
                if retry_count > 0:
                    error_feedback = f"""
IMPORTANT CORRECTION NEEDED:
Previous attempt failed with issues: {previous_error_info}

Please fix by:
1. Using ONLY basic TikZ commands (no libraries)
2. Using ONLY absolute positioning with coordinates
3. Ensuring all elements are properly enclosed in begin/end tags
4. Using thicker lines for better visibility
5. Avoiding overlapping elements
"""
                else:
                    error_feedback = """
CRITICAL REQUIREMENTS:
1. CAREFULLY IDENTIFY AND EXTRACT all numerical values from the question text
2. ENSURE ALL NUMERICAL VALUES appear on the diagram in the correct locations with units
3. For 3D objects, use PROPER PERSPECTIVE with consistent vanishing points
4. Show visible edges with THICK SOLID LINES and hidden edges with THINNER DASHED LINES
5. Apply SUBTLE SHADING to enhance depth perception in 3D diagrams
"""
                
                prompt = f"""
You are an expert at creating and modifying TikZ diagrams for academic exams. Your task is to precisely implement requested changes while maintaining diagram integrity and exam suitability.

**MODIFICATION REQUEST:**
- Subject: {subject}
- Original Description: {description}
- Question Text: {q_text}
- Modification Instructions: {instructions}
- Original Code:
```latex
{original_code}
```

{error_feedback}

**CRITICAL FIRST STEP - Question Analysis:**
Before writing any code, EXPLICITLY analyze the question to determine:
1. What specific geometric or physical setup is being described?
2. What are the key elements that MUST be visualized?
3. What dimension (2D vs 3D) is appropriate for this question?
4. What specific notation, labels, or elements are mentioned in the question that must appear in the diagram?
5. What numerical data or measurements need to be precisely represented?
   - CAREFULLY EXAMINE the question for ALL numerical values (masses, lengths, angles, etc.)
   - Extract these values along with their units (if any)
   - Plan how to display these values on appropriate diagram elements

**MODIFICATION PROCESS - FOLLOW EXACTLY:**

1. ANALYZE QUESTION AND REQUIREMENTS:
   - Identify the key elements in the original diagram
   - Understand how these elements relate to the exam question
   - Determine which elements must be preserved versus modified
   - EXTRACT ALL NUMERICAL VALUES that must be displayed on the diagram

2. IMPLEMENT THE REQUESTED CHANGES PRECISELY:
   - Make ONLY the specific modifications requested
   - Maintain absolute positioning with explicit coordinates
   - Preserve the educational purpose of the diagram
   - Ensure no solutions are inadvertently revealed
   - Display ALL numerical values from the question on the diagram with appropriate units

3. ENSURE TECHNICAL COMPLIANCE:
   - Use ONLY allowed packages: tikz, amsmath, amssymb
   - Avoid ALL TikZ libraries (positioning, arrows.meta, etc.)
   - Use basic TikZ commands with absolute coordinates:
     * \\node at (x,y) {{text}};
     * \\draw[options] (x1,y1) -- (x2,y2);
     * \\draw (x,y) circle (radius);
     * \\draw (x1,y1) rectangle (x2,y2);

4. OPTIMIZE FOR PRINT QUALITY:
   - Use 'thick' (line width=1pt) for main lines and 'line width=0.5pt' for secondary elements
   - Set appropriate font sizes (\\small, \\normalsize, \\large)
   - Ensure sufficient spacing between elements
   - Maintain consistent scale (keep coordinates within [-5,5])

5. FOR 3D DIAGRAMS, ENSURE CLARITY:
   - Use proper 3D perspective drawing with consistent vanishing points
   - Show visible edges with thick solid lines and hidden edges with thinner dashed lines
   - Use subtle shading or line weight variation to enhance depth perception
   - Ensure 3D objects maintain proper proportions from all viewing angles
   - Use appropriate viewing angle to clearly show all critical features

6. DATA REPRESENTATION:
   - PROMINENTLY DISPLAY every numerical value mentioned in the question text
   - Use appropriate notation for measurements (m, kg, s, N, etc.)
   - For dimensions, add measurement lines with arrows and values
   - For forces, label vectors with their magnitudes
   - For angles, show both the arc and the numerical value
   - For masses, label objects with their mass values
   - For other quantities, place values near relevant diagram elements

7. VERIFY AFTER MODIFICATION:
   - Check that all elements remain properly positioned
   - Ensure labels are clear and appropriately placed
   - Verify ALL numerical values from the question are accurately displayed
   - Verify the diagram still illustrates the problem without revealing solutions
   - Confirm no advanced TikZ features were introduced

**OUTPUT REQUIREMENTS:**
- Return a complete, compilable LaTeX document (standalone class)
- Include all necessary preamble commands
- Produce a clean \\begin{{tikzpicture}} environment
- Output ONLY the modified code - no explanations

DO NOT output any explanations, analysis, or comments - PROVIDE ONLY THE COMPILABLE LATEX CODE in this exact format:

\\documentclass[tikz,border=5mm]{{standalone}}
\\usepackage{{tikz,amsmath,amssymb}}
\\begin{{document}}
\\begin{{tikzpicture}}[scale=1.0]
    % Modified diagram elements here
\\end{{tikzpicture}}
\\end{{document}}
"""
                
                api_key = os.getenv('CHATGPT_API_KEY')
                if not api_key:
                    raise ValueError("API key not found. Set CHATGPT_API_KEY environment variable.")
                
                gpt_response = requests.post(
                    'https://api.openai.com/v1/chat/completions',
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f"Bearer {api_key}"
                    },
                    json={
                        "model": "gpt-4.1",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2
                    }
                )
                
                if gpt_response.status_code != 200:
                    print(f"API error: {gpt_response.status_code}")
                    print(gpt_response.text)
                    retry_count += 1
                    previous_error_info = "API communication error"
                    continue
                
                response = gpt_response.json()['choices'][0]['message']['content']
                
                latex_patterns = [
                    r"```latex\n(.*?)\n```", 
                    r"```\n(.*?)\n```",   
                    r"`{3}(.*?)`{3}"  
                ]
                
                latex_content = None
                for pattern in latex_patterns:
                    matches = re.findall(pattern, response, re.DOTALL)
                    if matches:
                        latex_content = matches[0].strip()
                        break
                
                if not latex_content:
                    latex_content = response.strip()
                
                required_elements = [
                    "\\documentclass",
                    "\\begin{document}",
                    "\\begin{tikzpicture}",
                    "\\end{tikzpicture}",
                    "\\end{document}"
                ]
                
                missing_elements = []
                for element in required_elements:
                    if element not in latex_content:
                        missing_elements.append(element)
                
                if missing_elements:
                    print(f"Missing LaTeX elements: {', '.join(missing_elements)}")
                    retry_count += 1
                    previous_error_info = f"Missing LaTeX elements: {', '.join(missing_elements)}"
                    continue
                
                disallowed_features = [
                    "\\usetikzlibrary",
                    "arrows.meta",
                    "positioning",
                    "[right of=",
                    "[left of=",
                    "[above of=",
                    "[below of=",
                    "node[right of=",
                    "node[left of=",
                    "node[above of=",
                    "node[below of="
                ]
                
                found_disallowed = []
                for feature in disallowed_features:
                    if feature in latex_content:
                        found_disallowed.append(feature)
                
                if found_disallowed:
                    print(f"Disallowed TikZ features: {', '.join(found_disallowed)}")
                    retry_count += 1
                    previous_error_info = f"Disallowed TikZ features: {', '.join(found_disallowed)}"
                    continue
                
                file_base = str(uuid.uuid4())
                DIAGRAM_FOLDER = os.path.join(os.getcwd(), "diagrams") 
                os.makedirs(DIAGRAM_FOLDER, exist_ok=True)
                
                tex_path = os.path.join(DIAGRAM_FOLDER, f"{file_base}.tex")
                pdf_path = os.path.join(DIAGRAM_FOLDER, f"{file_base}.pdf")
                log_path = os.path.join(DIAGRAM_FOLDER, f"{file_base}.log")
                aux_path = os.path.join(DIAGRAM_FOLDER, f"{file_base}.aux")
                
                temp_files = [tex_path, pdf_path, log_path, aux_path]
                
                try:
                    with open(tex_path, "w", encoding="utf-8") as f:
                        f.write(latex_content)
                    
                    result = subprocess.run(
                        ["pdflatex", "-interaction=nonstopmode", "-output-directory", DIAGRAM_FOLDER, tex_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode != 0:
                        error_info = ""
                        lines = result.stdout.split('\n')
                        for i, line in enumerate(lines):
                            if any(err in line.lower() for err in ["error:", "emergency stop", "undefined control", "fatal error"]):
                                error_info += line.strip() + "\n"
                                for j in range(1, 3):
                                    if i + j < len(lines) and lines[i + j].strip():
                                        error_info += lines[i + j].strip() + "\n"
                        
                        print(f"LaTeX compilation failed: {error_info}")
                        retry_count += 1
                        previous_error_info = f"Compilation errors: {error_info[:200]}..."
                        continue
                    
                    print("Successfully compiled modified LaTeX code")
                    return latex_content
                    
                finally:
                    for file_path in temp_files:
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                        except Exception as cleanup_error:
                            print(f"Warning: Could not delete {file_path}: {str(cleanup_error)}")
                
            except Exception as e:
                print(f"Error during attempt {retry_count + 1}: {str(e)}")
                retry_count += 1
                previous_error_info = str(e)
        
        print(f"Failed to generate valid modified LaTeX code after {max_retries} attempts")
        return None
        
    except Exception as e:
        print(f"Error generating modified LaTeX code: {str(e)}")
        traceback.print_exc()
        return None

# New two-step process to generate questions and then MCQ answers
def generate_questions_with_solutions(content, subject, num_questions, difficulty_distribution):
    """
    Two-step process:
    1. Generate questions
    2. Generate solutions with MCQ options for those questions

    Args:
        content (dict): Content keyed by chapter/page number
        subject (str): Subject area
        num_questions (int): Number of questions to generate
        difficulty_distribution (dict): Distribution of difficulty levels

    Returns:
        list: Questions with solutions and MCQ options
    """
    # Step 1: Generate questions with duplicate checking
    questions = generate_questions_with_duplicate_check(content, subject, num_questions, difficulty_distribution)
    print(f"Generated {len(questions)} unique questions.")

    # Step 2: Generate solutions with MCQ options for the questions
    solutions = solve_questions(questions)
    print(f"Generated solutions for {len(solutions)} questions.")

    # Step 3: Update questions with solution data
    questions_with_solutions = update_questions_with_solutions(questions, solutions)

    return questions_with_solutions

def generate_individual_solution(question):
    """Generate solution for a single question with improved parsing"""
    try:
        # Extract the correct answer from the question if it exists
        correct_answer = question.get('correct_answer', '')
        correct_option = None
        
        # If there's a correct_answer specified like "Option B"
        if correct_answer and correct_answer.startswith('Option ') and len(correct_answer) > 7:
            correct_option = correct_answer[7:]  # Extract just the letter
        
        # Get the options if they exist
        options = question.get('options', [])
        
        # Create a more focused prompt for solution generation
        prompt = f"""
        IMPORTANT: You must return VALID JSON only.

        Generate a detailed solution for this question:

        Question ID: {question['id']}
        Question: {question['question']}
        """
        
        # Add options to the prompt if they exist
        if options:
            option_text = "\n".join([f"Option {chr(65+i)}: {opt}" for i, opt in enumerate(options)])
            prompt += f"\n\nOptions:\n{option_text}"
        
        # Add correct answer to the prompt if it exists
        if correct_answer:
            if correct_option and options:
                # Find the index of the option letter in the alphabet (0=A, 1=B, etc.)
                option_index = ord(correct_option) - 65
                if 0 <= option_index < len(options):
                    prompt += f"\n\nCorrect Answer: Option {correct_option}: {options[option_index]}"
            else:
                prompt += f"\n\nCorrect Answer: {correct_answer}"

        # Append instructions for the expected output format
        prompt += """

        Your response MUST be a valid JSON object with these fields:
        - id: The question ID
        - correct_answer: Format as "Option X: [full answer text]", e.g., "Option B: Determining the surface area and volume"
        - explanation: Detailed, step-by-step solution explaining why the correct answer is right
        - key_insights: Key principles and concepts needed to understand this type of problem

        Output format:
        {{
            "id": "q1",
            "correct_answer": "Option B: The same correct answer string that was provided to you",
            "explanation": "Detailed, step-by-step explanation proving why the given correct answer is right.",
            "key_insights": "Key principles needed to understand this problem..."
        }}

        DO NOT include any text or explanation outside of the JSON object.
        DO NOT use markdown formatting or code blocks.
        RETURN ONLY THE JSON OBJECT.
        """

        # Generate solution using Gemma model
        model = genai.GenerativeModel('gemma-3-27b-it')
        response = model.generate_content(prompt)
            
        if not response.text:
            return {"error": "Generation failed: No response from model."}
        
        generated_text = response.text

        # Extract JSON from the response
        solution = extract_json_from_text(generated_text)

        if solution:
            # Handle single solution object or solutions array
            if "solutions" in solution and isinstance(solution["solutions"], list):
                solution = solution["solutions"][0]  # Get first solution

            # Ensure required fields exist
            if not all(k in solution for k in ["id", "correct_answer", "explanation"]):
                # Create missing fields
                if "id" not in solution:
                    solution["id"] = question["id"]
                
                # Format the correct answer if needed
                if "correct_answer" not in solution:
                    if correct_option and options:
                        option_index = ord(correct_option) - 65
                        if 0 <= option_index < len(options):
                            solution["correct_answer"] = f"Option {correct_option}: {options[option_index]}"
                        else:
                            solution["correct_answer"] = correct_answer
                    else:
                        solution["correct_answer"] = correct_answer
                
                # Ensure explanation exists
                if "explanation" not in solution:
                    solution["explanation"] = "Explanation for the answer"
                
                # Add key insights if missing
                if "key_insights" not in solution:
                    solution["key_insights"] = "Key principles related to this problem"

            return solution
        else:
            return {"error": "Failed to extract valid JSON from model response"}
    except Exception as e:
        print(f"Error generating individual solution: {str(e)}")
        traceback.print_exc()
        return {"error": f"Exception occurred: {str(e)}"}