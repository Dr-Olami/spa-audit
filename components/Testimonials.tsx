import { Quote } from "lucide-react";

const quotes = [
  {
    name: "Adaeze O.",
    business: "Braid studio · Lekki, Lagos",
    text:
      "I used to lose at least 4 bookings a week to slow replies. The bot now handles all of that while I’m in the chair."
  },
  {
    name: "Hauwa M.",
    business: "Bridal makeup · Abuja",
    text:
      "Deposits are now automatic. No-shows dropped to almost zero in my first month."
  },
  {
    name: "Chioma N.",
    business: "Day spa · Wuse, Abuja",
    text:
      "Massage and facial bookings used to be a mess of voice notes. Now clients book and pay deposits themselves. Game changer."
  }
];

export function Testimonials() {
  return (
    <section className="relative py-16 sm:py-24">
      <div className="container-px mx-auto max-w-6xl">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-400">
            Loved by salon owners
          </p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
            Built for the modern Nigerian salon, spa & beauty business
          </h2>
        </div>

        <div className="mt-12 grid gap-4 md:grid-cols-3">
          {quotes.map((q) => (
            <figure key={q.name} className="glass rounded-2xl p-6">
              <Quote className="h-5 w-5 text-brand-400" />
              <blockquote className="mt-4 text-sm leading-relaxed text-ink-100/85">
                “{q.text}”
              </blockquote>
              <figcaption className="mt-5 text-sm">
                <p className="font-semibold">{q.name}</p>
                <p className="text-ink-100/60">{q.business}</p>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}
