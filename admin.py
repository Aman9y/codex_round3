from flask import Flask, render_template, request, redirect, url_for, flash, Response, jsonify
import sqlite3
import json
import random
import secrets
import csv
import io
import bcrypt
import time
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
DATABASE = 'database/contest.db'

# Security headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Simple admin check - in production, implement proper authentication
        return f(*args, **kwargs)
    return decorated_function

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
@admin_required
def admin_dashboard():
    conn = get_db()
    
    # Get stats
    total_teams = conn.execute('SELECT COUNT(*) as count FROM teams').fetchone()['count']
    total_submissions = conn.execute('SELECT COUNT(*) as count FROM submissions').fetchone()['count']
    teams_solved_story = conn.execute('SELECT COUNT(*) as count FROM team_progress WHERE story_solved = TRUE').fetchone()['count']
    
    # Get recent submissions
    recent_submissions = conn.execute('''
        SELECT s.*, t.username,
               CASE WHEN COALESCE(ts.max_switches, 0) > 0 THEN 'Yes' ELSE 'No' END as tab_alert
        FROM submissions s 
        JOIN teams t ON s.team_id = t.team_id 
        LEFT JOIN (
            SELECT team_id, MAX(switch_count) as max_switches
            FROM tab_switches 
            GROUP BY team_id
        ) ts ON s.team_id = ts.team_id
        ORDER BY s.submitted_at DESC 
        LIMIT 10
    ''').fetchall()
    
    conn.close()
    
    return render_template('admin/dashboard.html', 
                         total_teams=total_teams,
                         total_submissions=total_submissions,
                         teams_solved_story=teams_solved_story,
                         recent_submissions=recent_submissions)

@app.route('/teams')
@admin_required
def manage_teams():
    conn = get_db()
    teams = conn.execute('''
        SELECT t.*, 
               COUNT(s.id) as submission_count,
               MAX(s.submitted_at) as last_submission,
               COALESCE(ts.max_switches, 0) as tab_switches
        FROM teams t
        LEFT JOIN submissions s ON t.team_id = s.team_id
        LEFT JOIN (
            SELECT team_id, MAX(switch_count) as max_switches
            FROM tab_switches 
            GROUP BY team_id
        ) ts ON t.team_id = ts.team_id
        GROUP BY t.id
        ORDER BY t.created_at
    ''').fetchall()
    conn.close()
    return render_template('admin/teams.html', teams=teams)

@app.route('/add_team', methods=['POST'])
@admin_required
def add_team():
    team_id = request.form.get('team_id', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    
    # Input validation
    if not team_id or not username or not password:
        flash('All fields are required!')
        return redirect(url_for('manage_teams'))
    
    if len(team_id) > 50 or len(username) > 50 or len(password) > 100:
        flash('Input too long!')
        return redirect(url_for('manage_teams'))
    
    conn = get_db()
    try:
        # Hash the password using bcrypt
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        conn.execute(
            'INSERT INTO teams (team_id, username, password, plain_password) VALUES (?, ?, ?, ?)',
            (team_id, username, hashed_password.decode('utf-8'), password)
        )
        conn.commit()
        flash('Team added successfully!')
    except Exception as e:
        flash(f'Error adding team: {str(e)}')
        print(f"Database error: {e}")  # Debug output
    finally:
        conn.close()
    
    return redirect(url_for('manage_teams'))

@app.route('/submissions')
@admin_required
def view_submissions():
    conn = get_db()
    submissions = conn.execute('''
        SELECT s.*, t.username, cq.title as question_title
        FROM submissions s
        JOIN teams t ON s.team_id = t.team_id
        JOIN coding_questions cq ON s.story_id = cq.story_id
        ORDER BY s.submitted_at DESC
    ''').fetchall()
    conn.close()
    return render_template('admin/submissions.html', submissions=submissions)

@app.route('/submissions/download')
@admin_required
def download_submissions_csv():
    conn = get_db()
    submissions = conn.execute('''
        SELECT s.*, t.username, cq.title as question_title
        FROM submissions s
        JOIN teams t ON s.team_id = t.team_id
        JOIN coding_questions cq ON s.story_id = cq.story_id
        ORDER BY s.submitted_at DESC
    ''').fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Team', 'Question', 'Score', 'Tests Passed', 'Total Tests', 'IP Address', 'Submitted At', 'Code'])
    
    for sub in submissions:
        writer.writerow([
            sub['username'],
            sub['question_title'],
            sub['score'],
            sub['passed_tests'],
            sub['total_tests'],
            sub['ip_address'] or 'N/A',
            sub['submitted_at'],
            sub['code']
        ])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=submissions.csv'}
    )

