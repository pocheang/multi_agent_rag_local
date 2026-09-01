import { useTranslation } from "react-i18next";

type Props = {
  sectionsHidden: boolean;
  onToggle: () => void;
};

export function SectionToggleButton({ sectionsHidden, onToggle }: Props) {
  const { t } = useTranslation();

  return (
    <button
      type="button"
      className="section-toggle-btn"
      onClick={onToggle}
      title={sectionsHidden ? t("components.chat.showSections") : t("components.chat.hideSections")}
      aria-label={sectionsHidden ? t("components.chat.showSections") : t("components.chat.hideSections")}
      aria-pressed={sectionsHidden}
    >
      <span className="icon" aria-hidden="true">
        {sectionsHidden ? "👁️" : "🙈"}
      </span>
      <span>{sectionsHidden ? t("components.chat.showSections") : t("components.chat.hideSections")}</span>
    </button>
  );
}
