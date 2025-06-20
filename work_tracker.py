import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
from datetime import datetime, date, timedelta
import time
import os
import sys
import uuid
import shutil
import logging

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_db_path():
    base_path = get_base_path()
    db_name = "work_tracker.db"
    db_path = os.path.join(base_path, db_name)
    
    debug_db_path = r"D:\projects\work tracker\work_tracker.db"
    if os.path.exists(debug_db_path) and not getattr(sys, 'frozen', False):
        return debug_db_path
    
    if getattr(sys, 'frozen', False):
        user_db_path = os.path.join(os.path.expanduser("~"), db_name)
        if not os.path.exists(user_db_path) and os.path.exists(db_path):
            try:
                shutil.copy(db_path, user_db_path)
                print(f"Copied database to {user_db_path}")
                logging.info(f"Copied database to {user_db_path}")
            except Exception as e:
                print(f"Failed to copy database to user directory: {e}")
                logging.error(f"Failed to copy database to user directory: {e}")
        return user_db_path
    
    return db_path

logging.basicConfig(
    filename=os.path.join(get_base_path(), "work_tracker.log"),
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

BASE_PATH = get_base_path()
DB_PATH = get_db_path()

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    logging.info(f"Connected to database at {DB_PATH}")
except sqlite3.Error as e:
    logging.error(f"Database connection error: {e}")
    print(f"Database connection error: {e}")
    sys.exit(1)

try:
    cursor.execute("PRAGMA table_info(categories)")
    cat_columns = [col[1] for col in cursor.fetchall()]
    if cat_columns != ["name"]:
        cursor.execute("DROP TABLE IF EXISTS categories")
        cursor.execute("CREATE TABLE categories (name TEXT PRIMARY KEY)")

    cursor.execute("PRAGMA table_info(logs)")
    log_columns = [col[1] for col in cursor.fetchall()]
    expected_log_columns = ["id", "name", "date", "time_spent", "completed", "outcome"]
    if log_columns != expected_log_columns:
        cursor.execute("DROP TABLE IF EXISTS logs")
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

    cursor.execute("PRAGMA table_info(tasks)")
    task_columns = [col[1] for col in cursor.fetchall()]
    expected_task_columns = ["id", "task_text", "created_date", "x", "y", "completed", "completed_time", "very_important", "semi_important"]
    if task_columns != expected_task_columns:
        cursor.execute("DROP TABLE IF EXISTS tasks")
        cursor.execute("""
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_text TEXT NOT NULL,
                created_date TEXT NOT NULL,
                x REAL NOT NULL DEFAULT 50,
                y REAL NOT NULL DEFAULT 50,
                completed INTEGER NOT NULL,
                completed_time TEXT,
                very_important INTEGER DEFAULT 0,
                semi_important INTEGER DEFAULT 0
            )
        """)

    cursor.execute("PRAGMA table_info(playground_elements)")
    playground_columns = [col[1] for col in cursor.fetchall()]
    expected_playground_columns = ["id", "element_type", "x1", "y1", "x2", "y2", "color", "width", "text", "created_date"]
    if playground_columns != expected_playground_columns:
        cursor.execute("DROP TABLE IF EXISTS playground_elements")
        cursor.execute("""
            CREATE TABLE playground_elements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                element_type TEXT NOT NULL,  -- 'line', 'square', 'circle', 'arrow', 'text'
                x1 REAL NOT NULL,           -- Starting x-coordinate
                y1 REAL NOT NULL,           -- Starting y-coordinate
                x2 REAL,                    -- Ending x-coordinate (null for text)
                y2 REAL,                    -- Ending y-coordinate (null for text)
                color TEXT,                 -- Color of the element
                width REAL,                 -- Line width or shape outline width
                text TEXT,                  -- Text content for text elements
                created_date TEXT NOT NULL  -- Date of creation
            )
        """)

    try:
        cursor.execute("ALTER TABLE logs ADD COLUMN outcome TEXT")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            logging.error(f"Migration error: {e}")
            print(f"Migration error: {e}")

    cursor.execute("PRAGMA table_info(categories)")
    logging.info("Categories table schema: " + str(cursor.fetchall()))
    cursor.execute("PRAGMA table_info(logs)")
    logging.info("Logs table schema: " + str(cursor.fetchall()))
    cursor.execute("PRAGMA table_info(tasks)")
    logging.info("Tasks table schema: " + str(cursor.fetchall()))
    cursor.execute("PRAGMA table_info(playground_elements)")
    logging.info("Playground elements table schema: " + str(cursor.fetchall()))
    conn.commit()
except sqlite3.Error as e:
    logging.error(f"Database setup error: {e}")
    print(f"Database setup error: {e}")
    sys.exit(1)

try:
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        default_categories = ["Project Work", "Projects", "Job Applications"]
        for cat in default_categories:
            cursor.execute("INSERT INTO categories (name) VALUES (?)", (cat,))
            logging.info(f"Inserted default category '{cat}'")
    conn.commit()
except sqlite3.Error as e:
    logging.error(f"Error inserting default categories: {e}")
    print(f"Error inserting default categories: {e}")
    sys.exit(1)

try:
    cursor.execute("SELECT name FROM categories")
    categories = cursor.fetchall()
    logging.info(f"Current categories: {categories}")
except sqlite3.Error as e:
    logging.error(f"Error fetching categories: {e}")

class WorkTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Task Tracker Application")
        self.root.geometry("800x600")
        
        self.active_category = ""
        self.start_time = None
        self.paused_time = 0
        self.paused = False
        self.category_frames = {}
        self.category_buttons = {}
        self.stopwatch_running = False
        self.tooltip = None
        self.outcomes = {}
        self.overlay = None
        self.drag_data = {"x": 0, "y": 0, "widget": None}
        self.expanded_rows = {}
        self.categories = []
        self.task_cards = {}
        self.dragging_task = None
        
        # Create notebook for tabbed interface
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tracker frame
        self.tracker_frame = tk.Frame(self.notebook)
        self.notebook.add(self.tracker_frame, text="Tracker")
        
        # Notes frame (whiteboard)
        self.notes_frame = tk.Frame(self.notebook)
        self.notebook.add(self.notes_frame, text="Notes")
        
        # Completed Tasks frame
        self.completed_frame = tk.Frame(self.notebook)
        self.notebook.add(self.completed_frame, text="Completed Tasks")
        
        # Playground frame (whiteboard)
        self.playground_frame = tk.Frame(self.notebook)
        self.notebook.add(self.playground_frame, text="Play Ground")

        # Setup tracker frame
        self.label = tk.Label(self.tracker_frame, text="Select a category to start tracking:")
        self.label.pack(pady=10)
        
        self.category_frame = tk.Frame(self.tracker_frame)
        self.category_frame.pack(pady=10)
        
        self.add_frame = tk.Frame(self.tracker_frame)
        self.add_frame.pack(pady=5)
        self.new_category_entry = tk.Entry(self.add_frame)
        self.new_category_entry.pack(side=tk.LEFT, padx=5)
        self.add_button = tk.Button(self.add_frame, text="Add Category", command=self.add_category)
        self.add_button.pack(side=tk.LEFT)
        
        self.control_frame = tk.Frame(self.tracker_frame)
        self.control_frame.pack(pady=5)
        self.pause_resume_button = tk.Button(self.control_frame, text="Pause", command=self.toggle_pause, state=tk.DISABLED)
        self.pause_resume_button.pack(side=tk.LEFT, padx=5)
        
        self.search_frame = tk.Frame(self.tracker_frame)
        self.search_frame.pack(pady=5)
        tk.Label(self.search_frame, text="Search by Date:").pack(side=tk.LEFT, padx=5)
        self.month_var = tk.StringVar()
        self.day_var = tk.StringVar()
        self.year_var = tk.StringVar()
        months = [str(i).zfill(2) for i in range(1, 13)]
        days = [str(i).zfill(2) for i in range(1, 32)]
        years = [str(i) for i in range(2020, 2026)]
        ttk.Combobox(self.search_frame, textvariable=self.month_var, values=months, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Combobox(self.search_frame, textvariable=self.day_var, values=days, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Combobox(self.search_frame, textvariable=self.year_var, values=years, width=7).pack(side=tk.LEFT, padx=5)
        tk.Button(self.search_frame, text="Search", command=self.search_logs).pack(side=tk.LEFT, padx=5)
        tk.Button(self.search_frame, text="Clear", command=self.clear_search).pack(side=tk.LEFT, padx=5)
        
        self.left_outcome_frame = tk.Frame(self.tracker_frame, bd=2, relief="sunken")
        self.left_outcome_frame.place(x=0, y=0, width=150, height=100)
        self.right_outcome_frame = tk.Frame(self.tracker_frame, bd=2, relief="sunken")
        self.right_outcome_frame.place(x=650, y=0, width=150, height=100)
        
        self.outcome_text_left = tk.Text(self.left_outcome_frame, wrap=tk.WORD, font=("Helvetica", 8), height=5)
        self.outcome_text_left.pack(fill=tk.BOTH, expand=True)
        self.outcome_text_right = tk.Text(self.right_outcome_frame, wrap=tk.WORD, font=("Helvetica", 8), height=5)
        self.outcome_text_right.pack(fill=tk.BOTH, expand=True)
        
        self.day_offset = 0
        self.update_outcome_display()
        
        tk.Button(self.left_outcome_frame, text="<<", command=self.prev_day).pack(side=tk.LEFT, padx=5)
        tk.Button(self.right_outcome_frame, text=">>", command=self.next_day).pack(side=tk.RIGHT, padx=5)
        
        # Important tasks section
        self.important_frame = tk.Frame(self.tracker_frame, bd=2, relief="groove")
        self.important_frame.pack(pady=10, fill=tk.X, padx=5)
        tk.Label(self.important_frame, text="Important Tasks to Complete:", font=("Helvetica", 10, "bold")).pack(anchor="w", padx=5)
        self.important_tasks_labels = []
        for i in range(3):
            label = tk.Label(self.important_frame, text="", font=("Helvetica", 9), wraplength=700, anchor="w")
            label.pack(anchor="w", padx=10)
            self.important_tasks_labels.append(label)
        
        self.log_frame = tk.Frame(self.tracker_frame)
        self.log_frame.pack(pady=10, fill=tk.BOTH, expand=True)
        self.log_tree = ttk.Treeview(self.log_frame, show="headings")
        self.log_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(self.log_frame, orient=tk.VERTICAL, command=self.log_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_tree.configure(yscrollcommand=scrollbar.set)
        
        style = ttk.Style()
        style.configure("Treeview", font=("Helvetica", 8))
        style.configure("Treeview.Heading", font=("Helvetica", 8, "bold"))
        style.configure("Completed.Treeview", foreground="green")
        style.configure("NotCompleted.Treeview", foreground="red")
        
        self.log_tree.bind("<Motion>", self.show_tooltip)
        self.log_tree.bind("<Leave>", self.hide_tooltip)
        self.log_tree.bind("<Double-1>", self.show_row_details)
        self.log_tree.bind("<Button-1>", self.toggle_expand)
        
        self.status_label = tk.Label(self.tracker_frame, text="Status: Idle")
        self.status_label.pack(pady=5)
        self.stopwatch_label = tk.Label(self.tracker_frame, text="Time: 00:00")
        self.stopwatch_label.pack(pady=5)
        self.date_label = tk.Label(self.tracker_frame, text=f"Date: {date.today()}")
        self.date_label.pack(pady=5)
        
        # Setup notes frame (whiteboard)
        self.task_input_frame = tk.Frame(self.notes_frame)
        self.task_input_frame.pack(fill=tk.X, padx=5, pady=5)
        self.task_input = tk.Entry(self.task_input_frame)
        self.task_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(self.task_input_frame, text="Add Task", command=self.add_task).pack(side=tk.LEFT, padx=5)
        
        self.whiteboard = tk.Canvas(self.notes_frame, bg="grey", scrollregion=(0, 0, 800, 600))
        self.whiteboard.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar = ttk.Scrollbar(self.notes_frame, orient=tk.VERTICAL, command=self.whiteboard.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.whiteboard.configure(yscrollcommand=scrollbar.set)
        
        # Setup completed tasks frame
        self.completed_tree = ttk.Treeview(self.completed_frame, columns=("Task", "Created", "Completed"), show="headings")
        self.completed_tree.heading("Task", text="Task")
        self.completed_tree.heading("Created", text="Created Date")
        self.completed_tree.heading("Completed", text="Completed Time")
        self.completed_tree.column("Task", width=400)
        self.completed_tree.column("Created", width=150)
        self.completed_tree.column("Completed", width=150)
        self.completed_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        completed_scrollbar = ttk.Scrollbar(self.completed_frame, orient=tk.VERTICAL, command=self.completed_tree.yview)
        completed_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.completed_tree.configure(yscrollcommand=completed_scrollbar.set)
        
        # Toolbar for playground tools
        self.toolbar = tk.Frame(self.playground_frame, bd=1, relief="raised")
        self.toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Tool variables
        self.current_tool = tk.StringVar(value="pen")
        self.current_color = tk.StringVar(value="black")
        self.line_width = tk.DoubleVar(value=2.0)
        self.start_x = None
        self.start_y = None
        self.current_element = None
        self.playground_elements = {}  # Store canvas element IDs

        # Tool buttons
        tools = [
            ("Pen", "pen"),
            ("Eraser", "eraser"),
            ("Text", "text"),
            ("Square", "square"),
            ("Circle", "circle"),
            ("Arrow", "arrow")
        ]
        for text, tool in tools:
            tk.Radiobutton(self.toolbar, text=text, variable=self.current_tool, value=tool, command=self.select_tool).pack(side=tk.LEFT, padx=5)

        # Color selection
        colors = ["black", "red", "blue", "green"]
        tk.Label(self.toolbar, text="Color:").pack(side=tk.LEFT, padx=5)
        ttk.Combobox(self.toolbar, textvariable=self.current_color, values=colors, width=10, state="readonly").pack(side=tk.LEFT, padx=5)

        # Line width
        tk.Label(self.toolbar, text="Width:").pack(side=tk.LEFT, padx=5)
        tk.Spinbox(self.toolbar, from_=1, to=10, width=5, textvariable=self.line_width).pack(side=tk.LEFT, padx=5)

        # Clear canvas button
        tk.Button(self.toolbar, text="Clear All", command=self.clear_canvas).pack(side=tk.RIGHT, padx=5)

        # Playground canvas
        self.playground_canvas = tk.Canvas(self.playground_frame, bg="white", scrollregion=(0, 0, 1000, 1000))
        self.playground_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar = ttk.Scrollbar(self.playground_frame, orient=tk.VERTICAL, command=self.playground_canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.playground_canvas.configure(yscrollcommand=scrollbar.set)

        # Bind mouse events for drawing
        self.playground_canvas.bind("<Button-1>", self.start_drawing)
        self.playground_canvas.bind("<B1-Motion>", self.draw_drawing)
        self.playground_canvas.bind("<ButtonRelease-1>", self.stop_drawing)

        self.load_categories()
        self.load_tasks()
        self.load_completed_tasks()
        self.load_important_tasks()
        self.update_log_display()
        self.load_playground_elements()
        self.update_countdown()

    def load_playground_elements(self):
        for db_id, canvas_id in list(self.playground_elements.items()):
            self.playground_canvas.delete(canvas_id)
        self.playground_elements.clear()

        try:
            cursor.execute("SELECT id, element_type, x1, y1, x2, y2, color, width, text FROM playground_elements WHERE created_date = ?",
                           (self.day_id.isoformat(),))
            elements = cursor.fetchall()
            for element in elements:
                db_id, element_type, x1, y1, x2, y2, color, width, text = element
                if element_type == "text":
                    canvas_id = self.playground_canvas.create_text(x1, y1, text=text, fill=color, anchor="nw", font=("Helvetica", 12))
                elif element_type == "square":
                    canvas_id = self.playground_canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=width)
                elif element_type == "circle":
                    canvas_id = self.playground_canvas.create_oval(x1, y1, x2, y2, outline=color, width=width)
                elif element_type == "arrow":
                    canvas_id = self.playground_canvas.create_line(x1, y1, x2, y2, fill=color, width=width, arrow=tk.LAST)
                elif element_type == "pen":
                    canvas_id = self.playground_canvas.create_line(x1, y1, x2, y2, fill=color, width=width, capstyle=tk.ROUND)
                self.playground_elements[db_id] = canvas_id
            logging.info(f"Loaded {len(elements)} playground elements for {self.day_id}")
        except sqlite3.Error as e:
            logging.error(f"Failed to load playground elements: {e}")
            messagebox.showerror("Error", f"Failed to load playground elements: {e}")

    def start_drawing(self, event):
        self.start_x = self.playground_canvas.canvasx(event.x)
        self.start_y = self.playground_canvas.canvasy(event.y)
        tool = self.current_tool.get()
        color = self.current_color.get()
        width = self.line_width.get()

        if tool == "text":
            text = simpledialog.askstring("Text Input", "Enter text:", parent=self.root)
            if text:
                element_id = self.playground_canvas.create_text(self.start_x, self.start_y, text=text, fill=color, anchor="nw", font=("Helvetica", 12))
                try:
                    cursor.execute("""
                        INSERT INTO playground_elements (element_type, x1, y1, color, text, created_date)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, ("text", self.start_x, self.start_y, color, text, date.today().isoformat()))
                    db_id = cursor.lastrowid
                    conn.commit()
                    self.playground_elements[db_id] = element_id
                    logging.info(f"Added text element: {text} at ({self.start_x}, {self.start_y})")
                except sqlite3.Error as e:
                    logging.error(f"Failed to save text element: {e}")
                    messagebox.showerror("Error", f"Failed to save text element: {e}")
        elif tool == "eraser":
            items = self.playground_canvas.find_closest(self.start_x, self.start_y, halo=10)
            for item in items:
                for db_id, canvas_id in list(self.playground_items.items()):
                    if canvas_id == item:
                        try:
                            cursor.execute("DELETE FROM playground_elements WHERE id = ?", (db_id,))
                            conn.commit()
                            self.playground_canvas.delete(item)
                            del self.playground_elements[db_id]
                            logging.info(f"Erased element ID {db_id}")
                        except sqlite3.Error as e:
                            logging.error(f"Failed to erase element ID {db_id}: {e}")
                            messagebox.showerror("Error", f"Failed to erase element: {e}")
                        break
        else:
            if tool == "square":
                self.current_element = self.playground_canvas.create_rectangle(
                    self.start_x, self.start_y, self.start_x, self.start_y, outline=color, width=width
                )
            elif tool == "circle":
                self.current_element = self.playground_canvas.create_oval(
                    self.start_x, self.start_y, self.start_x, self.start_y, outline=color, width=width
                )
            elif tool == "arrow":
                self.current_element = self.playground_canvas.create_line(
                    self.start_x, self.start_y, self.start_x, self.start_y, fill=color, width=width, arrow=tk.LAST
                )
            elif tool == "pen":
                self.current_element = self.playground_canvas.create_line(
                    self.start_x, self.start_y, self.start_x, self.start_y, fill=color, width=width, capstyle=tk.ROUND
                )

    def select_tool(self):
        if self.current_tool.get() == "eraser":
            self.playground_canvas.config(cursor="dotbox")
        elif self.current_tool.get() == "text":
            self.playground_canvas.config(cursor="xterm")
        else:
            self.playground_canvas.config(cursor="crosshair")

    def draw_drawing(self, event):
        if self.current_tool.get() in ["pen", "square", "circle", "arrow"] and self.current_element:
            current_x = self.playground_canvas.canvasx(event.x)
            current_y = self.playground_canvas.canvasy(event.y)
            tool = self.current_tool.get()
            if tool == "square":
                self.playground_canvas.coords(self.current_element, self.start_x, self.start_y, current_x, current_y)
            elif tool == "circle":
                self.playground_canvas.coords(self.current_element, self.start_x, self.start_y, current_x, current_y)
            elif tool in ["pen", "arrow"]:
                coords = self.playground_canvas.coords(self.current_element)
                self.playground_canvas.coords(self.current_element, coords + [current_x, current_y])

    def stop_drawing(self, event):
        if self.current_tool.get() in ["pen", "square", "circle", "arrow"] and self.current_element:
            current_x = self.playground_canvas.canvasx(event.x)
            current_y = self.playground_canvas.canvasy(event.y)
            tool = self.current_tool.get()
            try:
                cursor.execute("""
                    INSERT INTO playground_elements (element_type, x1, y1, x2, y2, color, width, created_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (tool, self.start_x, self.start_y, current_x, current_y, self.current_color.get(), self.line_width.get(), date.today().isoformat()))
                db_id = cursor.lastrowid
                conn.commit()
                self.playground_elements[db_id] = self.current_element
                logging.info(f"Added {tool} element from ({self.start_x}, {self.start_y}) to ({current_x}, {current_y})")
            except sqlite3.Error as e:
                logging.error(f"Failed to save {tool} element: {e}")
                messagebox.showerror("Error", f"Failed to save element: {e}")
            self.current_element = None
            self.start_x = None
            self.start_y = None

    def clear_canvas(self):
        if messagebox.askyesno("Confirm", "Clear all elements from the playground?"):
            try:
                cursor.execute("DELETE FROM playground_elements WHERE created_date = ?", (date.today().isoformat(),))
                conn.commit()
                self.playground_canvas.delete("all")
                self.playground_elements.clear()
                logging.info("Cleared all playground elements")
            except Exception as e:
                logging.error(f"Failed to clear playground elements: {e}")
                messagebox.showerror("Error", f"Failed to clear playground elements: {e}")

    def add_task(self):
        task_text = self.task_input.get().strip()
        if not task_text:
            messagebox.showerror("Error", "Task description cannot be empty!")
            return
        try:
            cursor.execute("INSERT INTO tasks (task_text, created_date, x, y, completed, very_important, semi_important) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (task_text, date.today().isoformat(), 50, 50, 0, 0, 0))
            conn.commit()
            logging.info(f"Added task: {task_text}")
            self.task_input.delete(0, tk.END)
            self.load_tasks()
            self.load_important_tasks()
        except sqlite3.Error as e:
            logging.error(f"Failed to add task: {e}")
            messagebox.showerror("Error", f"Failed to add task: {e}")

    def edit_task(self, task_id, text_widget):
        new_text = text_widget.get("1.0", tk.END).strip()
        try:
            cursor.execute("UPDATE tasks SET task_text = ? WHERE id = ?", (new_text, task_id))
            conn.commit()
            logging.info(f"Edited task ID {task_id} to: {new_text}")
            self.load_important()
        except sqlite3.Error as e:
            logging.error(f"Failed to edit task ID {task_id}: {e}")
            messagebox.showerror("Error", f"Failed to edit task: {e}")

    def toggle_task_completion(self, task_id, var):
        completed = var.get()
        completed_time = datetime.now().isoformat() if completed else None
        try:
            cursor.execute("UPDATE tasks SET completed = ?, completed_time = ? WHERE id = ?",
                         (completed, completed_time, task_id))
            conn.commit()
            logging.info(f"Task ID {task_id} marked as {'completed' if completed else 'uncompleted'}")
            self.load_tasks()
            self.load_completed_tasks()
            self.load_important_tasks()
        except sqlite3.Error as e:
            logging.error(f"Failed to toggle completion for task ID {task_id}: {e}")
            messagebox.showerror("Error", f"Failed to toggle completion: {e}")

    def toggle_very_important(self, task_id, var):
        very_important = var.get()
        try:
            cursor.execute("UPDATE tasks SET very_important = ? WHERE id = ?", (very_important, task_id))
            conn.commit()
            logging.info(f"Task ID {task_id} marked as {'very important' if very_important else 'not very important'}")
            self.load_important_tasks()
        except sqlite3.Error as e:
            logging.error(f"Failed to toggle very important for task ID {task_id} : {e}")
            messagebox.showerror("Error", f"Failed to toggle very important: {e}")

    def toggle_semi_important(self, task_id, var):
        semi_important = var.get()
        try:
            cursor.execute("UPDATE tasks SET semi_important = ? WHERE id = ?", (semi_important, task_id))
            conn.commit()
            logging.info(f"Task ID {task_id} marked as {'semi important' if semi_important else 'not semi important'}")
        except sqlite3.Error as e:
            logging.error(f"Failed to toggle semi important for task ID {task_id}: {e}")
            messagebox.showerror("Error", f"Failed to toggle semi important: {e}")

    def check_completed_tasks(self):
        try:
            cursor.execute("SELECT id, completed_time FROM tasks WHERE completed = 1")
            tasks = cursor.fetchall()
            current_time = datetime.now()
            for task_id, completed_time in tasks:
                if completed_time:
                    completed_dt = datetime.fromisoformat(completed_time)
                    if current_time - completed_dt >= timedelta(hours=1):
                        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                        conn.commit()
                        logging.info(f"Deleted completed task ID {task_id} after 1 hour")
            self.load_tasks()
            self.load_completed_tasks()
            self.load_important_tasks()
        except sqlite3.Error as e:
            logging.error(f"Failed to check completed tasks: {e}")
        self.root.after(60000, self.check_completed_tasks())  # Check every minute

    def load_tasks(self):
        for task_id, widgets in self.task_cards.items():
            widgets["frame"].destroy()
        self.task_cards.clear()
        
        try:
            cursor.execute("SELECT id, task_text, created_date, x, y, completed, very_important, semi_important FROM tasks WHERE created_date = ? AND completed = 0 ORDER BY id",
                         (date.today().isoformat()))
            tasks = cursor.fetchall()
            logging.info(f"Loaded {len(tasks)} tasks for {date.today()}")
            
            for task_id, task_text, created_date, x, y, completed, very_important, semi_important in tasks:
                card_frame = tk.Frame(self.whiteboard, bg="#FFFF99", bd=2, relief="raised")
                card_window = self.whiteboard.create_window(x, y, window=card_frame, anchor="nw")
                
                text = tk.Text(card_frame, wrap=tk.WORD, width=20, height=3, bg="#FFFF99", font=("Helvetica", 10), bd=0)
                text.insert(tk.END, task_text)
                text.pack(padx=5, pady=5)
                text.bind("<Double-1>", lambda e, tid=task_id, t=text: self.edit_task(tid, t))
                
                check_frame = tk.Frame(card_frame, bg="#FFFF99")
                check_frame.pack(anchor="w", padx=5)
                
                check_var = tk.BooleanVar(value=bool(completed))
                check = tk.Checkbutton(check_frame, variable=check_var, command=lambda tid=task_id, v=check_var: self.toggle_task_completion(tid, v), bg="#FFFF99")
                check.pack(side=tk.LEFT, padx=2)
                
                very_important_var = tk.BooleanVar(value=bool(very_important))
                very_important_check = tk.Checkbutton(check_frame, variable=very_important_var, command=lambda tid=task_id, v=very_important_var: self.toggle_very_important(tid, v), bg="#FFFF99", selectcolor="red")
                very_important_check.pack(side=tk.LEFT, padx=2)
                
                semi_important_var = tk.BooleanVar(value=bool(semi_important))
                semi_important_check = tk.Checkbutton(check_frame, variable=semi_important_var, command=lambda tid=task_id, v=semi_important_var: self.toggle_semi_important(tid, v), bg="#FFFF99", selectcolor="green")
                semi_important_check.pack(side=tk.LEFT, padx=2)
                
                date_label = tk.Label(card_frame, text=f"Created: {created_date}", font=("Helvetica", 8), bg="#FFFF99")
                date_label.pack(anchor="w", padx=5, pady=2)
                
                for widget in (card_frame, text, check_frame, check, very_important_check, semi_important_check, date_label):
                    widget.bind("<Button-1>", lambda e, tid=task_id: self.start_task_drag(e, tid))
                    widget.bind("<B1-Motion>", lambda e, tid=task_id: self.on_task_drag(e, tid))
                    widget.bind("<ButtonRelease-1>", lambda e, tid=task_id: self.stop_task_drag(e, tid))
                
                self.task_cards[task_id] = {
                    "frame": card_frame,
                    "window": card_window,
                    "text": text,
                    "check_var": check_var,
                    "very_important_var": very_important_var,
                    "semi_important_var": semi_important_var
                }
        except sqlite3.Error as e:
            logging.error(f"Failed to load tasks: {e}")
            messagebox.showerror("Error", f"Failed to load tasks: {e}")

    def load_completed_tasks(self):
        for item in self.completed_tree.get_children():
            self.completed_tree.delete(item)
        try:
            cursor.execute("SELECT task_text, created_date, completed_time FROM tasks WHERE completed = 1 ORDER BY completed_time DESC")
            tasks = cursor.fetchall()
            for task_text, created_date, completed_time in tasks:
                self.completed_tree.insert("", tk.END, values=(task_text, created_date, completed_time))
            logging.info(f"Loaded {len(tasks)} completed tasks")
        except sqlite3.Error as e:
            logging.error(f"Failed to load completed tasks: {e}")
            messagebox.showerror("Error", f"Failed to load completed tasks: {e}")

    def load_important_tasks(self):
        for label in self.important_tasks_labels:
            label.config(text="")
        try:
            cursor.execute("SELECT task_text FROM tasks WHERE created_date = ? AND very_important = 1 AND completed = 0 ORDER BY id DESC LIMIT 3",
                         (date.today().isoformat(),))
            tasks = cursor.fetchall()
            for i, (task_text,) in enumerate(tasks):
                self.important_tasks_labels[i].config(text=f"{i+1}. {task_text}")
            logging.info(f"Loaded {len(tasks)} important tasks for Tracker page")
        except sqlite3.Error as e:
            logging.error(f"Failed to load important tasks: {e}")
            messagebox.showerror("Error", f"Failed to load important tasks: {e}")

    def start_task_drag(self, event, task_id):
        self.dragging_task = task_id
        self.drag_data["x"] = event.x_root
        self.drag_data["y"] = event.y_root

    def on_task_drag(self, event, task_id):
        if self.dragging_task == task_id:
            delta_x = event.x_root - self.drag_data["x"]
            delta_y = event.y_root - self.drag_data["y"]
            current_coords = self.whiteboard.coords(self.task_cards[task_id]["window"])
            new_x = current_coords[0] + delta_x
            new_y = current_coords[1] + delta_y
            self.whiteboard.coords(self.task_cards[task_id]["window"], new_x, new_y)
            self.drag_data["x"] = event.x_root
            self.drag_data["y"] = event.y_root

    def stop_task_drag(self, event, task_id):
        if self.dragging_task == task_id:
            current_coords = self.whiteboard.coords(self.task_cards[task_id]["window"])
            try:
                cursor.execute("UPDATE tasks SET x = ?, y = ? WHERE id = ?", (current_coords[0], current_coords[1], task_id))
                conn.commit()
                logging.info(f"Updated position for task ID {task_id} to ({current_coords[0]}, {current_coords[1]})")
            except sqlite3.Error as e:
                logging.error(f"Failed to update task position for ID {task_id}: {e}")
            self.dragging_task = None
            self.drag_data["x"] = 0
            self.drag_data["y"] = 0

    def create_overlay(self):
        if self.overlay:
            self.overlay.destroy()
        
        self.overlay = tk.Toplevel(self.root)
        self.overlay_id = str(uuid.uuid4())
        self.overlay.overrideredirect(True)
        self.overlay.attributes("-alpha", 0.7)
        self.overlay.wm_attributes("-topmost", 1)
        
        overlay_width, overlay_height = 200, 100
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = screen_width - overlay_width - 10
        y = screen_height - overlay_height - 10
        self.overlay.geometry(f"{overlay_width}x{overlay_height}+{x}+{y}")
        
        frame = tk.Frame(self.overlay, bg="black")
        frame.pack(fill=tk.BOTH, expand=True)
        
        self.overlay_label = tk.Label(frame, text=f"Working on: {self.active_category}", bg="black", fg="white", font=("Helvetica", 8))
        self.overlay_label.pack(pady=5)
        
        self.overlay_time = tk.Label(frame, text="Time: 00:00", bg="black", fg="white", font=("Helvetica", 8))
        self.overlay_time.pack(pady=5)
        
        button_frame = tk.Frame(frame)
        button_frame.pack(pady=5)
        
        self.overlay_pause_resume_button = tk.Button(button_frame, text="Pause", command=self.toggle_pause, bg="yellow", fg="black", width=6)
        self.overlay_pause_resume_button.pack(side=tk.LEFT, padx=2)
        
        stop_button = tk.Button(button_frame, text="Stop", command=lambda: self.toggle_timer(self.active_category), bg="red", fg="white", width=6)
        stop_button.pack(side=tk.LEFT, padx=2)
        
        for widget in (frame, self.overlay_label, self.overlay_time, button_frame, self.overlay_pause_resume_button, stop_button):
            widget.bind("<Button-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.on_drag)
            widget.bind("<ButtonRelease-1>", self.stop_drag)

    def start_drag(self, event):
        if self.overlay:
            self.drag_data["x"] = event.x_root
            self.drag_data["y"] = event.y_root
            self.drag_data["widget"] = event.widget

    def on_drag(self, event):
        if self.overlay and self.drag_data["widget"]:
            delta_x = event.x_root - self.drag_data["x"]
            delta_y = event.y_root - self.drag_data["y"]
            x = self.overlay.winfo_x() + delta_x
            y = self.overlay.winfo_y() + delta_y
            self.overlay.geometry(f"+{x}+{y}")
            self.drag_data["x"] = event.x_root
            self.drag_data["y"] = event.y_root

    def stop_drag(self, event):
        self.drag_data["x"] = 0
        self.drag_data["y"] = 0
        self.drag_data["widget"] = None

    def update_event_time(self):
        if self.event_running and self.overlay and not self.paused:
            elapsed = int(time.time() - self.start_event_time + self.paused_time)
            minutes = elapsed // 60
            seconds = elapsed % 60
            self.event_time_label.config(text=f"Time: {minutes:02d}:{seconds:02d}")

    def show_tooltip(self, event):
        if self.tooltip:
            self.tooltip.destroy()
        
        item = self.log_tree.identify_row(event.y)
        if not item:
            return
        
        col = self.log_tree.identify_column(event.x)
        col_name = self.log_tree.column(col)["id"]
        if col_name == "Date" or col_name == "Total":
            return
        
        values = self.log_tree.item(item)["values"]
        date = values[0]
        if (date, col_name) in self.outcomes:
            outcome = self.outcomes.get((date, col_name), "No outcome")
            tooltip_text = f"Outcome: {outcome}"
            x, y = event.x_root + 10, event.y_root + 10
            self.tooltip = tk.Toplevel(self.root)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{x}+{y}")
            label = tk.Label(self.tooltip, text=tooltip_text, bg="lightyellow", fg="black",
                             borderwidth=1, relief="solid", padx=5, pady=5)
            label.pack()

    def hide_tooltip(self, event):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

    def toggle_expand(self, event):
        item = self.log_tree.identify_row(event.y)
        if not item or item not in self.expanded_rows:
            return
        
        date = self.log_tree.item(item)["values"][0]
        if self.expanded_rows.get(item, False):
            for child in self.log_tree.get_children(item):
                self.log_tree.delete(child)
            self.expanded_rows[item] = False
        else:
            try:
                cursor.execute("""
                    SELECT c.name, l.time_spent, l.completed, l.outcome
                    FROM logs l
                    JOIN categories c ON l.name = c.name
                    WHERE l.date = ?
                    ORDER BY c.name, l.id
                """, (date,))
                logs = cursor.fetchall()
                
                for i, (name, time_spent, completed, outcome) in enumerate(logs, 1):
                    minutes = time_spent // 60
                    status = "✓" if completed else "✗"
                    outcome_text = outcome or "No outcome"
                    row_data = [""] + [f"{i}. {outcome_text}" if cat == name else "" for cat in self.categories] + [f"{status} ({minutes}m)", ""]
                    child = self.log_tree.insert(item, tk.END, values=row_data)
                    self.log_tree.item(child, tags=("Completed" if completed else "NotCompleted",))
                self.expanded_rows[item] = True
            except sqlite3.Error as e:
                logging.error(f"Failed to expand row: {e}")
                messagebox.showerror("Error", f"Failed to expand row: {e}")

    def show_row_details(self, event):
        item = self.log_tree.identify_row(event.y)
        if not item or item in self.log_tree.get_children():
            return
        
        values = self.log_tree.item(item)["values"]
        date = values[0]
        
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"Insights for {date}")
        detail_window.geometry("400x300")
        
        text = tk.Text(detail_window, wrap=tk.WORD, font=("Helvetica", 10))
        text.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(detail_window, orient=tk.VERTICAL, command=text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.configure(yscrollcommand=scrollbar.set)
        
        try:
            cursor.execute("""
                SELECT c.name, l.time_spent, l.completed, l.outcome
                FROM logs l
                JOIN categories c ON l.name = c.name
                WHERE l.date = ?
                ORDER BY c.name, l.id
            """, (date,))
            logs = cursor.fetchall()
            
            total_points = 0
            total_time = 0
            completed_tasks = 0
            category_times = {}
            outcomes = []
            
            for name, time_spent, completed, outcome in logs:
                minutes = time_spent // 60
                total_time += minutes
                total_points += minutes
                if completed:
                    total_points += 10
                    completed_tasks += 1
                category_times[name] = category_times.get(name, 0) + minutes
                if outcome and outcome != "No outcome":
                    outcomes.append(f"{name}: {outcome}")
            
            most_active = max(category_times.items(), key=lambda x: x[1], default=("None", 0))
            
            text.insert(tk.END, f"Insights for {date}\n\n")
            text.insert(tk.END, f"Point Calculation:\n")
            text.insert(tk.END, f"  Total Points: {total_points}\n")
            text.insert(tk.END, f"  - {total_time} points from time spent (1 point/minute)\n")
            text.insert(tk.END, f"  - {completed_tasks * 10} points from {completed_tasks} completed tasks (10 points each)\n\n")
            text.insert(tk.END, f"Key Insights:\n")
            text.insert(tk.END, f"  Total Time Spent: {total_time} minutes\n")
            text.insert(tk.END, f"  Most Active Category: {most_active[0]} ({most_active[1]} minutes)\n")
            text.insert(tk.END, f"  Completed Tasks: {completed_tasks}\n")
            text.insert(tk.END, f"  Outcomes:\n")
            for i, outcome in enumerate(outcomes, 1):
                text.insert(tk.END, f"    {i}. {outcome}\n")
            if not outcomes:
                text.insert(tk.END, "    No outcomes recorded\n")
            
            text.config(state=tk.DISABLED)
        except sqlite3.Error as e:
            logging.error(f"Error fetching insights: {e}")
            text.insert(tk.END, f"Error fetching insights: {e}")
            text.config(state=tk.DISABLED)

    def search_logs(self):
        month = self.month_var.get()
        day = self.day_var.get()
        year = self.year_var.get()
        if month and day and year:
            try:
                search_date = f"{year}-{month}-{day}"
                datetime.strptime(search_date, "%Y-%m-%d")
                self.update_log_display(search_date=search_date)
            except ValueError:
                messagebox.showerror("Error", "Invalid date!")
        else:
            self.update_log_display()

    def clear_search(self):
        self.month_var.set("")
        self.day_var.set("")
        self.year_var.set("")
        self.update_log_display()

    def load_categories(self):
        for frame in self.category_frames.values():
            frame.destroy()
        self.category_frames.clear()
        self.category_buttons.clear()
        
        try:
            cursor.execute("SELECT name FROM categories ORDER BY name")
            categories = cursor.fetchall()
            self.categories = [cat[0] for cat in categories]
            logging.info(f"Loaded categories: {self.categories}")
            
            for name in self.categories:
                frame = tk.Frame(self.category_frame)
                frame.pack(pady=2, fill=tk.X)
                button = tk.Button(frame, text=name, width=20,
                                 command=lambda c=name: self.toggle_timer(c))
                button.pack(side=tk.LEFT, padx=5)
                self.category_buttons[name] = button
                edit_button = tk.Button(frame, text="Edit", width=8,
                                      command=lambda c=name: self.edit_category(c))
                edit_button.pack(side=tk.LEFT, padx=2)
                delete_button = tk.Button(frame, text="Delete", width=8,
                                       command=lambda c=name: self.delete_category(c))
                delete_button.pack(side=tk.LEFT)
                self.category_frames[name] = frame
                if name == self.active_category and self.stopwatch_running:
                    button.configure(bg="lightgreen")
            self.update_log_display()
            if not categories:
                messagebox.showwarning("Warning", "No categories found. Please add a category.")
        except sqlite3.Error as e:
            logging.error(f"Failed to load categories: {e}")
            messagebox.showerror("Error", f"Failed to load categories: {e}")

    def add_category(self):
        name = self.new_category_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Category name cannot be empty!")
            return
        try:
            cursor.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            conn.commit()
            logging.info(f"Added category '{name}'")
            self.new_category_entry.delete(0, tk.END)
            self.load_categories()
        except sqlite3.IntegrityError:
            logging.error(f"Failed to add category '{name}': Category already exists")
            messagebox.showerror("Error", "Category already exists!")

    def edit_category(self, old_name):
        new_name = simpledialog.askstring("Edit Category", f"Enter new name for '{old_name}':",
                                        parent=self.root)
        if new_name and new_name.strip():
            new_name = new_name.strip()
            if new_name != old_name:
                try:
                    cursor.execute("UPDATE categories SET name = ? WHERE name = ?",
                                  (new_name, old_name))
                    cursor.execute("UPDATE logs SET name = ? WHERE name = ?",
                                  (new_name, old_name))
                    if self.active_category == old_name:
                        self.active_category = new_name
                    conn.commit()
                    logging.info(f"Edited category from '{old_name}' to '{new_name}'")
                    self.load_categories()
                except sqlite3.Error:
                    logging.error(f"Failed to edit category to '{new_name}': Category already exists")
                    messagebox.showerror("Error", "Category name already exists!")
        elif new_name is not None:
            messagebox.showerror("Error", "Category name cannot be empty!")

    def delete_category(self, name):
        logging.info(f"Attempting to delete category '{name}'")
        if messagebox.askyesno("Confirm", f"Delete category '{name}' and its logs?"):
            try:
                cursor.execute("SELECT name FROM categories WHERE name = ?", (name,))
                if not cursor.fetchone():
                    logging.error(f"Category '{name}' not found in database")
                    messagebox.showerror("Error", f"Category '{name}' not found")
                    return
                cursor.execute("DELETE FROM logs WHERE name = ?", (name,))
                cursor.execute("DELETE FROM categories WHERE name = ?", (name,))
                logging.info(f"Successfully deleted category '{name}' and its logs")
                if self.active_category == name:
                    self.active_category = ""
                    self.stopwatch_running = False
                    self.status_label.config(text="Status: Idle")
                    self.stopwatch_label.config(text="Time: 00:00")
                    self.start_time = None
                    if self.overlay:
                        self.overlay.destroy()
                        self.overlay = None
                conn.commit()
                self.load_categories()
            except sqlite3.Error as e:
                logging.error(f"Failed to delete category '{name}': {e}")
                messagebox.showerror("Error", f"Failed to delete category: {e}")

    def toggle_timer(self, category):
        logging.info(f"Toggling timer for category '{category}'")
        if self.active_category == category:
            elapsed = int(self.paused_time if self.paused else time.time() - self.start_time + self.paused_time)
            self.stopwatch_running = False
            self.status_label.config(text="Status: Idle")
            self.stopwatch_label.config(text="Time: 00:00")
            self.category_buttons[category].configure(bg="SystemButtonFace")
            self.active_category = ""
            self.start_time = None
            self.paused_time = 0
            self.paused = False
            self.pause_resume_button.config(text="Pause", state=tk.DISABLED)
            if self.overlay:
                self.overlay.destroy()
                self.overlay = None
            outcome = simpledialog.askstring("Outcome", f"What was the outcome for '{category}'?",
                                           parent=self.root)
            outcome = outcome.strip() if outcome else ""
            try:
                cursor.execute("""
                    INSERT INTO logs (name, date, time_spent, completed, outcome)
                    VALUES (?, ?, ?, ?, ?)
                """, (category, date.today().isoformat(), elapsed, 1, outcome))
                conn.commit()
                logging.info(f"Logged time for '{category}': {elapsed} seconds, outcome: {outcome}")
                self.update_log_display()
                self.update_outcome_display()
            except sqlite3.Error as e:
                logging.error(f"Failed to log time for '{category}': {e}")
                messagebox.showerror("Error", f"Failed to log time: {e}")
        else:
            if self.active_category:
                elapsed = int(self.paused_time if self.paused else time.time() - self.start_time + self.paused_time)
                outcome = simpledialog.askstring("Outcome", f"What was the outcome for '{self.active_category}'?",
                                               parent=self.root)
                outcome = outcome.strip() if outcome else ""
                try:
                    cursor.execute("""
                        INSERT INTO logs (name, date, time_spent, completed, outcome)
                        VALUES (?, ?, ?, ?, ?)
                    """, (self.active_category, date.today().isoformat(), elapsed, 1, outcome))
                    conn.commit()
                    logging.info(f"Logged time for '{self.active_category}': {elapsed} seconds, outcome: {outcome}")
                    self.category_buttons[self.active_category].configure(bg="SystemButtonFace")
                    if self.overlay:
                        self.overlay.destroy()
                except sqlite3.Error as e:
                    logging.error(f"Failed to log time for '{self.active_category}': {e}")
                    messagebox.showerror("Error", f"Failed to log time: {e}")
            self.active_category = category
            self.start_time = time.time()
            self.stopwatch_running = True
            self.paused = False
            self.paused_time = 0
            self.status_label.config(text=f"Status: Tracking {category}")
            self.category_buttons[category].configure(bg="lightgreen")
            self.pause_resume_button.config(state=tk.NORMAL)
            self.create_overlay()
            self.update_log_display()

    def toggle_pause(self):
        if self.stopwatch_running and self.active_category:
            if not self.paused:
                self.paused = True
                self.paused_time += int(time.time() - self.start_time)
                self.status_label.config(text=f"Status: Paused ({self.active_category})")
                self.pause_resume_button.config(text="Resume")
                if self.overlay:
                    self.overlay_pause_resume_button.config(text="Resume")
                    self.overlay_time.config(text=f"Time: {self.paused_time // 60:02d}:{self.paused_time % 60:02d}")
            else:
                self.paused = False
                self.start_time = time.time()
                self.status_label.config(text=f"Status: Tracking {self.active_category}")
                self.pause_resume_button.config(text="Pause")
                if self.overlay:
                    self.overlay_pause_resume_button.config(text="Pause")

    def update_outcome_display(self):
        current_date = date.today() + timedelta(days=self.day_offset)
        prev_date = current_date - timedelta(days=1)
        
        self.outcome_text_left.delete(1.0, tk.END)
        self.outcome_text_right.delete(1.0, tk.END)
        
        try:
            cursor.execute("SELECT name, outcome FROM logs WHERE date = ?", (current_date.isoformat(),))
            current_outcomes = cursor.fetchall()
            cursor.execute("SELECT name, outcome FROM logs WHERE date = ?", (prev_date.isoformat(),))
            prev_outcomes = cursor.fetchall()
            
            for i, (name, outcome) in enumerate(current_outcomes[:5], 1):
                self.outcome_text_left.insert(tk.END, f"{i}. {name}: {outcome or 'No outcome'}\n")
            for i, (name, outcome) in enumerate(prev_outcomes[:5], 1):
                self.outcome_text_right.insert(tk.END, f"{i}. {name}: {outcome or 'No outcome'}\n")
            
            self.outcome_text_left.insert(tk.END, f"\nDate: {current_date}")
            self.outcome_text_right.insert(tk.END, f"\nDate: {prev_date}")
        except sqlite3.Error as e:
            logging.error(f"Failed to update outcome display: {e}")
            self.outcome_text_left.insert(tk.END, f"Error: {e}")
            self.outcome_text_right.insert(tk.END, f"Error: {e}")

    def prev_day(self):
        self.day_offset -= 1
        self.update_outcome_display()

    def next_day(self):
        self.day_offset += 1
        self.update_outcome_display()

    def update_stopwatch(self):
        if self.stopwatch_running and self.start_time:
            if not self.paused:
                elapsed = int(time.time() - self.start_time + self.paused_time)
                minutes = elapsed // 60
                seconds = elapsed % 60
                time_str = f"Time: {minutes:02d}:{seconds:02d}"
                self.stopwatch_label.config(text=time_str)
                if self.overlay:
                    self.overlay_time.config(text=time_str)
            else:
                minutes = self.paused_time // 60
                seconds = self.paused_time % 60
                time_str = f"Time: {minutes:02d}:{seconds:02d}"
                self.stopwatch_label.config(text=time_str)
                if self.overlay:
                    self.overlay_time.config(text=time_str)
        self.root.after(1000, self.update_stopwatch)

    def update_log_display(self, search_date=None):
        for row in self.log_tree.get_children():
            self.log_tree.delete(row)
        self.outcomes.clear()
        self.expanded_rows.clear()
        
        try:
            cursor.execute("SELECT name FROM categories ORDER BY name")
            self.categories = [row[0] for row in cursor.fetchall()]
            logging.info(f"Updating log display with categories: {self.categories}")
            
            columns = ["Date"] + self.categories + ["Total"]
            self.log_tree["columns"] = columns
            self.log_tree.heading("Date", text="Date")
            self.log_tree.column("Date", width=100, anchor="center")
            for cat in self.categories:
                self.log_tree.heading(cat, text=cat[:10])
                self.log_tree.column(cat, width=100, anchor="center")
            self.log_tree.heading("Total", text="Total")
            self.log_tree.column("Total", width=80, anchor="center")
            
            date_clause = "WHERE l.date = ?" if search_date else ""
            params = [search_date] if search_date else []
            cursor.execute(f"SELECT DISTINCT date FROM logs {date_clause} ORDER BY date DESC", params)
            dates = [row[0] for row in cursor.fetchall()]
            
            for date in dates:
                cursor.execute("""
                    SELECT c.name, SUM(l.time_spent), MAX(l.completed)
                    FROM logs l
                    JOIN categories c ON l.name = c.name
                    WHERE l.date = ?
                    GROUP BY c.name
                """, (date,))
                logs = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
                
                cursor.execute("""
                    SELECT c.name, l.outcome
                    FROM logs l
                    JOIN categories c ON l.name = c.name
                    WHERE l.date = ?
                    ORDER BY l.id
                """, (date,))
                for name, outcome in cursor.fetchall():
                    self.outcomes[(date, name)] = outcome or "No outcome"
                
                row_data = [date]
                total_minutes = 0
                for cat in self.categories:
                    if cat in logs:
                        time_spent, completed = logs[cat]
                        minutes = time_spent // 60
                        total_minutes += minutes
                        status = "✓" if completed else "✗"
                        row_data.append(f"{status} ({minutes}m)")
                    else:
                        row_data.append("✗ (0m)")
                row_data.append(f"{total_minutes}m")
                item = self.log_tree.insert("", tk.END, values=row_data)
                self.log_tree.item(item, tags=("Completed" if any(logs.get(cat, (0, 0))[1] for cat in logs) else "NotCompleted",))
                self.expanded_rows[item] = False
        except sqlite3.Error as e:
            logging.error(f"Failed to update log display: {e}")
            messagebox.showerror("Error", f"Failed to update log display: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = WorkTrackerApp(root)
    try:
        root.mainloop()
    finally:
        conn.close()