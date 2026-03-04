"use client";

import React, { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { queryApi } from "@/lib/api";

export default function QueryPage() {
  const searchParams = useSearchParams();
  const videoId = searchParams.get("video");

  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [queryProgress, setQueryProgress] = useState(0);
  const [queryStage, setQueryStage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError("");
    setResult(null);
    setQueryProgress(0);
    setQueryStage("Submitting query");

    try {
      // Submit query
      const submission = await queryApi.submit(query, videoId || undefined);
      setQueryProgress(submission.progress ?? 5);
      setQueryStage(submission.stage ?? "Queued");

      // Poll for result
      const finalResult = await queryApi.pollResult(
        submission.query_id,
        (progress, stage) => {
          setQueryProgress(Math.round(progress));
          setQueryStage(stage);
        },
      );
      setResult(finalResult);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1>🔍 Ask Questions</h1>
        <p>Query video content with RAG + Multi-Agent AI</p>
      </header>

      <main style={styles.main}>
        <form onSubmit={handleSubmit} style={styles.form}>
          <input
            type="text"
            placeholder="What do you want to know about the video?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={loading}
            style={styles.input}
          />
          <button type="submit" disabled={loading} style={styles.button}>
            {loading ? "🔄 Analyzing..." : "📤 Submit Query"}
          </button>
        </form>

        {loading && (
          <div style={styles.progressContainer}>
            <div style={styles.progressBar}>
              <div
                style={{ ...styles.progressFill, width: `${queryProgress}%` }}
              />
            </div>
            <p style={styles.progressText}>
              {queryProgress}% - {queryStage || "Analyzing"}
            </p>
          </div>
        )}

        {error && <div style={styles.error}>❌ Error: {error}</div>}

        {result && (
          <div style={styles.resultContainer}>
            <h2>📝 Analysis Result</h2>

            <section style={styles.section}>
              <h3>Report</h3>
              <div style={styles.reportText}>
                {result.result?.final_report || result.final_report || (
                  <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.9em" }}>
                    {JSON.stringify(result, null, 2)}
                  </pre>
                )}
              </div>
            </section>

            {result.result?.evidence_segments &&
              result.result.evidence_segments.length > 0 && (
                <section style={styles.section}>
                  <h3>📌 Evidence Segments</h3>
                  {result.result.evidence_segments.map(
                    (seg: any, idx: number) => (
                      <div key={idx} style={styles.segment}>
                        <div style={styles.segmentHeader}>
                          <strong>{seg.segment_id}</strong>
                          {seg.speaker && (
                            <span style={styles.speaker}>{seg.speaker}</span>
                          )}
                          <span style={styles.timestamp}>{seg.timestamp}</span>
                        </div>
                        <p>{seg.text}</p>
                        {seg.emotions && seg.emotions.length > 0 && (
                          <div style={styles.emotions}>
                            {seg.emotions.map((em: string) => (
                              <span key={em} style={styles.emotion}>
                                {em}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ),
                  )}
                </section>
              )}

            {result.result?.metadata && (
              <section style={styles.section}>
                <h3>📊 Metadata</h3>
                <div style={styles.metadata}>
                  <p>
                    <strong>Evidence Segments:</strong>{" "}
                    {result.result.metadata.evidence_count}
                  </p>
                  <p>
                    <strong>Iterations:</strong>{" "}
                    {result.result.metadata.iterations}
                  </p>
                  <p>
                    <strong>Timestamp:</strong>{" "}
                    {new Date(
                      result.result.metadata.timestamp,
                    ).toLocaleString()}
                  </p>
                </div>
              </section>
            )}
          </div>
        )}
      </main>

      <a href="/" style={styles.backLink}>
        ← Back to Home
      </a>
    </div>
  );
}

const styles = {
  reportText: {
    whiteSpace: "pre-wrap" as const,
    lineHeight: 1.6,
  } as React.CSSProperties,

  container: {
    minHeight: "100vh",
    background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    padding: "20px",
  } as React.CSSProperties,

  header: {
    textAlign: "center" as const,
    color: "white",
    marginBottom: "40px",
    marginTop: "20px",
  } as React.CSSProperties,

  main: {
    maxWidth: "900px",
    margin: "0 auto",
  } as React.CSSProperties,

  form: {
    background: "white",
    padding: "20px",
    borderRadius: "12px",
    marginBottom: "20px",
    display: "flex",
    gap: "10px",
    boxShadow: "0 10px 40px rgba(0, 0, 0, 0.1)",
  } as React.CSSProperties,

  input: {
    flex: 1,
    padding: "12px",
    border: "1px solid #ddd",
    borderRadius: "8px",
    fontSize: "1em",
  } as React.CSSProperties,

  button: {
    padding: "12px 24px",
    background: "#667eea",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    fontWeight: "bold",
  } as React.CSSProperties,

  progressContainer: {
    background: "white",
    padding: "16px",
    borderRadius: "12px",
    marginBottom: "20px",
    boxShadow: "0 10px 40px rgba(0, 0, 0, 0.1)",
  } as React.CSSProperties,

  progressBar: {
    width: "100%",
    height: "16px",
    background: "#e5e7eb",
    borderRadius: "10px",
    overflow: "hidden",
  } as React.CSSProperties,

  progressFill: {
    height: "100%",
    background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    transition: "width 0.4s ease",
  } as React.CSSProperties,

  progressText: {
    marginTop: "10px",
    color: "#4b5563",
    fontWeight: "bold",
  } as React.CSSProperties,

  error: {
    background: "#fee",
    color: "#c00",
    padding: "15px",
    borderRadius: "8px",
    marginBottom: "20px",
  } as React.CSSProperties,

  resultContainer: {
    background: "white",
    padding: "30px",
    borderRadius: "12px",
    boxShadow: "0 10px 40px rgba(0, 0, 0, 0.1)",
  } as React.CSSProperties,

  section: {
    marginBottom: "30px",
    paddingBottom: "20px",
    borderBottom: "1px solid #eee",
  } as React.CSSProperties,

  segment: {
    background: "#f8f9ff",
    padding: "15px",
    borderRadius: "8px",
    marginBottom: "15px",
    borderLeft: "4px solid #667eea",
  } as React.CSSProperties,

  segmentHeader: {
    display: "flex",
    gap: "10px",
    marginBottom: "10px",
    alignItems: "center",
  } as React.CSSProperties,

  speaker: {
    background: "#667eea",
    color: "white",
    padding: "4px 12px",
    borderRadius: "12px",
    fontSize: "0.9em",
  } as React.CSSProperties,

  timestamp: {
    color: "#999",
    fontSize: "0.9em",
  } as React.CSSProperties,

  emotions: {
    display: "flex",
    gap: "8px",
    marginTop: "10px",
    flexWrap: "wrap" as const,
  } as React.CSSProperties,

  emotion: {
    background: "#ffd700",
    color: "#333",
    padding: "4px 10px",
    borderRadius: "12px",
    fontSize: "0.85em",
  } as React.CSSProperties,

  metadata: {
    background: "#f0f0f0",
    padding: "15px",
    borderRadius: "8px",
  } as React.CSSProperties,

  backLink: {
    display: "inline-block",
    marginTop: "20px",
    color: "white",
    textDecoration: "none",
    fontSize: "1.1em",
  } as React.CSSProperties,
};
