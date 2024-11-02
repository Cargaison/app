import sqlite3
import pandas as pd

# Define file paths for CSV files
file_paths = {
    'nodes_addresses': 'mnt/data/nodes-addresses.csv',
    'nodes_entities': 'mnt/data/nodes-entities.csv',
    'nodes_intermediaries': 'mnt/data/nodes-intermediaries.csv',
    'nodes_officers': 'mnt/data/nodes-officers.csv',
    'nodes_others': 'mnt/data/nodes-others.csv',
    'relationships': 'mnt/data/relationships.csv'
}

# Connect to SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect('mnt/data/tax_evasion.db')
cursor = conn.cursor()


# Function to create tables and insert data
def create_and_populate_table(table_name, file_path):
    # Load data from CSV
    df = pd.read_csv(file_path)

    # Create table based on DataFrame columns
    df.to_sql(table_name, conn, if_exists='replace', index=False)
    print(f"Table {table_name} created and populated.")


# Create and populate tables
for table_name, file_path in file_paths.items():
    create_and_populate_table(table_name, file_path)

# Close the connection
conn.close()
