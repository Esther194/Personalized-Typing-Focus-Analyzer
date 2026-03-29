import mysql.connector
import os
from dotenv import load_dotenv

# 讀取.env 檔案
load_dotenv()

# 連接到 MariaDB 資料庫
conn = mysql.connector.connect(
    host=os.getenv("DB_HOST"),      # 讀取 .env 裡的 DB_HOST
    user=os.getenv("DB_USER"),      # 讀取 .env 裡的 DB_USER
    password=os.getenv("DB_PASSWORD"), # 讀取 .env 裡的 DB_PASSWORD
    database=os.getenv("DB_NAME"), # 讀取 .env 裡的 DB_NAME
)



# 創建游標對象來執行 SQL 查詢
cursor = conn.cursor()

#刪舊資料表
cursor.execute('''
    DROP TABLE IF EXISTS baseline
''')

cursor.execute('''
    DROP TABLE IF EXISTS focus_records
''')


#創建資料表存基準線
cursor.execute('''
    CREATE TABLE IF NOT EXISTS baseline (
        baseline_id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT UNIQUE,
        wpm FLOAT,
        iki_mean FLOAT,
        iki_std FLOAT,
        bsr FLOAT,
        sample_count INT DEFAULT 1,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
''')

#創建資料表存歷史紀錄
cursor.execute('''
    CREATE TABLE IF NOT EXISTS focus_records (
        record_id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        focus_score FLOAT,
        wpm FLOAT,
        iki_mean FLOAT,
        iki_std FLOAT,
        bsr FLOAT,
        total_keys INT,
        session_duration FLOAT,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
''')

# 提交事務
conn.commit()

# 關閉游標和連接
cursor.close()
conn.close()
