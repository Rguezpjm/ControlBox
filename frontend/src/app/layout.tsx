import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ThemeProvider } from "@/providers/theme-provider";
import { RealtimeProvider } from "@/providers/realtime-provider";
import { I18nProvider } from "@/providers/i18n-provider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { publicAsset } from "@/lib/base-path";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ControlBox",
  description: "Multi-tenant hosting control panel",
  icons: {
    icon: publicAsset("/logo.png"),
    apple: publicAsset("/logo.png"),
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${geistSans.variable} ${geistMono.variable} font-sans antialiased`}>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <I18nProvider>
            <RealtimeProvider>
              <TooltipProvider>
                {children}
              </TooltipProvider>
            </RealtimeProvider>
          </I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
