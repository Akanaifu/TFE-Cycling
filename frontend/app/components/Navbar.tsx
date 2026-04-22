"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const navigationItems = [
  { href: "/pipeline", label: "Pipeline" },
  { href: "/fit-import", label: "Import FIT" },
  { href: "/compare-models", label: "Comparaison" },
  { href: "/strava", label: "Strava" },
  { href: "/register", label: "Nouveau compte" },
];

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const isAuthRoute = pathname === "/login" || pathname === "/login/";

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";

    const fetchCurrentUserRole = async () => {
      try {
        const response = await fetch(`${apiUrl}/auth/me`, {
          credentials: "include",
        });

        if (!response.ok) {
          setIsAdmin(false);
          return;
        }

        const payload = await response.json();
        const role = String(payload?.user?.role ?? "").toLowerCase();
        setIsAdmin(role === "admin");
      } catch {
        setIsAdmin(false);
      }
    };

    fetchCurrentUserRole();

    const handlePointerDown = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  const handleLogout = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL;
      await fetch(`${apiUrl}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } finally {
      setMenuOpen(false);
      router.replace("/login");
      router.refresh();
    }
  };

  if (isAuthRoute) {
    return null;
  }

  return (
    <header className="sticky top-0 z-50 border-b border-[#003566]/70 bg-[#000814]/92 shadow-[0_14px_44px_rgba(0,0,0,0.34)] backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center gap-3 px-4 py-3 sm:px-6 lg:px-8">
        <Link href="/pipeline" className="group inline-flex items-center gap-3">
          <span className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-2xl border border-[#003566] bg-[#001d3d] shadow-lg shadow-[#000814]/40 transition-transform duration-200 group-hover:-translate-y-0.5">
            <Image
              src="/strava-app-icon-v3.svg"
              alt="Logo TFE Cycling"
              width={40}
              height={40}
              priority
            />
          </span>
          <span className="leading-tight">
            <span className="block text-xs uppercase tracking-[0.35em] text-[#ffd60a]/70">
              TFE Cycling
            </span>
            <span className="block text-lg font-semibold text-[#fff8d6]">
              Analyse
            </span>
          </span>
        </Link>

        <div className="ml-auto flex items-center gap-3">
          <div ref={menuRef} className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen((current) => !current)}
              aria-expanded={menuOpen}
              aria-haspopup="menu"
              className="inline-flex items-center gap-2 rounded-full border border-[#ffc300]/30 bg-[#003566] px-4 py-2 text-sm font-semibold text-[#fff8d6] shadow-[0_10px_22px_rgba(0,0,0,0.18)] transition-colors hover:bg-[#00467f]"
            >
              Menu
              <span aria-hidden="true">▾</span>
            </button>

            {menuOpen && (
              <div className="absolute right-0 mt-3 w-64 overflow-hidden rounded-2xl border border-[#003566] bg-[#000814] p-2 shadow-[0_18px_50px_rgba(0,0,0,0.45)]">
                {navigationItems
                  .filter((item) => item.href !== "/register" || isAdmin)
                  .map((item) => {
                    const isActive =
                      item.href === "/"
                        ? pathname === "/"
                        : pathname === item.href ||
                          pathname.startsWith(`${item.href}/`);

                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        aria-current={isActive ? "page" : undefined}
                        onClick={() => setMenuOpen(false)}
                        className={`block rounded-xl px-4 py-3 text-sm font-semibold transition-colors ${
                          isActive
                            ? "bg-[#ffc300] text-[#000814]"
                            : "text-[#fff8d6] hover:bg-[#001d3d] hover:text-[#ffd60a]"
                        }`}
                      >
                        {item.label}
                      </Link>
                    );
                  })}
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={handleLogout}
            className="rounded-full border border-[#ffc300]/35 bg-[#ffc300] px-4 py-2 text-sm font-semibold text-[#000814] shadow-[0_10px_22px_rgba(255,198,0,0.18)] transition-colors hover:bg-[#ffd60a]"
          >
            Déconnexion
          </button>
        </div>
      </div>
    </header>
  );
}