@app.route('/violations/download')
@admin_required
def download_violations_csv():
    conn = get_db()
    violations = conn.execute('''
        SELECT ts.team_id, t.username, t.ip_address, 
               ts.switch_count, ts.timestamp
        FROM tab_switches ts
        JOIN teams t ON ts.team_id = t.team_id
        ORDER BY ts.timestamp DESC
    ''').fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Team ID', 'Username', 'IP Address', 'Tab Switch Count', 'Timestamp'])
    
    for violation in violations:
        writer.writerow([
            violation['team_id'],
            violation['username'],
            violation['ip_address'] or 'N/A',
            violation['switch_count'],
            violation['timestamp']
        ])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=violations.csv'}
    )

@app.route('/timer')
@admin_required
def timer_control():
    conn = get_db()
    
    # Get current timer status
    try:
        config = conn.execute('SELECT key, value FROM contest_config WHERE key IN ("contest_start_time", "contest_duration")').fetchall()
        config_dict = {row['key']: int(row['value']) for row in config}
    except:
        config_dict = {'contest_start_time': 0, 'contest_duration': 0}
    
    start_time = config_dict.get('contest_start_time', 0)
    duration = config_dict.get('contest_duration', 0)
    
    status = {
        'started': start_time > 0,
        'start_time': start_time,
        'duration': duration,
        'duration_hours': duration // 3600,
        'duration_minutes': (duration % 3600) // 60
    }
    
    if start_time > 0:
        elapsed = int(time.time()) - start_time
        remaining = max(0, duration - elapsed)
        status.update({
            'elapsed': elapsed,
            'remaining': remaining,
            'finished': remaining == 0
        })
    
    conn.close()
    return render_template('admin/timer.html', status=status)

@app.route('/timer/control', methods=['POST'])
@admin_required
def timer_action():
    action = request.json.get('action')
    
    conn = get_db()
    
    try:
        if action == 'start':
            conn.execute('INSERT OR REPLACE INTO contest_config (key, value) VALUES ("contest_start_time", ?)', 
                       (str(int(time.time())),))
        elif action == 'reset':
            conn.execute('INSERT OR REPLACE INTO contest_config (key, value) VALUES ("contest_start_time", "0")')
        elif action == 'extend':
            minutes = request.json.get('minutes', 30)
            result = conn.execute('SELECT value FROM contest_config WHERE key = "contest_duration"').fetchone()
            current_duration = int(result['value']) if result else 0
            new_duration = current_duration + (minutes * 60)
            conn.execute('INSERT OR REPLACE INTO contest_config (key, value) VALUES ("contest_duration", ?)', 
                       (str(new_duration),))
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/randomization')
def view_randomization():
    conn = get_db()
    teams = conn.execute('SELECT team_id, username FROM teams ORDER BY team_id').fetchall()
    
    randomization_info = []
    for team in teams:
        team_seed = hash(team['team_id']) % 1000
        random.seed(team_seed)
        
        all_stories = conn.execute('SELECT id, title FROM stories ORDER BY id').fetchall()
        story_list = list(all_stories)
        random.shuffle(story_list)
        
        story_order = [f"{s['id']}: {s['title']}" for s in story_list]
        randomization_info.append({
            'team': f"{team['username']} ({team['team_id']})",
            'story_order': story_order
        })
    
    conn.close()
    
    return f'''
    <html><head><title>Question Randomization</title></head><body>
    <h1>Question Randomization by Team</h1>
    <p><a href="/">← Back to Dashboard</a></p>
    
    <table border="1" style="width:100%; border-collapse:collapse">
        <tr><th>Team</th><th>Story Order</th></tr>
        {"\n".join([f"<tr><td>{info['team']}</td><td>{', '.join(info['story_order'])}</td></tr>" for info in randomization_info])}
    </table>
    
    <p><strong>Note:</strong> Each team gets the same stories but in different order to prevent cheating.</p>
    </body></html>
    '''

if __name__ == '__main__':
    app.run( port=5123, debug=True) #host='0.0.0.0' for external access