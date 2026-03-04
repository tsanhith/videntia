"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Play, Pause, FastForward, Activity, MessageSquare } from "lucide-react";
import { videosApi } from "../../../lib/api";
import styles from "./analyze.module.css";

function formatTime(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

const NEGATIVE_EMOTIONS = ["anger", "disgust", "fear", "sadness"];
const POSITIVE_EMOTIONS = ["joy", "surprise"];

export default function AnalyzePage() {
  const params = useParams();
  const videoId = params.videoId as string;

  const [segments, setSegments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [activeTab, setActiveTab] = useState<"combined" | "diarization" | "emotion">("combined");
  const videoRef = useRef<HTMLVideoElement>(null);

  const SPEAKER_COLORS = [
    "#3b82f6", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#06b6d4"
  ];
  
  const uniqueSpeakers = Array.from(new Set(segments.map(s => s.speaker).filter(Boolean)));

  const handleSeek = (time: number) => {
    setCurrentTime(time);
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      videoRef.current.play().catch((e) => console.log("Auto-play prevented", e));
    }
  };

  // Because the actual browser video playback of a dynamically generated video path
  // can be complex without a streaming server, we use a placeholder or 
  // an HTML5 video pointing to the Next.js public directory if configured.
  // For the Videntia UI layout, we'll build a custom synchronized playback state.

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [segRes] = await Promise.all([
          videosApi.getSegments(videoId),
        ]);
        setSegments(segRes.segments || []);
      } catch (err) {
        setError("Failed to load forensic data. " + (err as Error).message);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [videoId]);

  const activeSegmentIndex = segments.findIndex(
    (s) => currentTime >= s.start_sec && currentTime <= s.end_sec
  );

  const activeSegment = activeSegmentIndex >= 0 ? segments[activeSegmentIndex] : null;

  if (loading) {
    return (
      <div className={styles.container} style={{ alignItems: "center", justifyContent: "center" }}>
        <p style={{ color: "var(--text-secondary)" }}>Loading forensic timeline...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container} style={{ alignItems: "center", justifyContent: "center" }}>
        <p style={{ color: "var(--error-color)" }}>{error}</p>
        <Link href="/" className={styles.backLink} style={{marginTop: "16px"}}>
            <ArrowLeft size={16}/> Return to Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {/* LEFT PANE: Video + Visualizations */}
      <div className={styles.leftPane}>
        <div className={styles.headerRow}>
          <Link href="/" className={styles.backLink}>
            <ArrowLeft size={16} /> Back to Hub
          </Link>
          <div style={{ fontSize: "0.9rem", color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>
            CASE ID: {videoId}
          </div>
        </div>

        <div className={styles.videoSection}>
             {/* Actual Video Player synchronized with our timeline state */}
             <video
                ref={videoRef}
                controls
                className={styles.realVideoPlayer}
                onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
             >
                <source src={`http://localhost:8000/api/videos/${videoId}/stream`} type="video/mp4" />
                Your browser does not support HTML video.
             </video>
        </div>

        <div className={styles.timelineSection}>
          <h3 className={styles.sectionTitle}>
             <Activity size={18} /> Global Timeline Visuzliation
          </h3>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
            High-density event map. Click on any segment in the transcript to seek.
          </p>
          
          <div className={styles.tabsRow}>
              <button 
                  className={`${styles.tab} ${activeTab === 'combined' ? styles.active : ''}`}
                  onClick={() => setActiveTab('combined')}
              >
                  Combined Tracks
              </button>
              <button 
                  className={`${styles.tab} ${activeTab === 'diarization' ? styles.active : ''}`}
                  onClick={() => setActiveTab('diarization')}
              >
                  Speaker Diarization
              </button>
              <button 
                  className={`${styles.tab} ${activeTab === 'emotion' ? styles.active : ''}`}
                  onClick={() => setActiveTab('emotion')}
              >
                  Emotion Density
              </button>
          </div>

          <div style={{ height: "120px", display: "flex", gap: "2px", alignItems: "flex-end", overflowX: "auto" }}>
             {segments.map((seg, idx) => {
                 const isNegative = seg.emotions?.some((e: string) => NEGATIVE_EMOTIONS.includes(e));
                 const isPositive = seg.emotions?.some((e: string) => POSITIVE_EMOTIONS.includes(e));
                 
                 let color = "var(--surface-hover)";
                 let height = `${Math.max(20, (seg.emotion_intensity || 0.5) * 100)}%`;
                 
                 if (activeTab === "diarization") {
                     height = "100%";
                     const speakerIdx = uniqueSpeakers.indexOf(seg.speaker);
                     color = speakerIdx >= 0 ? SPEAKER_COLORS[speakerIdx % SPEAKER_COLORS.length] : color;
                 } else if (activeTab === "emotion") {
                     if (isNegative) color = "rgba(239, 68, 68, 0.8)";
                     if (isPositive) color = "rgba(16, 185, 129, 0.8)";
                 } else {
                     // combined
                     if (isNegative) color = "rgba(239, 68, 68, 0.4)";
                     if (isPositive) color = "rgba(16, 185, 129, 0.4)";
                 }
                 
                 return (
                     <div 
                        key={idx}
                        style={{
                            flex: 1,
                            minWidth: "4px",
                            height: height,
                            background: idx === activeSegmentIndex ? "var(--accent-color)" : color,
                            borderRadius: "2px 2px 0 0",
                            cursor: "pointer",
                            transition: "background 0.2s"
                        }}
                        title={`[${formatTime(seg.start_sec)}] ${seg.speaker || "Unknown"}`}
                        onClick={() => handleSeek(seg.start_sec)}
                     />
                 )
             })}
          </div>
        </div>
      </div>

      {/* RIGHT PANE: Transcript */}
      <div className={styles.rightPane}>
        <div className={styles.transcriptHeader}>
           <h2 className={styles.transcriptTitle}>Indexed Transcript</h2>
           <Link href={`/query/${videoId}`} style={{
               background: "var(--text-primary)",
               color: "var(--bg-color)",
               padding: "6px 12px",
               borderRadius: "4px",
               fontSize: "0.85rem",
               fontWeight: 500,
               display: "flex",
               alignItems: "center",
               gap: "6px"
           }}>
             <MessageSquare size={14} /> AI Query
           </Link>
        </div>

        <div className={styles.transcriptList}>
          {segments.map((seg, i) => {
             const isActive = i === activeSegmentIndex;
             return (
                 <div 
                    key={seg.segment_id} 
                    className={`${styles.segmentCard} ${isActive ? styles.active : ''}`}
                    onClick={() => handleSeek(seg.start_sec)}
                 >
                     <div className={styles.segmentHeader}>
                        <span className={styles.speakerBadge}>{seg.speaker || "UNKNOWN"}</span>
                        <span className={styles.timestamp}>
                            {formatTime(seg.start_sec)} - {formatTime(seg.end_sec)}
                        </span>
                     </div>
                     <p className={styles.transcriptText}>
                         {seg.transcript || <span style={{ color: "var(--text-secondary)", fontStyle: "italic" }}>[No spoken audio detected]</span>}
                     </p>
                     
                     <div className={styles.emotionTags}>
                         {seg.emotions?.map((emotion: string, eIdx: number) => {
                             const isNegative = NEGATIVE_EMOTIONS.includes(emotion);
                             const isPositive = POSITIVE_EMOTIONS.includes(emotion);
                             let cls = styles.emotionTag;
                             if (isNegative) cls += ` ${styles.negative}`;
                             if (isPositive) cls += ` ${styles.positive}`;
                             
                             return (
                                 <span key={eIdx} className={cls}>
                                     {emotion}
                                 </span>
                             )
                         })}
                         {seg.captions && (
                             <span className={styles.emotionTag} style={{ background: "transparent", borderStyle: "dashed" }}>
                                 👁️ Visual Cue
                             </span>
                         )}
                     </div>
                 </div>
             )
          })}
        </div>
      </div>
    </div>
  );
}
