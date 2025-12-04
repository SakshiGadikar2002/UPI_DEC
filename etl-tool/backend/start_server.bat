@echo off
REM Start backend server
REM On Windows, Gunicorn doesn't work well, so we use Uvicorn directly
REM On Linux/Mac, use: gunicorn main:app -c gunicorn_config.py

echo Starting ETL Tool Backend Server...
echo.

REM Check if running on Windows
if "%OS%"=="Windows_NT" (
    echo Using Uvicorn (Windows compatible)...
    python main.py
) else (
    echo Using Gunicorn...
    gunicorn main:app -c gunicorn_config.py
)

