import { useCallback, useEffect, useRef, useState } from "react";
import { getJobStatus, uploadAudio } from "../api/client";

/**
 * Custom hook encapsulating the full upload → poll → done lifecycle.
 */
export function useJob() {
  const [file, setFile] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  // Clean up polling on unmount
  useEffect(() => () => clearInterval(pollRef.current), []);

  /** Start polling for job status. */
  const startPolling = useCallback((id) => {
    // Clear any existing interval
    if (pollRef.current) clearInterval(pollRef.current);

    const poll = async () => {
      try {
        const data = await getJobStatus(id);
        setJob(data);
        if (data.status === "done" || data.status === "failed") {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    };

    // Immediate first poll
    poll();
    pollRef.current = setInterval(poll, 1500);
  }, []);

  /** Handle file selection. */
  const selectFile = useCallback((f) => {
    setFile(f);
    setJobId(null);
    setJob(null);
    setError(null);
  }, []);

  /** Upload the file and start the pipeline. */
  const generate = useCallback(async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    setJob(null);
    setJobId(null);

    try {
      const result = await uploadAudio(file);
      setJobId(result.job_id);
      setJob({ status: result.status, progress: 0, logs: "" });
      startPolling(result.job_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }, [file, startPolling]);

  /** Reset to initial state. */
  const reset = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    setFile(null);
    setJobId(null);
    setJob(null);
    setUploading(false);
    setError(null);
  }, []);

  return { file, jobId, job, uploading, error, selectFile, generate, reset };
}
