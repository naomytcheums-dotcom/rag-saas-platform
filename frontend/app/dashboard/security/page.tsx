"use client";

import LoadingState from "@/components/LoadingState";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, fileUrl } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useTranslation } from "@/lib/i18n";

interface Member {
  user_id: string;
  email: string;
  role: string;
  joined_at: string;
}

interface Permission {
  id: string;
  key: string;
  resource: string;
  action: string;
  description: string;
}

interface CustomRole {
  id: string;
  name: string;
  description: string | null;
  permission_keys: string[];
}

interface AuditLogEntry {
  id: string;
  user_id: string | null;
  action: string;
  ip: string | null;
  timestamp: string;
  success: boolean;
}

interface SecurityAlert {
  id: string;
  message: string;
  severity: string;
  created_at: string;
}

interface SecurityScan {
  id: string;
  scan_type: string;
  status: string;
  summary: string | null;
  started_at: string;
  vulnerability_count: number;
}

interface Vulnerability {
  id: string;
  severity: string;
  status: string;
  title: string;
  location: string | null;
}

interface SecurityPolicy {
  require_2fa_for_admins: boolean;
  session_timeout_minutes: number;
  max_login_attempts: number;
  ip_allowlist: string | null;
  min_password_strength_bits: number;
  auto_lock_after_failed_attempts: boolean;
}

const TABS = ["Overview", "Roles & Permissions", "Audit log", "Encryption", "Compliance", "Vulnerability scan", "Policies"] as const;
type Tab = (typeof TABS)[number];
const TAB_LABEL_KEYS: Record<Tab, string> = {
  Overview: "security.tab_overview",
  "Roles & Permissions": "security.tab_roles",
  "Audit log": "security.tab_audit",
  Encryption: "security.tab_encryption",
  Compliance: "security.tab_compliance",
  "Vulnerability scan": "security.tab_scan",
  Policies: "security.tab_policies",
};

