import {
  CalendarCheck,
  CreditCard,
  Clock4,
  MessagesSquare,
  Bell,
  BarChart3
} from "lucide-react";

const items = [
  {
    icon: MessagesSquare,
    title: "Replies in seconds, 24/7",
    body:
      "Your AI assistant answers prices, services and FAQs the moment a client messages — even at 2am."
  },
  {
    icon: CalendarCheck,
    title: "Smart booking calendar",
    body:
      "Clients pick a slot themselves. No more back-and-forth. Double-bookings? Impossible."
  },
  {
    icon: CreditCard,
    title: "Paystack & Flutterwave deposits",
    body:
      "Auto-collect a deposit to secure every slot. Say goodbye to no-shows costing you hours."
  },
  {
    icon: Bell,
    title: "Automatic reminders",
    body:
      "WhatsApp and SMS reminders 24h and 1h before — in your own brand voice."
  },
  {
    icon: Clock4,
    title: "Set up in under a week",
    body:
      "Keep your existing WhatsApp number. We handle the setup — you keep doing what you do best."
  },
  {
    icon: BarChart3,
    title: "See what you’re earning",
    body:
      "Simple dashboard: bookings this week, revenue collected, top services."
  }
];

export function Features() {
  return (
    <section className="relative py-16 sm:py-24">
      <div className="container-px mx-auto max-w-6xl">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-400">
            What you get
          </p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
            Everything a modern Nigerian salon or spa needs
          </h2>
        </div>

        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map(({ icon: Icon, title, body }) => (
            <div
              key={title}
              className="glass group rounded-2xl p-6 transition hover:border-brand-500/40"
            >
              <div className="mb-4 inline-grid h-10 w-10 place-items-center rounded-xl bg-brand-500/15 text-brand-400 ring-1 ring-brand-500/30">
                <Icon className="h-5 w-5" />
              </div>
              <h3 className="font-display text-lg font-semibold">{title}</h3>
              <p className="mt-2 text-sm text-ink-100/70">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
