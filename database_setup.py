import mysql.connector
import os
from dotenv import load_dotenv

# 讀取.env 檔案
load_dotenv()

# 連接到 MariaDB 資料庫 '0226'
conn = mysql.connector.connect(
    host=os.getenv("DB_HOST"),      # 讀取 .env 裡的 DB_HOST
    user=os.getenv("DB_USER"),      # 讀取 .env 裡的 DB_USER
    password=os.getenv("DB_PASSWORD"), # 讀取 .env 裡的 DB_PASSWORD
)



# 創建游標對象來執行 SQL 查詢
cursor = conn.cursor()
db_name = os.getenv("DB_NAME")

#創資料庫
cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")

#選資料庫
cursor.execute(f"USE {db_name}")

# SQL 語句：創建資料表
create_table_query = '''
CREATE TABLE IF NOT EXISTS Information (
    userid INT,
    time INT,
    FocusIndex INT,
    LevelOfFocus INT
);
'''

# 執行創建資料表語句
cursor.execute(create_table_query)


# 提交事務
conn.commit()

# 關閉游標和連接
cursor.close()
conn.close()
