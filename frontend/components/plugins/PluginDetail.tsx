"use client";

import { useState } from "react";
import { usePlugin } from "@/lib/hooks/usePlugin";
import PluginInstallButton from "./PluginInstallButton";
import PluginLogs from "./PluginLogs";
import PluginReviewForm from "./PluginReviewForm";
import PluginReviews from "./PluginReviews";

interface PluginDetailProps {
  orgId: string;
  pluginId: string;
  currentUserId?: string;
  isInstalled?: boolean;
  onError?: (message: string) => void;
}

// Partie 16 (ter) -- one plugin's full detail: manifest info,
// permissions, real rating, reviews, install action, and (once
// installed) the real execution log.
export default function PluginDetail({ orgId, pluginId, currentUserId, isInstalled, onError }: PluginDetailProps) {
  const { plugin, rating, loading, reload } = usePlugin(pluginId);
  const [reviewsKey, setReviewsKey] = useState(0);

  if (loading) return <p className="text-sm text-foreground-muted">Loading…</p>;
  if (!plugin) return <p className="text-sm text-foreground-muted">Plugin not found.</p>;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold text-foreground">{plugin.name}</h2>
        <p className="mt-1 text-sm text-foreground-muted">{plugin.description}</p>
        <p className="mt-1 text-xs text-foreground-muted">
          v{plugin.version} &middot; {plugin.category} &middot; {plugin.install_count} installs
          {rating?.average_rating != null && ` · ${rating.average_rating}/5 (${rating.review_count})`}
        </p>
        <p className="mt-2 text-xs text-foreground-muted">Permissions: {plugin.manifest.permissions.join(", ") || "none"}</p>
        {plugin.manifest.hooks && plugin.manifest.hooks.length > 0 && (
          <p className="mt-1 text-xs text-foreground-muted">Hooks: {plugin.manifest.hooks.join(", ")}</p>
        )}
        {!isInstalled && <div className="mt-3"><PluginInstallButton orgId={orgId} pluginId={plugin.id} onError={onError} /></div>}
      </div>

      {isInstalled && <PluginLogs orgId={orgId} pluginId={plugin.id} onError={onError} />}

      <div>
        <h3 className="text-sm font-semibold text-foreground">Reviews</h3>
        <div className="mt-2">
          <PluginReviews pluginId={plugin.id} currentUserId={currentUserId} onError={onError} refreshKey={reviewsKey} />
        </div>
        <div className="mt-3">
          <PluginReviewForm
            orgId={orgId}
            pluginId={plugin.id}
            onSubmitted={() => {
              setReviewsKey((k) => k + 1);
              void reload();
            }}
            onError={onError}
          />
        </div>
      </div>
    </div>
  );
}
