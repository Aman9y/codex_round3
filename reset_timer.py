import sqlite3

# Reset contest timer
conn = sqlite3.connect('database/contest.db')
cursor = conn.cursor()

# Reset timer to not started (no duration reset)
cursor.execute('UPDATE contest_config SET value = "0" WHERE key = "contest_start_time"')

conn.commit()
conn.close()

print("Contest timer reset successfully!")