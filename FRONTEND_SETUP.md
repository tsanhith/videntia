# Videntia - Full Stack Video Analysis System

**Complete AI-powered video analysis with visual frontend, REST API, and multi-agent orchestration.**

## 🎯 What is Videntia?

Videntia is an **agentic AI system** that analyzes videos using:

- **Phase 5 Audio Processing**: Speaker diarization + speaker embeddings + transcription
- **Phase 4 Multi-Agent System**: 5 specialized agents (Detective, Retriever, Scribe, Verifier, Summarizer)
- **Phase 3 Hybrid Retrieval**: BM25 + dense vector search + reranking
- **Phase 2 RAG**: Retrieval-Augmented Generation for accurate answers
- **Visual Frontend**: React/Next.js UI for uploading videos and asking questions
- **REST API**: FastAPI backend exposing all functionality

## 🚀 Quick Start (Visual)

### Prerequisites

- Python 3.13+ with virtual environment activated
- Node.js 18+ (for frontend)
- Video file (MP4, WebM, etc.)

### Option 1: One-Click Launch (Windows PowerShell)

```powershell
# From project root
.\start-fullstack.ps1
```

This automatically:

1. ✅ Starts Backend API on `http://localhost:8000`
2. ✅ Starts Frontend on `http://localhost:3000`
3. ✅ Opens browser ready to use

### Option 2: Manual Start

**Terminal 1 - Backend API:**

```powershell
& .\venv\Scripts\Activate.ps1
pip install fastapi uvicorn python-multipart -q
python api.py
```

**Terminal 2 - Frontend:**

```powershell
cd frontend
npm install
npm run dev
```

Then open: `http://localhost:3000`

## 📊 Frontend Features

### 1. Home Page (`/`)

- 📁 **Upload Video** - Select MP4/WebM file
- 🎯 **Auto-processing** - Extract segments, transcribe, diarize, embed

### 2. Query Page (`/query?video=XXX`)

- 🔍 **Natural Language Queries** - Ask anything about the video
- 📌 **Evidence Display** - See which segments support the answer
- 😊 **Emotion Analysis** - View detected emotions in each segment
- 🎤 **Speaker Attribution** - Know who said what

### 3. Analysis Page (`/analyze/{videoId}`)

- **Speaker Timeline** - Visual representation of speaker segments
- **Emotion Heatmap** - Emotional intensity over time
- **Segment Metadata** - Detailed breakdown of each segment

## 🔌 REST API Endpoints

| Method | Endpoint                    | Purpose               |
| ------ | --------------------------- | --------------------- |
| POST   | `/api/videos/upload`        | Upload & ingest video |
| GET    | `/api/videos`               | List all videos       |
| GET    | `/api/videos/{id}/segments` | Get video segments    |
| GET    | `/api/videos/{id}/speakers` | Get speaker timeline  |
| GET    | `/api/videos/{id}/emotions` | Get emotion analysis  |
| POST   | `/api/query`                | Submit analysis query |
| GET    | `/api/query/{id}`           | Poll query result     |

**Interactive API Docs:** http://localhost:8000/docs

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   React Frontend (Next.js)                  │
│                     localhost:3000                          │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP/REST
┌──────────────────────────▼──────────────────────────────────┐
│                  FastAPI Backend (api.py)                   │
│                     localhost:8000                          │
└──────────────────────────┬──────────────────────────────────┘
                           │ Python imports
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼────────┐ ┌───────▼────────┐ ┌──────▼──────────┐
│  Phase 5       │ │  Phase 4       │ │  Phase 3        │
│  Audio Proc.   │ │  5 Agents      │ │  Retrieval      │
├────────────────┤ ├────────────────┤ ├─────────────────┤
│ • Whisper      │ │ • Detective    │ │ • BM25 search   │
│ • Diarization  │ │ • Retriever    │ │ • Dense search  │
│ • Embeddings   │ │ • Scribe       │ │ • Reranking     │
│ • Speaker ID   │ │ • Verifier     │ │ • ChromaDB      │
│                │ │ • Summarizer   │ │                 │
└────────────────┘ └────────────────┘ └─────────────────┘
```

## 📁 Project Structure

```
videntia/
├── api.py                      # FastAPI server
├── main.py                     # CLI orchestration
├── config.py                   # Configuration
├── requirements.txt            # Python dependencies
│
├── frontend/                   # React/Next.js
│   ├── app/
│   │   ├── page.tsx           # Home/upload
│   │   ├── query/page.tsx     # Query interface
│   │   └── analyze/[videoId]/ # Analysis dashboard
│   ├── lib/api.ts             # API client
│   ├── package.json
│   └── README.md
│
├── pipeline/                   # Video processing
│   ├── ingest.py              # Ingestion pipeline
│   ├── audio_embeddings.py    # Phase 5 audio
│   ├── transcribe.py
│   ├── segment.py
│   └── ...
│
├── agents/                     # Multi-agent orchestration
│   ├── lead_detective.py
│   ├── retriever_agent.py
│   ├── scribe_agent.py
│   ├── verifier_agent.py
│   └── ...
│
├── rag/                        # Retrieval system
│   ├── retriever.py
│   └── reranker.py
│
├── embed/                      # Embeddings
│   ├── store.py
│   ├── text_embedder.py
│   └── bm25_index.py
│
└── data/                       # Data storage
    ├── videos/
    ├── segments/
    ├── records/                # JSON segment metadata
    ├── transcripts/
    └── ...
