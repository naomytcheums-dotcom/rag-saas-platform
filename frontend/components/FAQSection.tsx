"use client";

import { useState } from "react";

// Answers describe real, already-shipped behavior of this app (see the
// linked backend/frontend code for each), not marketing claims about
// features that don't exist yet.
const FAQ_ITEMS = [
  {
    question: "Quels formats de documents puis-je envoyer ?",
    answer: "PDF, DOCX, TXT, Markdown, HTML, CSV, JSON, XML et EPUB. Chaque document est automatiquement découpé, vectorisé et indexé pour la recherche sémantique.",
  },
  {
    question: "Mes données sont-elles utilisées pour entraîner un modèle tiers ?",
    answer: "Non. Vos documents servent uniquement à ancrer les réponses de vos propres agents (retrieval-augmented generation), pas à entraîner un modèle partagé avec d'autres clients.",
  },
  {
    question: "Puis-je déployer un agent sur mon propre site web ?",
    answer: "Oui, via un widget de chat embarquable (une seule balise script) personnalisable en couleurs, position et message d'accueil, ou via l'API publique pour une intégration sur mesure.",
  },
  {
    question: "Le produit gère-t-il plusieurs organisations et rôles ?",
    answer: "Oui : organisations multi-tenant, rôles Propriétaire/Admin/Manager/Membre/Lecteur, et la possibilité de créer des rôles personnalisés avec des permissions précises.",
  },
  {
    question: "Que se passe-t-il si je dépasse mon forfait ?",
    answer: "Vous êtes prévenu avant d'atteindre vos limites (documents, agents, membres). Vous pouvez changer de forfait à tout moment depuis votre tableau de bord, sans perte de données.",
  },
  {
    question: "Comment sont protégées mes données ?",
    answer: "Chiffrement des champs sensibles, authentification à deux facteurs, journal d'audit complet, et conformité RGPD/CCPA (export et suppression de vos données à la demande).",
  },
];

export default function FAQSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <section className="mt-28">
      <h2 className="text-center text-2xl font-semibold text-foreground">Questions fréquentes</h2>
      <div className="mx-auto mt-8 flex max-w-2xl flex-col gap-2">
        {FAQ_ITEMS.map((item, index) => {
          const open = openIndex === index;
          return (
            <div key={item.question} className="rounded-xl border border-border bg-surface">
              <button
                type="button"
                onClick={() => setOpenIndex(open ? null : index)}
                aria-expanded={open}
                className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left text-sm font-medium text-foreground"
              >
                {item.question}
                <span aria-hidden="true" className={`shrink-0 text-foreground-muted transition-transform ${open ? "rotate-180" : ""}`}>▾</span>
              </button>
              {open && <p className="px-5 pb-4 text-sm text-foreground-muted">{item.answer}</p>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
