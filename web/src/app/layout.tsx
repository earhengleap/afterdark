import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AfterDark Vault",
  description: "AI-powered Telegram media gallery",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
