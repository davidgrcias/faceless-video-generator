import FileUpload from "./components/FileUpload";
import GenerateButton from "./components/GenerateButton";
import JobStatus from "./components/JobStatus";
import { useJob } from "./hooks/useJob";

export default function App() {
  const { file, jobId, job, uploading, error, selectFile, generate, reset } =
    useJob();

  const isProcessing =
    job && (job.status === "queued" || job.status === "processing");
  const isDone = job && job.status === "done";
  const canGenerate = !!file && !uploading && !isProcessing;

  return (
    <div className="app">
      <header className="header">
        <h1>
          <span className="logo">🎬</span> Faceless Video Generator
        </h1>
        <p className="subtitle">
          Upload an MP3 voice-over and generate a video with burned-in subtitles
        </p>
      </header>

      <main className="main">
        <div className="card">
          {/* Step 1: Upload */}
          <div className="step">
            <div className="step-label">
              <span className="step-number">1</span> Upload Audio
            </div>
            <FileUpload
              file={file}
              onSelect={selectFile}
              disabled={uploading || isProcessing}
            />
          </div>

          {/* Step 2: Generate */}
          <div className="step">
            <div className="step-label">
              <span className="step-number">2</span> Generate Video
            </div>
            <GenerateButton
              onClick={generate}
              disabled={!canGenerate}
              uploading={uploading}
            />
          </div>

          {/* Upload error */}
          {error && (
            <div className="error-container">
              <strong>Upload Error:</strong> {error}
            </div>
          )}

          {/* Step 3: Status & Download */}
          {job && (
            <div className="step">
              <div className="step-label">
                <span className="step-number">3</span>{" "}
                {isDone ? "Download" : "Status"}
              </div>
              <JobStatus job={job} jobId={jobId} />
            </div>
          )}

          {/* Reset button */}
          {(isDone || (job && job.status === "failed")) && (
            <button className="reset-btn" onClick={reset}>
              ↩️ Generate Another
            </button>
          )}
        </div>
      </main>

      <footer className="footer">
        Faceless Video Generator — MVP
      </footer>
    </div>
  );
}
