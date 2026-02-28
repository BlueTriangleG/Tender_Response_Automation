import { useRef } from "react";
import type { DragEvent } from "react";

type UploadDropzoneProps = {
  accept?: string;
  browseLabel?: string;
  dragActiveTitle?: string;
  fileName: string | null;
  inputId: string;
  isDragActive: boolean;
  label: string;
  idleTitle?: string;
  onDragEnter: (event: DragEvent<HTMLDivElement>) => void;
  onDragLeave: (event: DragEvent<HTMLDivElement>) => void;
  onDragOver: (event: DragEvent<HTMLDivElement>) => void;
  onDrop: (event: DragEvent<HTMLDivElement>) => void;
  onFileChange: (file: File | null) => void;
  supportLabel?: string;
  caption?: string;
};

export function UploadDropzone({
  accept = ".csv",
  browseLabel = "Browse csv",
  caption = "Stage one tender questionnaire, then send it to the FastAPI workflow for autofill generation.",
  dragActiveTitle = "Drop csv to queue this run",
  fileName,
  inputId,
  isDragActive,
  idleTitle = "Drag your tender csv here or browse from disk",
  label,
  onDragEnter,
  onDragLeave,
  onDragOver,
  onDrop,
  onFileChange,
  supportLabel = "Supports .csv only",
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
        {isDragActive ? dragActiveTitle : idleTitle}
      </p>

      <div className="dropzone__actions">
        <button
          className="secondary-button secondary-button--strong"
          type="button"
          onClick={() => inputRef.current?.click()}
        >
          {browseLabel}
        </button>
        <span className="dropzone__meta">{supportLabel}</span>
      </div>

      <input
        ref={inputRef}
        id={inputId}
        name={inputId}
        className="sr-only"
        type="file"
        accept={accept}
        onChange={(event) => onFileChange(event.target.files?.item(0) ?? null)}
      />

      <p className="dropzone__caption">
        {isDragActive ? "Release to stage the file for processing." : caption}
      </p>

      {fileName ? <p className="selected-file">Selected file: {fileName}</p> : null}
    </div>
  );
}
