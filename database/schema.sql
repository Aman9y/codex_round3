-- Teams table
CREATE TABLE teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id TEXT UNIQUE NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    plain_password TEXT,
    ip_address TEXT,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
);

-- Stories/Riddles table
CREATE TABLE stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    story_text TEXT NOT NULL,
    riddle_question TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
);

-- Coding questions linked to stories
CREATE TABLE coding_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    problem_statement TEXT NOT NULL,
    constraints TEXT,
    sample_input TEXT,
    sample_output TEXT,
    test_cases TEXT, -- JSON format
    base_score INTEGER DEFAULT 100,
    allowed_languages TEXT DEFAULT 'python,c', -- Comma-separated list
    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (story_id) REFERENCES stories (id)
);

-- Team progress tracking
CREATE TABLE team_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id TEXT NOT NULL,
    story_id INTEGER NOT NULL,
    story_solved BOOLEAN DEFAULT FALSE,
    story_solved_at TIMESTAMP,
    coding_submitted BOOLEAN DEFAULT FALSE,
    coding_submitted_at TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES teams (team_id),
    FOREIGN KEY (story_id) REFERENCES stories (id),
    UNIQUE(team_id, story_id)
);

-- Submissions table
CREATE TABLE submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id TEXT NOT NULL,
    story_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'python',
    test_results TEXT, -- JSON format
    score INTEGER DEFAULT 0,
    passed_tests INTEGER DEFAULT 0,
    total_tests INTEGER DEFAULT 0,
    ip_address TEXT,
    submitted_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (team_id) REFERENCES teams (team_id),
    FOREIGN KEY (story_id) REFERENCES stories (id)
);

-- Hints usage tracking
CREATE TABLE hints_used (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id TEXT NOT NULL,
    story_id INTEGER NOT NULL,
    hint_number INTEGER NOT NULL,
    penalty_points INTEGER DEFAULT 10,
    used_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (team_id) REFERENCES teams (team_id),
    FOREIGN KEY (story_id) REFERENCES stories (id)
);

-- Hints table
CREATE TABLE hints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id INTEGER NOT NULL,
    hint_number INTEGER NOT NULL,
    hint_text TEXT NOT NULL,
    penalty_points INTEGER DEFAULT 10,
    FOREIGN KEY (story_id) REFERENCES stories (id)
);

-- Anti-cheat tab switches tracking
CREATE TABLE tab_switches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id TEXT NOT NULL,
    ip_address TEXT,
    switch_count INTEGER,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (team_id) REFERENCES teams (team_id)
);

-- Leaderboard view
CREATE VIEW leaderboard_view AS
SELECT 
    t.team_id,
    t.username,
    COALESCE(s.score, 0) - COALESCE(h.total_penalty, 0) as final_score,
    s.submitted_at,
    s.passed_tests,
    s.total_tests,
    COALESCE(h.hints_count, 0) as hints_used
FROM teams t
LEFT JOIN submissions s ON t.team_id = s.team_id
LEFT JOIN (
    SELECT 
        team_id, 
        SUM(penalty_points) as total_penalty,
        COUNT(*) as hints_count
    FROM hints_used 
    GROUP BY team_id
) h ON t.team_id = h.team_id
ORDER BY final_score DESC, s.submitted_at ASC;