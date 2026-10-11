"use client";

import React from "react";
import { Menu, Sparkles, Wifi } from "lucide-react";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

interface ChatHeaderProps {
  title: string;
  onOpenSidebar: () => void;
  isBackendOnline?: boolean;
}

export function ChatHeader({
  title,
  onOpenSidebar,
  isBackendOnline = true,
}: ChatHeaderProps) {
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between px-4 py-3 glass-panel border-b border-[var(--border-light)]">
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenSidebar}
          aria-label="Open menu"
          className="lg:hidden p-1.5 rounded-lg text-[var(--text-secondary)] hover:bg-black/5 dark:hover:bg-white/5 cursor-pointer"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <h2 className="text-sm font-semibold text-[var(--text-primary)] truncate max-w-[240px] md:max-w-md">
            {title || "Dental Study Session"}
          </h2>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <ThemeToggle />
      </div>
    </header>
  );
}
