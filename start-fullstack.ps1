# Videntia Full Stack Startup Script
# Windows PowerShell - Start both Backend API and Frontend

Write-Host " Starting Videntia (Backend + Frontend)" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# Check if venv is activated
if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-Host " Virtual environment not found!" -ForegroundColor Red
    exit 1
}

# Check if Node.js is installed
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host " Node.js/npm not found! Please install from https://nodejs.org/" -ForegroundColor Red
    exit 1
}

# Check if fastapi/uvicorn are installed
Write-Host "`n Checking Python dependencies..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1
python -c "import fastapi, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host " Installing fastapi and uvicorn..." -ForegroundColor Yellow
    pip install fastapi uvicorn -q
}

# Start Backend API in background
Write-Host "`n Starting Backend API on port 8000..." -ForegroundColor Green
Start-Process -FilePath "python" -ArgumentList "api.py" -WindowStyle Normal

# Wait for API to start
Start-Sleep -Seconds 3

# Check if API is running
$apiHealth = $null
try {
    $apiHealth = curl -s http://localhost:8000/health 2>$null
} catch {
    Write-Host "  Could not verify API startup" -ForegroundColor Yellow
}

if ($apiHealth) {
    Write-Host " Backend API started successfully" -ForegroundColor Green
} else {
    Write-Host "  Backend API may not be responding" -ForegroundColor Yellow
}

# Start Frontend in background
Write-Host "`n Starting Frontend on port 3000..." -ForegroundColor Green

# Check if node_modules exist in frontend
if (-not (Test-Path "frontend\node_modules")) {
    Write-Host " Installing frontend dependencies (this may take a minute)..." -ForegroundColor Yellow
    cd frontend
    npm install
    cd ..
}

Start-Process -FilePath "cmd" -ArgumentList "/c cd frontend && npm run dev" -WindowStyle Normal

# Wait a bit for frontend to start
Start-Sleep -Seconds 5

Write-Host "`n================================================" -ForegroundColor Cyan
Write-Host " Videntia is starting!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host " Frontend:  http://localhost:3000" -ForegroundColor Cyan
Write-Host " API:       http://localhost:8000" -ForegroundColor Cyan
Write-Host " API Docs:  http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host " Open your browser and start analyzing videos!" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Both services are running in separate windows." -ForegroundColor Gray
Write-Host " To stop: Close both windows or press Ctrl+C" -ForegroundColor Gray
