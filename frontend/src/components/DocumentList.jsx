import { useState, useEffect } from 'react';
import { getDocuments, deleteDocument } from '../api';
import { FiFile, FiTrash2, FiRefreshCw, FiCheckCircle, FiClock, FiAlertTriangle } from 'react-icons/fi';

export default function DocumentList() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDocs();
    // Poll for updates every 5 seconds (for processing status)
    const interval = setInterval(loadDocs, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadDocs = async () => {
    try {
      const res = await getDocuments();
      setDocuments(res.data);
    } catch (err) {
      console.error('Failed to load documents:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (docId) => {
    if (!window.confirm('Delete this document and its embeddings?')) return;
    try {
      await deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
    } catch (err) {
      console.error('Failed to delete document:', err);
    }
  };

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const statusIcon = (status) => {
    switch (status) {
      case 'ready': return <FiCheckCircle className="status-ready" />;
      case 'processing': return <FiClock className="status-processing" />;
      case 'failed': return <FiAlertTriangle className="status-failed" />;
      default: return null;
    }
  };

  if (loading) {
    return <div className="doc-list-loading">Loading documents...</div>;
  }

  return (
    <div className="document-list" id="document-list">
      <div className="doc-list-header">
        <h3>Your Documents ({documents.length})</h3>
        <button className="refresh-btn" onClick={loadDocs} title="Refresh">
          <FiRefreshCw />
        </button>
      </div>
      {documents.length === 0 ? (
        <p className="no-docs">No documents uploaded yet.</p>
      ) : (
        <div className="doc-items">
          {documents.map((doc) => (
            <div key={doc.id} className="doc-item">
              <div className="doc-icon">
                <FiFile />
              </div>
              <div className="doc-info">
                <span className="doc-name">{doc.filename}</span>
                <span className="doc-meta">
                  {formatSize(doc.file_size)} · {doc.chunk_count} chunks · {statusIcon(doc.status)} {doc.status}
                </span>
              </div>
              <button
                className="doc-delete-btn"
                onClick={() => handleDelete(doc.id)}
                title="Delete document"
              >
                <FiTrash2 />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
