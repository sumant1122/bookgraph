import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "BookGraph",
  description: "Book knowledge graph explorer"
};

export default function RootLayout({
  children
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <main>
          <div className="card" style={{ marginBottom: 16 }}>
            <h1 style={{ marginTop: 0 }}>BookGraph</h1>
            <nav style={{ display: "flex", gap: 16 }}>
              <Link href="/books">Books</Link>
              <Link href="/graph">Graph</Link>
              <Link href="/insights">Insights</Link>
            </nav>
          </div>
          {children}
        </main>
      </body>
    </html>
  );
}

