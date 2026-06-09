import type { Metadata } from "next";
import "./globals.css";
import { UIProvider } from "@/lib/ui-context";

export const metadata: Metadata = {
  title: "GEDS — Cascade Propagation Engine",
  description:
    "Research-grade simulation of cascading international economic disruptions over the global trade and supply-chain network.",
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
        <UIProvider>
          <div className="relative z-10">{children}</div>
        </UIProvider>
      </body>
    </html>
  );
}
