/**
 * Session management API client
 *
 * Provides typed interfaces for session metadata, search, and export/import operations.
 */

import { authFetch, authRequest, parseOrThrow } from '@/services/http/client';

function sessionPath(sessionId: string, suffix = ''): string {
  return `/api/v1/sessions/${encodeURIComponent(sessionId)}${suffix}`;
}

// ============================================================================
// Types
// ============================================================================

export type SessionCategory = 'research' | 'development' | 'debugging' | 'learning' | 'other';
export type ExportFormat = 'json' | 'zip';
export type ConflictStrategy = 'skip' | 'overwrite' | 'rename';

export interface SessionMetadata {
  session_id: string;
  tags: string[];
  category: SessionCategory | null;
  description: string | null;
  auto_tags: string[];
  created_at: string;
  updated_at: string;
  query_count: number;
  last_query_at: string | null;
}

export interface UpdateMetadataRequest {
  tags?: string[];
  category?: SessionCategory | null;
  description?: string | null;
  increment_query_count?: boolean;
}

export interface SearchQuery {
  q?: string;
  tags?: string[];
  tags_all?: string[];
  category?: SessionCategory | null;
  created_after?: string;
  created_before?: string;
  updated_after?: string;
  updated_before?: string;
  min_queries?: number;
  max_queries?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

export interface SearchResult {
  session_id: string;
  metadata: SessionMetadata;
  score: number;
  matched_tags: string[] | null;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  limit: number;
  offset: number;
}

export interface ExportRequest {
  format?: ExportFormat;
  include_context?: boolean;
}

export interface ImportResponse {
  session_id: string;
  original_session_id: string;
  conflict_occurred: boolean;
  conflict_resolution: string | null;
  messages_imported: number;
  metadata_imported: boolean;
  context_imported: boolean;
}

export interface Facets {
  categories: SessionCategory[];
  tags: string[];
  query_count_range: {
    min: number;
    max: number;
  };
}

// ============================================================================
// API Client
// ============================================================================

export const sessionManagementApi = {
  /**
   * Create or update session metadata
   */
  async updateMetadata(
    sessionId: string,
    request: UpdateMetadataRequest
  ): Promise<SessionMetadata> {
    return authRequest<SessionMetadata>(sessionPath(sessionId, '/metadata'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
  },

  /**
   * Get session metadata
   */
  async getMetadata(sessionId: string): Promise<SessionMetadata> {
    return authRequest<SessionMetadata>(sessionPath(sessionId, '/metadata'));
  },

  /**
   * Delete session metadata
   */
  async deleteMetadata(sessionId: string): Promise<void> {
    await authRequest(sessionPath(sessionId, '/metadata'), { method: 'DELETE' });
  },

  /**
   * Extract automatic tags from messages
   */
  async extractAutoTags(
    sessionId: string,
    messages: Array<{ role: string; content: string }>
  ): Promise<SessionMetadata> {
    return authRequest<SessionMetadata>(sessionPath(sessionId, '/metadata/extract-tags'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages }),
    });
  },

  /**
   * Search sessions
   */
  async search(query: SearchQuery): Promise<SearchResponse> {
    return authRequest<SearchResponse>('/api/v1/sessions/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(query),
    });
  },

  /**
   * Get all unique tags
   */
  async getAllTags(): Promise<string[]> {
    const response = await authRequest<{ tags: string[] }>('/api/v1/sessions/tags');
    return response.tags;
  },

  /**
   * Get search facets
   */
  async getFacets(): Promise<Facets> {
    return authRequest<Facets>('/api/v1/sessions/facets');
  },

  /**
   * Export session
   */
  async exportSession(
    sessionId: string,
    request: ExportRequest = {}
  ): Promise<Blob> {
    const response = await authFetch(sessionPath(sessionId, '/export'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (!response.ok) return parseOrThrow<never>(response);
    return response.blob();
  },

  /**
   * Import session
   */
  async importSession(
    file: File,
    conflictStrategy: ConflictStrategy = 'skip'
  ): Promise<ImportResponse> {
    const formData = new FormData();
    formData.append('file', file);

    return authRequest<ImportResponse>(
      `/api/v1/sessions/import?conflict_strategy=${encodeURIComponent(conflictStrategy)}`,
      { method: 'POST', body: formData },
    );
  },
};
