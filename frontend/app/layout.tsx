import type { Metadata } from "next";
import CookieBanner from "@/components/CookieBanner";
import { AuthProvider } from "@/lib/auth";
import { I18nProvider } from "@/lib/i18n";
import "./globals.css";

export const metadata: Metadata = {
  title: "RAG SaaS Platform",
  description: "Multi-tenant RAG SaaS chat interface",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        <I18nProvider>
          <AuthProvider>{children}</AuthProvider>
        </I18nProvider>
        <CookieBanner />
      </body>
    </html>
  );
}
