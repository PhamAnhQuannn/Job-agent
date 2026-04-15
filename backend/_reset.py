import sqlite3
conn = sqlite3.connect('../data/job_agent.db')
conn.execute("UPDATE jobs SET status='AUTO_APPLY', failure_step=NULL, screenshot_path=NULL, date_applied=NULL WHERE id=70862")
conn.commit()
print('Zscaler reset to AUTO_APPLY')
conn.close()
