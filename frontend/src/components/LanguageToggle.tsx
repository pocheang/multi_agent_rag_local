import { useTranslation } from 'react-i18next';
import '@/styles/components/language-toggle.css';

export function LanguageToggle() {
  const { i18n, t } = useTranslation();

  const toggleLanguage = () => {
    const newLang = i18n.language === 'en' ? 'zh' : 'en';
    i18n.changeLanguage(newLang);
    localStorage.setItem('language', newLang);
  };

  return (
    <button
      className="language-toggle"
      onClick={toggleLanguage}
      title={t('language.toggle')}
      aria-label={t('language.toggle')}
    >
      <span className="language-icon" aria-hidden="true">文</span>
      <span className="language-text">
        {i18n.language === 'en' ? t('language.en') : t('language.zh')}
      </span>
    </button>
  );
}
