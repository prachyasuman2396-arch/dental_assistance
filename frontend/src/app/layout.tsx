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
  title: "Scholar AI — Personal Study & Research Companion",
  description:
    "A personalized, premium study and research assistant crafted for students. Conceptual mastery, exam preparation, and academic literature research.",
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
