"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Send,
  Terminal,
  FileText,
  CheckCircle,
  Search,
  Activity,
  Play,
  X,
  Clock,
  User,
  ChevronDown,
  ChevronUp,
  Shield,
  Database,
  Eye,
  BookOpen,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import { queryApi } from "../../../lib/api";
import styles from "./query.module.css";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOP_SEGMENTS_DEFAULT = 5;

function formatTime(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function timeNow() {
  const d = new Date();
  return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}:${d.getSeconds().toString().padStart(2, "0")}`;
}

// Parse agent prefix from stage message
function parseAgent(text: string): {
  agent: string;
  arrow: string;
  rest: string;
} {
  const AGENTS = ["DETECTIVE", "RETRIEVER", "VERIFIER", "SCRIBE"];
  for (const agent of AGENTS) {
    const arrowMatch = text.match(new RegExp(`^(${agent})→(\\w+):\\s*(.*)`));
    if (arrowMatch)
      return {
        agent: arrowMatch[1],
        arrow: arrowMatch[2],
        rest: arrowMatch[3],
      };
    const match = text.match(new RegExp(`^${agent}:\\s*(.*)`));
    if (match) return { agent, arrow: "", rest: match[1] };
  }
  return { agent: "", arrow: "", rest: text };
}

const AGENT_COLORS: Record<string, string> = {
  DETECTIVE: "#818cf8", // indigo
  RETRIEVER: "#34d399", // emerald
  VERIFIER: "#fb923c", // orange
  SCRIBE: "#60a5fa", // blue
};

const AGENT_ICONS: Record<string, React.ReactNode> = {
  DETECTIVE: <Eye size={11} />,
  RETRIEVER: <Database size={11} />,
  VERIFIER: <Shield size={11} />,
  SCRIBE: <BookOpen size={11} />,
};

interface EvidenceSegment {
  segment_id: string;
  transcript: string;
  start_sec: number;
  end_sec: number;
  speaker?: string;
  rerank_score?: number;
  rrf_score?: number;
}

interface LogEntry {
  id: string;
  time: string;
  text: string;
  active: boolean;
  isSystem?: boolean;
}

export default function QueryPage() {
  const params = useParams();
  const videoId = params.videoId as string;

  const [inputStr, setInputStr] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [finalReport, setFinalReport] = useState<string | null>(null);
  const [evidenceSegments, setEvidenceSegments] = useState<EvidenceSegment[]>(
    [],
  );
  const [confidence, setConfidence] = useState<number | null>(null);
  const [showAllSegments, setShowAllSegments] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Video modal state
  const [watchingSegment, setWatchingSegment] =
    useState<EvidenceSegment | null>(null);
  const modalVideoRef = useRef<HTMLVideoElement>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Escape closes modal
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === "Escape") setWatchingSegment(null);
  }, []);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);

  // When a segment is selected, seek the video to start_sec
  useEffect(() => {
    if (watchingSegment && modalVideoRef.current) {
      const video = modalVideoRef.current;
      const seekAndPlay = () => {
        video.currentTime = watchingSegment.start_sec;
        video.play().catch(() => {});
      };
      if (video.readyState >= 1) {
        seekAndPlay();
      } else {
        video.addEventListener("loadedmetadata", seekAndPlay, { once: true });
      }
    }
  }, [watchingSegment]);

  const addLog = (text: string, active = false, isSystem = false) => {
    setLogs((prev) => {
      const newLogs = prev.map((l) => ({ ...l, active: false }));
      return [
        ...newLogs,
        {
          id: Math.random().toString(),
          time: timeNow(),
          text,
          active,
          isSystem,
        },
      ];
    });
  };

  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputStr.trim() || isProcessing) return;

    const q = inputStr;
    setInputStr("");
    setIsProcessing(true);
    setError(null);
    setFinalReport(null);
    setEvidenceSegments([]);
    setConfidence(null);
    setShowAllSegments(false);
    setLogs([]);

    addLog(`TARGET: ${videoId}`, false, true);
    addLog(`QUERY: "${q}"`, false, true);
    addLog("DETECTIVE: Received query. Decomposing into sub-tasks...", true);

    try {
      const { query_id } = await queryApi.submit(q, videoId);

      let lastStage = "";
      const result = await queryApi.pollResult(query_id, (_prog, stage) => {
        if (stage && stage !== lastStage) {
          addLog(stage, true);
          lastStage = stage;
        }
      });

      addLog(
        "SCRIBE: Intelligence report compiled. Transmission complete.",
        false,
      );
      addLog("STATUS: Multi-agent analysis finished", false, true);

      setFinalReport(result.result?.final_report || "No report generated.");
      setEvidenceSegments(result.result?.evidence_segments || []);
      setConfidence(result.result?.metadata?.confidence_score ?? null);
    } catch (err: any) {
      addLog(`ERROR: ${err.message}`, false, true);
      setError(err.message);
    } finally {
      setIsProcessing(false);
      setLogs((prev) => prev.map((l) => ({ ...l, active: false })));
    }
  };

  const displayedSegments = showAllSegments
    ? evidenceSegments
    : evidenceSegments.slice(0, TOP_SEGMENTS_DEFAULT);

  return (
    <div className={styles.container}>
      {/* SIDEBAR: Terminal Console */}
      <div className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <Link href={`/analyze/${videoId}`} className={styles.backLink}>
            <ArrowLeft size={16} /> Analysis Timeline
          </Link>
          <div
            style={{
              fontSize: "1.1rem",
              fontWeight: 500,
              color: "var(--text-primary)",
            }}
          >
            Forensic Query Terminal
          </div>
          <div
            style={{
              fontSize: "0.8rem",
              color: "var(--text-secondary)",
              fontFamily: "var(--font-mono)",
              marginTop: "4px",
            }}
          >
            TARGET_ID: {videoId}
          </div>
        </div>

        <div className={styles.terminal}>
          <div className={styles.terminalHeader}>
            <Terminal size={14} />
            <span>Multi-Agent Event Stream</span>
            <div className={styles.agentLegend}>
              {Object.entries(AGENT_COLORS).map(([name, color]) => (
                <span
                  key={name}
                  className={styles.legendDot}
                  style={{ color }}
                  title={name}
                >
                  {AGENT_ICONS[name]} {name.slice(0, 3)}
                </span>
              ))}
            </div>
          </div>
          <div className={styles.terminalBody}>
            {logs.length === 0 && (
              <div style={{ color: "var(--text-secondary)", opacity: 0.5 }}>
                System idle. Awaiting user input...
              </div>
            )}
            {logs.map((log) => {
              const { agent, arrow, rest } = parseAgent(log.text);
              const color = agent ? AGENT_COLORS[agent] : undefined;
              return (
                <div
                  key={log.id}
                  className={`${styles.logEntry} ${log.active ? styles.active : ""} ${log.isSystem ? styles.system : ""}`}
                >
                  <span className={styles.logTime}>[{log.time}]</span>
                  {agent ? (
                    <span className={styles.logContent}>
                      <span
                        className={styles.agentBadge}
                        style={{ color, borderColor: color }}
                      >
                        {AGENT_ICONS[agent]} {agent}
                      </span>
                      {arrow && (
                        <>
                          <span className={styles.arrowSep}>→</span>
                          <span
                            className={styles.agentBadge}
                            style={{
                              color: AGENT_COLORS[arrow],
                              borderColor: AGENT_COLORS[arrow],
                            }}
                          >
                            {AGENT_ICONS[arrow]} {arrow}
                          </span>
                        </>
                      )}
                      <span className={styles.logText}>{rest}</span>
                    </span>
                  ) : (
                    <span className={styles.logText}>{log.text}</span>
                  )}
                </div>
              );
            })}
            <div ref={logsEndRef} />
          </div>
        </div>

        <form className={styles.queryInputBox} onSubmit={handleQuery}>
          <input
            className={styles.input}
            placeholder="e.g., How many voices were heard?"
            value={inputStr}
            onChange={(e) => setInputStr(e.target.value)}
            disabled={isProcessing}
          />
          <button
            type="submit"
            className={styles.submitBtn}
            disabled={isProcessing || !inputStr.trim()}
          >
            <Send size={18} />
          </button>
        </form>
      </div>

      {/* MAIN AREA: Report + Evidence */}
      <div className={styles.reportArea}>
        <div className={styles.reportContent}>
          {!finalReport && !isProcessing && !error && (
            <div className={styles.emptyState}>
              <Search size={48} opacity={0.3} />
              <div>Ask a question to generate a forensic report.</div>
            </div>
          )}

          {isProcessing && !finalReport && (
            <div className={styles.emptyState}>
              <Activity size={48} color="var(--accent-color)" opacity={0.8} />
              <div
                style={{
                  color: "var(--accent-color)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                Multi-agent analysis in progress...
              </div>
            </div>
          )}

          {error && (
            <div className={styles.emptyState}>
              <div style={{ color: "var(--error-color)" }}>
                Query Failed: {error}
              </div>
            </div>
          )}

          {finalReport && (
            <div>
              {/* ── Report Header ── */}
              <div className={styles.reportHeader}>
                <CheckCircle size={28} color="var(--success-color)" />
                <div style={{ flex: 1 }}>
                  <h2
                    style={{ margin: 0, fontSize: "1.4rem", fontWeight: 500 }}
                  >
                    Verified Intelligence Report
                  </h2>
                  <div
                    style={{
                      color: "var(--text-secondary)",
                      fontSize: "0.85rem",
                      marginTop: "4px",
                    }}
                  >
                    Generated by Videntia Multi-Agent Engine
                  </div>
                </div>
                {confidence !== null && (
                  <div
                    className={styles.confidenceBadge}
                    title="Agent confidence score"
                  >
                    <div className={styles.confLabel}>CONFIDENCE</div>
                    <div
                      className={styles.confValue}
                      style={{
                        color:
                          confidence >= 0.6
                            ? "var(--success-color)"
                            : confidence >= 0.3
                              ? "#fb923c"
                              : "var(--error-color)",
                      }}
                    >
                      {(confidence * 100).toFixed(0)}%
                    </div>
                  </div>
                )}
              </div>

              {/* ── Markdown Report ── */}
              <div className={styles.markdown}>
                <ReactMarkdown>{finalReport}</ReactMarkdown>
              </div>

              {/* ── Evidence Segments (below report) ── */}
              {evidenceSegments.length > 0 && (
                <div className={styles.evidenceSection}>
                  <div className={styles.evidenceSectionHeader}>
                    <h3 className={styles.evidenceTitle}>
                      <Play size={14} />
                      Evidence Segments
                      <span className={styles.evidenceCount}>
                        {evidenceSegments.length}
                      </span>
                    </h3>
                    <div
                      style={{
                        fontSize: "0.8rem",
                        color: "var(--text-secondary)",
                      }}
                    >
                      {evidenceSegments.length > TOP_SEGMENTS_DEFAULT &&
                      !showAllSegments
                        ? `Showing top ${TOP_SEGMENTS_DEFAULT} — `
                        : ""}
                      {evidenceSegments.length > TOP_SEGMENTS_DEFAULT && (
                        <button
                          className={styles.showMoreBtn}
                          onClick={() => setShowAllSegments((v) => !v)}
                        >
                          {showAllSegments ? (
                            <>
                              <ChevronUp size={13} /> Show less
                            </>
                          ) : (
                            <>
                              <ChevronDown size={13} /> Show all{" "}
                              {evidenceSegments.length}
                            </>
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                  <div className={styles.evidenceGrid}>
                    {displayedSegments.map((seg, idx) => (
                      <div
                        key={seg.segment_id || idx}
                        className={styles.evidenceCard}
                      >
                        <div className={styles.evidenceCardHeader}>
                          <div className={styles.evidenceMeta}>
                            <span className={styles.evidenceTimestamp}>
                              <Clock size={11} />
                              {formatTime(seg.start_sec)} –{" "}
                              {formatTime(seg.end_sec)}
                            </span>
                            {seg.speaker && (
                              <span className={styles.evidenceSpeaker}>
                                <User size={11} />
                                {seg.speaker}
                              </span>
                            )}
                          </div>
                          <button
                            className={styles.watchBtn}
                            onClick={() => setWatchingSegment(seg)}
                            title={`Watch from ${formatTime(seg.start_sec)}`}
                          >
                            <Play size={12} />
                            Watch
                          </button>
                        </div>
                        <p className={styles.evidenceTranscript}>
                          {seg.transcript || (
                            <em style={{ opacity: 0.5 }}>[No transcript]</em>
                          )}
                        </p>
                        {seg.rerank_score != null && (
                          <div className={styles.evidenceScore}>
                            <div
                              className={styles.scoreBar}
                              style={{
                                width: `${Math.min(100, seg.rerank_score * 100)}%`,
                              }}
                            />
                            <span>
                              relevance{" "}
                              {Math.min(
                                100,
                                Math.round(seg.rerank_score * 100),
                              )}
                              %
                            </span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div
                style={{
                  marginTop: "40px",
                  paddingTop: "24px",
                  borderTop: "1px solid var(--border-color)",
                  display: "flex",
                  gap: "16px",
                }}
              >
                <Link
                  href={`/analyze/${videoId}`}
                  style={{
                    padding: "10px 16px",
                    background: "var(--surface-color)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "4px",
                    color: "var(--text-primary)",
                    fontSize: "0.9rem",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <FileText size={16} /> Open Timeline
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Watch Segment Modal ── */}
      {watchingSegment && (
        <div
          className={styles.modalOverlay}
          onClick={() => setWatchingSegment(null)}
        >
          <div className={styles.modalBox} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <div>
                <div className={styles.modalTitle}>Evidence Segment</div>
                <div className={styles.modalMeta}>
                  <Clock size={12} />
                  {formatTime(watchingSegment.start_sec)} –{" "}
                  {formatTime(watchingSegment.end_sec)}
                  {watchingSegment.speaker && (
                    <>
                      <User size={12} /> {watchingSegment.speaker}
                    </>
                  )}
                  <span style={{ opacity: 0.5, marginLeft: 4 }}>
                    · Press Esc to close
                  </span>
                </div>
              </div>
              <button
                className={styles.modalClose}
                onClick={() => setWatchingSegment(null)}
              >
                <X size={20} />
              </button>
            </div>

            <video
              ref={modalVideoRef}
              controls
              className={styles.modalVideo}
              src={`${API_BASE}/api/videos/${videoId}/stream`}
            />

            <div className={styles.modalTranscript}>
              <span
                style={{
                  color: "var(--text-secondary)",
                  fontSize: "0.75rem",
                  fontFamily: "var(--font-mono)",
                  textTransform: "uppercase",
                }}
              >
                Transcript
              </span>
              <p style={{ margin: "8px 0 0" }}>
                {watchingSegment.transcript || "[No transcript]"}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
