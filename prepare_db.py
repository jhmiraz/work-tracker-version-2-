import sqlite3

# Create or connect to the database
db_path = "work_tracker.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Create categories table
    cursor.execute("""
        CREATE TABLE categories (
            name TEXT PRIMARY KEY
        )
    """)

    # Insert default categories
    default_categories = ["Project Work", "Projects", "Job Applications"]
    for cat in default_categories:
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (cat,))
    print(f"Inserted default categories: {default_categories}")

    # Create logs table with the correct schema
    cursor.execute("""
        CREATE TABLE logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            time_spent INTEGER,
            completed INTEGER,
            outcome TEXT,
            FOREIGN KEY (name) REFERENCES categories(name)
        )
    """)
    print("Created logs table with correct schema")

    # Commit changes
    conn.commit()
    print(f"Database created successfully at {db_path}")

except sqlite3.Error as e:
    print(f"Error creating database: {e}")
finally:
    conn.close()