/**
 * SessionMetadataEditor Component
 *
 * Allows users to edit session metadata including tags, category, and description.
 * Supports automatic tag extraction from messages.
 */

import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  sessionManagementApi,
  SessionMetadata,
  SessionCategory,
  UpdateMetadataRequest,
} from '../../services/sessionManagement';
import { ApiError } from '@/services/http/client';
import { TagInput } from './TagInput';
import './SessionMetadataEditor.css';

interface SessionMetadataEditorProps {
  sessionId: string;
  messages?: Array<{ role: string; content: string }>;
  onSave?: (metadata: SessionMetadata) => void;
  onCancel?: () => void;
}

export const SessionMetadataEditor: React.FC<SessionMetadataEditorProps> = ({
  sessionId,
  messages = [],
  onSave,
  onCancel,
}) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [tags, setTags] = useState<string[]>([]);
  const [category, setCategory] = useState<SessionCategory | null>(null);
  const [description, setDescription] = useState('');
  const [autoTags, setAutoTags] = useState<string[]>([]);

  // Category options
  const categories: SessionCategory[] = [
    'research',
    'development',
    'debugging',
    'learning',
    'other',
  ];

  // Load existing metadata on mount
  useEffect(() => {
    loadMetadata();
  }, [sessionId]);

  const loadMetadata = async () => {
    setLoading(true);
    setError(null);

    try {
      const metadata = await sessionManagementApi.getMetadata(sessionId);
      setTags(metadata.tags);
      setCategory(metadata.category);
      setDescription(metadata.description || '');
      setAutoTags(metadata.auto_tags);
    } catch (err: unknown) {
      // Metadata may not exist yet, which is fine
      if (!(err instanceof ApiError && err.status === 404)) {
        console.error('Failed to load metadata:', err);
        setError(t('sessionManagement.errorLoadingMetadata'));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleExtractTags = async () => {
    if (messages.length === 0) {
      setError(t('sessionManagement.noMessagesToExtract'));
      return;
    }

    setExtracting(true);
    setError(null);

    try {
      const metadata = await sessionManagementApi.extractAutoTags(sessionId, messages);
      setAutoTags(metadata.auto_tags);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to extract tags:', err);
      setError(t('sessionManagement.errorExtractingTags'));
    } finally {
      setExtracting(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);

    try {
      const request: UpdateMetadataRequest = {
        tags,
        category,
        description: description.trim() || null,
      };

      const metadata = await sessionManagementApi.updateMetadata(sessionId, request);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);

      if (onSave) {
        onSave(metadata);
      }
    } catch (err) {
      console.error('Failed to save metadata:', err);
      setError(t('sessionManagement.errorSavingMetadata'));
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    if (onCancel) {
      onCancel();
    } else {
      // Reset to original values
      loadMetadata();
    }
  };

  if (loading) {
    return (
      <div className="metadata-editor">
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#6b7280' }}>
          {t('sessionManagement.loadingMetadata')}...
        </div>
      </div>
    );
  }

  return (
    <div className="metadata-editor">
      {/* Header */}
      <div className="metadata-editor-header">
        <h3 className="metadata-editor-title">
          {t('sessionManagement.editMetadata')}
        </h3>
      </div>

      {/* Error/Success Messages */}
      {error && <div className="error-message">{error}</div>}
      {success && <div className="success-message">{t('sessionManagement.savedSuccessfully')}</div>}

      {/* Form */}
      <form className="metadata-editor-form" onSubmit={(e) => { e.preventDefault(); handleSave(); }}>
        {/* Tags */}
        <div className="form-group">
          <label className="form-label">
            {t('sessionManagement.tags')}
          </label>
          <TagInput
            value={tags}
            onChange={setTags}
            placeholder={t('sessionManagement.tagsPlaceholder')}
            maxTags={10}
            disabled={saving}
          />
        </div>

        {/* Category */}
        <div className="form-group">
          <label className="form-label" htmlFor="category">
            {t('sessionManagement.category')}
          </label>
          <select
            id="category"
            className="form-select"
            value={category || ''}
            onChange={(e) => setCategory((e.target.value || null) as SessionCategory | null)}
            disabled={saving}
          >
            <option value="">{t('sessionManagement.selectCategory')}</option>
            {categories.map(cat => (
              <option key={cat} value={cat}>
                {t(`sessionManagement.categories.${cat}`)}
              </option>
            ))}
          </select>
        </div>

        {/* Description */}
        <div className="form-group">
          <label className="form-label" htmlFor="description">
            {t('sessionManagement.description')}
          </label>
          <textarea
            id="description"
            className="form-input form-textarea"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t('sessionManagement.descriptionPlaceholder')}
            maxLength={500}
            disabled={saving}
          />
          <div className="tag-count">
            {description.length} / 500
          </div>
        </div>

        {/* Auto Tags */}
        <div className="form-group">
          <div className="auto-tags-section">
            <div className="auto-tags-label">
              <svg className="auto-tags-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
              </svg>
              {t('sessionManagement.autoTags')}
            </div>

            {autoTags.length > 0 ? (
              <div className="auto-tags-list">
                {autoTags.map(tag => (
                  <span key={tag} className="auto-tag">
                    {tag}
                  </span>
                ))}
              </div>
            ) : (
              <div className="auto-tags-empty">
                {t('sessionManagement.noAutoTags')}
              </div>
            )}

            <div style={{ marginTop: '12px' }}>
              <button
                type="button"
                className="extract-tags-button"
                onClick={handleExtractTags}
                disabled={extracting || messages.length === 0}
              >
                {extracting && <span className="loading-spinner" />}
                {t('sessionManagement.extractTags')}
              </button>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="metadata-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleCancel}
            disabled={saving}
          >
            {t('common.cancel')}
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={saving}
          >
            {saving && <span className="loading-spinner" />}
            {t('common.save')}
          </button>
        </div>
      </form>
    </div>
  );
};
