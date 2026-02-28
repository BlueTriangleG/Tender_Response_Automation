import { useRef } from "react";
import type { DragEvent } from "react";

type UploadDropzoneProps = {
  fileName: string | null;
  inputId: string;
  isDragActive: boolean;
  label: string;
  onDragEnter: (event: DragEvent<HTMLDivElement>) => void;
  onDragLeave: (event: DragEvent<HTMLDivElement>) => void;
  onDragOver: (event: DragEvent<HTMLDivElement>) => void;
  onDrop: (event: DragEvent<HTMLDivElement>) => void;
  onFileChange: (file: File | null) => void;
};

export function UploadDropzone({
  fileName,
  inputId,
  isDragActive,
  label,
  onDragEnter,
  onDragLeave,
  onDragOver,
  onDrop,
  onFileChange,
}: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  return (
    <div
      className={isDragActive ? "dropzone dropzone--active" : "dropzone"}
      onDragEnter={onDragEnter}
      onDragLeave={onDragLeave}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <label className="dropzone__label" htmlFor={inputId}>
        {label}
      </label>
      <p className="dropzone__title">
        {isDragActive
          ? "Drop workbook to queue this run"
          : "Drag your workbook here or browse from disk"}
      </p>

      <div className="dropzone__actions">
        <button
          className="secondary-button secondary-button--strong"
          type="button"
          onClick={() => inputRef.current?.click()}
        >
          Browse workbook
        </button>
        <span className="dropzone__meta">Supports .xlsx, .xls, and .csv</span>
      </div>

      <input
        ref={inputRef}
        id={inputId}
        name={inputId}
        className="sr-only"
        type="file"
        accept=".xlsx,.xls,.csv"
        onChange={(event) => onFileChange(event.target.files?.item(0) ?? null)}
      />

      <p className="dropzone__caption">
        {isDragActive
          ? "Release to stage the workbook for processing."
          : "Built for interview demos, but wired like a real batch intake surface."}
      </p>

      {fileName ? <p className="selected-file">Selected file: {fileName}</p> : null}
    </div>
  );
}
