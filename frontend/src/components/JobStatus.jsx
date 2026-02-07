import { getDownloadUrl } from "../api/client";

const STATUS_CONFIG = {
  queued: { emoji: "⏳", label: "Queued", color: "#f59e0b" },
  processing: { emoji: "⚙️", label: "Processing", color: "#3b82f6" },
  done: { emoji: "✅", label: "Complete", color: "#10b981" },
  failed: { emoji: "❌", label: "Failed", color: "#ef4444" },
};

/**
 * Job status display with progress bar, logs, and download link.
 */
export default function JobStatus({ job, jobId }) {
  if (!job) return null;

  const cfg = STATUS_CONFIG[job.status] || STATUS_CONFIG.queued;
  const progress = job.progress || 0;

  return (
    <div className="job-status">
      {/* Status badge */}
      <div className="status-header">
        <span className="status-badge" style={{ borderColor: cfg.color }}>
          <span>{cfg.emoji}</span>
          <span style={{ color: cfg.color }}>{cfg.label}</span>
        </span>
        {jobId && <span className="job-id">Job: {jobId}</span>}
      </div>

      {/* Progress bar */}
      {(job.status === "processing" || job.status === "queued") && (
        <div className="progress-container">
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${progress}%`, backgroundColor: cfg.color }}
            />
          </div>
          <span className="progress-text">{progress}%</span>
        </div>
      )}

      {/* Logs */}
      {job.logs && (
        <div className="logs-container">
          <div className="logs-header">Pipeline Logs</div>
          <pre className="logs">{job.logs}</pre>
        </div>
      )}

      {/* Error */}
      {job.error && (
        <div className="error-container">
          <strong>Error:</strong> {job.error}
        </div>
      )}

      {/* Download */}
      {job.status === "done" && jobId && (
        <a
          className="download-btn"
          href={getDownloadUrl(jobId)}
          download
        >
          ⬇️ Download MP4
        </a>
      )}
    </div>
  );
}
