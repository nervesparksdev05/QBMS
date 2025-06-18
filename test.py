from utils.model_interface import generate_questions

# Test content for question generation
test_content = {1: "This is a test paragraph about planets. Mercury is the closest planet to the sun. Venus is the hottest planet."}

# Generate questions based on the test content
questions = generate_questions(
    content=test_content,
    subject="Astronomy",
    num_questions=2,
    difficulty_distribution={"easy": 1, "medium": 1}
)

# Print the generated questions
print(questions)