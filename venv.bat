@echo off
echo Activating virtual environment...
call "D:\projects\work tracker\venv\Scripts\activate"
if errorlevel 1 (
    echo Failed to activate virtual environment.
    pause
    exit /b %errorlevel%
)
echo Virtual environment activated. Python version:
python --version
echo You can now run 'python work_tracker.py'
cmd /k