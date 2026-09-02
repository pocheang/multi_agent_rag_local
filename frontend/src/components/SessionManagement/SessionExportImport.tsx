/**
 * SessionExportImport Component
 *
 * Allows users to export sessions to JSON/ZIP and import sessions from files.
 * Supports conflict resolution strategies and progress tracking.
 */

import React, { useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  sessionManagementApi,
  ExportFormat,
  ConflictStrategy,
  ImportResponse,
} from '../../services/sessionManagement';
import './SessionExportImport.css';
import { activateOnKey } from "@/lib/a11y";

interface SessionExportImportProps {
  sessionId?: string; // For export
  onImportSuccess?: (result: ImportResponse) => void;
}

export const SessionExportImport: React.FC<SessionExportImportProps> = ({
  sessionId,
  onImportSuccess,
}) => {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Export state
  const [exportFormat, setExportFormat] = useState<ExportFormat>('json');
  const [includeContext, setIncludeContext] = useState(true);
  const [exporting, setExporting] = useState(false);

  // Import state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [conflictStrategy, setConflictStrategy] = useState<ConflictStrategy>('skip');
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResponse | null>(null);

  // Error/success state
  const [error, setError] = useState<string | null>(null);

  // Export handler
  const handleExport = async () => {
    if (!sessionId) {
      setError(t('sessionManagement.noSessionToExport'));
      return;
    }

    setExporting(true);
    setError(null);

    try {
      const blob = await sessionManagementApi.exportSession(sessionId, {
        format: exportFormat,
        include_context: includeContext,
      });

      // Trigger download
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `session_${sessionId}.${exportFormat}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
      setError(t('sessionManagement.exportFailed'));
    } finally {
      setExporting(false);
    }
  };

  // File selection handler
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate file type
      if (!file.name.endsWith('.json') && !file.name.endsWith('.zip')) {
        setError(t('sessionManagement.invalidFileType'));
        return;
      }
      setSelectedFile(file);
      setError(null);
      setImportResult(null);
    }
  };

  // Drag and drop handlers
  const openFilePicker = () => fileInputRef.current?.click();

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.currentTarget.classList.add('drag-over');
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.currentTarget.classList.remove('drag-over');
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');

    const file = e.dataTransfer.files[0];
    if (file) {
      if (!file.name.endsWith('.json') && !file.name.endsWith('.zip')) {
        setError(t('sessionManagement.invalidFileType'));
        return;
      }
      setSelectedFile(file);
      setError(null);
      setImportResult(null);
    }
  };

  // Import handler
  const handleImport = async () => {
    if (!selectedFile) {
      setError(t('sessionManagement.noFileSelected'));
      return;
    }

    setImporting(true);
    setError(null);
    setImportResult(null);

    try {
      const result = await sessionManagementApi.importSession(selectedFile, conflictStrategy);
      setImportResult(result);

      if (onImportSuccess) {
        onImportSuccess(result);
      }
    } catch (err: unknown) {
      console.error('Import failed:', err);
      const errorDetail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(errorDetail || t('sessionManagement.importFailed'));
    } finally {
      setImporting(false);
    }
  };

  const handleClearFile = () => {
    setSelectedFile(null);
    setImportResult(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="export-import-container">
      {/* Export Section */}
      {sessionId && (
        <div className="export-section">
          <h3 className="section-title">{t('sessionManagement.exportSession')}</h3>

          <div className="form-group">
            <label className="form-label">{t('sessionManagement.exportFormat')}</label>
            <div className="radio-group">
              <label className="radio-label">
                <input
                  type="radio"
                  name="format"
                  value="json"
                  checked={exportFormat === 'json'}
                  onChange={(e) => setExportFormat(e.target.value as ExportFormat)}
                  disabled={exporting}
                />
                <span>JSON</span>
              </label>
              <label className="radio-label">
                <input
                  type="radio"
                  name="format"
                  value="zip"
                  checked={exportFormat === 'zip'}
                  onChange={(e) => setExportFormat(e.target.value as ExportFormat)}
                  disabled={exporting}
                />
                <span>ZIP</span>
              </label>
            </div>
          </div>

          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={includeContext}
                onChange={(e) => setIncludeContext(e.target.checked)}
                disabled={exporting}
              />
              <span>{t('sessionManagement.includeContext')}</span>
            </label>
          </div>

          <button
            className="btn btn-primary"
            onClick={handleExport}
            disabled={exporting}
          >
            {exporting && <span className="loading-spinner" />}
            {t('sessionManagement.export')}
          </button>
        </div>
      )}

      {/* Import Section */}
      <div className="import-section">
        <h3 className="section-title">{t('sessionManagement.importSession')}</h3>

        {/* File Upload */}
        <div
          className="file-drop-zone"
          role="button"
          tabIndex={0}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={openFilePicker}
          onKeyDown={activateOnKey(openFilePicker)}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,.zip"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />

          {selectedFile ? (
            <div className="file-selected">
              <svg className="file-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <div className="file-info">
                <div className="file-name">{selectedFile.name}</div>
                <div className="file-size">
                  {(selectedFile.size / 1024).toFixed(1)} KB
                </div>
              </div>
              <button
                type="button"
                className="file-remove"
                onClick={(e) => {
                  e.stopPropagation();
                  handleClearFile();
                }}
              >
                ×
              </button>
            </div>
          ) : (
            <div className="file-drop-prompt">
              <svg className="upload-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              <div className="drop-text">{t('sessionManagement.dragDropFile')}</div>
              <div className="drop-subtext">{t('sessionManagement.orClickToSelect')}</div>
              <div className="file-types">JSON or ZIP</div>
            </div>
          )}
        </div>

        {/* Conflict Strategy */}
        {selectedFile && (
          <>
            <div className="form-group">
              <label className="form-label">{t('sessionManagement.conflictStrategy')}</label>
              <select
                className="form-select"
                value={conflictStrategy}
                onChange={(e) => setConflictStrategy(e.target.value as ConflictStrategy)}
                disabled={importing}
              >
                <option value="skip">{t('sessionManagement.strategies.skip')}</option>
                <option value="overwrite">{t('sessionManagement.strategies.overwrite')}</option>
                <option value="rename">{t('sessionManagement.strategies.rename')}</option>
              </select>
              <div className="form-help">
                {t(`sessionManagement.strategiesHelp.${conflictStrategy}`)}
              </div>
            </div>

            <button
              className="btn btn-primary"
              onClick={handleImport}
              disabled={importing}
            >
              {importing && <span className="loading-spinner" />}
              {t('sessionManagement.import')}
            </button>
          </>
        )}

        {/* Import Result */}
        {importResult && (
          <div className="import-result">
            <div className="result-header">
              <svg className="success-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{t('sessionManagement.importSuccessful')}</span>
            </div>
            <div className="result-details">
              <div className="result-item">
                <span className="result-label">{t('sessionManagement.sessionId')}:</span>
                <span className="result-value">{importResult.session_id}</span>
              </div>
              {importResult.conflict_occurred && (
                <div className="result-item">
                  <span className="result-label">{t('sessionManagement.conflictResolution')}:</span>
                  <span className="result-value">{importResult.conflict_resolution}</span>
                </div>
              )}
              <div className="result-item">
                <span className="result-label">{t('sessionManagement.messagesImported')}:</span>
                <span className="result-value">{importResult.messages_imported}</span>
              </div>
              <div className="result-item">
                <span className="result-label">{t('sessionManagement.metadataImported')}:</span>
                <span className="result-value">
                  {importResult.metadata_imported ? '✓' : '✗'}
                </span>
              </div>
              <div className="result-item">
                <span className="result-label">{t('sessionManagement.contextImported')}:</span>
                <span className="result-value">
                  {importResult.context_imported ? '✓' : '✗'}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && <div className="error-message">{error}</div>}
    </div>
  );
};