export default function SecurityPage() {
  const { org, loading: orgLoading } = useCurrentOrg();
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("Overview");
  const [error, setError] = useState<string | null>(null);

  if (orgLoading || !org) {
    return <LoadingState fullScreen={false} />;
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-xl font-semibold text-foreground">{t("security.title")}</h1>
      <p className="mt-1 text-sm text-foreground-muted">{t("security.subtitle")} {org.name}.</p>

      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

      <div className="mt-5 flex flex-wrap gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm font-medium transition-colors ${
              tab === t ? "border-b-2 border-accent text-accent-hover" : "text-foreground-muted hover:text-foreground"
            }`}
          >
            {t(TAB_LABEL_KEYS[t])}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {tab === "Overview" && <OverviewTab orgId={org.id} onError={setError} />}
        {tab === "Roles & Permissions" && <RolesTab orgId={org.id} onError={setError} />}
        {tab === "Audit log" && <AuditLogTab orgId={org.id} onError={setError} />}
        {tab === "Encryption" && <EncryptionTab onError={setError} />}
        {tab === "Compliance" && <ComplianceTab orgId={org.id} onError={setError} />}
        {tab === "Vulnerability scan" && <ScanTab orgId={org.id} onError={setError} />}
        {tab === "Policies" && <PoliciesTab orgId={org.id} onError={setError} />}
      </div>
    </div>
  );
}

function OverviewTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const { t } = useTranslation();
  const [score, setScore] = useState<number | null>(null);
  const [alerts, setAlerts] = useState<SecurityAlert[]>([]);

  const load = useCallback(async () => {
    try {
      const [scoreRes, alertsRes] = await Promise.all([
        api.get<{ score: number }>(`/organizations/${orgId}/security/score`),
        api.get<SecurityAlert[]>(`/organizations/${orgId}/security/alerts`),
      ]);
      setScore(scoreRes.score);
      setAlerts(alertsRes);
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("security.error_overview_load"));
    }
  }, [orgId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  async function dismiss(alertId: string) {
    await api.post(`/organizations/${orgId}/security/alerts/${alertId}/dismiss`);
    await load();
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-sm font-semibold text-foreground">Score de sécurité</h2>
        <p className="mt-2 text-3xl font-semibold" style={{ color: score === null ? undefined : score >= 80 ? "var(--color-success)" : score >= 50 ? "var(--color-warning)" : "var(--color-danger)" }}>
          {score ?? "…"}<span className="text-base text-foreground-muted"> / 100</span>
        </p>
        <p className="mt-1 text-xs text-foreground-muted">100 moins une déduction pondérée par vulnérabilité ouverte détectée par une vraie analyse (onglet Analyse de vulnérabilités).</p>
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-foreground">Alertes actives</h2>
        {alerts.length === 0 ? (
          <p className="text-sm text-foreground-muted">Aucune alerte active.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {alerts.map((alert) => (
              <div key={alert.id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-3 text-sm">
                <div>
                  <span className="mr-2 rounded-full bg-danger-soft px-2 py-0.5 text-xs font-medium uppercase text-danger">{alert.severity}</span>
                  {alert.message}
                </div>
                <button type="button" onClick={() => void dismiss(alert.id)} className="text-xs font-medium text-foreground-muted hover:text-foreground">Ignorer</button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function RolesTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const { t } = useTranslation();
  const [roles, setRoles] = useState<CustomRole[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [newRoleName, setNewRoleName] = useState("");

  const load = useCallback(async () => {
    try {
      const [rolesRes, permsRes, membersRes] = await Promise.all([
        api.get<CustomRole[]>(`/organizations/${orgId}/rbac/roles`),
        api.get<Permission[]>(`/organizations/${orgId}/rbac/permissions`),
        api.get<{ items: Member[] }>(`/organizations/${orgId}/members`),
      ]);
      setRoles(rolesRes);
      setPermissions(permsRes);
      setMembers(membersRes.items);
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("security.error_roles_load"));
    }
  }, [orgId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  async function createRole() {
    if (!newRoleName.trim()) return;
    try {
      await api.post(`/organizations/${orgId}/rbac/roles`, { name: newRoleName });
      setNewRoleName("");
      await load();
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("security.error_role_create"));
    }
  }

  async function deleteRole(roleId: string) {
    await api.delete(`/organizations/${orgId}/rbac/roles/${roleId}`);
    await load();
  }

  async function togglePermission(role: CustomRole, permission: Permission) {
    const has = role.permission_keys.includes(permission.key);
    try {
      if (has) {
        await api.delete(`/organizations/${orgId}/rbac/roles/${role.id}/permissions/${permission.id}`);
      } else {
        await api.post(`/organizations/${orgId}/rbac/roles/${role.id}/permissions`, { permission_ids: [permission.id] });
      }
      await load();
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("security.error_permission"));
    }
  }

  async function assignRoleToUser(userId: string, roleId: string) {
    if (!roleId) return;
    await api.post(`/organizations/${orgId}/rbac/users/${userId}/roles`, { role_id: roleId });
  }

  const groupedPermissions = permissions.reduce<Record<string, Permission[]>>((acc, p) => {
    (acc[p.resource] ??= []).push(p);
    return acc;
  }, {});

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-sm font-semibold text-foreground">{t("security.roles.create_heading")}</h2>
        <p className="mt-1 text-xs text-foreground-muted">{t("security.roles.create_desc")}</p>
        <div className="mt-2 flex gap-2">
          <input value={newRoleName} onChange={(e) => setNewRoleName(e.target.value)} placeholder={t("security.roles.name_placeholder")} className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent" />
          <button type="button" onClick={() => void createRole()} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">{t("security.roles.create_button")}</button>
        </div>
      </div>

      {roles.map((role) => (
        <div key={role.id} className="rounded-xl border border-border bg-surface p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-foreground">{role.name}</h3>
            <button type="button" onClick={() => void deleteRole(role.id)} className="text-xs font-medium text-danger hover:underline">{t("security.roles.delete")}</button>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
            {Object.entries(groupedPermissions).map(([resource, perms]) => (
              <div key={resource} className="mb-2">
                <p className="text-xs font-semibold uppercase text-foreground-muted">{resource}</p>
                {perms.map((permission) => (
                  <label key={permission.id} className="flex items-center gap-1.5 text-xs text-foreground">
                    <input
                      type="checkbox"
                      checked={role.permission_keys.includes(permission.key)}
                      onChange={() => void togglePermission(role, permission)}
                    />
                    {permission.action}
                  </label>
                ))}
              </div>
            ))}
          </div>

          <div className="mt-3 border-t border-border pt-3">
            <p className="text-xs font-semibold text-foreground-muted">{t("security.roles.assign_to")}</p>
            <select
              defaultValue=""
              onChange={(e) => { void assignRoleToUser(e.target.value, role.id); e.target.value = ""; }}
              className="mt-1 rounded-lg border border-border bg-background px-2 py-1 text-xs"
            >
              <option value="" disabled>{t("security.roles.choose_member")}</option>
              {members.map((m) => (
                <option key={m.user_id} value={m.user_id}>{m.email}</option>
              ))}
            </select>
          </div>
        </div>
      ))}
    </div>
  );
}

function AuditLogTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const { t } = useTranslation();
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);

  const load = useCallback(async () => {
    try {
      const response = await api.get<{ items: AuditLogEntry[]; total: number }>(`/organizations/${orgId}/audit-logs?limit=50`);
      setLogs(response.items);
      setTotal(response.total);
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("security.error_audit_load"));
    }
  }, [orgId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm text-foreground-muted">{total} {t("security.audit.total")}</p>
        <a href={fileUrl(`/audit/export?fmt=csv`)} target="_blank" rel="noreferrer" className="text-xs font-medium text-accent hover:underline">{t("security.audit.export")}</a>
      </div>
      <div className="flex flex-col gap-1">
        {logs.map((log) => (
          <div key={log.id} className="flex items-center justify-between rounded-lg border border-border bg-surface px-3 py-2 text-xs">
            <span className="font-medium text-foreground">{log.action}</span>
            <span className="text-foreground-muted">{log.ip ?? "—"} · {new Date(log.timestamp).toLocaleString()}</span>
            <span className={log.success ? "text-success" : "text-danger"}>{log.success ? t("security.audit.success") : t("security.audit.failure")}</span>
          </div>
        ))}
        {logs.length === 0 && <p className="text-sm text-foreground-muted">{t("security.audit.empty")}</p>}
      </div>
    </div>
  );
}

function EncryptionTab({ onError }: { onError: (e: string) => void }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<{ enabled: boolean; algorithm: string; key_storage: string; encrypted_fields: string[]; last_rotation_at: string | null } | null>(null);
  const [restricted, setRestricted] = useState(false);
  const [rotating, setRotating] = useState(false);

  const load = useCallback(async () => {
    try {
      setStatus(await api.get("/encryption/status"));
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setRestricted(true);
      else onError(err instanceof ApiError ? String(err.detail) : t("security.error_encryption_load"));
    }
  }, [onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  async function rotate() {
    setRotating(true);
    try {
      await api.post("/encryption/rotate-keys");
      await load();
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("security.error_encryption_rotate"));
    } finally {
      setRotating(false);
    }
  }

  if (restricted) {
    return <p className="text-sm text-foreground-muted">{t("security.encryption.restricted")}</p>;
  }
  if (!status) {
    return <LoadingState fullScreen={false} />;
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <div className="flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${status.enabled ? "bg-success" : "bg-danger"}`} />
        <h2 className="text-sm font-semibold text-foreground">{status.enabled ? t("security.encryption.enabled") : t("security.encryption.disabled")}</h2>
      </div>
      <p className="mt-2 text-sm text-foreground-muted">{t("security.encryption.algorithm")} <span className="text-foreground">{status.algorithm}</span></p>
      <p className="text-sm text-foreground-muted">{t("security.encryption.key_storage")} <span className="text-foreground">{status.key_storage}</span></p>
      <p className="text-sm text-foreground-muted">{t("security.encryption.last_rotation")} <span className="text-foreground">{status.last_rotation_at ? new Date(status.last_rotation_at).toLocaleString() : t("security.encryption.never")}</span></p>
      <div className="mt-3">
        <p className="text-xs font-semibold text-foreground-muted">{t("security.encryption.fields")}</p>
        <ul className="mt-1 list-inside list-disc text-xs text-foreground-muted">
          {status.encrypted_fields.map((field) => <li key={field}>{field}</li>)}
        </ul>
      </div>
      <button type="button" onClick={() => void rotate()} disabled={rotating} className="mt-4 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
        {rotating ? t("security.encryption.rotating") : t("security.encryption.rotate")}
      </button>
    </div>
  );
}

