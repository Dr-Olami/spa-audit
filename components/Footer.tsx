import { Sparkles } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t border-white/5 py-10">
      <div className="container-px mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 text-sm text-ink-100/60 sm:flex-row">
        <div className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-gradient-to-br from-brand-500 to-brand-700">
            <Sparkles className="h-3.5 w-3.5 text-white" />
          </span>
          <span>SalonAutomate · Built for Nigerian beauty businesses</span>
        </div>
        <p>© {new Date().getFullYear()} SalonAutomate. All rights reserved.</p>
      </div>
    </footer>
  );
}
