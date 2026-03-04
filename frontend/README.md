# Running Videntia with Frontend

## Prerequisites

1. **Python Backend** (already set up)
   - Virtual environment activated: `& .\venv\Scripts\Activate.ps1`
   - All dependencies installed

2. **Node.js Frontend**
   - Install Node.js from https://nodejs.org/
   - Run from `/frontend` directory

## Quick Start

### Terminal 1: Start the Backend API

```powershell
& .\venv\Scripts\Activate.ps1
pip install fastapi uvicorn
python api.py
```

The API will be available at `http://localhost:8000`

### Terminal 2: Start the Frontend

```powershell
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Usage

1. **Open browser:** http://localhost:3000
2. **Upload a video** (MP4, WebM, etc.)
3. **Choose an action:**
   - **Ask Questions** - Query the video with natural language
   - **View Analysis** - See speaker diarization and emotion timeline

## API Endpoints

- `POST /api/videos/upload` - Upload a video
- `GET /api/videos` - List uploaded videos
- `GET /api/videos/{video_id}/segments` - Get video segments
- `POST /api/query` - Submit a query
- `GET /api/query/{query_id}` - Get query result
- `GET /api/videos/{video_id}/speakers` - Get speaker timeline
- `GET /api/videos/{video_id}/emotions` - Get emotion analysis

## Architecture

```
┌─────────────────┐
│  React Frontend │ (port 3000)
│   Next.js App   │
└────────┬────────┘
         │ HTTP
┌────────▼────────┐
│  FastAPI Server │ (port 8000)
│  (api.py)       │
└────────┬────────┘
         │
┌────────▼──────────────┐
│  Backend Modules      │
├──────────────────────┤
│ - Phase 5: Audio     │
│ - Phase 4: Agents    │
│ - Phase 3: Retrieval │
│ - Phase 2: RAG       │
└──────────────────────┘
```

## Troubleshooting

### Port Already in Use

- Backend: `lsof -i :8000` then kill the process
- Frontend: `lsof -i :3000` then kill the process

### CORS Errors

- Frontend is configured to accept requests from backend
- Ensure both are running on correct ports

### Video Upload Issues

- Check that `data/videos` directory exists
- Ensure sufficient disk space
- Try with smaller MP4 file first

## Development

### Backend (FastAPI)

- Edit `api.py` for new endpoints
- Hot reload available: `python api.py`

### Frontend (Next.js)

- Edit files in `frontend/app/` directory
- Hot reload automatic on save
- Rebuild with `npm run build`

## Production Deployment

### Backend

```powershell
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 api:app
```

### Frontend

```powershell
npm run build
npm run start
```

## Notes

- Videos are stored in `data/videos/`
- Embeddings and metadata stored in `db/chroma/`
- Segment records stored in `data/records/`
- All analysis runs via the 5-agent orchestration system
