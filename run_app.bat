@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ==================================================
echo      啟動 JAMOVI 智能助手 (Jamovi Assistant)
echo ==================================================
echo.

echo 正在啟動 Streamlit 伺服器...
streamlit run app.py

if %errorlevel% neq 0 (
    echo.
    echo [錯誤] 程式發生錯誤或意外終止。
    echo 請檢查是否有錯誤訊息。
    pause
)
