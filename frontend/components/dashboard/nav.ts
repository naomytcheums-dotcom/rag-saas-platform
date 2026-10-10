import {
  BookOpen, Bot, Building2, ChartColumn, Cpu, CreditCard, Crown, FileText, FlaskConical, KeyRound, LayoutDashboard, Lock, MessageSquare, Mic,
  Lightbulb, LifeBuoy, Plug, Puzzle, Settings2, ShieldCheck, SlidersHorizontal, Store, TrendingUp, User, Webhook, Workflow, type LucideIcon,
} from "lucide-react";

/** One icon per dashboard destination (same visual language as the Figma "Designo" sidebar). Unknown routes fall back to a generic icon. */
const ICONS: Record<string, LucideIcon> = {
  "/dashboard": LayoutDashboard,
  "/chat": MessageSquare,
  "/dashboard/documents": FileText,
  "/dashboard/agents": Bot,
  "/dashboard/autonomous-agents": Cpu,
  "/dashboard/workflows": Workflow,
  "/dashboard/fine-tuning": SlidersHorizontal,
  "/dashboard/analytics": ChartColumn,
  "/dashboard/eval": FlaskConical,
  "/dashboard/eval/evolution": TrendingUp,
  "/dashboard/quality": ShieldCheck,
  "/dashboard/voice-agent": Mic,
  "/dashboard/escalations": LifeBuoy,
  "/dashboard/insights": Lightbulb,
  "/dashboard/settings/api-keys": KeyRound,
  "/dashboard/settings/webhooks": Webhook,
  "/dashboard/settings/llm-config": Settings2,
  "/dashboard/api-docs": BookOpen,
  "/dashboard/settings/widget": Puzzle,
  "/dashboard/settings/integrations": Plug,
  "/dashboard/marketplace": Store,
  "/dashboard/profile": User,
  "/dashboard/settings/organization": Building2,
  "/dashboard/billing": CreditCard,
  "/dashboard/security": Lock,
  "/admin": Crown,
};

export function navIcon(href: string): LucideIcon {
  return ICONS[href] ?? LayoutDashboard;
}
