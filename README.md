# 基於打字行為的即時專注力分析平台
## 簡介
基於幾項指標來分析打字時的認知負荷狀態，包括打字速度(WPM)、按鍵間隔(IKI)、退格率(BSR)，根據專注分數切換介面顏色

<img width="496" height="406" alt="image" src="https://github.com/user-attachments/assets/b06644fa-44e0-41e1-bbaf-9602903a1fac" />

<img width="740" height="663" alt="image" src="https://github.com/user-attachments/assets/575e5dbc-8eb8-498e-b395-bb3507abf4b3" />

<img width="678" height="783" alt="image" src="https://github.com/user-attachments/assets/39d994e0-18b7-421a-b5ed-d0da484afc7a" />
## 使用方法
下載MySQL Server(如MariaDB)並簡易設定

在資料夾內建立.env檔放資料(DB_HOST、DB_USER、DB_PASSWORD、DB_NAME)，詳見下圖
<img width="628" height="203" alt="image" src="https://github.com/user-attachments/assets/592cf287-83ba-4f5e-accd-254f9325eaa9" />

確認模組皆可使用

執行database_setup.py

執行main.py

登入，按指引操作
## 使用工具
**python**

鍵盤監聽:keyboard

資料庫:mysql.connector

數值分析:np(numpy)

讀取env檔:dotenv
## 流程圖
<img width="588" height="397" alt="Untitled-Page-1" src="https://github.com/user-attachments/assets/dae487ab-708e-4cd2-a78e-266767bc057a" />

<img width="586" height="392" alt="Untitled-Page-2 (1)" src="https://github.com/user-attachments/assets/6b8117e9-7359-4730-b927-7afff3c60dcb" />

<img width="601" height="263" alt="Untitled-Page-3 (1)" src="https://github.com/user-attachments/assets/0d88c3cb-e534-4211-8bf0-bfa366f1bc34" />

<img width="592" height="779" alt="Untitled-Page-4 (1)" src="https://github.com/user-attachments/assets/498bb1cf-4ebe-49e8-87dc-b4c384b46c2a" />

