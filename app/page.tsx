import { Header } from "@/components/Header";
import { Hero } from "@/components/Hero";
import { ProblemSolution } from "@/components/ProblemSolution";
import { DemoChat } from "@/components/DemoChat";
import { Features } from "@/components/Features";
import { Testimonials } from "@/components/Testimonials";
import { FAQ } from "@/components/FAQ";
import { BookingSection } from "@/components/BookingSection";
import { Footer } from "@/components/Footer";

export default function Page() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <ProblemSolution />
        <DemoChat />
        <Features />
        <Testimonials />
        <BookingSection />
        <FAQ />
      </main>
      <Footer />
    </>
  );
}
