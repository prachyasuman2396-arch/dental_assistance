import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme/ThemeProvider";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Sristi AI — Personal Dental Study & Research Companion",
  description:
    "A personalized, premium 3D study and research assistant crafted for Sristi Biswal. Deep clinical concepts, board exam preparation, and biomedical literature research.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} antialiased selection:bg-violet-200 selection:text-violet-900`}>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
