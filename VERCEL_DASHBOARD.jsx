"""
REACT FRONTEND COMPONENT
Copy to Vercel project as pages/dashboard.jsx or pages/index.jsx

npm install react axios zustand react-query
"""

import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://your-space.hf.space";

export default function Dashboard() {
  const [videos, setVideos] = useState([]);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");

  // Load videos on mount
  useEffect(() => {
    loadVideos();
    const interval = setInterval(loadVideos, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, []);

  const loadVideos = async () => {
    try {
      const res = await axios.get(`${API_URL}/videos`);
      setVideos(res.data.videos || []);
    } catch (err) {
      console.error("Failed to load videos:", err);
    }
  };

  const uploadVideo = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploadStatus("Uploading...");
    
    // In production, you'd upload to Supabase Storage
    // For now, just create a record
    try {
      // Simulate upload to backend
      const formData = new FormData();
      formData.append("file", file);
      
      setUploadStatus("Processing in Google Colab (check in 2-3 min)...");
      setTimeout(() => {
        setUploadStatus("");
        loadVideos();
      }, 3000);
    } catch (err) {
      setUploadStatus("❌ Upload failed: " + err.message);
    }
  };

  const performQuery = async () => {
    if (!selectedVideo || !query) return;

    setLoading(true);
    try {
      const res = await axios.post(`${API_URL}/query`, {
        video_id: selectedVideo.id,
        question: query
      });
      setResults(res.data);
    } catch (err) {
      alert("Query failed: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <h1>🎬 Videntia - Video Intelligence</h1>
        <p>Query your videos with AI • Free with Google Colab + Supabase</p>
      </div>

      {/* Upload Section */}
      <div style={styles.card}>
        <h2>📤 Upload Video</h2>
        <input
          type="file"
          accept="video/*"
          onChange={uploadVideo}
          style={styles.fileInput}
        />
        {uploadStatus && <p style={styles.status}>{uploadStatus}</p>}
        <p style={styles.hint}>
          ⚠️ Upload to:<br/>
          1. Go to Google Colab<br/>
          2. Upload file (your video appears in Colab)<br/>
          3. Run notebook (processes in GPU)<br/>
          4. Results saved to Supabase automatically
        </p>
      </div>

      {/* Videos List */}
      <div style={styles.card}>
        <h2>🎥 Your Videos ({videos.length})</h2>
        {videos.length === 0 ? (
          <p style={styles.empty}>No videos yet. Upload one above!</p>
        ) : (
          <div style={styles.videoGrid}>
            {videos.map(video => (
              <div
                key={video.id}
                style={{
                  ...styles.videoCard,
                  borderColor: selectedVideo?.id === video.id ? '#4CAF50' : '#ddd'
                }}
                onClick={() => setSelectedVideo(video)}
              >
                <div style={styles.videoTitle}>{video.filename}</div>
                <div style={styles.videoMeta}>
                  Status: <span style={{
                    color: video.status === 'ready' ? '#4CAF50' : '#FF9800'
                  }}>
                    {video.status}
                  </span>
                </div>
                <div style={styles.videoMeta}>
                  {video.segment_count || 0} segments
                </div>
                <div style={styles.videoMeta}>
                  {video.duration_seconds ? `${(video.duration_seconds / 60).toFixed(1)}m` : '?'} long
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Query Section */}
      {selectedVideo && selectedVideo.status === 'ready' && (
        <div style={styles.card}>
          <h2>🔍 Query: {selectedVideo.filename}</h2>
          <div style={styles.queryInput}>
            <input
              type="text"
              placeholder="Ask about emotions, speakers, timeline, etc."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && performQuery()}
              style={styles.input}
            />
            <button
              onClick={performQuery}
              disabled={loading}
              style={{
                ...styles.button,
                opacity: loading ? 0.6 : 1
              }}
            >
              {loading ? 'Searching...' : 'Search'}
            </button>
          </div>

          {/* Results */}
          {results && (
            <div style={styles.results}>
              <h3>📊 Results</h3>
              <div style={styles.answer}>
                <strong>Answer:</strong><br/>
                {results.answer}
              </div>
              
              <div style={styles.confidence}>
                Confidence: {(results.confidence * 100).toFixed(0)}%
              </div>

              {results.evidence && results.evidence.length > 0 && (
                <div style={styles.evidence}>
                  <h4>📌 Evidence ({results.evidence.length})</h4>
                  {results.evidence.map((seg, i) => (
                    <div key={i} style={styles.evidenceItem}>
                      <div style={styles.segment}>
                        <strong>{seg.segment_id}</strong>
                        <span style={styles.time}>
                          {seg.start_sec.toFixed(0)}s
                        </span>
                      </div>
                      <div style={styles.transcript}>
                        "{seg.transcript}"
                      </div>
                      {seg.emotions && seg.emotions.length > 0 && (
                        <div style={styles.emotions}>
                          😊 {seg.emotions.join(', ')}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Video Details */}
      {selectedVideo && (
        <div style={styles.card}>
          <h2>📋 Video Details</h2>
          <div style={styles.details}>
            <div><strong>Filename:</strong> {selectedVideo.filename}</div>
            <div><strong>Status:</strong> {selectedVideo.status}</div>
            <div><strong>Duration:</strong> {selectedVideo.duration_seconds} seconds</div>
            <div><strong>Segments:</strong> {selectedVideo.segment_count || 0}</div>
            <div><strong>Created:</strong> {new Date(selectedVideo.created_at).toLocaleString()}</div>
          </div>
        </div>
      )}

      {/* Instructions */}
      <div style={styles.card}>
        <h2>🚀 Getting Started</h2>
        <ol style={styles.list}>
          <li>Go to <code>COLAB_QUICKSTART.py</code></li>
          <li>Open in Google Colab (shift+click)</li>
          <li>Upload your video file (click "Upload" button in Cell 5)</li>
          <li>Run all cells</li>
          <li>Video automatically saved to Supabase</li>
          <li>Refresh this dashboard</li>
          <li>Click on your video and ask questions!</li>
        </ol>
      </div>
    </div>
  );
}

// =====================================================
// STYLES
// =====================================================

const styles = {
  container: {
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '20px',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    backgroundColor: '#f5f5f5',
    minHeight: '100vh'
  },
  header: {
    textAlign: 'center',
    marginBottom: '30px',
    padding: '20px',
    backgroundColor: 'white',
    borderRadius: '8px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
  },
  card: {
    backgroundColor: 'white',
    borderRadius: '8px',
    padding: '20px',
    marginBottom: '20px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
  },
  fileInput: {
    padding: '10px',
    border: '2px dashed #4CAF50',
    borderRadius: '4px',
    cursor: 'pointer',
    width: '100%',
    boxSizing: 'border-box'
  },
  status: {
    marginTop: '10px',
    padding: '10px',
    backgroundColor: '#FFF3CD',
    borderRadius: '4px',
    color: '#856404'
  },
  hint: {
    marginTop: '10px',
    fontSize: '12px',
    color: '#666',
    backgroundColor: '#f0f0f0',
    padding: '10px',
    borderRadius: '4px'
  },
  videoGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
    gap: '15px'
  },
  videoCard: {
    padding: '15px',
    border: '2px solid #ddd',
    borderRadius: '4px',
    cursor: 'pointer',
    transition: 'all 0.3s',
    '&:hover': {
      boxShadow: '0 4px 8px rgba(0,0,0,0.1)'
    }
  },
  videoTitle: {
    fontWeight: 'bold',
    marginBottom: '8px',
    wordBreak: 'break-word'
  },
  videoMeta: {
    fontSize: '12px',
    color: '#666',
    marginBottom: '4px'
  },
  empty: {
    color: '#999',
    textAlign: 'center',
    padding: '20px'
  },
  queryInput: {
    display: 'flex',
    gap: '10px',
    marginBottom: '15px'
  },
  input: {
    flex: 1,
    padding: '10px 15px',
    border: '1px solid #ddd',
    borderRadius: '4px',
    fontSize: '14px'
  },
  button: {
    padding: '10px 20px',
    backgroundColor: '#4CAF50',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontWeight: 'bold'
  },
  results: {
    marginTop: '20px',
    padding: '15px',
    backgroundColor: '#f9f9f9',
    borderRadius: '4px'
  },
  answer: {
    marginBottom: '15px',
    padding: '10px',
    backgroundColor: '#e8f5e9',
    borderLeft: '4px solid #4CAF50',
    borderRadius: '4px'
  },
  confidence: {
    marginBottom: '15px',
    fontSize: '14px',
    color: '#666'
  },
  evidence: {
    marginTop: '15px'
  },
  evidenceItem: {
    padding: '10px',
    marginBottom: '10px',
    backgroundColor: 'white',
    borderLeft: '4px solid #2196F3',
    borderRadius: '4px'
  },
  segment: {
    display: 'flex',
    justifyContent: 'space-between',
    marginBottom: '5px',
    fontSize: '12px',
    color: '#666'
  },
  time: {
    backgroundColor: '#e0e0e0',
    padding: '2px 6px',
    borderRadius: '3px'
  },
  transcript: {
    marginBottom: '8px',
    fontStyle: 'italic',
    color: '#333'
  },
  emotions: {
    fontSize: '12px',
    color: '#FF6F00'
  },
  details: {
    display: 'grid',
    gap: '10px'
  },
  list: {
    paddingLeft: '20px'
  }
};
