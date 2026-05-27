import { Check, X } from "lucide-react";

const chaos = [
  { from: "client", text: "Hi, how much for knotless braids?" },
  { from: "client", text: "Hello? Are you there?" },
  { from: "client", text: "Never mind, I’ll try another salon 😒" },
  { from: "you", text: "(5 hours later) Hi dear, sorry I was busy…" }
];

const calm = [
  { from: "client", text: "Hi, how much for knotless braids?" },
  {
    from: "bot",
    text:
      "Hi love! 💖 Knotless braids start from ₦25,000 (waist length). Here’s our full price list 👉"
  },
  {
    from: "bot",
    text:
      "Want to book? Pick a slot here: salon.link/book — a ₦5,000 deposit secures it via Paystack."
  },
  { from: "client", text: "Booked ✅ deposit sent!" }
];

export function ProblemSolution() {
  return (
    <section id="how-it-works" className="relative py-16 sm:py-24">
      <div className="container-px mx-auto max-w-6xl">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-400">
            The difference
          </p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
            Your DMs right now vs. your DMs with AI
          </h2>
          <p className="mt-3 text-ink-100/70">
            Whether you run a salon, spa or beauty studio — every reply you miss
            is ₦15,000–₦50,000 walking to a competitor.
          </p>
        </div>

        <div className="mt-12 grid gap-6 md:grid-cols-2">
          <PhoneCard title="Without automation" tone="bad" messages={chaos} />
          <PhoneCard title="With SalonAutomate" tone="good" messages={calm} />
        </div>
      </div>
    </section>
  );
}

function PhoneCard({
  title,
  tone,
  messages
}: {
  title: string;
  tone: "good" | "bad";
  messages: { from: string; text: string }[];
}) {
  const Icon = tone === "good" ? Check : X;
  const ring =
    tone === "good"
      ? "ring-1 ring-brand-500/40 shadow-glow"
      : "ring-1 ring-white/10";

  return (
    <div className={`glass rounded-3xl p-5 sm:p-6 ${ring}`}>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-display text-lg font-semibold">{title}</h3>
        <span
          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
            tone === "good"
              ? "bg-emerald-500/15 text-emerald-300"
              : "bg-red-500/15 text-red-300"
          }`}
        >
          <Icon className="h-3.5 w-3.5" />
          {tone === "good" ? "Booked" : "Lost client"}
        </span>
      </div>

      <div className="space-y-2.5 rounded-2xl bg-ink-950/60 p-4">
        {messages.map((m, i) => (
          <Bubble key={i} from={m.from} text={m.text} />
        ))}
      </div>
    </div>
  );
}

function Bubble({ from, text }: { from: string; text: string }) {
  const isYou = from === "you" || from === "bot";
  const bg =
    from === "bot"
      ? "bg-brand-500 text-white"
      : isYou
      ? "bg-white/10 text-white"
      : "bg-white text-ink-950";
  const align = isYou ? "ml-auto" : "";
  return (
    <div
      className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-sm leading-snug ${bg} ${align}`}
    >
      {text}
    </div>
  );
}
