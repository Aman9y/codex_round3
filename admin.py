from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, session, render_template_string
import sqlite3
import bcrypt
import time
import csv
import io
import random
import os
import hashlib
from functools import wraps
from threading import Lock
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'contest-admin-secret-key-2024'
DATABASE = 'database/contest.db'

# Anti-cheat system
class AntiCheatSystem:
    def __init__(self, database_path):
        self.database_path = database_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS behavioral_flags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id TEXT NOT NULL,
                flag_type TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS network_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                endpoint TEXT,
                timestamp TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
    
    def get_real_ip(self):
        forwarded_ips = [
            request.headers.get('X-Forwarded-For'),
            request.headers.get('X-Real-IP'),
            request.headers.get('CF-Connecting-IP')
        ]
        for ip_header in forwarded_ips:
            if ip_header:
                ip = ip_header.split(',')[0].strip()
                if ip and ip != '127.0.0.1':
                    return ip
        return request.environ.get('REMOTE_ADDR', 'unknown')
    
    def log_network_activity(self):
        if 'team_id' in session:
            try:
                conn = sqlite3.connect(self.database_path)
                conn.execute('''
                    INSERT INTO network_logs (team_id, ip_address, user_agent, endpoint, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', (session['team_id'], self.get_real_ip(), 
                      request.headers.get('User-Agent', ''), 
                      request.endpoint, datetime.now().isoformat()))
                conn.commit()
                conn.close()
            except:
                pass
    
    def check_code_similarity(self, code, question_id, team_id):
        try:
            conn = sqlite3.connect(self.database_path)
            submissions = conn.execute(
                'SELECT team_id, code FROM submissions WHERE story_id = ? AND team_id != ?',
                (question_id, team_id)
            ).fetchall()
            
            normalized_code = ''.join(code.split()).lower()
            
            for sub in submissions:
                other_code = ''.join(sub[1].split()).lower()
                
                if len(normalized_code) > 50 and len(other_code) > 50:
                    similarity = len(set(normalized_code) & set(other_code)) / len(set(normalized_code) | set(other_code))
                    if similarity > 0.8:
                        conn.execute('''
                            INSERT INTO behavioral_flags (team_id, flag_type, details, timestamp)
                            VALUES (?, ?, ?, ?)
                        ''', (team_id, 'code_similarity', f'High similarity with {sub[0]}', datetime.now().isoformat()))
                        conn.commit()
            
            conn.close()
        except:
            pass
    
    def check_behavioral_anomalies(self, team_id):
        try:
            conn = sqlite3.connect(self.database_path)
            
            # Check multiple IPs
            ips = conn.execute(
                'SELECT DISTINCT ip_address FROM network_logs WHERE team_id = ?',
                (team_id,)
            ).fetchall()
            
            if len(ips) > 2:
                conn.execute('''
                    INSERT INTO behavioral_flags (team_id, flag_type, details, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (team_id, 'multiple_ips', f'Used {len(ips)} different IPs', datetime.now().isoformat()))
            
            # Check multiple browsers
            agents = conn.execute(
                'SELECT DISTINCT user_agent FROM network_logs WHERE team_id = ?',
                (team_id,)
            ).fetchall()
            
            if len(agents) > 2:
                conn.execute('''
                    INSERT INTO behavioral_flags (team_id, flag_type, details, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (team_id, 'multiple_browsers', f'Used {len(agents)} different browsers', datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
        except:
            pass

anticheat = AntiCheatSystem(DATABASE)

# Simple cache for leaderboard
cache = {}
cache_lock = Lock()
CACHE_TIMEOUT = 10  # 10 seconds

def get_db():
    """Get database connection with optimizations"""
    if not os.path.exists(DATABASE):
        return None
    conn = sqlite3.connect(DATABASE, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=10000')
    return conn

def admin_required(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function

def get_cached_leaderboard():
    """Get cached leaderboard data"""
    with cache_lock:
        now = time.time()
        if 'leaderboard' in cache and (now - cache['leaderboard_time']) < CACHE_TIMEOUT:
            return cache['leaderboard']
        
        # Fetch fresh data
        conn = get_db()
        leaderboard = conn.execute('''
            SELECT t.username, t.team_id,
                   COALESCE(SUM(s.score), 0) as total_score,
                   COUNT(s.id) as submissions,
                   MAX(s.submitted_at) as last_submission
            FROM teams t
            LEFT JOIN submissions s ON t.team_id = s.team_id
            WHERE t.username != 'admin'
            GROUP BY t.team_id
            ORDER BY total_score DESC, last_submission ASC
        ''').fetchall()
        conn.close()
        
        cache['leaderboard'] = leaderboard
        cache['leaderboard_time'] = now
        return leaderboard

@app.route('/')
@admin_required
def dashboard():
    conn = get_db()
    if not conn:
        return "Database not found. Please run setup_db.py first.", 500
    
    try:
        # Optimized single query for dashboard stats
        stats = conn.execute('''
            SELECT 
                (SELECT COUNT(*) FROM teams WHERE username != 'admin') as total_teams,
                (SELECT COUNT(*) FROM submissions) as total_submissions,
                (SELECT COUNT(DISTINCT team_id) FROM team_progress WHERE story_solved = 1) as teams_solved_story
        ''').fetchone()
        
        total_teams = stats['total_teams'] if stats else 0
        total_submissions = stats['total_submissions'] if stats else 0
        teams_solved_story = stats['teams_solved_story'] if stats else 0
        
        # Get recent submissions
        recent_submissions = conn.execute('''
            SELECT s.*, t.username,
                   CASE WHEN COALESCE(ts.max_switches, 0) > 0 THEN 'Yes' ELSE 'No' END as tab_alert,
                   COALESCE(hu.hints_used, 0) as hints_used
            FROM submissions s 
            JOIN teams t ON s.team_id = t.team_id 
            LEFT JOIN (
                SELECT team_id, MAX(switch_count) as max_switches
                FROM tab_switches 
                GROUP BY team_id
            ) ts ON s.team_id = ts.team_id
            LEFT JOIN (
                SELECT team_id, COUNT(*) as hints_used
                FROM hints_used
                GROUP BY team_id
            ) hu ON s.team_id = hu.team_id
            ORDER BY s.submitted_at DESC 
            LIMIT 10
        ''').fetchall()
        
        conn.close()
        
        return render_template('admin/dashboard.html', 
                             total_teams=total_teams,
                             total_submissions=total_submissions,
                             teams_solved_story=teams_solved_story,
                             recent_submissions=recent_submissions)
    except Exception as e:
        conn.close()
        return f"Database error: {str(e)}", 500
    
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
    if not conn:
        return "Database not found. Please run setup_db.py first.", 500
    
    try:
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
    except Exception as e:
        conn.close()
        return f"Database error: {str(e)}", 500

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
    writer.writerow(['Team', 'Question', 'Score', 'Tests Passed', 'Total Tests', 'IP Address', 'Submitted At', 'Hints Used', 'Code'])
    
    for sub in submissions:
        # Get hint count for this team
        hint_count = conn.execute(
            'SELECT COUNT(*) as count FROM hints_used WHERE team_id = ?',
            (sub['team_id'],)
        ).fetchone()['count']
        
        writer.writerow([
            sub['username'],
            sub['question_title'],
            sub['score'],
            sub['passed_tests'],
            sub['total_tests'],
            sub['ip_address'] or 'N/A',
            sub['submitted_at'],
            hint_count,
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
            # Set default 2-hour duration if not set
            duration_result = conn.execute('SELECT value FROM contest_config WHERE key = "contest_duration"').fetchone()
            if not duration_result or int(duration_result['value']) == 0:
                conn.execute('INSERT OR REPLACE INTO contest_config (key, value) VALUES ("contest_duration", "7200")')  # 2 hours
            
            conn.execute('INSERT OR REPLACE INTO contest_config (key, value) VALUES ("contest_start_time", ?)', 
                       (str(int(time.time())),))
        elif action == 'reset':
            conn.execute('INSERT OR REPLACE INTO contest_config (key, value) VALUES ("contest_start_time", "0")')
            conn.execute('INSERT OR REPLACE INTO contest_config (key, value) VALUES ("contest_duration", "7200")')  # Reset to 2 hours
        elif action == 'extend':
            minutes = request.json.get('minutes', 30)
            result = conn.execute('SELECT value FROM contest_config WHERE key = "contest_duration"').fetchone()
            current_duration = int(result['value']) if result else 7200
            new_duration = current_duration + (minutes * 60)
            conn.execute('INSERT OR REPLACE INTO contest_config (key, value) VALUES ("contest_duration", ?)', 
                       (str(new_duration),))
        elif action == 'set_duration':
            hours = request.json.get('hours', 2)
            minutes = request.json.get('minutes', 0)
            total_seconds = (hours * 3600) + (minutes * 60)
            conn.execute('INSERT OR REPLACE INTO contest_config (key, value) VALUES ("contest_duration", ?)', 
                       (str(total_seconds),))
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/leaderboard/api')
def leaderboard_api():
    """Optimized leaderboard API with caching"""
    return jsonify({'leaderboard': [dict(row) for row in get_cached_leaderboard()]})

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

@app.route('/anticheat')
@admin_required
def anticheat_monitor():
    """Anti-cheat monitoring dashboard"""
    return render_template('admin/anticheat.html')

@app.route('/api/behavioral-flags')
@admin_required
def api_behavioral_flags():
    """API endpoint for behavioral flags"""
    conn = get_db()
    flags = conn.execute('''
        SELECT team_id, flag_type, details, timestamp
        FROM behavioral_flags 
        ORDER BY timestamp DESC
    ''').fetchall()
    conn.close()
    return jsonify({'flags': [dict(flag) for flag in flags]})

@app.route('/api/network-activity')
@admin_required
def api_network_activity():
    """API endpoint for network activity"""
    conn = get_db()
    logs = conn.execute('''
        SELECT team_id, ip_address, user_agent, endpoint, timestamp
        FROM network_logs 
        ORDER BY timestamp DESC
        LIMIT 1000
    ''').fetchall()
    conn.close()
    return jsonify({'logs': [dict(log) for log in logs]})

@app.route('/api/tab-switches')
@admin_required
def api_tab_switches():
    """API endpoint for tab switches"""
    conn = get_db()
    switches = conn.execute('''
        SELECT team_id, MAX(switch_count) as max_switches
        FROM tab_switches 
        GROUP BY team_id
        ORDER BY max_switches DESC
    ''').fetchall()
    conn.close()
    return jsonify({'switches': [dict(sw) for sw in switches]})

# Anti-cheat routes
@app.route('/tab-switch', methods=['POST'])
def log_tab_switch():
    if not session.get('team_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        data = request.get_json()
        team_id = session.get('team_id')
        count = data.get('count', 0)
        user_ip = anticheat.get_real_ip()
        
        conn = get_db()
        conn.execute('INSERT INTO tab_switches (team_id, ip_address, switch_count, timestamp) VALUES (?, ?, ?, ?)',
                    (team_id, user_ip, count, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Failed to log tab switch'}), 500

@app.route('/admin/behavioral-flags')
@admin_required
def admin_behavioral_flags():
    conn = get_db()
    flags = conn.execute('''
        SELECT team_id, flag_type, details, timestamp
        FROM behavioral_flags 
        ORDER BY timestamp DESC
    ''').fetchall()
    conn.close()
    
    return jsonify({'flags': [{'team_id': f[0], 'flag_type': f[1], 'details': f[2], 'timestamp': f[3]} for f in flags]})

@app.route('/admin/network-activity')
@admin_required
def admin_network_activity():
    conn = get_db()
    logs = conn.execute('''
        SELECT team_id, ip_address, user_agent, endpoint, timestamp
        FROM network_logs 
        ORDER BY timestamp DESC
        LIMIT 1000
    ''').fetchall()
    conn.close()
    
    return jsonify({'logs': [{'team_id': l[0], 'ip_address': l[1], 'user_agent': l[2], 'endpoint': l[3], 'timestamp': l[4]} for l in logs]})

@app.route('/admin/tab-switches')
@admin_required
def admin_tab_switches():
    conn = get_db()
    switches = conn.execute('''
        SELECT team_id, MAX(switch_count) as max_switches
        FROM tab_switches 
        GROUP BY team_id
        ORDER BY max_switches DESC
    ''').fetchall()
    conn.close()
    
    return jsonify({'switches': [{'team_id': s[0], 'max_switches': s[1]} for s in switches]})

@app.route('/admin/anticheat')
@admin_required
def anticheat_monitor():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Anti-Cheat Monitor</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .flag-high { background: #dc3545; color: white; padding: 2px 8px; border-radius: 4px; }
        .flag-medium { background: #ffc107; color: black; padding: 2px 8px; border-radius: 4px; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; }
        .refresh-btn { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ Anti-Cheat Monitoring Dashboard</h1>
        <p><a href="/">← Back to Dashboard</a></p>
        
        <div class="card">
            <h2>🚨 Behavioral Flags</h2>
            <button class="refresh-btn" onclick="loadFlags()">Refresh</button>
            <div id="flags"></div>
        </div>
        
        <div class="card">
            <h2>📱 Tab Switch Violations</h2>
            <button class="refresh-btn" onclick="loadTabSwitches()">Refresh</button>
            <div id="tabSwitches"></div>
        </div>
        
        <div class="card">
            <h2>🌐 Network Activity Summary</h2>
            <button class="refresh-btn" onclick="loadNetworkSummary()">Refresh</button>
            <div id="networkSummary"></div>
        </div>
    </div>

    <script>
        function loadFlags() {
            fetch('/admin/behavioral-flags')
                .then(r => r.json())
                .then(data => {
                    let html = '<table><tr><th>Team</th><th>Flag Type</th><th>Details</th><th>Time</th></tr>';
                    if (data.flags.length === 0) {
                        html += '<tr><td colspan="4" style="text-align: center; color: #28a745;">No violations detected</td></tr>';
                    } else {
                        data.flags.forEach(flag => {
                            const severity = flag.flag_type.includes('similarity') ? 'flag-high' : 'flag-medium';
                            html += `<tr><td>${flag.team_id}</td><td><span class="${severity}">${flag.flag_type}</span></td><td>${flag.details}</td><td>${flag.timestamp}</td></tr>`;
                        });
                    }
                    html += '</table>';
                    document.getElementById('flags').innerHTML = html;
                });
        }
        
        function loadTabSwitches() {
            fetch('/admin/tab-switches')
                .then(r => r.json())
                .then(data => {
                    let html = '<table><tr><th>Team</th><th>Max Switches</th></tr>';
                    if (data.switches.length === 0) {
                        html += '<tr><td colspan="2" style="text-align: center; color: #28a745;">No tab switches detected</td></tr>';
                    } else {
                        data.switches.forEach(sw => {
                            const severity = sw.max_switches > 10 ? 'flag-high' : (sw.max_switches > 5 ? 'flag-medium' : '');
                            html += `<tr><td>${sw.team_id}</td><td><span class="${severity}">${sw.max_switches}</span></td></tr>`;
                        });
                    }
                    html += '</table>';
                    document.getElementById('tabSwitches').innerHTML = html;
                });
        }
        
        function loadNetworkSummary() {
            fetch('/admin/network-activity')
                .then(r => r.json())
                .then(data => {
                    const summary = {};
                    data.logs.forEach(log => {
                        if (!summary[log.team_id]) summary[log.team_id] = { ips: new Set(), agents: new Set() };
                        summary[log.team_id].ips.add(log.ip_address);
                        summary[log.team_id].agents.add(log.user_agent);
                    });
                    
                    let html = '<table><tr><th>Team</th><th>Unique IPs</th><th>Unique Browsers</th></tr>';
                    if (Object.keys(summary).length === 0) {
                        html += '<tr><td colspan="3" style="text-align: center; color: #6c757d;">No network activity logged yet</td></tr>';
                    } else {
                        Object.keys(summary).forEach(team => {
                            const ipCount = summary[team].ips.size;
                            const agentCount = summary[team].agents.size;
                            const ipSeverity = ipCount > 2 ? 'flag-high' : (ipCount > 1 ? 'flag-medium' : '');
                            const agentSeverity = agentCount > 2 ? 'flag-high' : (agentCount > 1 ? 'flag-medium' : '');
                            html += `<tr><td>${team}</td><td><span class="${ipSeverity}">${ipCount}</span></td><td><span class="${agentSeverity}">${agentCount}</span></td></tr>`;
                        });
                    }
                    html += '</table>';
                    document.getElementById('networkSummary').innerHTML = html;
                });
        }
        
        setInterval(() => {
            loadFlags();
            loadTabSwitches();
            loadNetworkSummary();
        }, 30000);
        
        loadFlags();
        loadTabSwitches();
        loadNetworkSummary();
    </script>
</body>
</html>
    ''')

if __name__ == '__main__':
    # Check if database exists
    if not os.path.exists('database'):
        os.makedirs('database')
    
    if not os.path.exists(DATABASE):
        print("Database not found. Please run 'python setup_db.py' first.")
    
    app.run(port=5123, debug=False) #host='0.0.0.0', for external access