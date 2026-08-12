import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import "@/styles/pages/architecture.css";
import { DataFlowVisualization } from "@/components/DataFlowVisualization";
import { getThemeIcon } from "@/lib/theme";
import { LanguageToggle } from "@/components/LanguageToggle";

type Props = {
  isLoggedIn: boolean;
  themeLabel: string;
  onThemeToggle: () => void;
};

export function ArchitecturePage({ isLoggedIn, themeLabel, onThemeToggle }: Props) {
  const { t } = useTranslation();
  const themeIcon = getThemeIcon(themeLabel);
  const heroSectionKeys = [
    'dataFlow',
    'coreMethods',
    'database',
    'security',
    'keyEndpoints',
    'modelBackends',
    'operations',
    'frontend',
  ] as const;

  return (
    <div className="admin-shell architecture-shell">
      <header className="topbar">
        <div className="architecture-hero-copy">
          <div className="architecture-kicker">{t('nav.dataFlow')}</div>
          <h2>{t('dataFlow.title')}</h2>
          <p className="muted">{t('dataFlow.description')}</p>
          <div className="architecture-hero-tags" aria-label={t('dataFlow.title')}>
            {heroSectionKeys.map((key) => (
              <span key={key}>{t(`architecture.sections.${key}`)}</span>
            ))}
          </div>
        </div>
        <div className="architecture-hero-actions">
          <div className="top-actions">
            <LanguageToggle />
            <button type="button" className="secondary" onClick={onThemeToggle}>
              {themeIcon} {themeLabel}
            </button>
            <Link className="secondary link-btn" to={isLoggedIn ? "/app" : "/app/login"}>
              {isLoggedIn ? t('nav.home') : t('auth.login')}
            </Link>
          </div>
        </div>
      </header>

      <section className="panel">
        <div className="section-head">
          <strong>{t('architecture.sections.dataFlow')}</strong>
        </div>
        <DataFlowVisualization />
      </section>

      <section className="architecture-grid">
        <article className="panel">
          <div className="section-head">
            <strong>{t('architecture.sections.coreMethods')}</strong>
          </div>
          <ul className="compact-list">
            {(t('architecture.content.coreMethods', { returnObjects: true }) as string[]).map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </article>

        <article className="panel">
          <div className="section-head">
            <strong>{t('architecture.sections.database')}</strong>
          </div>
          <ul className="compact-list">
            {(t('architecture.content.database', { returnObjects: true }) as string[]).map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </article>

        <article className="panel">
          <div className="section-head">
            <strong>{t('architecture.sections.security')}</strong>
          </div>
          <ul className="compact-list">
            {(t('architecture.content.security', { returnObjects: true }) as string[]).map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </article>

        <article className="panel">
          <div className="section-head">
            <strong>{t('architecture.sections.keyEndpoints')}</strong>
          </div>
          <pre className="diagram-block">{t('architecture.apiEndpoints', {
            returnObjects: false,
            interpolation: { escapeValue: false }
          })}</pre>
        </article>

        <article className="panel">
          <div className="section-head">
            <strong>{t('architecture.sections.modelBackends')}</strong>
          </div>
          <ul className="compact-list">
            {(t('architecture.content.modelBackends', { returnObjects: true }) as string[]).map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </article>

        <article className="panel">
          <div className="section-head">
            <strong>{t('architecture.sections.operations')}</strong>
          </div>
          <ul className="compact-list">
            {(t('architecture.content.operations', { returnObjects: true }) as string[]).map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </article>

        <article className="panel">
          <div className="section-head">
            <strong>{t('architecture.sections.frontend')}</strong>
          </div>
          <ul className="compact-list">
            {(t('architecture.content.frontend', { returnObjects: true }) as string[]).map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </article>
      </section>
    </div>
  );
}
