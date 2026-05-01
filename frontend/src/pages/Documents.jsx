import { useState, useEffect, useRef } from 'react';
import {
  FiFileText,
  FiLayers,
  FiLoader,
  FiMenu,
  FiTrash2,
  FiUploadCloud,
  FiX,
} from 'react-icons/fi';
import { deleteDocument, getDocuments, getSessions, uploadDocument } from '../api';
import SettingsModal from '../components/SettingsModal';
import Sidebar from '../components/Sidebar';
import { useAuth } from '../context/AuthContext';

const formatSize = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export default function Documents() {
  const { user } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const fileInputRef = useRef(null);

  const loadWorkspaceData = async () => {
    try {
      const [documentsResponse, sessionsResponse] = await Promise.all([
        getDocuments(),
        getSessions(),
      ]);
      setDocuments(documentsResponse.data);
      setSessions(sessionsResponse.data);
    } catch (err) {
      console.error('Failed to load workspace data:', err);
    }
  };

  useEffect(() => {
    loadWorkspaceData();
  }, []);

  useEffect(() => {
    const hasProcessing = documents.some((doc) => doc.status === 'processing');
    if (!hasProcessing) {
      return undefined;
    }

    const interval = setInterval(loadWorkspaceData, 5000);
    return () => clearInterval(interval);
  }, [documents]);

  const handleFileUpload = async (file) => {
    if (!file) {
      return;
    }

    setUploading(true);
    setUploadStatus({ type: 'info', msg: `Uploading "${file.name}"...` });

    try {
      await uploadDocument(file);
      setUploadStatus({ type: 'success', msg: `Successfully uploaded "${file.name}".` });
      loadWorkspaceData();
      setTimeout(() => setUploadStatus(null), 5000);
    } catch (err) {
      setUploadStatus({ type: 'error', msg: err.response?.data?.detail || 'Upload failed.' });
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDocument = async (documentId) => {
    if (!window.confirm('Delete this document and remove its indexed chunks from the knowledge base?')) {
      return;
    }

    try {
      await deleteDocument(documentId);
      loadWorkspaceData();
    } catch (err) {
      console.error('Failed to delete document:', err);
    }
  };

  const readyCount = documents.filter((doc) => doc.status === 'ready').length;
  const processingCount = documents.filter((doc) => doc.status === 'processing').length;
  const totalChunks = documents.reduce((sum, doc) => sum + (doc.chunk_count || 0), 0);
  const totalSize = documents.reduce((sum, doc) => sum + (doc.file_size || 0), 0);
  const formats = Object.entries(
    documents.reduce((acc, doc) => {
      const key = doc.file_type.toUpperCase();
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {})
  ).sort((left, right) => right[1] - left[1]);

  return (
    <div className="chat-layout">
      <button className="mobile-menu-btn" onClick={() => setSidebarOpen((current) => !current)}>
        {sidebarOpen ? <FiX /> : <FiMenu />}
      </button>

      <Sidebar
        isOpen={sidebarOpen}
        user={user}
        onOpenSettings={() => setSettingsOpen(true)}
        sessions={sessions}
        documents={documents}
        onNavigate={() => setSidebarOpen(false)}
      />
      <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />

      <main className="workspace-main">
        <div className="workspace-scroll">
          {uploadStatus && (
            <div className={`upload-toast ${uploadStatus.type}`}>
              <span>{uploadStatus.msg}</span>
              <button type="button" onClick={() => setUploadStatus(null)}>Close</button>
            </div>
          )}

          <section className="page-panel">
            <header className="page-header">
              <div className="page-title-group">
                <span className="page-kicker">Knowledge base</span>
                <h1>Manage the files behind every answer.</h1>
                <p>
                  Upload documents, monitor processing status, and keep your workspace library organized.
                </p>
              </div>

              <div className="page-actions">
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                >
                  <FiUploadCloud /> {uploading ? 'Uploading...' : 'Upload document'}
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.txt,.csv,.xlsx,.md"
                  onChange={(event) => {
                    handleFileUpload(event.target.files[0]);
                    event.target.value = '';
                  }}
                  hidden
                />
              </div>
            </header>

            <div className="stats-grid">
              <div className="stat-card">
                <span className="stat-label">Total documents</span>
                <strong>{documents.length}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Ready for chat</span>
                <strong>{readyCount}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Processing</span>
                <strong>{processingCount}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Indexed chunks</span>
                <strong>{totalChunks}</strong>
              </div>
            </div>

            <div className="content-grid">
              <section className="panel-card">
                <div className="panel-card-header">
                  <div>
                    <h2>Upload overview</h2>
                    <p>Supported formats: PDF, DOCX, TXT, CSV, XLSX, and Markdown.</p>
                  </div>
                </div>

                <div className="upload-cta">
                  <div className="upload-cta-icon"><FiUploadCloud /></div>
                  <div className="upload-cta-copy">
                    <strong>Build your workspace knowledge base</strong>
                    <span>Large files are processed in the background and become searchable when ready.</span>
                  </div>
                </div>

                <div className="metric-stack">
                  <div className="metric-row">
                    <span>Total storage</span>
                    <strong>{formatSize(totalSize)}</strong>
                  </div>
                  <div className="metric-row">
                    <span>Supported size limit</span>
                    <strong>50 MB per file</strong>
                  </div>
                </div>
              </section>

              <section className="panel-card">
                <div className="panel-card-header">
                  <div>
                    <h2>Format coverage</h2>
                    <p>See how your uploaded library is distributed.</p>
                  </div>
                </div>

                {formats.length === 0 ? (
                  <div className="empty-note">No documents uploaded yet.</div>
                ) : (
                  <div className="tag-list">
                    {formats.map(([format, count]) => (
                      <span key={format} className="tag">
                        <FiLayers /> {format} - {count}
                      </span>
                    ))}
                  </div>
                )}
              </section>
            </div>

            <section className="panel-card table-card">
              <div className="panel-card-header">
                <div>
                  <h2>Uploaded documents</h2>
                  <p>Track indexing progress and remove files you no longer need.</p>
                </div>
              </div>

              {documents.length === 0 ? (
                <div className="empty-state">
                  <FiFileText />
                  <h3>No documents yet</h3>
                  <p>Upload your first file to begin building a searchable knowledge base.</p>
                </div>
              ) : (
                <div className="table-wrapper">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Document</th>
                        <th>Type</th>
                        <th>Size</th>
                        <th>Chunks</th>
                        <th>Status</th>
                        <th>Uploaded</th>
                        <th className="align-right">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {documents.map((doc) => (
                        <tr key={doc.id}>
                          <td>
                            <div className="table-primary">{doc.filename}</div>
                            {doc.error_message && <div className="table-secondary">{doc.error_message}</div>}
                          </td>
                          <td>{doc.file_type.toUpperCase()}</td>
                          <td>{formatSize(doc.file_size)}</td>
                          <td>{doc.chunk_count}</td>
                          <td>
                            <span className={`status-badge ${doc.status}`}>
                              {doc.status === 'processing' && <FiLoader className="spin-icon" />}
                              {doc.status}
                            </span>
                          </td>
                          <td>{new Date(doc.created_at).toLocaleDateString()}</td>
                          <td className="align-right">
                            <button
                              type="button"
                              className="icon-button danger"
                              onClick={() => handleDeleteDocument(doc.id)}
                            >
                              <FiTrash2 />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </section>
        </div>
      </main>
    </div>
  );
}
