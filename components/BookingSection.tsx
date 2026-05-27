"use client";

import { useEffect } from "react";
import { getCalApi } from "@calcom/embed-react";
import Cal from "@calcom/embed-react";
import { ClipboardList, Clock, Search } from "lucide-react";
import { siteConfig } from "@/lib/site";

export function BookingSection() {
  useEffect(() => {
    (async () => {
      const cal = await getCalApi({ namespace: "salon-audit" });
      cal("ui", {
        theme: "dark",
        hideEventTypeDetails: false,
        layout: "month_view",
        cssVarsPerTheme: {
          dark: {
            "cal-brand": "#ff2e7a",
            "cal-bg": "#0b0b10",
            "cal-bg-muted": "#11111a",
            "cal-text": "#f6f6f7",
            "cal-text-emphasis": "#ffffff",
            "cal-border": "rgba(255,255,255,0.08)"
          }
        }
      });
    })();
  }, []);

  return (
    <section id="book" className="relative py-16 sm:py-24">
      <div className="container-px mx-auto max-w-6xl">
        <div className="grid gap-10 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-400">
              Free audit
            </p>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
              Book your free 20-min{" "}
              <span className="gradient-text">automation audit.</span>
            </h2>
            <p className="mt-4 text-ink-100/70">
              In 20 minutes we’ll review how you currently handle bookings,
              identify where you’re leaking time and revenue, and recommend
              exactly what to automate first. No pressure to hire us.
            </p>

            <ul className="mt-8 space-y-3 text-sm">
              <Bullet icon={Clock}>20-minute call on Google Meet or Zoom</Bullet>
              <Bullet icon={Search}>
                Live review of your current WhatsApp / booking flow & bottlenecks
              </Bullet>
              <Bullet icon={ClipboardList}>
                A written summary with an estimated revenue-loss number and
                prioritised next steps — yours to keep
              </Bullet>
            </ul>

            <p className="mt-8 text-xs text-ink-100/50">
              Available for salons, spas and beauty businesses in{" "}
              {siteConfig.cities.slice(0, -1).join(", ")} &{" "}
              {siteConfig.cities.slice(-1)}.
            </p>
          </div>

          <div className="lg:col-span-3">
            <div className="overflow-hidden rounded-3xl border border-white/10 bg-ink-950/60 shadow-glow">
              <Cal
                namespace="salon-audit"
                calLink={siteConfig.calLink}
                style={{ width: "100%", height: "640px", overflow: "scroll" }}
                config={{ layout: "month_view", theme: "dark" }}
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Bullet({
  icon: Icon,
  children
}: {
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <li className="flex items-start gap-3">
      <span className="mt-0.5 grid h-7 w-7 place-items-center rounded-lg bg-brand-500/15 text-brand-400 ring-1 ring-brand-500/30">
        <Icon className="h-4 w-4" />
      </span>
      <span className="text-ink-100/85">{children}</span>
    </li>
  );
}