function ComplianceTab({ onError }: { orgId: string; onError: (e: string) => void }) {
  const { t } = useTranslation();
  const [consents, setConsents] = useState<{ consent_type: string; granted: boolean }[]>([]);
  const [status, setStatus] = useState<{ pending_data_requests: number; unnotified_breaches: number; compliant: boolean } | null>(null);
  const [statusRestricted, setStatusRestricted] = useState(false);

  const load = useCallback(async () => {
    try {
      setConsents(await api.get("/compliance/consent"));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("security.error_consent_load"));
    }
    try {
      setStatus(await api.get("/compliance/status"));
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setStatusRestricted(true);
    }
  }, [onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  async function toggleConsent(type: string, granted: boolean) {
    if (granted) {
      await api.delete(`/compliance/consent/${type}`);
    } else {
      await api.post("/compliance/consent", { consent_type: type, granted: true });
    }
    await load();
  }

  const consentTypes = ["marketing", "analytics", "cookies"];
  const consentMap = new Map(consents.map((c) => [c.consent_type, c.granted]));

  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-sm font-semibold text-foreground">{t("security.compliance.my_data")}</h2>
        <p className="mt-1 text-xs text-foreground-muted">{t("security.compliance.my_data_desc")}</p>
        <div className="mt-3 flex gap-3">
          <a href={fileUrl("/compliance/data-export?fmt=json")} target="_blank" rel="noreferrer" className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-surface-muted">{t("security.compliance.export_data")}</a>
          <a href="/dashboard/profile" className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-surface-muted">{t("security.compliance.delete_account")}</a>
        </div>

        <div className="mt-4">
          <p className="text-xs font-semibold text-foreground-muted">{t("security.compliance.consent")}</p>
          {consentTypes.map((type) => (
            <label key={type} className="mt-1 flex items-center gap-2 text-sm text-foreground">
              <input type="checkbox" checked={consentMap.get(type) ?? false} onChange={() => void toggleConsent(type, consentMap.get(type) ?? false)} />
              {type.charAt(0).toUpperCase() + type.slice(1)}
            </label>
          ))}
        </div>
      </div>

      {!statusRestricted && status && (
        <div className="rounded-xl border border-border bg-surface p-5">
          <h2 className="text-sm font-semibold text-foreground">{t("security.compliance.org_status")}</h2>
          <p className="mt-2 text-sm"><span className={status.compliant ? "text-success" : "text-warning"}>{status.compliant ? t("security.compliance.compliant") : t("security.compliance.needs_attention")}</span></p>
          <p className="mt-1 text-xs text-foreground-muted">{status.pending_data_requests} {t("security.compliance.pending_requests")} · {status.unnotified_breaches} {t("security.compliance.unnotified_breaches")}</p>
        </div>
      )}
    </div>
  );
}

function ScanTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const { t } = useTranslation();
  const [scans, setScans] = useState<SecurityScan[]>([]);
  const [vulnerabilities, setVulnerabilities] = useState<Vulnerability[]>([]);
  const [running, setRunning] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [scansRes, vulnsRes] = await Promise.all([
        api.get<SecurityScan[]>(`/organizations/${orgId}/security/scans`),
        api.get<Vulnerability[]>(`/organizations/${orgId}/security/vulnerabilities?status_filter=open`),
      ]);
      setScans(scansRes);
      setVulnerabilities(vulnsRes);
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("security.error_scan_load"));
    }
  }, [orgId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  async function runScan(scanType: string) {
    setRunning(scanType);
    try {
      await api.post(`/organizations/${orgId}/security/scan`, { scan_type: scanType });
      await load();
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("security.error_scan_run"));
    } finally {
      setRunning(null);
    }
  }

  async function resolveVulnerability(id: string) {
    await api.patch(`/organizations/${orgId}/security/vulnerabilities/${id}`, { status: "resolved" });
    await load();
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap gap-2">
        {["dependency", "code", "secret", "container", "infrastructure"].map((type) => (
          <button key={type} type="button" onClick={() => void runScan(type)} disabled={running !== null} className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-surface-muted disabled:opacity-50">
            {running === type ? t("security.scan.running") : `${t("security.scan.run")} ${type}`}
          </button>
        ))}
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-foreground">{t("security.scan.open_vulns")}</h2>
        {vulnerabilities.length === 0 ? (
          <p className="text-sm text-foreground-muted">{t("security.scan.none_found")}</p>
        ) : (
          <div className="flex flex-col gap-2">
            {vulnerabilities.map((v) => (
              <div key={v.id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-3 text-xs">
                <div>
                  <span className="mr-2 rounded-full bg-danger-soft px-2 py-0.5 font-medium uppercase text-danger">{v.severity}</span>
                  <span className="text-foreground">{v.title}</span>
                  {v.location && <p className="mt-0.5 text-foreground-muted">{v.location}</p>}
                </div>
                <button type="button" onClick={() => void resolveVulnerability(v.id)} className="font-medium text-accent hover:underline">{t("security.scan.mark_resolved")}</button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-foreground">{t("security.scan.history")}</h2>
        <div className="flex flex-col gap-1">
          {scans.map((s) => (
            <div key={s.id} className="flex items-center justify-between rounded-lg border border-border bg-surface px-3 py-2 text-xs">
              <span className="font-medium text-foreground">{s.scan_type}</span>
              <span className="text-foreground-muted">{s.summary ?? s.status}</span>
              <span className="text-foreground-muted">{new Date(s.started_at).toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PoliciesTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const { t } = useTranslation();
  const [policy, setPolicy] = useState<SecurityPolicy | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setPolicy(await api.get(`/organizations/${orgId}/security/policies`));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("security.error_policies_load"));
    }
  }, [orgId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  async function save() {
    if (!policy) return;
    setSaving(true);
    try {
      setPolicy(await api.patch(`/organizations/${orgId}/security/policies`, policy));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("security.error_policies_save"));
    } finally {
      setSaving(false);
    }
  }

  if (!policy) return <LoadingState fullScreen={false} />;

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <label className="flex items-center gap-2 text-sm text-foreground">
        <input type="checkbox" checked={policy.require_2fa_for_admins} onChange={(e) => setPolicy({ ...policy, require_2fa_for_admins: e.target.checked })} />
        Exiger le 2FA pour les admins
      </label>
      <label className="flex items-center gap-2 text-sm text-foreground">
        <input type="checkbox" checked={policy.auto_lock_after_failed_attempts} onChange={(e) => setPolicy({ ...policy, auto_lock_after_failed_attempts: e.target.checked })} />
        Verrouiller automatiquement le compte après trop de tentatives échouées
      </label>

      <div className="mt-3 grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="policy-session-timeout" className="text-xs font-medium text-foreground-muted">{t("security.policies.session_timeout")}</label>
          <input id="policy-session-timeout" type="number" value={policy.session_timeout_minutes} onChange={(e) => setPolicy({ ...policy, session_timeout_minutes: Number(e.target.value) })} className="mt-1 w-full rounded-lg border border-border bg-background px-2 py-1 text-sm" />
        </div>
        <div>
          <label htmlFor="policy-max-login-attempts" className="text-xs font-medium text-foreground-muted">{t("security.policies.max_attempts")}</label>
          <input id="policy-max-login-attempts" type="number" value={policy.max_login_attempts} onChange={(e) => setPolicy({ ...policy, max_login_attempts: Number(e.target.value) })} className="mt-1 w-full rounded-lg border border-border bg-background px-2 py-1 text-sm" />
        </div>
      </div>

      <div className="mt-3">
        <label htmlFor="policy-ip-allowlist" className="text-xs font-medium text-foreground-muted">{t("security.policies.ip_allowlist")}</label>
        <textarea id="policy-ip-allowlist" value={policy.ip_allowlist ?? ""} onChange={(e) => setPolicy({ ...policy, ip_allowlist: e.target.value })} rows={3} className="mt-1 w-full rounded-lg border border-border bg-background px-2 py-1 text-sm" />
      </div>

      <button type="button" onClick={() => void save()} disabled={saving} className="mt-4 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
        {saving ? t("security.policies.saving") : t("security.policies.save")}
      </button>
    </div>
  );
}
