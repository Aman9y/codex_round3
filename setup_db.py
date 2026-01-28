import sqlite3
import json
import bcrypt

def setup_database():
    """Initialize database with sample data"""
    conn = sqlite3.connect('database/contest.db')
    
    # Create tables (skip if exists)
    try:
        with open('database/schema.sql', 'r') as f:
            conn.executescript(f.read())
    except sqlite3.OperationalError:
        pass  # Tables already exist
    
    # Sample teams
    teams = [
        ('team01', 'alpha', 'pass123'),
        ('team02', 'beta', 'pass123'),
        ('team03', 'gamma', 'pass123'),
        ('team04', 'delta', 'pass123'),
        ('team05', 'epsilon', 'pass123'),
    ]
    
    for team_id, username, password in teams:
        # Hash password with bcrypt
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        conn.execute(
            'INSERT OR IGNORE INTO teams (team_id, username, password, plain_password) VALUES (?, ?, ?, ?)',
            (team_id, username, hashed_password.decode('utf-8'), password)
        )
    
    # Multiple stories
    stories = [
        {
            'title': 'The Mystery of the Lost Algorithm',
            'story_text': '''In the ancient kingdom of Codelandia, there lived a wise programmer named Ada. 
She discovered a magical algorithm that could solve any problem in the world. However, one day, 
the algorithm went missing! The only clue she left behind was a riddle that would reveal the 
location of her precious algorithm.''',
            'riddle_question': 'I am not alive, but I grow; I don\'t have lungs, but I need air; I don\'t have a mouth, but water kills me. What am I?',
            'correct_answer': 'fire'
        },
        {
            'title': 'The Secret of the Binary Forest',
            'story_text': '''Deep in the Binary Forest, ancient trees store secrets in their rings. Each ring represents a number, 
and the forest\'s magic lies in understanding patterns. A young coder must solve the forest\'s riddle 
to unlock the power of recursive thinking.''',
            'riddle_question': 'I can be cracked, I can be made, I can be told, I can be played. What am I?',
            'correct_answer': 'joke'
        },
        {
            'title': 'The Palindrome Palace Mystery',
            'story_text': '''In the Palindrome Palace, everything reads the same forwards and backwards. The palace guards 
speak only in palindromes, and visitors must prove their worth by solving the palace\'s ancient riddle 
before accessing the coding chamber.''',
            'riddle_question': 'The more you take, the more you leave behind. What am I?',
            'correct_answer': 'footsteps'
        }
    ]
    
    for story in stories:
        conn.execute('''
            INSERT OR IGNORE INTO stories (title, story_text, riddle_question, correct_answer)
            VALUES (?, ?, ?, ?)
        ''', (story['title'], story['story_text'], story['riddle_question'], story['correct_answer']))
    
    # Hints for each story
    all_hints = [
        # Story 1 hints
        (1, 1, 'Think about something that consumes oxygen to survive.', 1),
        (1, 2, 'This element is one of the four classical elements in ancient philosophy.', 1),
        (1, 3, 'It produces light and heat, and can spread rapidly.', 1),
        # Story 2 hints
        (2, 1, 'Think about something that makes people laugh.', 1),
        (2, 2, 'It can be a riddle, a pun, or a funny story.', 1),
        # Story 3 hints
        (3, 1, 'Think about what you create when you walk.', 1),
        (3, 2, 'Every step you take leaves a mark behind you.', 1)
    ]
    
    for story_id, hint_number, hint_text, penalty in all_hints:
        conn.execute('''
            INSERT OR IGNORE INTO hints (story_id, hint_number, hint_text, penalty_points)
            VALUES (?, ?, ?, ?)
        ''', (story_id, hint_number, hint_text, penalty))
    
    # Coding questions for each story
    coding_questions = [
        {
            'story_id': 1,
            'title': 'Ada\'s Factorial Challenge',
            'problem_statement': '''Ada's lost algorithm was actually a function to calculate factorials!

Write a Python program that reads an integer from input and prints its factorial.

Factorial of n (n!) = n × (n-1) × (n-2) × ... × 1
Example: 5! = 5 × 4 × 3 × 2 × 1 = 120''',
            'constraints': 'Input: 0 ≤ n ≤ 10',
            'sample_input': '5',
            'sample_output': '120',
            'test_cases': json.dumps([
                {'input': '5', 'output': '120'},
                {'input': '0', 'output': '1'},
                {'input': '1', 'output': '1'},
                {'input': '3', 'output': '6'}
            ])
        },
        {
            'story_id': 2,
            'title': 'Binary Forest Fibonacci',
            'problem_statement': '''The Binary Forest reveals its secret: the Fibonacci sequence!

Write a Python program that reads an integer n and prints the nth Fibonacci number.

Fibonacci sequence: 0, 1, 1, 2, 3, 5, 8, 13, 21...
F(0) = 0, F(1) = 1, F(n) = F(n-1) + F(n-2)''',
            'constraints': 'Input: 0 ≤ n ≤ 20',
            'sample_input': '6',
            'sample_output': '8',
            'test_cases': json.dumps([
                {'input': '0', 'output': '0'},
                {'input': '1', 'output': '1'},
                {'input': '6', 'output': '8'},
                {'input': '10', 'output': '55'}
            ])
        },
        {
            'story_id': 3,
            'title': 'Palindrome Palace Checker',
            'problem_statement': '''The Palindrome Palace needs a guardian program!

Write a Python program that reads a string and checks if it\'s a palindrome.
Print "YES" if it\'s a palindrome, "NO" otherwise.

A palindrome reads the same forwards and backwards (ignore case and spaces).''',
            'constraints': 'Input: string with length ≤ 100',
            'sample_input': 'racecar',
            'sample_output': 'YES',
            'test_cases': json.dumps([
                {'input': 'racecar', 'output': 'YES'},
                {'input': 'hello', 'output': 'NO'},
                {'input': 'A man a plan a canal Panama', 'output': 'YES'},
                {'input': 'race a car', 'output': 'NO'}
            ])
        }
    ]
    
    for question in coding_questions:
        conn.execute('''
            INSERT OR IGNORE INTO coding_questions 
            (story_id, title, problem_statement, constraints, sample_input, sample_output, test_cases, base_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (question['story_id'], question['title'], question['problem_statement'], 
              question['constraints'], question['sample_input'], question['sample_output'],
              question['test_cases'], 12.5))
    
    conn.commit()
    conn.close()
    print("Database setup complete!")
    print("\nSample Teams:")
    for team_id, username, password in teams:
        print(f"Username: {username}, Password: {password}")
    print("\nStories Created:")
    for i, story in enumerate(stories, 1):
        print(f"{i}. {story['title']}")
    print("\nCoding Questions:")
    for question in coding_questions:
        print(f"Story {question['story_id']}: {question['title']}")

if __name__ == '__main__':
    setup_database()