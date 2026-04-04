"""
Run database migrations from SQL files
Usage: python run_migrations.py
"""
from dotenv import load_dotenv
from pathlib import Path
import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv(Path('.env'))

import os
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in .env")
    exit(1)

print(f"Connecting to: {DATABASE_URL}")

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    migrations_dir = Path('migrations')
    sql_files = sorted(migrations_dir.glob('*.sql'))
    
    print(f"\nFound {len(sql_files)} migration files:")
    for sql_file in sql_files:
        print(f"  - {sql_file.name}")
    
    print("\nRunning migrations...")
    for sql_file in sql_files:
        print(f"\n[{sql_file.name}]")
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql = f.read()
        
        try:
            cursor.execute(sql)
            conn.commit()
            print(f"✓ Success")
        except Exception as e:
            print(f"✗ Error: {e}")
            conn.rollback()
    
    cursor.close()
    conn.close()
    print("\n✓ All migrations completed!")
    
except Exception as e:
    print(f"Connection error: {e}")
    exit(1)
