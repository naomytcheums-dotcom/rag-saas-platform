"use client";

import { useEffect, useState } from "react";
import Telephony from "@/components/Telephony";
import VoiceSettings from "@/components/VoiceSettings";
import { api } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useTranslation } from "@/lib/i18n";

/** Specs 8.2.8 / 8.2.9 (voice settings and voice choice) and 8.2.13 (telephony). The components existed but no page mounted them. */
export default function VoiceSettingsPage() {
  const { org } = useCurrentOrg();
  const { t } = useTranslation();
  const [agentId, setAgentId] = useState<string | null>(null);

  useEffect(() => {
    if (!org) return;
    void api.get<{ id: string }[]>(`/organizations/${org.id}/agents`).then((agents) => setAgentId(agents[0]?.id ?? null)).catch(() => setAgentId(null));
  }, [org]);

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <section className="space-y-3">
        <h1 className="text-xl font-semibold text-foreground">{t("voice_agent.settings_title")}</h1>
        <VoiceSettings />
      </section>
      {org && agentId && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-foreground">{t("voice_agent.telephony_title")}</h2>
          <Telephony orgId={org.id} agentId={agentId} />
        </section>
      )}
    </div>
  );
}
