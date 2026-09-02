import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { ClarificationQuestion, ClarificationContext } from "../../../types/api";

interface ClarificationPromptProps {
  question: ClarificationQuestion;
  context: ClarificationContext;
  onAnswer: (fieldName: string, answer: string) => void;
  onSkip: () => void;
  isSubmitting?: boolean;
}

export const ClarificationPrompt: React.FC<ClarificationPromptProps> = ({
  question,
  context,
  onAnswer,
  onSkip,
  isSubmitting = false,
}) => {
  const { t } = useTranslation();
  const [selectedOption, setSelectedOption] = useState<string>("");
  const [customInput, setCustomInput] = useState<string>("");
  const [useCustom, setUseCustom] = useState<boolean>(false);

  useEffect(() => {
    setSelectedOption("");
    setCustomInput("");
    setUseCustom(false);
  }, [question.field_name]);

  const handleSubmit = () => {
    const answer = useCustom ? customInput.trim() : selectedOption;
    if (!answer) return;
    onAnswer(question.field_name, answer);
  };

  const handleOptionSelect = (option: string) => {
    setSelectedOption(option);
    setUseCustom(false);
  };

  const handleCustomToggle = () => {
    setUseCustom(true);
    setSelectedOption("");
  };

  const isValid = useCustom ? customInput.trim().length > 0 : selectedOption.length > 0;

  return (
    <div className="clarification-prompt">
      <div className="clarification-header">
        <div className="clarification-title">
          <svg className="clarification-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <circle cx="12" cy="12" r="10" strokeWidth="2" />
            <path d="M12 16v-4M12 8h.01" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <h3>{t("clarification.title")}</h3>
        </div>
        <div className="clarification-progress">
          {t("clarification.round", {
            current: context.clarification_round + 1,
            max: context.max_rounds,
          })}
        </div>
      </div>

      <div className="clarification-question">
        <p>{question.question}</p>
      </div>

      <div className="clarification-options">
        {question.options.map((option, index) => (
          <button
            key={index}
            className={`clarification-option ${selectedOption === option && !useCustom ? "selected" : ""}`}
            onClick={() => handleOptionSelect(option)}
            disabled={isSubmitting}
          >
            <div className="option-radio">
              {selectedOption === option && !useCustom && (
                <div className="option-radio-dot" />
              )}
            </div>
            <span className="option-text">{option}</span>
          </button>
        ))}

        {question.allow_custom_input && (
          <div className="clarification-custom">
            <button
              className={`clarification-option ${useCustom ? "selected" : ""}`}
              onClick={handleCustomToggle}
              disabled={isSubmitting}
            >
              <div className="option-radio">
                {useCustom && <div className="option-radio-dot" />}
              </div>
              <span className="option-text">{t("clarification.customInput")}</span>
            </button>
            {useCustom && (
              <input
                type="text"
                className="clarification-input"
                placeholder={t("clarification.customInputPlaceholder")}
                value={customInput}
                onChange={(e) => setCustomInput(e.target.value)}
                disabled={isSubmitting}
                autoFocus
              />
            )}
          </div>
        )}
      </div>

      <div className="clarification-actions">
        <button
          className="clarification-btn clarification-btn-secondary"
          onClick={onSkip}
          disabled={isSubmitting}
        >
          {t("clarification.skip")}
        </button>
        <button
          className="clarification-btn clarification-btn-primary"
          onClick={handleSubmit}
          disabled={!isValid || isSubmitting}
        >
          {isSubmitting ? t("clarification.submitting") : t("clarification.submit")}
        </button>
      </div>

      {context.collected_info && Object.keys(context.collected_info).length > 0 && (
        <div className="clarification-collected">
          <details>
            <summary>{t("clarification.collectedInfo")}</summary>
            <ul className="collected-list">
              {Object.entries(context.collected_info).map(([key, value]) => (
                <li key={key}>
                  <strong>{key}:</strong> {value}
                </li>
              ))}
            </ul>
          </details>
        </div>
      )}
    </div>
  );
};
