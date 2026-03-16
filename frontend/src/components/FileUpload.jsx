import { useState, useRef } from 'react';
import { uploadDocument } from '../api';
import { FiUploadCloud, FiCheck, FiAlertCircle } from 'react-icons/fi';

export default function FileUpload({ onUploadComplete }) {
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [status, setStatus] = useState(null); // { type: 'success'|'error', message: '' }
  const fileInputRef = useRef(null);

  const handleFile = async (file) => {
    if (!file) return;

    const allowed = ['pdf', 'docx', 'txt'];
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!allowed.includes(ext)) {
      setStatus({ type: 'error', message: `Unsupported file type. Allowed: ${allowed.join(', ')}` });
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      setStatus({ type: 'error', message: 'File too large. Maximum 50 MB.' });
      return;
    }

    setUploading(true);
    setStatus(null);
    try {
      await uploadDocument(file);
      setStatus({ type: 'success', message: `"${file.name}" uploaded! Processing will begin shortly.` });
      if (onUploadComplete) onUploadComplete();
    } catch (err) {
      setStatus({
        type: 'error',
        message: err.response?.data?.detail || 'Upload failed. Please try again.',
      });
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    handleFile(file);
  };

  return (
    <div className="file-upload" id="file-upload">
      <div
        className={`upload-zone ${dragOver ? 'drag-over' : ''} ${uploading ? 'uploading' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <FiUploadCloud className="upload-icon" />
        <p>{uploading ? 'Uploading...' : 'Drop a file or click to upload'}</p>
        <span className="upload-hint">PDF, DOCX, TXT — up to 50 MB</span>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          onChange={(e) => handleFile(e.target.files[0])}
          hidden
          id="file-input"
        />
      </div>
      {status && (
        <div className={`upload-status ${status.type}`}>
          {status.type === 'success' ? <FiCheck /> : <FiAlertCircle />}
          <span>{status.message}</span>
        </div>
      )}
    </div>
  );
}
