import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Videntia — Forensic Video Intelligence",
  description: "Multimodal Video Analysis with Agentic AI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <div style={{ display: "flex", minHeight: "100vh", flexDirection: "column" }}>
            <header style={{
                height: "60px",
                borderBottom: "1px solid var(--border-color)",
                display: "flex",
                alignItems: "center",
                padding: "0 24px",
                backgroundColor: "var(--surface-color)",
                gap: "12px",
                zIndex: 10
            }}>
                <div style={{
                    width: "24px",
                    height: "24px",
                    background: "var(--text-primary)",
                    borderRadius: "4px"
                }}/>
                <h1 style={{ fontSize: "1.1rem", fontWeight: 600, margin: 0, letterSpacing: "-0.02em" }}>
                    Videntia <span style={{ color: "var(--text-secondary)", fontWeight: 400 }}>Engine</span>
                </h1>
            </header>
            <main style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                {children}
            </main>
        </div>
      </body>
    </html>
  );
}
