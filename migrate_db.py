import sqlite3

# Connect to the database
conn = sqlite3.connect("work_tracker.db")
cursor = conn.cursor()

try:
    # Add the outcome column to the logs table
    cursor.execute("ALTER TABLE logs ADD COLUMN outcome TEXT")
    print("Successfully added 'outcome' column to logs table.")
except sqlite3.OperationalError as e:
    print(f"Error: {e}. The column might already exist or the table is corrupted.")
finally:
    conn.commit()
    conn.close()