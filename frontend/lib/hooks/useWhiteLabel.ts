"use client";

import { useCallback, useEffect, useState } from "react";
import * as whiteLabelService from "@/lib/services/whitelabel";
import type { WhiteLabelConfig, WhiteLabelConfigUpdate } from "@/lib/services/whitelabel";

export function useWhiteLabel(orgId: string) {
  const [config, setConfig] = useState<WhiteLabelConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setConfig(await whiteLabelService.getWhiteLabelConfig(orgId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load white-label config");
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void reload();
  }, [reload]);

  const update = useCallback(async (data: WhiteLabelConfigUpdate) => {
    const updated = await whiteLabelService.updateWhiteLabelConfig(orgId, data);
    setConfig(updated);
    return updated;
  }, [orgId]);

  const uploadLogo = useCallback(async (file: File) => {
    const updated = await whiteLabelService.uploadLogo(orgId, file);
    setConfig(updated);
    return updated;
  }, [orgId]);

  const removeLogo = useCallback(async () => {
    const updated = await whiteLabelService.removeLogo(orgId);
    setConfig(updated);
    return updated;
  }, [orgId]);

  const uploadFavicon = useCallback(async (file: File) => {
    const updated = await whiteLabelService.uploadFavicon(orgId, file);
    setConfig(updated);
    return updated;
  }, [orgId]);

  const setDomain = useCallback(async (domain: string) => {
    const updated = await whiteLabelService.setCustomDomain(orgId, domain);
    setConfig(updated);
    return updated;
  }, [orgId]);

  const removeDomain = useCallback(async () => {
    const updated = await whiteLabelService.removeCustomDomain(orgId);
    setConfig(updated);
    return updated;
  }, [orgId]);

  const verifyDomain = useCallback(async () => {
    const updated = await whiteLabelService.verifyDomain(orgId);
    setConfig(updated);
    return updated;
  }, [orgId]);

  const configureEmail = useCallback(async (data: { sender_name: string; sender_email: string }) => {
    const updated = await whiteLabelService.configureEmail(orgId, data);
    setConfig(updated);
    return updated;
  }, [orgId]);

  const removeEmail = useCallback(async () => {
    const updated = await whiteLabelService.removeEmailConfig(orgId);
    setConfig(updated);
    return updated;
  }, [orgId]);

  const reset = useCallback(async () => {
    const updated = await whiteLabelService.resetWhiteLabel(orgId);
    setConfig(updated);
    return updated;
  }, [orgId]);

  return {
    config, loading, error, reload, update, uploadLogo, removeLogo, uploadFavicon,
    setDomain, removeDomain, verifyDomain, configureEmail, removeEmail, reset,
  };
}
