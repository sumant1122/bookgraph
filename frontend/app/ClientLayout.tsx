"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const navItems = [
  { href: "/books", label: "Ingestion" },
  { href: "/graph", label: "Globe" },
  { href: "/chat", label: "Chat" },
];

function ThemeToggle() {
  const [dark, setDark] = useState(true);
  return (
    <button
      className="theme-toggle"
      onClick={() => setDark(!dark)}
      aria-label="Toggle theme"
    >
      {dark ? (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 3v2m0 14v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" strokeLinecap="round" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
    </button>
  );
}

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link href="/" className="topbar-brand">
          <span className="topbar-brand-icon">B</span>
          <span>BookGraph</span>
        </Link>

        <nav className="topbar-nav">
          {navItems.map(item => (
            <Link
              key={item.href}
              href={item.href}
              className={`topbar-nav-link ${pathname === item.href ? "active" : ""}`}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="topbar-actions">
          <ThemeToggle />
        </div>
      </header>

      <main className="page-content wide">
        {children}
      </main>
    </div>
  );
}
