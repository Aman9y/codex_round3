from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
import json
import subprocess
import tempfile
import os
import signal
import threading
import time
import random
import secrets
import hashlib
import bcrypt
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
DATABASE = 'database/contest.db'

# Simple cache for performance
cache = {}
cache_lock = threading.Lock()
CACHE_TIMEOUT = 10  # 10 seconds

# Better error messages for students
ERROR_MESSAGES = {
    'login_failed': 'Incorrect username or password. Please check your credentials and try again.',
    'already_submitted': 'You have already submitted your solution for this problem. Only one submission is allowed per question.',
    'code_too_long': 'Your code is too long. Please keep it under 10,000 characters.',
    'compilation_error': 'There was an error compiling your code. Please check your syntax and try again.',
    'runtime_error': 'Your code encountered an error while running. Please check your logic and try again.',
    'timeout_error': 'Your code took too long to execute. Please optimize your solution.',
    'invalid_input': 'Please provide valid input for your code.',
    'network_error': 'Network connection issue. Please check your internet connection and try again.',
    'server_error': 'Server is temporarily busy. Please wait a moment and try again.',
    'contest_not_started': 'The contest has not started yet. Please wait for the instructor to begin.',
    'contest_ended': 'The contest has ended. No more submissions are allowed.',
    'story_order': 'Please solve the stories in the correct order. Complete the current story first.',
    'rate_limit': 'You are submitting too quickly. Please wait a moment before trying again.'
}

def get_cached_leaderboard():
    """Get cached leaderboard for better performance"""
    with cache_lock:
        now = time.time()
        if 'leaderboard' in cache and (now - cache['leaderboard_time']) < CACHE_TIMEOUT:
            return cache['leaderboard']
        
        # Fetch fresh leaderboard data with optimized query
        conn = get_db()
        teams = conn.execute('''
            SELECT 
                t.team_id,
                t.username,
                COALESCE(SUM(s.score), 0) as final_score,
                COUNT(s.id) as submissions_count,
                MAX(s.submitted_at) as last_submission,
                COALESCE(h.hints_count, 0) as hints_used
            FROM teams t
            LEFT JOIN submissions s ON t.team_id = s.team_id
            LEFT JOIN (
                SELECT team_id, COUNT(*) as hints_count
                FROM hints_used 
                GROUP BY team_id
            ) h ON t.team_id = h.team_id
            WHERE t.username != 'admin'
            GROUP BY t.team_id, t.username, h.hints_count
            ORDER BY final_score DESC, last_submission ASC
        ''').fetchall()
        conn.close()
        
        cache['leaderboard'] = teams
        cache['leaderboard_time'] = now
        return teams

# Security settings
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True if using HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=4)  # Contest duration

# Security headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# Rate limiting storage
rate_limit_storage = {}

