import type { Metadata, Viewport } from "next";
import { PwaRegister } from "@/components/pwa-register";
import "./globals.css";

export const metadata: Metadata = {
  title: "PromoTrix",
  description: "Promoções que o seu PC encontrou no Pelando, dentro dos seus alvos.",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/icons/icon-192.png", apple: "/icons/icon-192.png" },
  appleWebApp: { capable: true, title: "PromoTrix", statusBarStyle: "default" },
};

export const viewport: Viewport = { themeColor: "#ffe600", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>
        {children}
        <PwaRegister />
      </body>
    </html>
  );
}
