"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

interface Member {
  user_id: string;
  email: string;
  role: string;
  joined_at: string;
}

export default function OrganizationSettingsPage() {
  const { org } = useCurrentOrg();
  const [name, setName] = useState("");
  const [members, setMembers] = useState<Member[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);

  const load = useCallback(async () => {
    if (!org) return;
    setName(org.name);
    try {
      const data = await api.get<{ items: Member[] }>(`/organizations/${org.id}/members`);
      setMembers(data.items);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Échec du chargement des membres");
    }
  }, [org]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  async function saveName() {
    if (!org) return;
    setSaving(true);
    setError(null);
    try {
      await api.patch(`/organizations/${org.id}`, { name });
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2000);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Échec de l'enregistrement");
    } finally {
      setSaving(false);
    }
  }

  async function invite() {
    if (!org || !inviteEmail.trim()) return;
    setError(null);
    try {
      await api.post(`/organizations/${org.id}/members/invite`, { email: inviteEmail, role: inviteRole });
      setInviteEmail("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Échec de l'invitation du membre");
    }
  }

  async function removeMember(userId: string) {
    if (!org) return;
    await api.delete(`/organizations/${org.id}/members/${userId}`);
    await load();
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-xl font-semibold text-foreground">Paramètres de l&apos;organisation</h1>

      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {savedFlash && <p className="mt-4 rounded-lg bg-success-soft px-3 py-2 text-sm text-success">Enregistré !</p>}

      <div className="mt-6 rounded-xl border border-border bg-surface p-4">
        <h2 className="text-sm font-semibold text-foreground">Nom</h2>
        <div className="mt-2 flex gap-2">
          <input value={name} onChange={(e) => setName(e.target.value)} className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent" />
          <button type="button" onClick={() => void saveName()} disabled={saving} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
            {saving ? "Enregistrement…" : "Enregistrer"}
          </button>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-border bg-surface p-4">
        <h2 className="text-sm font-semibold text-foreground">Inviter un membre</h2>
        <div className="mt-2 flex gap-2">
          <input value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="collegue@exemple.com" className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent" />
          <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)} className="rounded-lg border border-border bg-background px-2 text-sm">
            <option value="member">Membre</option>
            <option value="admin">Admin</option>
            <option value="viewer">Lecteur</option>
          </select>
          <button type="button" onClick={() => void invite()} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">Inviter</button>
        </div>
      </div>

      <div className="mt-6">
        <h2 className="mb-2 text-sm font-semibold text-foreground">Membres</h2>
        <div className="flex flex-col gap-2">
          {members.map((member) => (
            <div key={member.user_id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-3">
              <div>
                <p className="text-sm font-medium text-foreground">{member.email}</p>
                <p className="text-xs text-foreground-muted">{member.role}</p>
              </div>
              {member.role !== "owner" && (
                <button type="button" onClick={() => void removeMember(member.user_id)} className="text-xs font-medium text-danger hover:underline">Retirer</button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
