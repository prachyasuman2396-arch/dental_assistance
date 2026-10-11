"use client";

import React from "react";
import { useTheme } from "./ThemeProvider";
import { Sun, Moon } from "lucide-react";

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
      className={`relative inline-flex items-center justify-center p-2 rounded-xl transition-all duration-300 hover:scale-105 active:scale-95 glass-panel ${className}`}
    >
      <div className="relative w-4 h-4">
        <Sun
          className={`w-4 h-4 text-amber-500 transition-all duration-300 absolute inset-0 ${
            theme === "dark" ? "opacity-0 rotate-90 scale-50" : "opacity-100 rotate-0 scale-100"
          }`}
        />
        <Moon
          className={`w-4 h-4 text-indigo-400 transition-all duration-300 absolute inset-0 ${
            theme === "dark" ? "opacity-100 rotate-0 scale-100" : "opacity-0 -rotate-90 scale-50"
          }`}
        />
      </div>
    </button>
  );
}