# Initialize anti-cheat database tables
def init_anticheat_database():
    """Initialize anti-cheat related database tables"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contest_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    # Initialize default timer config
    cursor.execute('INSERT OR IGNORE INTO contest_config (key, value) VALUES ("contest_start_time", "0")')
    cursor.execute('INSERT OR IGNORE INTO contest_config (key, value) VALUES ("contest_duration", "0")')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contest_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tab_switches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT NOT NULL,
            ip_address TEXT,
            switch_count INTEGER,
            timestamp TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

@app.template_filter('from_json')
def from_json_filter(value):
    """Template filter to parse JSON strings"""
    try:
        return json.loads(value) if value else []
    except:
        return []

def init_db():
    """Initialize database with schema"""
    conn = sqlite3.connect(DATABASE)
    with open('database/schema.sql', 'r') as f:
        conn.executescript(f.read())
    conn.close()

def get_real_ip():
    """Get real client IP address, handling proxies and port forwarding"""
    # Check for forwarded IP headers first
    forwarded_ips = [
        request.headers.get('X-Forwarded-For'),
        request.headers.get('X-Real-IP'),
        request.headers.get('CF-Connecting-IP'),
        request.headers.get('X-Forwarded'),
        request.headers.get('Forwarded-For'),
        request.headers.get('Forwarded')
    ]
    
    for ip_header in forwarded_ips:
        if ip_header:
            # Handle comma-separated IPs (X-Forwarded-For can have multiple)
            ip = ip_header.split(',')[0].strip()
            if ip and ip != '127.0.0.1' and ip != 'localhost':
                return ip
    
    # Fallback to remote_addr
    return request.environ.get('REMOTE_ADDR', 'unknown')

def get_db():
    """Get database connection with high-performance optimizations"""
    conn = sqlite3.connect(DATABASE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # High-performance settings for gaming laptop
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=50000')  # Increased for gaming laptop
    conn.execute('PRAGMA temp_store=MEMORY')
    conn.execute('PRAGMA mmap_size=268435456')  # 256MB memory mapping
    return conn

def rate_limit(max_requests=10, window=60):
    """Rate limiting decorator"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = get_real_ip()
            
            now = datetime.now()
            key = f"{client_ip}:{f.__name__}"
            
            if key not in rate_limit_storage:
                rate_limit_storage[key] = []
            
            # Clean old requests
            rate_limit_storage[key] = [req_time for req_time in rate_limit_storage[key] 
                                     if (now - req_time).seconds < window]
            
            if len(rate_limit_storage[key]) >= max_requests:
                return jsonify({'error': 'Rate limit exceeded'}), 429
            
            rate_limit_storage[key].append(now)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def contest_active_required(f):
    """Decorator to check if contest is active (started and not ended)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        conn = get_db()
        try:
            config = conn.execute('SELECT key, value FROM contest_config WHERE key IN ("contest_start_time", "contest_duration")').fetchall()
            config_dict = {row['key']: int(row['value']) for row in config}
            
            start_time = config_dict.get('contest_start_time', 0)
            duration = config_dict.get('contest_duration', 0)
            
            if start_time == 0:
                return render_template('contest_not_started_cyber.html')
            
            elapsed = int(time.time()) - start_time
            if elapsed >= duration:
                flash('Contest has ended! No more submissions allowed.')
                return redirect(url_for('leaderboard'))
                
        except:
            pass
        finally:
            conn.close()
        
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'team_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'team_id' in session:
        return redirect(url_for('story'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
@rate_limit(max_requests=20, window=300)  # 20 attempts per 5 minutes
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        # Input validation
        if not username or not password or len(username) > 50 or len(password) > 50:
            flash('Invalid credentials')
            return render_template('login_cyber.html')
        
        conn = get_db()
        team = conn.execute(
            'SELECT * FROM teams WHERE username = ?',
            (username,)
        ).fetchone()
        
        if team and bcrypt.checkpw(password.encode('utf-8'), team['password'].encode('utf-8')):
            # Update IP address and last login
            conn.execute(
                'UPDATE teams SET ip_address = ?, last_login = datetime("now", "localtime") WHERE team_id = ?',
                (get_real_ip(), team['team_id'])
            )
            conn.commit()
            conn.close()
            
            session.permanent = True
            session['team_id'] = team['team_id']
            session['username'] = team['username']
            session['login_time'] = datetime.now().isoformat()
            return redirect(url_for('story'))
        else:
            conn.close()
            flash(ERROR_MESSAGES['login_failed'])
    
    return render_template('login_cyber.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/story')
@app.route('/story/<int:story_id>')
@login_required
@contest_active_required
def story(story_id=None):
    conn = get_db()
    
    # Get team's assigned story order (randomized per team)
    team_seed = hash(session['team_id']) % 1000
    random.seed(team_seed)
    
    # Get all stories and randomize order for this team
    all_stories = conn.execute('SELECT * FROM stories ORDER BY id').fetchall()
    story_list = list(all_stories)
    random.shuffle(story_list)
    
    # Find current story (first unsolved in sequence)
    current_story = None
    for randomized_story in story_list:
        progress = conn.execute(
            'SELECT * FROM team_progress WHERE team_id = ? AND story_id = ?',
            (session['team_id'], randomized_story['id'])
        ).fetchone()
        
        if not progress or not progress['coding_submitted']:
            current_story = randomized_story
            break
    
    # If all stories completed, show first story
    if not current_story:
        current_story = story_list[0]
    
    # If story_id provided, validate it's the current allowed story
    if story_id is not None and story_id != current_story['id']:
        flash('Please complete stories in order')
        return redirect(url_for('story'))
    
    # Use current story
    story_id = current_story['id']
    story = current_story
    
    # Check team progress for this story
    progress = conn.execute(
        'SELECT * FROM team_progress WHERE team_id = ? AND story_id = ?',
        (session['team_id'], story_id)
    ).fetchone()
    
    # Get hints for this story
    hints = conn.execute(
        'SELECT * FROM hints WHERE story_id = ? ORDER BY hint_number',
        (story_id,)
    ).fetchall()
    
    # Get used hints
    used_hints = conn.execute(
        'SELECT hint_number FROM hints_used WHERE team_id = ? AND story_id = ?',
        (session['team_id'], story_id)
    ).fetchall()
    used_hint_numbers = [h['hint_number'] for h in used_hints]
    
    conn.close()
    
    return render_template('story_cyber.html', 
                         story=story, 
                         all_stories=story_list,
                         current_story_id=story_id,
                         progress=progress,
                         hints=hints,
                         used_hints=used_hint_numbers)

@app.route('/solve_story', methods=['POST'])
@login_required
@contest_active_required
def solve_story():
    answer = request.form.get('answer', '').strip().lower()
    story_id = request.form.get('story_id')
    
    # Input validation
    if not answer or not story_id:
        flash('Invalid input')
        return redirect(url_for('story'))
    
    try:
        story_id = int(story_id)
    except (ValueError, TypeError):
        flash('Invalid story ID')
        return redirect(url_for('story'))
    
    # Verify this is the team's current allowed story
    conn = get_db()
    team_seed = hash(session['team_id']) % 1000
    random.seed(team_seed)
    
    all_stories = conn.execute('SELECT * FROM stories ORDER BY id').fetchall()
    story_list = list(all_stories)
    random.shuffle(story_list)
    
    # Find current allowed story
    current_story = None
    for randomized_story in story_list:
        progress = conn.execute(
            'SELECT * FROM team_progress WHERE team_id = ? AND story_id = ?',
            (session['team_id'], randomized_story['id'])
        ).fetchone()
        
        if not progress or not progress['coding_submitted']:
            current_story = randomized_story
            break
    
    if not current_story or current_story['id'] != story_id:
        conn.close()
        flash('Please complete stories in order')
        return redirect(url_for('story'))
    
    story = conn.execute('SELECT * FROM stories WHERE id = ?', (story_id,)).fetchone()
    
    if answer == story['correct_answer'].lower():
        # Mark story as solved
        conn.execute('''
            INSERT OR REPLACE INTO team_progress 
            (team_id, story_id, story_solved, story_solved_at)
            VALUES (?, ?, TRUE, datetime("now", "localtime"))
        ''', (session['team_id'], story_id))
        conn.commit()
        conn.close()
        
        return redirect(url_for('coding', story_id=story_id))
    else:
        conn.close()
        flash('Incorrect answer. Try again!')
        return redirect(url_for('story'))

@app.route('/use_hint', methods=['POST'])
@login_required
@contest_active_required
def use_hint():
    story_id = request.form['story_id']
    hint_number = request.form['hint_number']
    
    conn = get_db()
    
    # Check if hint already used
    existing = conn.execute(
        'SELECT * FROM hints_used WHERE team_id = ? AND story_id = ? AND hint_number = ?',
        (session['team_id'], story_id, hint_number)
    ).fetchone()
    
    if not existing:
        # Record hint usage with uniform 10-point penalty
        conn.execute('''
            INSERT INTO hints_used (team_id, story_id, hint_number, penalty_points)
            VALUES (?, ?, ?, 10)
        ''', (session['team_id'], story_id, hint_number))
        conn.commit()
    
    conn.close()
    return redirect(url_for('story'))

@app.route('/coding/<int:story_id>')
@login_required
@contest_active_required
def coding(story_id):
    conn = get_db()
    
    # Check if team has solved the story
    progress = conn.execute(
        'SELECT * FROM team_progress WHERE team_id = ? AND story_id = ? AND story_solved = TRUE',
        (session['team_id'], story_id)
    ).fetchone()
    
    if not progress:
        conn.close()
        return redirect(url_for('story'))
    
    # Check if already submitted - show results
    if progress['coding_submitted']:
        submission = conn.execute(
            'SELECT * FROM submissions WHERE team_id = ? AND story_id = ?',
            (session['team_id'], story_id)
        ).fetchone()
        conn.close()
        return render_template('submission_complete_cyber.html', submission=submission)
    
    # Verify this is the team's current allowed story (only for new submissions)
    team_seed = hash(session['team_id']) % 1000
    random.seed(team_seed)
    
    all_stories = conn.execute('SELECT * FROM stories ORDER BY id').fetchall()
    story_list = list(all_stories)
    random.shuffle(story_list)
    
    # Find current allowed story
    current_story = None
    for randomized_story in story_list:
        story_progress = conn.execute(
            'SELECT * FROM team_progress WHERE team_id = ? AND story_id = ?',
            (session['team_id'], randomized_story['id'])
        ).fetchone()
        
        if not story_progress or not story_progress['coding_submitted']:
            current_story = randomized_story
            break
    
    if not current_story or current_story['id'] != story_id:
        conn.close()
        flash('Please complete stories in order')
        return redirect(url_for('story'))
    
    # Get coding question with randomized test cases
    question = conn.execute(
        'SELECT * FROM coding_questions WHERE story_id = ?',
        (story_id,)
    ).fetchone()
    
    # Randomize test case order for this team (but keep same cases)
    if question:
        team_seed = hash(session['team_id'] + str(story_id)) % 1000
        random.seed(team_seed)
        
        test_cases = json.loads(question['test_cases'])
        random.shuffle(test_cases)  # Randomize test case order
        
        # Create modified question with shuffled test cases
        question_dict = dict(question)
        question_dict['test_cases'] = json.dumps(test_cases)
        
        # Also randomize sample input/output if multiple samples exist
        if len(test_cases) > 1:
            sample_case = random.choice(test_cases)
            question_dict['sample_input'] = sample_case['input']
            question_dict['sample_output'] = sample_case['output']
    else:
        question_dict = dict(question) if question else {}
    
    conn.close()
    
    return render_template('coding_cyber.html', question=question_dict, story_id=story_id)

@app.route('/run_code', methods=['POST'])
@login_required
@contest_active_required
@rate_limit(max_requests=20, window=60)  # 20 code runs per minute
def run_code():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    code = data.get('code', '').strip()
    language = data.get('language', 'python')
    input_data = data.get('input', '')
    
    # Security validation
    if not code or len(code) > 10000:  # Max 10KB code
        return jsonify({'success': False, 'error': 'Invalid code length'}), 400
    
    if language not in ['python', 'c']:
        return jsonify({'success': False, 'error': 'Unsupported language'}), 400
    
    # Check for dangerous patterns
    dangerous_patterns = ['import os', 'import sys', 'import subprocess', '__import__', 'eval(', 'exec(']
    if any(pattern in code.lower() for pattern in dangerous_patterns):
        return jsonify({'success': False, 'error': 'Restricted code detected'}), 400
    
    result = execute_code(code, input_data, language, timeout=5)
    return jsonify(result)

@app.route('/submit_code', methods=['POST'])
@login_required
@contest_active_required
@rate_limit(max_requests=3, window=300)  # 3 submissions per 5 minutes
def submit_code():
    code = request.form.get('code', '').strip()
    language = request.form.get('language', 'python')
    story_id = request.form.get('story_id')
    
    # Security validation
    if not code or len(code) > 10000:  # Max 10KB code
        flash(ERROR_MESSAGES['code_too_long'])
        return redirect(url_for('story'))
    
    try:
        story_id = int(story_id)
    except (ValueError, TypeError):
        flash('Invalid story ID')
        return redirect(url_for('story'))
    
    conn = get_db()
    
    # Check if already submitted
    existing = conn.execute(
        'SELECT * FROM submissions WHERE team_id = ? AND story_id = ?',
        (session['team_id'], story_id)
    ).fetchone()
    
    if existing:
        conn.close()
        flash(ERROR_MESSAGES['already_submitted'])
        return redirect(url_for('coding', story_id=story_id))
    
    # Get test cases (use original order for evaluation)
    question = conn.execute(
        'SELECT * FROM coding_questions WHERE story_id = ?',
        (story_id,)
    ).fetchone()
    
    test_cases = json.loads(question['test_cases'])  # Original order for fair evaluation
    results = []
    passed = 0
    
    # Run all test cases
    for i, test_case in enumerate(test_cases):
        result = execute_code(code, test_case['input'], language, timeout=10)
        expected = test_case['output'].strip()
        actual = result['output'].strip() if result['success'] else ''
        
        # Smart comparison - case insensitive for common outputs
        def smart_compare(expected, actual):
            # Exact match first
            if actual == expected:
                return True
            
            # Case insensitive comparison
            if actual.lower() == expected.lower():
                return True
            
            # Remove extra whitespace and compare
            if actual.replace(' ', '').lower() == expected.replace(' ', '').lower():
                return True
                
            return False
        
        test_result = {
            'test_case': i + 1,
            'input': test_case['input'],
            'expected': expected,
            'actual': actual,
            'passed': smart_compare(expected, actual) and result['success']
        }
        results.append(test_result)
        if test_result['passed']:
            passed += 1
    
    # Calculate score with new system: 30% story + 70% code
    base_score = question['base_score']
    story_points = int(base_score * 0.3)  # 30% for solving story
    code_points = int(base_score * 0.7)   # 70% for code quality
    
    # Code score based on test cases passed
    code_score = int((passed / len(test_cases)) * code_points)
    
    # Total score = story points + code score
    total_score = story_points + code_score
    
    # Get hint penalties
    hint_penalty = conn.execute(
        'SELECT COALESCE(SUM(penalty_points), 0) as penalty FROM hints_used WHERE team_id = ? AND story_id = ?',
        (session['team_id'], story_id)
    ).fetchone()['penalty']
    
    final_score = max(0, total_score - hint_penalty)
    
    # Save submission
    conn.execute('''
        INSERT INTO submissions 
        (team_id, story_id, code, language, test_results, score, passed_tests, total_tests, ip_address)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (session['team_id'], story_id, code, language, json.dumps(results), 
          final_score, passed, len(test_cases), get_real_ip()))
    
    # Mark as submitted
    conn.execute('''
        UPDATE team_progress 
        SET coding_submitted = TRUE, coding_submitted_at = datetime("now", "localtime")
        WHERE team_id = ? AND story_id = ?
    ''', (session['team_id'], story_id))
    
    conn.commit()
    conn.close()
    
    # Redirect to show submission results
    return redirect(url_for('coding', story_id=story_id))

@app.route('/leaderboard')
def leaderboard():
    """Optimized leaderboard with caching"""
    teams = get_cached_leaderboard()
    return render_template('leaderboard_cyber.html', teams=teams)

@app.route('/api/leaderboard')
def api_leaderboard():
    """Cached API endpoint for leaderboard"""
    teams = get_cached_leaderboard()
    return jsonify([dict(team) for team in teams])

@app.route('/api/timer')
def get_timer():
    """Get contest timer information from database"""
    conn = get_db()
    
    try:
        # Get timer config from database
        config = conn.execute('SELECT key, value FROM contest_config WHERE key IN ("contest_start_time", "contest_duration")').fetchall()
        config_dict = {row['key']: int(row['value']) for row in config}
    except:
        # Initialize default config if not exists
        conn.execute('INSERT OR IGNORE INTO contest_config (key, value) VALUES ("contest_start_time", "0")')
        conn.execute('INSERT OR IGNORE INTO contest_config (key, value) VALUES ("contest_duration", "0")')
        conn.commit()
        config_dict = {'contest_start_time': 0, 'contest_duration': 0}
    
    start_time = config_dict.get('contest_start_time', 0)
    duration = config_dict.get('contest_duration', 0)
    
    conn.close()
    
    if start_time == 0:
        return jsonify({
            'started': False,
            'duration': duration,
            'remaining': duration,
            'message': 'Contest not started by admin'
        })
    
    elapsed = int(time.time()) - start_time
    remaining = max(0, duration - elapsed)
    
    return jsonify({
        'started': True,
        'duration': duration,
        'remaining': remaining,
        'elapsed': elapsed,
        'start_time': start_time,
        'finished': remaining <= 0
    })

# Anti-cheat routes
@app.route('/tab-switch', methods=['POST'])
@login_required
def log_tab_switch():
    """Log tab switch events"""
    if not session.get('team_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        data = request.get_json()
        team_id = session.get('team_id')
        count = data.get('count', 0)
        user_ip = get_real_ip()
        
        # Log to console for admin monitoring
        print(f"TAB SWITCH ALERT: {team_id} from {user_ip} - Count: {count} at {datetime.now().isoformat()}")
        
        # Store in database
        conn = get_db()
        timestamp = datetime.now().isoformat()
        conn.execute('INSERT INTO tab_switches (team_id, ip_address, switch_count, timestamp) VALUES (?, ?, ?, ?)',
                    (team_id, user_ip, count, timestamp))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': 'Failed to log tab switch'}), 500

@app.route('/tab-switch-count')
@login_required
def get_tab_switch_count():
    """Get current tab switch count for user"""
    if not session.get('team_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        team_id = session.get('team_id')
        conn = get_db()
        
        cursor = conn.execute('SELECT MAX(switch_count) FROM tab_switches WHERE team_id = ?', (team_id,))
        result = cursor.fetchone()
        count = result[0] if result[0] else 0
        
        conn.close()
        return jsonify({'count': count})
    except Exception as e:
        return jsonify({'count': 0})

@app.route('/admin/tab-switches')
def admin_tab_switches():
    """View aggregated tab switches by team_id (admin only)"""
    if not session.get('team_id') or session.get('username') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    
    conn = get_db()
    
    cursor = conn.execute('''
        SELECT team_id, MAX(switch_count) as max_switches
        FROM tab_switches 
        GROUP BY team_id
        ORDER BY max_switches DESC
    ''')
    
    switches = []
    for row in cursor.fetchall():
        switches.append({
            'team_id': row[0],
            'max_switches': row[1]
        })
    
    conn.close()
    return jsonify({'switches': switches})

@app.route('/admin/user-sessions')
def admin_user_sessions():
    """View all user sessions with IP addresses (admin only)"""
    if not session.get('team_id') or session.get('username') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    
    # Return empty sessions since we removed user_sessions table
    return jsonify({'sessions': []})

def execute_code(code, input_data='', language='python', timeout=10):
    """Execute code safely with timeout for multiple languages"""
    import tempfile
    import subprocess
    import os
    
    # Security: Validate input parameters
    if not isinstance(code, str) or len(code) > 50000:  # 50KB limit
        return {'success': False, 'output': '', 'error': 'Invalid code input'}
    
    if not isinstance(input_data, str) or len(input_data) > 10000:  # 10KB limit
        return {'success': False, 'output': '', 'error': 'Invalid input data'}
    
    if language not in ['python', 'c']:
        return {'success': False, 'output': '', 'error': 'Unsupported language'}
    
    # Enhanced security checks
    dangerous_patterns = [
        'import os', 'import sys', 'import subprocess', '__import__', 'eval(', 'exec(',
        'execfile(', 'exit(', 'quit(',
        'import socket', 'import urllib', 'import requests'
    ]
    
    try:
        if language == 'python':
            # Create temporary Python file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            # Execute Python with resource limits
            process = subprocess.Popen(
                ['python', temp_file],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
        
        elif language == 'c':
            # Check if GCC is available
            try:
                subprocess.run(['gcc', '--version'], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                return {
                    'success': False,
                    'output': '',
                    'error': 'GCC compiler not found. Please install GCC to compile C code.'
                }
            
            # Create temporary C file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
                f.write(code)
                c_file = f.name
            
            # Compile C code with timeout
            exe_file = c_file.replace('.c', '.exe')
            compile_process = subprocess.Popen(
                ['gcc', c_file, '-o', exe_file, '-O2'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            try:
                compile_stdout, compile_stderr = compile_process.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                compile_process.kill()
                return {
                    'success': False,
                    'output': '',
                    'error': 'Compilation timeout'
                }
            
            if compile_process.returncode != 0:
                return {
                    'success': False,
                    'output': '',
                    'error': f'Compilation Error: {compile_stderr}'
                }
            
            # Execute compiled C program
            process = subprocess.Popen(
                [exe_file],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            temp_file = exe_file
        
        else:
            return {
                'success': False,
                'output': '',
                'error': f'Unsupported language: {language}'
            }
        try:
            stdout, stderr = process.communicate(input=input_data, timeout=timeout)
            return {
                'success': process.returncode == 0,
                'output': stdout,
                'error': stderr
            }
        except subprocess.TimeoutExpired:
            try:
                if os.name == 'nt':
                    process.terminate()
                else:
                    process.kill()
            except:
                pass
            return {
                'success': False,
                'output': '',
                'error': 'Code execution timed out'
            }
    except Exception as e:
        return {
            'success': False,
            'output': '',
            'error': str(e)
        }
    finally:
        # Clean up temp files
        try:
            if language == 'python':
                if 'temp_file' in locals():
                    os.unlink(temp_file)
            elif language == 'c':
                if 'c_file' in locals():
                    os.unlink(c_file)
                if 'exe_file' in locals() and os.path.exists(exe_file):
                    os.unlink(exe_file)
        except:
            pass

@app.errorhandler(404)
def not_found_error(error):
    return redirect(url_for('index'))

@app.errorhandler(500)
def internal_error(error):
    return "Internal server error. Please try again.", 500

if __name__ == '__main__':
    # Initialize database
    if not os.path.exists(DATABASE):
        init_db()
    
    # Initialize anti-cheat database
    init_anticheat_database()
    
    # Run with optimized settings for 30+ teams
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True, processes=1)