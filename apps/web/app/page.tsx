import { AnnouncementBar } from "@/components/landing/announcement-bar";
import { Nav } from "@/components/landing/nav";
import { Hero } from "@/components/landing/hero";
import { LogoCloud } from "@/components/landing/logo-cloud";
import { HowItWorks } from "@/components/landing/how-it-works";
import { Product } from "@/components/landing/product";
import { OpenSource } from "@/components/landing/open-source";
import { Faq } from "@/components/landing/faq";
import { CtaBand } from "@/components/landing/cta-band";
import { Footer } from "@/components/landing/footer";

export default function Home() {
  return (
    <>
      <AnnouncementBar />
      <Nav />
      <main>
        <Hero />
        <LogoCloud />
        <HowItWorks />
        <Product />
        <OpenSource />
        <Faq />
        <CtaBand />
      </main>
      <Footer />
    </>
  );
}