```

## 🛠️ Troubleshooting

### Port Already in Use

```powershell
# Find process on port 8000
Get-NetTCPConnection -LocalPort 8000
# Kill it
Stop-Process -Id <PID> -Force
```

### API Not Responding

```powershell
# Verify API is running
curl http://localhost:8000/health
```

### Video Upload Fails

- Ensure `data/videos/` directory exists
- Try with smaller file first
- Check: `data/videos/` directory permissions

### Frontend Doesn't Connect to API

- Verify backend API is running on port 8000
- Check `.env.local` in frontend directory
- CORS should be enabled (it is by default)

## 📝 Example Usage

### 1. Upload a Video

```
Home page → Click upload box → Select MP4 file → Wait for processing
```

### 2. Ask a Question

```
Query page → "What were the main topics discussed?"
→ See evidence segments + confidence score
```

### 3. View Speaker Analysis

```
Analysis page → See speaker segments on timeline
→ Click segment to see full transcript
```

## 🔑 Key Features

### ✅ Audio Analysis

- ✨ Speaker diarization (who speaks when)
- 📊 Speaker embeddings (256-dim vectors)
- 🎙️ Transcription (Whisper-based)
- 😊 Emotion detection per segment

### ✅ Multi-Agent Intelligence

- 🕵️ **Detective**: Orchestrates investigation
- 🔍 **Retriever**: Fetches relevant segments
- ✍️ **Scribe**: Summarizes findings
- ✔️ **Verifier**: Checks for contradictions
- 📝 **Summarizer**: Generates final report

### ✅ Smart Retrieval

- BM25 keyword search (fast)
- Dense vector search (semantic)
- Reciprocal Rank Fusion (hybrid)
- Learning-to-rank reranking

### ✅ Production Ready

- Graceful error handling
- Async queries with polling
- Background tasks
- CORS enabled
- API documentation

## 🚀 Deployment

### Development

```powershell
.\start-fullstack.ps1
```

### Production (Docker coming soon)

```powershell
# Backend
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 api:app

# Frontend
npm run build
npm run start
```

## 🎓 How It Works

1. **User uploads video** → Frontend sends to API
2. **API ingests video** → Phases 2-5 process it
   - Phase 5: Extract transcription + diarization + embeddings
   - Phase 2: Build RAG index (ChromaDB)
3. **User asks question** → Sent to `/api/query`
4. **5-agent system activates:**
   - Detective breaks down question
   - Retriever finds relevant segments
   - Scribe summarizes evidence
   - Verifier checks contradictions
   - Summarizer generates report
5. **Results displayed** → Frontend shows answer + evidence

## 📚 Documentation

- **Backend API**: http://localhost:8000/docs (Swagger UI)
- **Frontend README**: `frontend/README.md`
- **Architecture**: See `Architecture` section above
- **Configuration**: See `config.py`

## 🤝 Integration Points

### Python Backend

- Modify `config.py` for models/settings
- Edit `api.py` for new endpoints
- Add agents in `agents/` directory

### React Frontend

- Edit pages in `frontend/app/`
- Update API calls in `frontend/lib/api.ts`
- Add components in `frontend/app/components/`

## ⚙️ System Requirements

### Backend (Recommended)

- CPU: 4+ cores
- RAM: 16GB+
- GPU: NVIDIA RTX 3080+ (optional, speeds up processing)
- Disk: 50GB+ (for videos + models)

### Frontend

- Any modern browser (Chrome, Firefox, Safari, Edge)
- Stable internet connection

## 🔐 Security Notes

- `.env` file contains API keys (never commit)
- HF_TOKEN required for gated models
- CORS enabled for localhost only (adjust for production)
- No authentication (add if needed for production)

## 📞 Support

1. **Check logs**: Backend terminal shows all errors
2. **API Health**: http://localhost:8000/health
3. **Frontend Console**: Browser DevTools (F12)
4. **Full Debug**: Run with verbose output:
   ```powershell
   python api.py --log-level debug
   ```

## 🎉 You're All Set!

```
Open browser → http://localhost:3000
Upload video → Click "Ask Questions" → Get answers!
```

**Enjoy your AI-powered video analysis! 🚀**
