import sqlite3
import sys
from tabulate import tabulate  # Optional: for prettier table formatting

def get_db_connection(db_path='game.db'):
    """Create a connection to the SQLite database with row factory enabled"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    return conn

def get_table_names(conn):
    """Get all table names from the database"""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    return [row[0] for row in cursor.fetchall()]

def view_table(conn, table_name):
    """View all contents of a specific table"""
    cursor = conn.cursor()
    
    # Get column names
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = [row[1] for row in cursor.fetchall()]
    
    # Get all rows
    cursor.execute(f"SELECT * FROM {table_name};")
    rows = cursor.fetchall()
    
    # Convert rows to list of dicts
    data = []
    for row in rows:
        data.append(dict(row))
    
    return columns, data

def print_table(table_name, columns, data):
    """Print table data in a formatted way"""
    print(f"\n=== {table_name.upper()} TABLE ===")
    
    if not data:
        print("(No data found in this table)")
        return
    
    try:
        # Try to use tabulate for prettier formatting if available
        from tabulate import tabulate
        rows = [[row[col] for col in columns] for row in data]
        print(tabulate(rows, headers=columns, tablefmt="grid"))
    except ImportError:
        # Fallback to simple formatting
        header = " | ".join(columns)
        print(header)
        print("-" * len(header))
        for row in data:
            print(" | ".join(str(row[col]) for col in columns))

def view_all_tables(db_path='game.db'):
    """View the contents of all tables in the database"""
    try:
        conn = get_db_connection(db_path)
        table_names = get_table_names(conn)
        
        for table_name in table_names:
            columns, data = view_table(conn, table_name)
            print_table(table_name, columns, data)
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

def view_specific_table(table_name, db_path='game.db'):
    """View the contents of a specific table"""
    try:
        conn = get_db_connection(db_path)
        try:
            columns, data = view_table(conn, table_name)
            print_table(table_name, columns, data)
        except sqlite3.Error:
            print(f"Table '{table_name}' not found in database.")
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

def main():
    if len(sys.argv) == 1:
        # No arguments, show all tables
        view_all_tables()
    elif len(sys.argv) == 2:
        # One argument, could be table name or database path
        arg = sys.argv[1]
        if arg.endswith('.db'):
            # It's a database path
            view_all_tables(arg)
        else:
            # It's a table name
            view_specific_table(arg)
    elif len(sys.argv) == 3:
        # Two arguments: table name and database path
        table_name = sys.argv[1]
        db_path = sys.argv[2]
        view_specific_table(table_name, db_path)
    else:
        print("Usage:")
        print("  python view_game_db.py                  # View all tables in game.db")
        print("  python view_game_db.py <table_name>     # View specific table in game.db")
        print("  python view_game_db.py <db_path>        # View all tables in specified DB")
        print("  python view_game_db.py <table> <db_path> # View specific table in specified DB")

if __name__ == "__main__":
    main()