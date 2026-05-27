import type { Metadata, Viewport } from "next";
import { Inter, Sora } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter"
});

const sora = Sora({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-display"
});

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://example.com";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default:
      "Salon & Spa Automation for Lagos & Abuja | Stop Missing Bookings 24/7",
    template: "%s | Salon & Spa Automation"
  },
  description:
    "Built for Nigerian salons, spas and beauty businesses. Let AI answer your WhatsApp, book appointments, and collect Paystack/Flutterwave deposits 24/7 — even while you're with a client.",
  keywords: [
    "salon automation Nigeria",
    "spa automation Nigeria",
    "salon booking system Lagos",
    "spa booking system Abuja",
    "WhatsApp automation Nigeria",
    "AI booking salon spa",
    "beauty business automation",
    "wellness business booking",
    "Paystack spa deposit",
    "Flutterwave salon booking"
  ],
  authors: [{ name: "Salon & Spa Automation" }],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    locale: "en_NG",
    url: siteUrl,
    siteName: "Salon & Spa Automation",
    title:
      "Stop Missing Bookings While You Work — AI for Nigerian Salons & Spas",
    description:
      "AI answers your WhatsApp, books clients, and collects deposits 24/7. Built for Lagos & Abuja salons, spas and beauty businesses.",
    images: [
      {
        url: "/og.png",
        width: 1200,
        height: 630,
        alt: "Salon & Spa Automation — AI bookings on WhatsApp"
      }
    ]
  },
  twitter: {
    card: "summary_large_image",
    title: "Stop Missing Bookings While You Work",
    description:
      "AI answers WhatsApp, books clients, collects deposits. Built for Nigerian salons & spas.",
    images: ["/og.png"]
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1
    }
  },
  icons: {
    icon: "/favicon.ico",
    apple: "/apple-touch-icon.png"
  }
};

export const viewport: Viewport = {
  themeColor: "#06060a",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "ProfessionalService",
  name: "Salon & Spa Automation",
  url: siteUrl,
  areaServed: [
    { "@type": "City", name: "Lagos" },
    { "@type": "City", name: "Abuja" }
  ],
  serviceType: "AI booking and WhatsApp automation for salons, spas and beauty businesses",
  description:
    "We help Nigerian salons, spas and wellness businesses automate WhatsApp bookings, deposits and reminders with AI."
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${sora.variable}`}>
      <body className="min-h-screen bg-ink-950 font-sans text-ink-50 antialiased">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        {children}
      </body>
    </html>
  );
}
