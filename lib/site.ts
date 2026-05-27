export const siteConfig = {
  name: "Salon & Spa Automation",
  tagline:
    "Stop Missing Bookings While You Work. Let AI Answer Your WhatsApp and Collect Deposits 24/7.",
  whatsappNumber:
    process.env.NEXT_PUBLIC_WHATSAPP_NUMBER ?? "2348012345678",
  calLink: process.env.NEXT_PUBLIC_CAL_LINK ?? "miracle-edeh/salon-audit",
  whatsappMessage:
    "Hi! I saw your automation page and I'd like to book my free audit.",
  cities: ["Lagos", "Abuja", "Port Harcourt", "Ibadan"],
  businessTypes: ["salons", "spas", "barbershops", "nail studios", "wellness centres"]
};

export function getWhatsappUrl(message?: string) {
  const text = encodeURIComponent(message ?? siteConfig.whatsappMessage);
  return `https://wa.me/${siteConfig.whatsappNumber}?text=${text}`;
}
