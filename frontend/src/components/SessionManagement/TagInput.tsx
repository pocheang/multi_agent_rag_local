/**
 * TagInput Component
 *
 * Multi-select tag input with autocomplete support.
 * Displays tags as chips with remove functionality.
 */

import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { sessionManagementApi } from '../../services/sessionManagement';
import './TagInput.css';

interface TagInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  maxTags?: number;
  disabled?: boolean;
}

export const TagInput: React.FC<TagInputProps> = ({
  value,
  onChange,
  placeholder,
  maxTags = 10,
  disabled = false,
}) => {
  const { t } = useTranslation();
  const [input, setInput] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [allTags, setAllTags] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Load all available tags on mount
  useEffect(() => {
    loadAllTags();
  }, []);

  // Click outside handler
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const loadAllTags = async () => {
    try {
      const tags = await sessionManagementApi.getAllTags();
      setAllTags(tags);
    } catch (error) {
      console.error('Failed to load tags:', error);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newInput = e.target.value;
    setInput(newInput);

    if (newInput.trim()) {
      // Filter suggestions: exclude already selected tags, match input
      const filtered = allTags
        .filter(tag => !value.includes(tag))
        .filter(tag => tag.toLowerCase().includes(newInput.toLowerCase()))
        .slice(0, 5);

      setSuggestions(filtered);
      setShowSuggestions(filtered.length > 0);
    } else {
      setShowSuggestions(false);
    }
  };

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && input.trim()) {
      e.preventDefault();
      addTag(input.trim());
    } else if (e.key === 'Backspace' && !input && value.length > 0) {
      // Remove last tag on backspace when input is empty
      removeTag(value[value.length - 1]);
    }
  };

  const addTag = (tag: string) => {
    if (value.length >= maxTags) {
      return;
    }

    const normalizedTag = tag.toLowerCase().trim();
    if (normalizedTag && !value.includes(normalizedTag)) {
      onChange([...value, normalizedTag]);
      setInput('');
      setShowSuggestions(false);

      // Add to allTags if new
      if (!allTags.includes(normalizedTag)) {
        setAllTags([...allTags, normalizedTag]);
      }
    }
  };

  const removeTag = (tag: string) => {
    onChange(value.filter(t => t !== tag));
  };

  const handleSuggestionClick = (tag: string) => {
    addTag(tag);
    inputRef.current?.focus();
  };

  return (
    <div className="tag-input-container" ref={containerRef}>
      <div className={`tag-input-wrapper ${disabled ? 'disabled' : ''}`}>
        {/* Selected tags */}
        <div className="tag-list">
          {value.map(tag => (
            <span key={tag} className="tag-chip">
              {tag}
              {!disabled && (
                <button
                  type="button"
                  className="tag-remove"
                  onClick={() => removeTag(tag)}
                  aria-label={t('sessionManagement.removeTag')}
                >
                  ×
                </button>
              )}
            </span>
          ))}
        </div>

        {/* Input */}
        {!disabled && value.length < maxTags && (
          <input
            ref={inputRef}
            type="text"
            className="tag-input"
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleInputKeyDown}
            onFocus={() => input.trim() && setShowSuggestions(suggestions.length > 0)}
            placeholder={value.length === 0 ? placeholder : ''}
            disabled={disabled}
          />
        )}
      </div>

      {/* Tag count indicator */}
      {value.length > 0 && (
        <div className="tag-count">
          {value.length} / {maxTags} {t('sessionManagement.tags')}
        </div>
      )}

      {/* Autocomplete suggestions */}
      {showSuggestions && suggestions.length > 0 && (
        <div className="tag-suggestions">
          {suggestions.map(tag => (
            <button
              key={tag}
              type="button"
              className="tag-suggestion"
              onClick={() => handleSuggestionClick(tag)}
            >
              {tag}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
