# LAN-Based Story-Driven Coding Contest System

## � About

**Codex Round 3** is a comprehensive, LAN-based coding contest platform designed for educational institutions, coding clubs, and competitive programming events. Unlike traditional coding platforms, this system incorporates storytelling elements to make programming challenges more engaging and memorable.

### 🎯 Key Features

- **Story-Driven Challenges**: Each coding problem is tied to an intriguing story and riddle, creating a narrative-driven learning experience
- **Real-Time Leaderboard**: Live ranking system with automatic score calculation and tie-breaking by submission time
- **Anti-Cheat Protection**: Comprehensive security measures including copy/paste blocking, dev tools prevention, tab switch detection, and behavioral monitoring
- **Admin Dashboard**: Separate admin panel for contest management, team monitoring, and real-time statistics
- **Multi-Language Support**: Currently supports Python and C programming languages
- **Mobile-Friendly**: Responsive design that works on desktops, tablets, and mobile devices
- **LAN-Ready**: Designed for local network deployment, perfect for school labs or coding competitions
- **Hint System**: Progressive hints with penalty points to encourage independent problem-solving

### 🏗️ Architecture

Built with Python Flask and SQLite, the system consists of:
- **Main Contest App** (`app.py`): Handles team authentication, story progression, code submission, and evaluation
- **Admin Panel** (`admin.py`): Administrative interface for contest management
- **Database Layer**: SQLite with comprehensive schema for teams, stories, questions, submissions, and anti-cheat tracking
- **Security Layer**: JavaScript-based anti-cheat system and server-side validation
- **Monitoring Tools**: System performance monitoring and contest analytics

### 🎮 Contest Flow

1. **Authentication**: Teams login with pre-assigned credentials
2. **Story Engagement**: Read engaging stories and solve riddles to unlock coding challenges
3. **Problem Solving**: Access coding problems with constraints, sample I/O, and test cases
4. **Code Submission**: Submit solutions with automatic evaluation and partial scoring
5. **Progression**: Unlock subsequent stories by solving previous challenges
6. **Competition**: Real-time leaderboard shows team rankings and progress

### 🛡️ Security & Fairness

- Session-based authentication with secure cookies
- Code execution in isolated sandbox with 10-second timeout
- Rate limiting on submissions and login attempts
- Comprehensive logging for audit trails
- Anti-cheat measures prevent unauthorized assistance
- Single submission enforcement per challenge

### 📊 Scoring System

- Base score of 100 points per coding challenge
- Partial credit based on test case success rate
- Hint penalties (-10 to -20 points per hint used)
- Tie-breaking by earliest submission time
- Live leaderboard updates every 10 seconds

This platform transforms traditional coding contests into immersive, story-driven experiences that motivate participants while maintaining academic integrity and competitive fairness.

## �🚀 Quick Setup Guide

### 1. Install Dependencies
```bash
pip install Flask==2.3.3
```

### 2. Initialize Database
```bash
python setup_db.py
# OR on Windows:
py setup_db.py
```

### 3. Start the Contest Server
```bash
python app.py
# OR on Windows:
py app.py
```

### 4. Access the System
- **Contest URL**: `http://[YOUR_LAPTOP_IP]:5000`
- **Admin Panel**: `http://[YOUR_LAPTOP_IP]:5123` (run `python admin.py`)

## 🔧 Finding Your IP Address

### Windows:
```cmd
ipconfig
```
Look for "IPv4 Address" under your Wi-Fi adapter.

### Example:
If your IP is `192.168.1.100`, participants access: `http://192.168.1.100:5000`

## 👥 Sample Login Credentials

| Username | Password |
|----------|----------|
| alpha    | pass123  |
| beta     | pass123  |
| gamma    | pass123  |
| delta    | pass123  |
| epsilon  | pass123  |

## 📁 System Architecture

```
codex3/
├── app.py                 # Main Flask application
├── admin.py              # Admin panel (optional)
├── setup_db.py           # Database initialization
├── requirements.txt      # Dependencies
├── database/
│   ├── schema.sql        # Database schema
│   └── contest.db        # SQLite database (created after setup)
├── templates/
│   ├── base.html         # Base template
│   ├── login.html        # Login page
│   ├── story.html        # Story/riddle page
│   ├── coding.html       # Coding IDE
│   ├── leaderboard.html  # Live leaderboard
│   ├── submission_complete.html
│   └── admin/            # Admin templates
└── static/               # Static files (if needed)
```

## 🎯 Contest Flow

1. **Login** → Teams use pre-assigned credentials
2. **Story** → Read story and solve riddle (hints available with penalties)
3. **Coding** → Unlock coding challenge after solving riddle
4. **Submit** → One-time submission with auto-evaluation
5. **Leaderboard** → Live ranking updates

## 🔒 Security Features

- **Session-based authentication** with secure cookies
- **Anti-cheat protection**: Copy/paste blocking, dev tools blocking, tab switch detection
- **Code execution sandbox** with timeout (10 seconds) and restricted imports
- **Rate limiting** on login attempts and code submissions
- **Input validation** and SQL injection protection
- **Security headers** (XSS protection, content type sniffing prevention)
- **Single submission enforcement** per question
- **IP address logging** for audit trails

## 🏆 Scoring System

- **Base Score**: 100 points per question
- **Test Cases**: Partial credit based on passed tests
- **Hint Penalties**: -10 to -20 points per hint
- **Tie Breaker**: Earliest submission time

## 🛠️ Admin Features

Run admin panel separately:
```bash
python admin.py
```

- View contest statistics
- Manage teams
- Monitor submissions
- Real-time dashboard

## 📊 Database Tables

- `teams` - Team credentials and info
- `stories` - Story content and riddles
- `coding_questions` - Programming challenges
- `submissions` - Code submissions and results
- `hints` - Available hints per story
- `hints_used` - Track hint usage and penalties
- `team_progress` - Track team advancement
- `tab_switches` - Anti-cheat violation logging

## 🔧 Customization

### Adding New Teams:
```python
# In setup_db.py, add to teams list:
('team06', 'zeta', 'pass123'),
```

### Adding New Stories:
Modify the story_data in `setup_db.py` or use admin panel.

### Changing Scoring:
Modify `base_score` in coding_questions table or hint penalties.

## 🚨 Troubleshooting

### Port Already in Use:
Change port in app.py: `app.run(host='0.0.0.0', port=5002)`

### Participants Can't Access:
1. Check Windows Firewall settings
2. Ensure all devices on same Wi-Fi network
3. Verify IP address is correct

### Code Execution Issues:
- Ensure Python is in system PATH
- Check timeout settings in execute_code function

## 📱 Mobile Friendly

The system works on mobile browsers - participants can code on phones/tablets if needed.

## 🎮 Sample Contest Question

**Story**: The Mystery of the Lost Algorithm
**Riddle**: "I am not alive, but I grow; I don't have lungs, but I need air; I don't have a mouth, but water kills me. What am I?"
**Answer**: fire
**Coding Challenge**: Implement factorial function

## 🔄 Live Features

- **Auto-refresh leaderboard** (10-second intervals)
- **Real-time scoring** after submissions
- **Session persistence** across page refreshes
- **Responsive design** for various screen sizes

## 📈 Scalability

Tested for 30+ teams on a standard laptop. For larger contests:
- Use more powerful hardware
- Consider database optimization
- Monitor system resources during contest