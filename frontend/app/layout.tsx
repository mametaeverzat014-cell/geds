import type { Metadata } from "next";
import "./globals.css";
import SpotlightEffect from "@/components/SpotlightEffect";
import { UIProvider } from "@/lib/ui-context";

export const metadata: Metadata = {
  metadataBase: new URL("https://geds1.vercel.app"),
  title: "GEDS — Cascade Propagation Engine",
  description:
    "Research-grade simulation of cascading international economic disruptions over the global trade and supply-chain network.",
  openGraph: {
    title: "GEDS — Global Economic Dependency Simulator",
    description:
      "Watch one shock — a chip-fab shutdown, a blocked strait, a trade war — ripple through the world's supply-chain network, week by week. Honest, reproducible validation against 21 historical crises.",
    url: "https://geds1.vercel.app",
    siteName: "GEDS",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "GEDS — Global Economic Dependency Simulator",
    description:
      "Network simulation of cascading economic disruptions, validated against 21 historical crises.",
  },
};

export const viewport = {
  themeColor: "#07090C",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap"
        />
      </head>
      <body className="min-h-screen relative">
        <div className="aurora" aria-hidden="true" />
        <SpotlightEffect />
        <UIProvider>
          <div className="relative z-10">{children}</div>
        </UIProvider>
      </body>
    </html>
  );
}
