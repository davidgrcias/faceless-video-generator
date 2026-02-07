/**
 * Generate Video button with loading state.
 */
export default function GenerateButton({ onClick, disabled, uploading }) {
  return (
    <button
      className="generate-btn"
      onClick={onClick}
      disabled={disabled}
    >
      {uploading ? (
        <>
          <span className="spinner" />
          Uploading…
        </>
      ) : (
        <>🎬 Generate Video</>
      )}
    </button>
  );
}
