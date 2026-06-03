from storage.postgres import get_connection

def list_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
          AND table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name;
    """)

    rows = cur.fetchall()
    for row in rows:
        print(f"{row['table_schema']}.{row['table_name']}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    list_tables()
