"use client";

import { useCallback, useEffect, useState } from "react";
import LoadingState from "@/components/LoadingState";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useTranslation } from "@/lib/i18n";

interface Workspace { id: string; name: string }
interface Team { id: string; name: string; description: string | null }
interface Member { user_id: string; email: string; role: string }

/** Specs 1.3.2 (workspaces) and 1.3.3 (teams): create, rename, delete and, for teams, manage members by e-mail. The routes exist in
 * api/routers/workspaces.py and api/routers/teams.py; this is the screen that was missing. */
export default function TeamsPage() {
  const { org } = useCurrentOrg();
  const { t } = useTranslation();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [members, setMembers] = useState<Record<string, Member[]>>({});
  const [openTeam, setOpenTeam] = useState<string | null>(null);
  const [workspaceName, setWorkspaceName] = useState("");
  const [teamName, setTeamName] = useState("");
  const [memberEmail, setMemberEmail] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!org) return;
    try {
      const [w, tm] = await Promise.all([
        api.get<{ items: Workspace[] }>(`/organizations/${org.id}/workspaces`),
        api.get<{ items: Team[] }>(`/organizations/${org.id}/teams`),
      ]);
      setWorkspaces(w.items);
      setTeams(tm.items);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("teams.error_load"));
    } finally {
      setLoading(false);
    }
  }, [org, t]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with the backend API after mount.
    void load();
  }, [load]);

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("teams.error_action"));
    }
  }

  async function toggleTeam(team: Team) {
    if (openTeam === team.id) { setOpenTeam(null); return; }
    setOpenTeam(team.id);
    try {
      const data = await api.get<{ items: Member[] }>(`/teams/${team.id}/members`);
      setMembers((prev) => ({ ...prev, [team.id]: data.items }));
    } catch {
      setMembers((prev) => ({ ...prev, [team.id]: [] }));
    }
  }

  async function addMember(team: Team) {
    await api.post(`/teams/${team.id}/members`, { email: memberEmail.trim(), role: "member" });
    setMemberEmail("");
    const data = await api.get<{ items: Member[] }>(`/teams/${team.id}/members`);
    setMembers((prev) => ({ ...prev, [team.id]: data.items }));
  }

  async function removeMember(team: Team, userId: string) {
    await api.delete(`/teams/${team.id}/members/${userId}`);
    const data = await api.get<{ items: Member[] }>(`/teams/${team.id}/members`);
    setMembers((prev) => ({ ...prev, [team.id]: data.items }));
  }

  const card = "rounded-xl border border-border bg-surface p-4";
  const input = "rounded-lg border border-border bg-background px-2 py-1 text-sm";
  const btn = "rounded-lg border border-border px-3 py-1 text-xs hover:bg-surface-muted disabled:opacity-50";

  if (loading) return <LoadingState fullScreen={false} />;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">{t("teams.title")}</h1>
        <p className="mt-1 text-sm text-foreground-muted">{t("teams.subtitle")}</p>
      </div>
      {error && <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

      <section className={card}>
        <h2 className="mb-2 text-sm font-semibold text-foreground">{t("teams.workspaces")}</h2>
        {workspaces.length === 0 ? <p className="text-sm text-foreground-muted">{t("teams.no_workspaces")}</p> : (
          <ul className="space-y-1">
            {workspaces.map((w) => (
              <li key={w.id} className="flex items-center justify-between text-sm text-foreground">
                {w.name}
                <button type="button" className="text-xs text-danger hover:underline" onClick={() => void run(() => api.delete(`/workspaces/${w.id}`))}>{t("teams.delete")}</button>
              </li>
            ))}
          </ul>
        )}
        <div className="mt-3 flex gap-2">
          <input aria-label={t("teams.workspace_name")} placeholder={t("teams.workspace_name")} value={workspaceName} onChange={(e) => setWorkspaceName(e.target.value)} className={input} />
          <button type="button" className={btn} disabled={!workspaceName.trim()} onClick={() => void run(async () => { await api.post(`/organizations/${org?.id}/workspaces`, { name: workspaceName.trim() }); setWorkspaceName(""); })}>{t("teams.create")}</button>
        </div>
      </section>

      <section className={card}>
        <h2 className="mb-2 text-sm font-semibold text-foreground">{t("teams.teams")}</h2>
        {teams.length === 0 ? <p className="text-sm text-foreground-muted">{t("teams.no_teams")}</p> : (
          <ul className="space-y-2">
            {teams.map((team) => (
              <li key={team.id} className="rounded-lg border border-border p-2">
                <div className="flex items-center justify-between text-sm text-foreground">
                  <button type="button" className="font-medium hover:underline" onClick={() => void toggleTeam(team)}>{team.name}</button>
                  <button type="button" className="text-xs text-danger hover:underline" onClick={() => void run(() => api.delete(`/teams/${team.id}`))}>{t("teams.delete")}</button>
                </div>
                {openTeam === team.id && (
                  <div className="mt-2 space-y-2 text-sm">
                    <ul className="space-y-1">
                      {(members[team.id] ?? []).map((m) => (
                        <li key={m.user_id} className="flex items-center justify-between">
                          <span>{m.email} <span className="text-foreground-muted">({m.role})</span></span>
                          <button type="button" className="text-xs text-danger hover:underline" onClick={() => void run(() => removeMember(team, m.user_id))}>{t("teams.remove")}</button>
                        </li>
                      ))}
                      {(members[team.id] ?? []).length === 0 && <li className="text-foreground-muted">{t("teams.no_members")}</li>}
                    </ul>
                    <div className="flex gap-2">
                      <input aria-label={t("teams.member_email")} placeholder={t("teams.member_email")} type="email" value={memberEmail} onChange={(e) => setMemberEmail(e.target.value)} className={input} />
                      <button type="button" className={btn} disabled={!memberEmail.trim()} onClick={() => void run(() => addMember(team))}>{t("teams.add_member")}</button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
        <div className="mt-3 flex gap-2">
          <input aria-label={t("teams.team_name")} placeholder={t("teams.team_name")} value={teamName} onChange={(e) => setTeamName(e.target.value)} className={input} />
          <button type="button" className={btn} disabled={!teamName.trim()} onClick={() => void run(async () => { await api.post(`/organizations/${org?.id}/teams`, { name: teamName.trim() }); setTeamName(""); })}>{t("teams.create")}</button>
        </div>
      </section>
    </div>
  );
}
