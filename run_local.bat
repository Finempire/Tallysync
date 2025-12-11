@echo off
echo Starting Tally Automation Locally...

echo Starting Backend...
start "Tally Backend" cmd /k "cd backend && call venv\Scripts\activate && python manage.py runserver 0.0.0.0:8000"

echo Starting Frontend...
start "Tally Frontend" cmd /k "cd frontend && npm install && npm run dev"

echo Done. Backend running on 8000, Frontend on 3000 (usually).
echo Access at http://localhost:3000
pause
