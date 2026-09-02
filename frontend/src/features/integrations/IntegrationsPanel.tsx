import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  createConnector,
  listConnectors,
  setConnectorEnabled,
  testConnector,
  type ConnectorView,
} from "./api";

type Draft = {
  connector_id: string;
  name: string;
  base_url: string;
  allowed_hosts: string;
  secret: string;
};

const EMPTY_DRAFT: Draft = {
  connector_id: "",
  name: "",
  base_url: "",
  allowed_hosts: "",
  secret: "",
};

export function IntegrationsPanel() {
  const { t } = useTranslation();
  const [connectors, setConnectors] = useState<readonly ConnectorView[]>([]);
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    void Promise.resolve().then(async () => {
      if (controller.signal.aborted) return;
      try {
        const items = await listConnectors(controller.signal);
        if (active && !controller.signal.aborted) setConnectors(items);
      } catch (error: unknown) {
        if (active && !controller.signal.aborted) {
          setMessage(error instanceof Error ? error.message : t("features.integrations.loadError"));
        }
      } finally {
        if (active && !controller.signal.aborted) setLoading(false);
      }
    });
    return () => {
      active = false;
      controller.abort();
    };
  }, []);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage("");
    setBusyId("create");
    try {
      const created = await createConnector({
        connector_id: draft.connector_id.trim(),
        name: draft.name.trim(),
        base_url: draft.base_url.trim(),
        allowed_hosts: draft.allowed_hosts.split(",").map((host) => host.trim()).filter(Boolean),
        secret: draft.secret,
      });
      setConnectors((items) => [...items, created].sort((left, right) => left.name.localeCompare(right.name)));
      setDraft(EMPTY_DRAFT);
      setMessage(t("features.integrations.connected"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("features.integrations.connectError"));
    } finally {
      setBusyId(null);
    }
  };

  const toggle = async (connector: ConnectorView) => {
    setBusyId(connector.connector_id);
    setMessage("");
    try {
      const updated = await setConnectorEnabled(connector.connector_id, connector.status === "disabled");
      replaceConnector(updated);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("features.integrations.updateError"));
    } finally {
      setBusyId(null);
    }
  };

  const probe = async (connector: ConnectorView) => {
    setBusyId(connector.connector_id);
    setMessage("");
    try {
      const result = await testConnector(connector.connector_id);
      setConnectors((items) => items.map((item) => (
        item.connector_id === connector.connector_id ? { ...item, test_status: result.status } : item
      )));
      setMessage(result.message);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("features.integrations.testError"));
    } finally {
      setBusyId(null);
    }
  };

  const replaceConnector = (updated: ConnectorView) => {
    setConnectors((items) => items.map((item) => (
      item.connector_id === updated.connector_id ? updated : item
    )));
  };

  return (
    <section aria-label={t("features.integrations.ariaLabel")} className="integrations-panel">
      <details>
        <summary>{t("features.integrations.title")}</summary>
        <p>{t("features.integrations.description")}</p>
        <form onSubmit={(event) => void submit(event)}>
          <h2>{t("features.integrations.connectTitle")}</h2>
          <label>{t("features.integrations.integrationId")}<input required pattern="[a-z][a-z0-9_-]{0,63}" value={draft.connector_id} onChange={(event) => setDraft({ ...draft, connector_id: event.target.value })} /></label>
          <label>{t("features.integrations.name")}<input required maxLength={120} value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
          <label>{t("features.integrations.baseUrl")}<input required type="url" value={draft.base_url} onChange={(event) => setDraft({ ...draft, base_url: event.target.value })} /></label>
          <label>{t("features.integrations.allowedHosts")}<input required placeholder={t("features.integrations.allowedHostsPlaceholder")} value={draft.allowed_hosts} onChange={(event) => setDraft({ ...draft, allowed_hosts: event.target.value })} /></label>
          <label>{t("features.integrations.accessSecret")}<input required type="password" autoComplete="new-password" value={draft.secret} onChange={(event) => setDraft({ ...draft, secret: event.target.value })} /></label>
          <button type="submit" disabled={busyId !== null}>{busyId === "create" ? t("features.integrations.connecting") : t("features.integrations.addConnector")}</button>
        </form>
        {loading ? <p aria-live="polite">{t("features.integrations.loading")}</p> : null}
        <ul>
          {connectors.map((connector) => (
            <li key={connector.connector_id}>
              <strong>{connector.name}</strong> — {t(`features.integrations.status.${connector.status}`)}; {t("features.integrations.testStatusLabel")}: {t(`features.integrations.testStatus.${connector.test_status}`)}
              <button type="button" onClick={() => void toggle(connector)} disabled={busyId !== null}>
                {connector.status === "enabled" ? t("features.integrations.disable") : t("features.integrations.enable")}
              </button>
              <button type="button" onClick={() => void probe(connector)} disabled={busyId !== null || connector.status !== "enabled"}>{t("features.integrations.test")}</button>
            </li>
          ))}
        </ul>
        {!loading && connectors.length === 0 ? <p className="runtime-panel-empty">{t("features.integrations.empty")}</p> : null}
        {message ? <p role="status" aria-live="polite">{message}</p> : null}
      </details>
    </section>
  );
}
