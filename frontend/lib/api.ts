// lib/api.ts
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const videosApi = {
  upload: async (
    file: File,
    processingMode: "fast" | "balanced" | "full" = "fast",
  ) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("processing_mode", processingMode);
    const res = await fetch(`${API_BASE}/api/videos/upload`, {
      method: "POST",
      body: formData,
    });
    return res.json();
  },

  getUploadStatus: async (taskId: string) => {
    const res = await fetch(`${API_BASE}/api/videos/upload/${taskId}/status`);
    return res.json();
  },

  pollUploadStatus: async (
    taskId: string,
    onProgress?: (progress: number, stage: string) => void,
    maxWait: number = 900000, // 15 minutes
  ) => {
    const startTime = Date.now();
    const pollInterval = 1000; // 1 second

    while (Date.now() - startTime < maxWait) {
      const data = await videosApi.getUploadStatus(taskId);

      // Update progress callback
      if (onProgress) {
        onProgress(data.progress, data.stage);
      }

      if (data.status === "complete") {
        return data;
      }

      if (data.status === "failed") {
        throw new Error(data.error || "Upload processing failed");
      }

      await new Promise((resolve) => setTimeout(resolve, pollInterval));
    }

    throw new Error("Upload processing timeout");
  },

  list: async () => {
    const res = await fetch(`${API_BASE}/api/videos`);
    return res.json();
  },

  getSegments: async (videoId: string) => {
    const res = await fetch(`${API_BASE}/api/videos/${videoId}/segments`);
    return res.json();
  },

  getSpeakers: async (videoId: string) => {
    const res = await fetch(`${API_BASE}/api/videos/${videoId}/speakers`);
    return res.json();
  },

  getEmotions: async (videoId: string) => {
    const res = await fetch(`${API_BASE}/api/videos/${videoId}/emotions`);
    return res.json();
  },
};

export const queryApi = {
  submit: async (
    query: string,
    videoId?: string,
    maxIterations: number = 5,
  ) => {
    const res = await fetch(`${API_BASE}/api/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        video_id: videoId,
        max_iterations: maxIterations,
      }),
    });
    return res.json();
  },

  getResult: async (queryId: string) => {
    const res = await fetch(`${API_BASE}/api/query/${queryId}`);
    return res.json();
  },

  pollResult: async (
    queryId: string,
    onProgress?: (progress: number, stage: string) => void,
    maxWait: number = 300000,
  ) => {
    const startTime = Date.now();
    const pollInterval = 1000; // 1 second

    while (Date.now() - startTime < maxWait) {
      const data = await queryApi.getResult(queryId);

      if (onProgress) {
        onProgress(
          data.progress ?? 0,
          data.stage ?? data.status ?? "Processing",
        );
      }

      if (data.status === "complete" || data.status === "failed") {
        return data;
      }

      await new Promise((resolve) => setTimeout(resolve, pollInterval));
    }

    throw new Error("Query timeout");
  },
};
