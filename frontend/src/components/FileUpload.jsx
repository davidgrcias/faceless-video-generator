import { useCallback, useRef, useState } from "react";

/**
 * Drag-and-drop + click-to-browse file upload component.
 */
export default function FileUpload({ file, onSelect, disabled }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDragging(false);
      if (disabled) return;
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile) onSelect(droppedFile);
    },
    [disabled, onSelect]
  );

  const handleDragOver = useCallback(
    (e) => {
      e.preventDefault();
      if (!disabled) setDragging(true);
    },
    [disabled]
  );

  const handleDragLeave = useCallback(() => setDragging(false), []);

  const handleClick = useCallback(() => {
    if (!disabled) inputRef.current?.click();
  }, [disabled]);

  const handleChange = useCallback(
    (e) => {
      const selected = e.target.files[0];
      if (selected) onSelect(selected);
    },
    [onSelect]
  );

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div
      className={`upload-zone ${dragging ? "dragging" : ""} ${file ? "has-file" : ""} ${disabled ? "disabled" : ""}`}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onClick={handleClick}
    >
      <input
        ref={inputRef}
        type="file"
        accept="audio/*,.mp3,.wav,.m4a,.ogg,.flac,.aac"
        onChange={handleChange}
        hidden
      />

      {file ? (
        <div className="file-info">
          <span className="file-icon">🎵</span>
          <div className="file-details">
            <span className="file-name">{file.name}</span>
            <span className="file-size">{formatSize(file.size)}</span>
          </div>
        </div>
      ) : (
        <div className="upload-placeholder">
          <span className="upload-icon">📁</span>
          <p className="upload-text">
            Drop your audio file here, or <span className="link">browse</span>
          </p>
          <p className="upload-hint">MP3, WAV, M4A, OGG, FLAC, AAC — max 50 MB</p>
        </div>
      )}
    </div>
  );
}
