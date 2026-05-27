"use client";

import { ArrowRight, Clock3, ShieldCheck, Sparkles } from "lucide-react";

export function Hero() {
  return (
    <section className="hero-glow relative overflow-hidden">
      <div className="absolute inset-0 bg-grid-faint [background-size:36px_36px] opacity-30" />
      <div className="container-px relative mx-auto max-w-6xl pb-16 pt-14 sm:pb-24 sm:pt-20">
        <div className="mx-auto max-w-3xl text-center">
          <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-ink-100/80">
            <span className="h-1.5 w-1.5 animate-pulse-slow rounded-full bg-brand-400" />
            Built for salons, spas & beauty businesses in Lagos, Abuja & beyond
          </div>

          <h1 className="mt-6 font-display text-4xl font-semibold leading-[1.1] tracking-tight text-balance sm:text-5xl md:text-6xl">
            Stop losing bookings while you’re{" "}
            <span className="gradient-text">with a client.</span>
          </h1>

          <p className="mx-auto mt-5 max-w-xl text-balance text-base text-ink-100/70 sm:text-lg">
            For salons, spas and beauty businesses in Nigeria. Let AI answer your
            WhatsApp, send your price list, book appointments, and collect
            Paystack/Flutterwave deposits — 24/7. Even when your hands are full.
          </p>

          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a
              href="#book"
              className="group inline-flex w-full items-center justify-center gap-2 rounded-full bg-brand-500 px-6 py-3.5 text-sm font-semibold text-white shadow-glow transition hover:bg-brand-600 sm:w-auto"
            >
              Book a free audit
              <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
            </a>
            <a
              href="#demo"
              className="inline-flex w-full items-center justify-center gap-2 rounded-full border border-white/15 bg-white/5 px-6 py-3.5 text-sm font-semibold text-white transition hover:bg-white/10 sm:w-auto"
            >
              <Sparkles className="h-4 w-4" />
              Try the live demo
            </a>
          </div>

          <div className="mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-ink-100/60">
            <span className="inline-flex items-center gap-1.5">
              <Clock3 className="h-3.5 w-3.5 text-brand-400" />
              20 minutes, no obligation
            </span>
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 text-brand-400" />
              Keep your existing WhatsApp number
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-brand-400" />
              Get a written automation blueprint
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
