"use client";

import React from "react";

interface UserMessageProps {
  content: string;
}

export function UserMessage({ content }: UserMessageProps) {
  return (
    <div className="flex justify-end w-full mb-6">
      <div className="max-w-[85%] md:max-w-[70%] px-4 py-3 rounded-2xl rounded-tr-sm bg-violet-100/70 dark:bg-violet-900/40 text-[var(--text-primary)] border border-violet-200/60 dark:border-violet-700/40 shadow-sm text-sm md:text-[15px] leading-relaxed whitespace-pre-wrap">
        {content}
      </div>
    </div>
  );
}
