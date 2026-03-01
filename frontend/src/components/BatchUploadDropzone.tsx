import { useRef, useState } from "react";
import type { DragEvent } from "react";

type BatchUploadDropzoneProps = {
  inputId: string;
  label: string;
  onFilesChange: (files: File[]) => void;
};

export function BatchUploadDropzone({
  inputId,
  label,
  onFilesChange,
}: BatchUploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isDragActive, setIsDragActive] = useState(false);

  function applyFiles(list: FileList | File[] | null | undefined) {
    if (!list) {
      onFilesChange([]);
      setIsDragActive(false);
      return;
    }

    onFilesChange(Array.from(list));
    setIsDragActive(false);
  }

  function handleDragEnter(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragActive(true);
  }

  function handleDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  }

  function handleDragLeave(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();

    if (
      event.relatedTarget instanceof Node &&
      event.currentTarget.contains(event.relatedTarget)
    ) {
      return;
    }

    setIsDragActive(false);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    applyFiles(event.dataTransfer.files);
  }

  return (
    <div
      className={isDragActive ? "dropzone dropzone--active" : "dropzone"}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      <label className="dropzone__label" htmlFor={inputId}>
        {label}
      </label>
      <p className="dropzone__title">
        {isDragActive
          ? "Drop files to queue the sync"
          : "Drag reference files here or browse a batch from disk"}
      </p>

      <div className="dropzone__actions">
        <button
          className="secondary-button secondary-button--strong"
          type="button"
          onClick={() => inputRef.current?.click()}
        >
          Browse files
        </button>
        <span className="dropzone__meta">Supports .json, .md, .txt, .csv, and .xlsx</span>
      </div>

      <input
        ref={inputRef}
        id={inputId}
        name={inputId}
        className="sr-only"
        type="file"
        multiple
        accept=".json,.md,.txt,.csv,.xlsx"
        onChange={(event) => applyFiles(event.target.files)}
      />

      <p className="dropzone__caption">
        Queue historical tender content in one batch, then send it to the FastAPI
        ingest service for storage and processing.
      </p>
    </div>
  );
}
