# Videntia - Commands to Run

## Quick Start (Recommended)

### Option 1: Use the Startup Script (Windows PowerShell)

```powershell
.\start-fullstack.ps1
```

This starts both backend and frontend automatically.

---

## Manual Commands

### Option 2: Run Backend and Frontend Separately

#### Terminal 1 - Start Backend API (Port 8000)

```powershell
& .\venv\Scripts\Activate.ps1
python api.py
```

#### Terminal 2 - Start Frontend (Port 3000)

```powershell
cd frontend
npm install
npm run dev
```

---

## Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## Troubleshooting

### If Backend Fails

- Make sure Python virtual environment is created: `python -m venv venv`
- Install dependencies: `pip install -r requirements.txt`
- Check if port 8000 is available

### If Frontend Fails

- Make sure Node.js/npm is installed
- Delete `node_modules` and `package-lock.json`, then run `npm install` again
- Check if port 3000 is available

### To Stop Services

- Press `Ctrl+C` in the terminal windows
- Or close the command windows directly
