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
            'title': 'The Rotated Array Mystery',
            'story_text': '''The system logs were once sorted correctly, but during a cyber-attack, a rotation occurred.
The data is still ordered internally. Your task is to locate a critical value as fast as possible.''',
            'riddle_question': 'Sorted array rotated to. Still use binary search by finding pivot. What search variant?',
            'correct_answer': 'rotatedbs'
        },
        {
            'title': 'The Corrupted Data Stream',
            'story_text': '''A corrupted data stream is being analyzed.
The system detects uninterrupted sequences where no character repeats.
Your task is to find the strongest such signal.''',
            'riddle_question': 'Slide through "abcabcbb". Stop and restart when any letter repeats. Track longest unique stretch. What string technique?',
            'correct_answer': 'uniquesubstring'
        },
        {
            'title': 'The Encrypted Numeric Key',
            'story_text': '''A numeric key is encrypted into smaller components.
Each digit contributes to the final checksum.''',
            'riddle_question': 'Take any number, like 1234. Break it into single digits (1, 2, 3, 4) and add them together. What is this total called in coding problems?',
            'correct_answer': 'digitsum'
        },
        {
            'title': 'The System Validation Check',
            'story_text': '''The system validates values based on pairing logic.
If a number can be perfectly paired, it passes the check.''',
            'riddle_question': 'If a number divides by 2 with zero remainder, it\'s one type. Otherwise, it\'s the other. What check are you doing?',
            'correct_answer': 'parity'
        }
    ]
    
    for story in stories:
        conn.execute('''
            INSERT OR IGNORE INTO stories (title, story_text, riddle_question, correct_answer)
            VALUES (?, ?, ?, ?)
        ''', (story['title'], story['story_text'], story['riddle_question'], story['correct_answer']))
    
    # Hints for each story
    all_hints = [
        # Story 1 hints - Rotated Array
        (1, 1, 'Think about binary search with a twist - find the pivot point first.', 1),
        (1, 2, 'The array is sorted but rotated. Find where the rotation happened.', 1),
        (1, 3, 'Compare middle element with first/last to determine which half to search.', 1),
        # Story 2 hints - Unique Substring
        (2, 1, 'Use a sliding window approach with two pointers.', 1),
        (2, 2, 'Keep track of characters you\'ve seen and their positions.', 1),
        # Story 3 hints - Digit Sum
        (3, 1, 'Extract digits using modulo (%) and division (/) operations.', 1),
        (3, 2, 'Loop through the number, taking each digit one by one.', 1),
        # Story 4 hints - Parity
        (4, 1, 'Use the modulo operator (%) with 2.', 1),
        (4, 2, 'If remainder is 0, it\'s even. Otherwise, it\'s odd.', 1)
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
            'title': 'Rotated Array Search',
            'problem_statement': '''Find the index of target value X in a rotated sorted array.

A rotated sorted array is a sorted array that has been rotated at some pivot.
For example: [4,5,6,7,0,1,2] is a rotation of [0,1,2,4,5,6,7]

Your solution must run in O(log N) time complexity.''',
            'constraints': 'Array size: 1 ≤ N ≤ 1000\nArray elements: -1000 ≤ arr[i] ≤ 1000\nTarget: -1000 ≤ X ≤ 1000',
            'sample_input': '7\n4 5 6 7 0 1 2\n0',
            'sample_output': '4',
            'test_cases': json.dumps([
                {'input': '7\n4 5 6 7 0 1 2\n0', 'output': '4'},
                {'input': '7\n4 5 6 7 0 1 2\n3', 'output': '-1'},
                {'input': '5\n1 2 3 4 5\n3', 'output': '2'},
                {'input': '4\n2 3 4 1\n1', 'output': '3'}
            ])
        },
        {
            'story_id': 2,
            'title': 'Longest Unique Substring',
            'problem_statement': '''Find the length of the longest substring without repeating characters.

Given a string S, return the length of the longest substring that contains all unique characters.

Example: "abcabcbb" → longest unique substring is "abc" with length 3''',
            'constraints': 'String length: 1 ≤ |S| ≤ 1000\nString contains only ASCII characters',
            'sample_input': 'abcabcbb',
            'sample_output': '3',
            'test_cases': json.dumps([
                {'input': 'abcabcbb', 'output': '3'},
                {'input': 'bbbbb', 'output': '1'},
                {'input': 'pwwkew', 'output': '3'},
                {'input': 'abcdef', 'output': '6'}
            ])
        },
        {
            'story_id': 3,
            'title': 'Digit Sum Calculator',
            'problem_statement': '''Calculate the sum of all digits in a given integer N.

For example: N = 1234 → sum = 1 + 2 + 3 + 4 = 10

Handle both positive and negative numbers (ignore the negative sign).''',
            'constraints': 'Integer range: -10^9 ≤ N ≤ 10^9',
            'sample_input': '1234',
            'sample_output': '10',
            'test_cases': json.dumps([
                {'input': '1234', 'output': '10'},
                {'input': '0', 'output': '0'},
                {'input': '999', 'output': '27'},
                {'input': '-123', 'output': '6'}
            ])
        },
        {
            'story_id': 4,
            'title': 'Even or Odd Checker',
            'problem_statement': '''Determine whether a given integer N is EVEN or ODD.

If N is divisible by 2 (remainder is 0), print "EVEN"
Otherwise, print "ODD"''',
            'constraints': 'Integer range: -10^9 ≤ N ≤ 10^9',
            'sample_input': '4',
            'sample_output': 'EVEN',
            'test_cases': json.dumps([
                {'input': '4', 'output': 'EVEN'},
                {'input': '7', 'output': 'ODD'},
                {'input': '0', 'output': 'EVEN'},
                {'input': '-3', 'output': 'ODD'}
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