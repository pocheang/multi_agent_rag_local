/**
 * SessionSearch Component
 *
 * Advanced session search with text query, tag filters, category filter,
 * time ranges, and query count ranges. Displays paginated results with
 * relevance scores and matched tags highlighting.
 */

import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  sessionManagementApi,
  SearchQuery,
  SearchResult,
  SessionCategory,
} from '../../services/sessionManagement';
import { TagInput } from './TagInput';
import './SessionSearch.css';

interface SessionSearchProps {
  onSelectSession?: (sessionId: string) => void;
}

export const SessionSearch: React.FC<SessionSearchProps> = ({ onSelectSession }) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  // Search query state
  const [searchText, setSearchText] = useState('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<SessionCategory | null>(null);
  const [minQueries, setMinQueries] = useState<number | undefined>();
  const [maxQueries, setMaxQueries] = useState<number | undefined>();
  const [sortBy, setSortBy] = useState<'updated_at' | 'created_at' | 'query_count'>('updated_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  // Results state
  const [results, setResults] = useState<SearchResult[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [pageSize] = useState(20);

  const categories: SessionCategory[] = [
    'research',
    'development',
    'debugging',
    'learning',
    'other',
  ];

  // Search on mount and when filters change
  useEffect(() => {
    handleSearch();
  }, [page, sortBy, sortOrder]);

  const handleSearch = async () => {
    setLoading(true);

    try {
      const query: SearchQuery = {
        q: searchText.trim() || undefined,
        tags: selectedTags.length > 0 ? selectedTags : undefined,
        category: selectedCategory || undefined,
        min_queries: minQueries,
        max_queries: maxQueries,
        sort_by: sortBy,
        sort_order: sortOrder,
        limit: pageSize,
        offset: page * pageSize,
      };

      const response = await sessionManagementApi.search(query);
      setResults(response.results);
      setTotal(response.total);
    } catch (error) {
      console.error('Search failed:', error);
      setResults([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchClick = () => {
    setPage(0); // Reset to first page
    handleSearch();
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearchClick();
    }
  };

  const handleClearFilters = () => {
    setSearchText('');
    setSelectedTags([]);
    setSelectedCategory(null);
    setMinQueries(undefined);
    setMaxQueries(undefined);
    setPage(0);
  };

  const handleResultClick = (sessionId: string) => {
    if (onSelectSession) {
      onSelectSession(sessionId);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="session-search">
      {/* Header */}
      <div className="search-header">
        <h3 className="search-title">{t('sessionManagement.searchSessions')}</h3>

        {/* Search Box */}
        <div className="search-box">
          <div className="search-input-wrapper">
            <input
              type="text"
              className="search-input"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={t('sessionManagement.searchPlaceholder')}
              disabled={loading}
            />
            <svg className="search-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <button
            className="search-button"
            onClick={handleSearchClick}
            disabled={loading}
          >
            {loading ? t('common.searching') : t('common.search')}
          </button>
        </div>
      </div>

      {/* Filters Section */}
      <div className="filters-section">
        <button
          className="filters-toggle"
          onClick={() => setShowFilters(!showFilters)}
        >
          <svg className="filters-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
          </svg>
          {showFilters ? t('common.hideFilters') : t('common.showFilters')}
        </button>

        {showFilters && (
          <div className="filters-content">
            <div className="filters-grid">
              {/* Tags Filter */}
              <div className="filter-group">
                <label className="filter-label">{t('sessionManagement.filterByTags')}</label>
                <TagInput
                  value={selectedTags}
                  onChange={setSelectedTags}
                  placeholder={t('sessionManagement.selectTags')}
                  maxTags={5}
                />
              </div>

              {/* Category Filter */}
              <div className="filter-group">
                <label className="filter-label">{t('sessionManagement.filterByCategory')}</label>
                <select
                  className="filter-select"
                  value={selectedCategory || ''}
                  onChange={(e) => setSelectedCategory((e.target.value || null) as SessionCategory | null)}
                >
                  <option value="">{t('sessionManagement.allCategories')}</option>
                  {categories.map(cat => (
                    <option key={cat} value={cat}>
                      {t(`sessionManagement.categories.${cat}`)}
                    </option>
                  ))}
                </select>
              </div>

              {/* Min Queries */}
              <div className="filter-group">
                <label className="filter-label">{t('sessionManagement.minQueries')}</label>
                <input
                  type="number"
                  className="filter-input"
                  value={minQueries || ''}
                  onChange={(e) => setMinQueries(e.target.value ? parseInt(e.target.value) : undefined)}
                  min={0}
                  placeholder="0"
                />
              </div>

              {/* Max Queries */}
              <div className="filter-group">
                <label className="filter-label">{t('sessionManagement.maxQueries')}</label>
                <input
                  type="number"
                  className="filter-input"
                  value={maxQueries || ''}
                  onChange={(e) => setMaxQueries(e.target.value ? parseInt(e.target.value) : undefined)}
                  min={0}
                  placeholder="∞"
                />
              </div>
            </div>

            <div style={{ marginTop: '12px', textAlign: 'right' }}>
              <button
                className="filters-toggle"
                onClick={handleClearFilters}
                style={{ fontSize: '13px' }}
              >
                {t('common.clearFilters')}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Results */}
      {!loading && results.length > 0 && (
        <>
          <div className="results-header">
            <div className="results-count">
              {t('sessionManagement.resultsCount', { count: total })}
            </div>
            <div className="sort-controls">
              <span className="sort-label">{t('common.sortBy')}:</span>
              <select
                className="sort-select"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
              >
                <option value="updated_at">{t('sessionManagement.sortUpdated')}</option>
                <option value="created_at">{t('sessionManagement.sortCreated')}</option>
                <option value="query_count">{t('sessionManagement.sortQueries')}</option>
              </select>
              <select
                className="sort-select"
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value as any)}
              >
                <option value="desc">{t('common.descending')}</option>
                <option value="asc">{t('common.ascending')}</option>
              </select>
            </div>
          </div>

          <div className="results-list">
            {results.map(result => (
              <div
                key={result.session_id}
                className="result-card"
                onClick={() => handleResultClick(result.session_id)}
              >
                <div className="result-header">
                  <div className="result-session-id">{result.session_id}</div>
                  <div className="result-score">
                    {t('sessionManagement.score')}: {result.score.toFixed(2)}
                  </div>
                </div>

                {result.metadata.description && (
                  <div className="result-description">{result.metadata.description}</div>
                )}

                <div className="result-meta">
                  <div className="result-meta-item">
                    <span>{t('sessionManagement.category')}:</span>
                    <span>{result.metadata.category ? t(`sessionManagement.categories.${result.metadata.category}`) : '-'}</span>
                  </div>
                  <div className="result-meta-item">
                    <span>{t('sessionManagement.queries')}:</span>
                    <span>{result.metadata.query_count}</span>
                  </div>
                  <div className="result-meta-item">
                    <span>{t('common.updated')}:</span>
                    <span>{formatDate(result.metadata.updated_at)}</span>
                  </div>
                </div>

                {result.metadata.tags.length > 0 && (
                  <div className="result-tags">
                    {result.metadata.tags.map(tag => (
                      <span
                        key={tag}
                        className={`result-tag ${result.matched_tags?.includes(tag) ? 'matched' : ''}`}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="pagination">
              <button
                className="pagination-button"
                onClick={() => setPage(page - 1)}
                disabled={page === 0}
              >
                {t('common.previous')}
              </button>
              <div className="pagination-info">
                {t('common.pageOf', { current: page + 1, total: totalPages })}
              </div>
              <button
                className="pagination-button"
                onClick={() => setPage(page + 1)}
                disabled={page >= totalPages - 1}
              >
                {t('common.next')}
              </button>
            </div>
          )}
        </>
      )}

      {/* Empty State */}
      {!loading && results.length === 0 && (
        <div className="empty-state">
          <svg className="empty-state-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <h4 className="empty-state-title">{t('sessionManagement.noResults')}</h4>
          <p className="empty-state-description">{t('sessionManagement.tryDifferentSearch')}</p>
        </div>
      )}
    </div>
  );
};
