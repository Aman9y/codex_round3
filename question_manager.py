import sqlite3
import json

def view_questions():
    """View all questions in detail"""
    conn = sqlite3.connect('database/contest.db')
    conn.row_factory = sqlite3.Row
    
    # Get stories and questions
    stories = conn.execute('SELECT * FROM stories ORDER BY id').fetchall()
    
    for story in stories:
        print(f"\n{'='*60}")
        print(f"STORY {story['id']}: {story['title']}")
        print(f"{'='*60}")
        print(f"Story: {story['story_text']}")
        print(f"\nRiddle: {story['riddle_question']}")
        print(f"Answer: {story['correct_answer']}")
        
        # Get coding question for this story
        question = conn.execute(
            'SELECT * FROM coding_questions WHERE story_id = ?', 
            (story['id'],)
        ).fetchone()
        
        if question:
            print(f"\n--- CODING CHALLENGE ---")
            print(f"Title: {question['title']}")
            print(f"Problem: {question['problem_statement']}")
            print(f"Constraints: {question['constraints']}")
            print(f"Sample Input: {question['sample_input']}")
            print(f"Sample Output: {question['sample_output']}")
            
            # Show test cases
            test_cases = json.loads(question['test_cases'])
            print(f"\nTest Cases ({len(test_cases)} total):")
            for i, tc in enumerate(test_cases, 1):
                print(f"  Test {i}: Input='{tc['input']}' Output='{tc['output']}'")
    
    conn.close()
    input("\nPress Enter to continue...")

def update_question():
    """Update coding questions easily"""
    conn = sqlite3.connect('database/contest.db')
    conn.row_factory = sqlite3.Row
    
    # Show current questions
    print("=== CURRENT QUESTIONS ===")
    questions = conn.execute('SELECT * FROM coding_questions ORDER BY story_id').fetchall()
    
    for q in questions:
        print(f"\nStory {q['story_id']}: {q['title']}")
        print(f"Problem: {q['problem_statement'][:100]}...")
    
    # Select question to update
    story_id = input("\nEnter story ID to update (1-3): ")
    
    if story_id not in ['1', '2', '3']:
        print("Invalid story ID!")
        return
    
    print(f"\n=== UPDATE STORY {story_id} QUESTION ===")
    
    # Get new question details
    title = input("New title: ")
    problem = input("New problem statement: ")
    constraints = input("Constraints: ")
    sample_input = input("Sample input: ")
    sample_output = input("Sample output: ")
    
    # Get test cases
    print("\nEnter test cases (press Enter with empty input to finish):")
    test_cases = []
    i = 1
    while True:
        test_input = input(f"Test {i} input (or Enter to finish): ")
        if not test_input:
            break
        test_output = input(f"Test {i} output: ")
        test_cases.append({'input': test_input, 'output': test_output})
        i += 1
    
    if not test_cases:
        print("No test cases provided!")
        return
    
    # Update database
    conn.execute('''
        UPDATE coding_questions 
        SET title = ?, problem_statement = ?, constraints = ?, 
            sample_input = ?, sample_output = ?, test_cases = ?
        WHERE story_id = ?
    ''', (title, problem, constraints, sample_input, sample_output, 
          json.dumps(test_cases), story_id))
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Question for Story {story_id} updated successfully!")

def add_new_story():
    """Add a completely new story and question"""
    conn = sqlite3.connect('database/contest.db')
    conn.row_factory = sqlite3.Row
    
    print("=== ADD NEW STORY ===")
    
    # Story details
    title = input("Story title: ")
    story_text = input("Story text: ")
    riddle = input("Riddle question: ")
    answer = input("Riddle answer: ")
    
    # Add story
    cursor = conn.execute('''
        INSERT INTO stories (title, story_text, riddle_question, correct_answer)
        VALUES (?, ?, ?, ?)
    ''', (title, story_text, riddle, answer))
    
    story_id = cursor.lastrowid
    
    # Coding question
    print(f"\n=== ADD CODING QUESTION FOR STORY {story_id} ===")
    q_title = input("Question title: ")
    problem = input("Problem statement: ")
    constraints = input("Constraints: ")
    sample_input = input("Sample input: ")
    sample_output = input("Sample output: ")
    
    # Test cases
    print("\nEnter test cases:")
    test_cases = []
    i = 1
    while True:
        test_input = input(f"Test {i} input (or Enter to finish): ")
        if not test_input:
            break
        test_output = input(f"Test {i} output: ")
        test_cases.append({'input': test_input, 'output': test_output})
        i += 1
    
    # Add coding question
    conn.execute('''
        INSERT INTO coding_questions 
        (story_id, title, problem_statement, constraints, sample_input, sample_output, test_cases, base_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, 100)
    ''', (story_id, q_title, problem, constraints, sample_input, sample_output, json.dumps(test_cases)))
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ New story {story_id} added successfully!")

def main():
    print("=== QUESTION MANAGER ===")
    print("1. View all questions")
    print("2. Update existing question")
    print("3. Add new story + question")
    print("4. Exit")
    
    choice = input("\nChoose option (1-4): ")
    
    if choice == '1':
        view_questions()
    elif choice == '2':
        update_question()
    elif choice == '3':
        add_new_story()
    elif choice == '4':
        print("Goodbye!")
    else:
        print("Invalid choice!")

if __name__ == '__main__':
    main()