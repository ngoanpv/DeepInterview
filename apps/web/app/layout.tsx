import type { ReactNode } from "react";
import { cookies } from "next/headers";
import { Fraunces, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-inter",
  display: "swap",
});

const fraunces = Fraunces({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-fraunces",
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-jetbrains",
  display: "swap",
});

export const metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "https://deepinterview.ai",
  ),
  title: {
    default: "DeepInterview — Practice the interview out loud",
    template: "%s · DeepInterview",
  },
  description:
    "Open-source, voice-first AI mock interviews. DeepInterview reads your CV and the job, researches the company, runs an adaptive voice interview, then shows you exactly what to fix. English-first, 10+ languages.",
  applicationName: "DeepInterview",
  openGraph: {
    title: "DeepInterview — Practice the interview out loud",
    description:
      "Open-source, voice-first AI mock interviews — practice out loud, then pass the real one.",
    url: "/",
    siteName: "DeepInterview",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "DeepInterview — Practice the interview out loud",
    description:
      "Open-source, voice-first AI mock interviews — practice out loud, then pass the real one.",
  },
};

const THEME_INIT_SCRIPT = `(function(){try{var p=localStorage.getItem('theme');var d=p==='dark'||(p!=='light'&&window.matchMedia('(prefers-color-scheme: dark)').matches);var r=document.documentElement;r.classList.toggle('dark',d);r.style.colorScheme=d?'dark':'light';}catch(e){}})();`;

export default async function RootLayout({
  children,
}: {
  children: ReactNode;
}) {
  // Screen readers pick pronunciation from `lang` — resolve it from the same
  // `locale` cookie the LanguageToggle writes (EN default).
  const store = await cookies();
  const lang = store.get("locale")?.value === "vi" ? "vi" : "en";
  return (
    <html
      lang={lang}
      suppressHydrationWarning
      className={`${inter.variable} ${fraunces.variable} ${jetbrains.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="font-sans">
        <noscript>
          <style
            dangerouslySetInnerHTML={{
              __html: ".reveal{opacity:1!important;transform:none!important}",
            }}
          />
        </noscript>
        {children}
      </body>
    </html>
  );
}
