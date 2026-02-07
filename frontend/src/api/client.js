const API_BASE = "/api";

/**
 * Upload an MP3 file and create a new job.
 * @param {File} file
 * @returns {Promise<{job_id: string, status: string, message: string}>}
 */
export async function uploadAudio(file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/jobs/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Upload failed");
  }

  return res.json();
}

/**
 * Get the current status of a job.
 * @param {string} jobId
 * @returns {Promise<Object>}
 */
export async function getJobStatus(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to fetch status");
  }
  return res.json();
}

/**
 * Get the download URL for a completed job.
 * @param {string} jobId
 * @returns {string}
 */
export function getDownloadUrl(jobId) {
  return `${API_BASE}/jobs/${jobId}/download`;
}
