"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

const faqs = [
  {
    q: "Do I need a new WhatsApp number?",
    a: "No. We connect to your existing business WhatsApp number so your clients see the same brand and chat history."
  },
  {
    q: "How long does setup take?",
    a: "Most salons and spas are live within 5–7 days. We handle the entire setup, including your price list, services, and deposit flow."
  },
  {
    q: "Will the AI sound robotic?",
    a: "No. We train it on your tone, slang, and emojis. Your clients usually can’t tell it’s AI unless you tell them."
  },
  {
    q: "What does the free audit include?",
    a: "A 20-minute call where we map exactly how much time and money you’re losing to manual DMs, and give you a blueprint — whether you hire us or not."
  },
  {
    q: "How much does it cost after the audit?",
    a: "Pricing depends on your business size and services, but most salons and spas pay less than the cost of 2 missed bookings per month."
  },
  {
    q: "Do you support Paystack and Flutterwave?",
    a: "Yes — both, plus bank transfer confirmations. Deposits land directly in your existing account."
  }
];

export function FAQ() {
  return (
    <section id="faq" className="relative py-16 sm:py-24">
      <div className="container-px mx-auto max-w-3xl">
        <div className="text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-400">
            FAQ
          </p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
            Questions salon & spa owners always ask
          </h2>
        </div>

        <div className="mt-10 divide-y divide-white/10 rounded-2xl border border-white/10 bg-white/[0.02]">
          {faqs.map((f, i) => (
            <Item key={i} q={f.q} a={f.a} />
          ))}
        </div>
      </div>
    </section>
  );
}

function Item({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <button
      type="button"
      onClick={() => setOpen((v) => !v)}
      className="block w-full px-5 py-5 text-left"
      aria-expanded={open}
    >
      <div className="flex items-start justify-between gap-4">
        <span className="font-medium">{q}</span>
        <ChevronDown
          className={`mt-0.5 h-5 w-5 shrink-0 text-ink-100/60 transition ${
            open ? "rotate-180 text-brand-400" : ""
          }`}
        />
      </div>
      <div
        className={`grid transition-all duration-300 ${
          open ? "mt-3 grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
        }`}
      >
        <p className="overflow-hidden text-sm text-ink-100/70">{a}</p>
      </div>
    </button>
  );
}
