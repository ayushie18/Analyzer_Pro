import os
import mysql.connector

def get_connection():
    try:
        port = os.getenv("MYSQLPORT")

        conn = mysql.connector.connect(
            host=os.getenv("MYSQLHOST"),
            user=os.getenv("MYSQLUSER"),
            password=os.getenv("MYSQLPASSWORD"),
            database=os.getenv("MYSQLDATABASE"),
            port=int(port) if port else 3306   # ✅ FIX HERE
        )
        return conn

    except Exception as e:
        print("Database Error:", e)
        return None