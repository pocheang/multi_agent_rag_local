import { useTranslation } from 'react-i18next';

export function LanguageToggle() {
  const { i18n, t } = useTranslation();

  const toggleLanguage = () => {
    const newLang = i18n.language === 'en' ? 'zh' : 'en';
    i18n.changeLanguage(newLang);
    localStorage.setItem('language', newLang);
  };

  return (
    <button
      className="tw:flex tw:items-center tw:gap-2 tw:px-4 tw:py-2 tw:bg-surface tw:border tw:border-border-light tw:rounded-[var(--radius-md)] tw:cursor-pointer tw:transition-all tw:duration-[var(--transition-fast)] tw:text-sm tw:font-semibold tw:text-text-primary tw:normal-case hover:tw:bg-surface-hover hover:tw:border-accent hover:tw:-translate-y-px hover:tw:shadow-[var(--shadow-sm)] active:tw:translate-y-0 max-[768px]:tw:px-3 max-[768px]:tw:py-1.5 max-[768px]:tw:text-[0.8125rem]"
      onClick={toggleLanguage}
      title={t('language.toggle')}
      aria-label={t('language.toggle')}
    >
      <span className="tw:text-[1.25rem] tw:leading-none max-[768px]:tw:text-[1.125rem]" aria-hidden="true">文</span>
      <span className="tw:leading-none">
        {i18n.language === 'en' ? t('language.en') : t('language.zh')}
      </span>
    </button>
  );
}
