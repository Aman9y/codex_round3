from flask import Flask, render_template, request, redirect, url_for, flash, Response
import sqlite3
import json
import random
import secrets
import csv
import io
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
DATABASE = 'database/contest.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
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
def add_team():
    team_id = request.form['team_id']
    username = request.form['username']
    password = request.form['password']
    
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO teams (team_id, username, password) VALUES (?, ?, ?)',
            (team_id, username, password)
        )
        conn.commit()
        flash('Team added successfully!')
    except sqlite3.IntegrityError:
        flash('Team ID or username already exists!')
    finally:
        conn.close()
    
    return redirect(url_for('manage_teams'))

@app.route('/submissions')
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
    app.run(port=5123, debug=True) #host='0.0.0.0' for external access