"use client";

import { useEffect, useRef, useState } from "react";
import { Send, Bot } from "lucide-react";

type Msg = { id: number; from: "user" | "bot"; text: string };

const SUGGESTIONS = [
  "How much for a full body massage?",
  "Do you do facials this weekend?",
  "How much for knotless braids?",
  "Book an appointment for Saturday"
];

const RESPONSES: Record<string, string> = {
  massage:
    "Our Swedish full body massage is ₦18,000 (60 min) or ₦25,000 (90 min). I can hold a slot with a ₦5,000 Paystack deposit — want me to book you?",
  facial:
    "Yes ✨ Hydrating facial is ₦15,000 (45 min). We have Saturday 11am and Sunday 2pm open this weekend. Which works?",
  braid:
    "Knotless braids start at ₦25,000 (shoulder) up to ₦45,000 (waist). I can hold a slot with a ₦5,000 Paystack deposit. Want me to book you?",
  nails:
    "Gel manicure is ₦8,000 and pedicure is ₦10,000. Combo with both is ₦15,000 (saves you ₦3,000). Should I find you a slot?",
  makeup:
    "Bridal makeup is ₦60,000 and includes a trial session. We have Saturdays open this month — should I check times?",
  book:
    "Lovely 💖 Here are the next 3 slots: Sat 10am, Sat 2pm, Sun 11am. Reply with one and I’ll send the deposit link.",
  location:
    "We’re at 14B Admiralty Way, Lekki Phase 1, Lagos. Free parking after 5pm. Want directions on Google Maps?",
  default:
    "Got it! I can share prices, availability, location and collect a deposit to lock your slot. What would you like to do?"
};

function reply(q: string) {
  const t = q.toLowerCase();
  if (/(massage|spa|relax|deep tissue|swedish)/.test(t)) return RESPONSES.massage;
  if (/(facial|skin|glow)/.test(t)) return RESPONSES.facial;
  if (/(braid|hair|knotless|cornrow|weave)/.test(t)) return RESPONSES.braid;
  if (/(nail|mani|pedi|gel)/.test(t)) return RESPONSES.nails;
  if (/(makeup|bridal|wedding)/.test(t)) return RESPONSES.makeup;
  if (/(book|appointment|slot|saturday|sunday)/.test(t)) return RESPONSES.book;
  if (/(where|location|address|find)/.test(t)) return RESPONSES.location;
  return RESPONSES.default;
}

export function DemoChat() {
  const [messages, setMessages] = useState<Msg[]>([
    {
      id: 0,
      from: "bot",
      text: "Hi 👋 I’m the salon’s AI assistant. Ask me anything — prices, booking, location."
    }
  ]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, typing]);

  function send(text: string) {
    const q = text.trim();
    if (!q) return;
    setInput("");
    setMessages((m) => [...m, { id: m.length, from: "user", text: q }]);
    setTyping(true);
    setTimeout(() => {
      setMessages((m) => [
        ...m,
        { id: m.length, from: "bot", text: reply(q) }
      ]);
      setTyping(false);
    }, 750);
  }

  return (
    <section id="demo" className="relative py-16 sm:py-24">
      <div className="container-px mx-auto max-w-3xl">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-400">
            Try it now
          </p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
            Test the AI before you book the call
          </h2>
          <p className="mt-3 text-ink-100/70">
            A live preview of how the bot would talk to your clients on
            WhatsApp — whether you run a salon, spa or beauty studio.
          </p>
        </div>

        <div className="mt-10 overflow-hidden rounded-3xl border border-white/10 bg-ink-950/60 shadow-glow">
          <div className="flex items-center gap-3 border-b border-white/10 bg-white/5 px-4 py-3">
            <span className="grid h-9 w-9 place-items-center rounded-full bg-brand-500">
              <Bot className="h-4 w-4 text-white" />
            </span>
            <div className="leading-tight">
              <p className="text-sm font-semibold">Salon AI Assistant</p>
              <p className="text-xs text-emerald-400">● online · replies in seconds</p>
            </div>
          </div>

          <div className="max-h-[420px] min-h-[280px] space-y-2.5 overflow-y-auto p-4">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-sm ${
                  m.from === "bot"
                    ? "bg-white/10 text-white"
                    : "ml-auto bg-brand-500 text-white"
                }`}
              >
                {m.text}
              </div>
            ))}
            {typing && (
              <div className="max-w-[60%] rounded-2xl bg-white/10 px-3.5 py-2 text-sm">
                <span className="inline-flex gap-1">
                  <Dot /> <Dot delay={120} /> <Dot delay={240} />
                </span>
              </div>
            )}
            <div ref={endRef} />
          </div>

          <div className="flex flex-wrap gap-2 border-t border-white/10 bg-ink-950/80 px-4 py-3">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-ink-100/80 transition hover:bg-white/10"
              >
                {s}
              </button>
            ))}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex items-center gap-2 border-t border-white/10 p-3"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type a message…"
              className="flex-1 rounded-full bg-white/5 px-4 py-3 text-sm outline-none ring-1 ring-white/10 placeholder:text-ink-100/40 focus:ring-brand-500"
            />
            <button
              type="submit"
              aria-label="Send"
              className="grid h-11 w-11 place-items-center rounded-full bg-brand-500 text-white transition hover:bg-brand-600"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </div>
      </div>
    </section>
  );
}

function Dot({ delay = 0 }: { delay?: number }) {
  return (
    <span
      className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-white/70"
      style={{ animationDelay: `${delay}ms` }}
    />
  );
}
