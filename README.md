# SalonAutomate — Landing Page

A mobile-first, SEO-optimized Next.js 14 landing page targeting Nigerian salons (Lagos, Abuja). Built for WhatsApp outreach funnels.

## Stack
- Next.js 14 (App Router) + TypeScript
- Tailwind CSS
- `@calcom/embed-react` for the free-audit booking widget
- `lucide-react` icons

## Features
- Hero with clear value proposition (no jargon, result-focused)
- Side-by-side "chaotic DMs vs AI-powered DMs" comparison
- **Interactive demo chat** — visitors can try the AI before booking
- Features grid, testimonials, FAQ (collapsible, accessible)
- Embedded cal.com booking for the free 20-min tech audit
- Sticky WhatsApp CTA on mobile
- SEO: rich `metadata`, Open Graph, Twitter cards, JSON-LD (`ProfessionalService`), `sitemap.xml`, `robots.txt`

## Setup

```bash
npm install
cp .env.example .env.local   # then edit values
npm run dev
```

Open http://localhost:3000.

## Required environment variables

| Variable | Example | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_SITE_URL` | `https://salonautomate.ng` | Canonical URL, sitemap, OG |
| `NEXT_PUBLIC_CAL_LINK` | `jane-doe/salon-audit` | Your cal.com event link |
| `NEXT_PUBLIC_WHATSAPP_NUMBER` | `2348012345678` | WhatsApp deep-link (no `+`, no spaces) |

## Customization

- **Copy / pricing** — edit `components/Hero.tsx`, `components/ProblemSolution.tsx`, `components/Features.tsx`.
- **Bot demo replies** — edit the `RESPONSES` map in `components/DemoChat.tsx`.
- **Brand color** — edit `brand` palette in `tailwind.config.ts`.
- **SEO metadata** — edit `app/layout.tsx`.

## Deployment

Recommended: Vercel. Push to GitHub → import repo → set the three env vars above → deploy.

## Project structure

```
app/
  layout.tsx          # SEO metadata, fonts, JSON-LD
  page.tsx            # Composition
  globals.css
  sitemap.ts
  robots.ts
components/
  Header.tsx
  Hero.tsx
  ProblemSolution.tsx
  DemoChat.tsx        # interactive chat preview
  Features.tsx
  Testimonials.tsx
  FAQ.tsx
  BookingSection.tsx  # cal.com embed
  Footer.tsx
  StickyWhatsapp.tsx
lib/
  site.ts             # central config & helpers
```
