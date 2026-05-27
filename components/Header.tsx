import Link from "next/link";
import { Sparkles } from "lucide-react";

export function Header() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-white/5 bg-ink-950/70 backdrop-blur-lg">
      <div className="container-px mx-auto flex h-16 max-w-6xl items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 shadow-glow">
            <Sparkles className="h-4 w-4 text-white" />
          </span>
          <span className="font-display text-base font-semibold tracking-tight">
            Salon<span className="text-brand-400">Automate</span>
          </span>
        </Link>

        <nav className="hidden items-center gap-8 text-sm text-ink-100/70 md:flex">
          <a href="#how-it-works" className="hover:text-white">How it works</a>
          <a href="#demo" className="hover:text-white">Live demo</a>
          <a href="#faq" className="hover:text-white">FAQ</a>
        </nav>

        <a
          href="#book"
          className="hidden rounded-full bg-brand-500 px-4 py-2 text-sm font-semibold text-white shadow-glow transition hover:bg-brand-600 sm:inline-flex"
        >
          Book free audit
        </a>
      </div>
    </header>
  );
}
