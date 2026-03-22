import mysql.connector

def get_connection():
    try:
        return mysql.connector.connect(
             host="host.docker.internal",
            user="root",
            password="Mysql@ayu04",
            database="project",
            
        )
    except Exception as e:
        print(f"Error: {e}")
        return None