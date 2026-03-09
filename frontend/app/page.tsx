"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  Upload,
  FileVideo,
  HardDrive,
  TerminalSquare,
  Activity,
  ChevronRight,
} from "lucide-react";
import { videosApi } from "../lib/api";
import styles from "./page.module.css";

export default function Home() {
  const [uploading, setUploading] = useState(false);
  const [selectedVideo, setSelectedVideo] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [processingMode, setProcessingMode] = useState<
    "fast" | "balanced" | "full"
  >("balanced");

  const [existingVideos, setExistingVideos] = useState<any[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const saved = localStorage.getItem("lastVideoId");
    if (saved) {
      setSelectedVideo(saved);
    }

    fetch("http://localhost:8000/api/videos")
      .then((res) => res.json())
      .then((data) => {
        if (data.videos) {
          setExistingVideos(data.videos);
        }
      })
      .catch((err) => console.error("Failed to load existing videos", err));
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setProgress(0);
    setStage("Uploading file...");
    setError(null);
    setSelectedVideo(null);

    try {
      const uploadResult = await videosApi.upload(file, processingMode);
      const taskId = uploadResult.task_id;
      const videoId = uploadResult.video_id;

      await videosApi.pollUploadStatus(taskId, (prog, stg) => {
        setProgress(Math.round(prog));
        setStage(stg);
      });

      setSelectedVideo(videoId);
      localStorage.setItem("lastVideoId", videoId);
      setProgress(100);
      setStage("Complete!");

      // Refresh list
      setExistingVideos((prev) => [
        {
          video_id: videoId,
          filename: file.name,
          segments: 0,
          uploaded_at: "Just now",
        },
        ...prev,
      ]);
    } catch (err) {
      setError((err as Error).message);
      setStage("Failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1>Ingestion & Indexing</h1>
        <p>Upload new evidence or select from the secure project enclosure.</p>
      </header>

      <div className={styles.grid}>
        {/* Left Column: Upload New */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <Upload size={20} />
            <h2 className={styles.cardTitle}>Upload New Evidence</h2>
          </div>

          <label className={styles.label}>Processing Strategy</label>
          <select
            value={processingMode}
            onChange={(e) =>
              setProcessingMode(e.target.value as "fast" | "balanced" | "full")
            }
            disabled={uploading}
            className={styles.select}
          >
            <option value="fast">
              Fast (No Speaker Diarization / No Visual Emotion)
            </option>
            <option value="balanced">
              Balanced (Speaker Auth + Transcript Emotions)
            </option>
            <option value="full">
              Full Forensics (Deep Visual Emotion + Speaker + Transcript)
            </option>
          </select>

          <div
            className={styles.uploadBox}
            onClick={() => !uploading && fileInputRef.current?.click()}
          >
            <Upload className={styles.uploadIcon} size={32} />
            <p className={styles.uploadText}>
              Drop video file here or click to browse
            </p>
            <button
              className={styles.button}
              disabled={uploading}
              type="button"
            >
              Select Video
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              onChange={handleFileUpload}
              disabled={uploading}
              className={styles.fileInput}
            />
          </div>

          {uploading && (
            <div className={styles.progressContainer}>
              <div className={styles.progressBar}>
                <div
                  className={styles.progressFill}
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className={styles.progressText}>
                <span>{stage}</span>
                <span>{progress}%</span>
              </div>
            </div>
          )}

          {error && <div className={styles.error}>{error}</div>}
        </div>

        {/* Right Column: Existing Videos & Actions */}
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <HardDrive size={20} />
              <h2 className={styles.cardTitle}>Project Enclosure</h2>
            </div>

            {existingVideos.length > 0 ? (
              <div className={styles.videoList}>
                {existingVideos.map((v) => (
                  <div
                    key={v.video_id}
                    className={`${styles.videoItem} ${selectedVideo === v.video_id ? styles.selected : ""}`}
                    onClick={() => {
                      setSelectedVideo(v.video_id);
                      localStorage.setItem("lastVideoId", v.video_id);
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div className={styles.videoName} title={v.filename}>
                        {v.filename}
                      </div>
                      <div className={styles.videoMeta} title={v.video_id}>
                        <FileVideo size={14} />{" "}
                        {v.video_id
                          .replace(/^[0-9a-f]{8}_[0-9a-f]{8}_/, "")
                          .replace(/_/g, " ")}
                      </div>
                    </div>
                    {v.segments > 0 && (
                      <span className={styles.badge}>
                        {v.segments} segments
                      </span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                No videos found in the current project enclosure.
              </p>
            )}
          </div>

          {/* Actions Card */}
          <div className={styles.card} style={{ flex: 1 }}>
            <div className={styles.cardHeader}>
              <Activity size={20} />
              <h2 className={styles.cardTitle}>Action Deployment</h2>
            </div>

            <p
              style={{
                color: "var(--text-secondary)",
                fontSize: "0.9rem",
                marginBottom: "24px",
              }}
            >
              {selectedVideo
                ? `Target locked: ${selectedVideo}. Deploy agents or review base analytics.`
                : "Select or upload a video to access analysis actions."}
            </p>

            <div className={styles.grid}>
              {selectedVideo ? (
                <Link
                  href={`/query/${selectedVideo}`}
                  className={styles.buttonPrimary}
                >
                  <TerminalSquare size={16} /> Deploy Agents
                </Link>
              ) : (
                <span className={`${styles.buttonPrimary} ${styles.disabled}`}>
                  <TerminalSquare size={16} /> Deploy Agents
                </span>
              )}

              {selectedVideo ? (
                <Link
                  href={`/analyze/${selectedVideo}`}
                  className={styles.buttonSecondary}
                >
                  <Activity size={16} /> Review Timeline
                </Link>
              ) : (
                <span
                  className={`${styles.buttonSecondary} ${styles.disabled}`}
                >
                  <Activity size={16} /> Review Timeline
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
