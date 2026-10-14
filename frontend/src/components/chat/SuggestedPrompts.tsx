"use client";

import React from "react";
import { BookOpen, Search, FileText, GraduationCap } from "lucide-react";

interface SuggestedPromptsProps {
  onSelectPrompt: (promptText: string) => void;
}

export function SuggestedPrompts({ onSelectPrompt }: SuggestedPromptsProps) {
  const cards = [
    {
      id: "concept",
      icon: BookOpen,
      title: "Understand a concept",
      description: "Break difficult academic topics into simple explanations.",
      prompt: "Explain cellular respiration and ATP synthesis in simple language.",
      accentClass: "group-hover:text-violet-500",
    },
    {
      id: "research",
      icon: Search,
      title: "Research a topic",
      description: "Discover recent studies and reliable scientific evidence.",
      prompt: "Find recent peer-reviewed research on CRISPR gene therapy.",
      accentClass: "group-hover:text-blue-500",
    },
    {
      id: "notes",
      icon: FileText,
      title: "Ask my textbooks",
      description: "Learn from uploaded lecture notes and textbooks.",
      prompt: "Help me understand the most important points from my notes.",
      accentClass: "group-hover:text-teal-500",
    },
    {
      id: "exams",
      icon: GraduationCap,
      title: "Practice for exams",
      description: "Test your knowledge with MCQs and practice questions.",
      prompt: "Create 10 high-yield exam practice questions with explanations.",
      accentClass: "group-hover:text-rose-500",
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-2xl px-4 my-6">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <button
            key={card.id}
            onClick={() => onSelectPrompt(card.prompt)}
            className="group relative flex flex-col text-left p-4 rounded-2xl glass-panel transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:border-violet-300/40 active:scale-[0.99] cursor-pointer"
          >
            <div className="flex items-center gap-2.5 mb-1.5">
              <div className="p-2 rounded-xl bg-violet-50 dark:bg-violet-950/40 text-violet-600 dark:text-violet-300 transition-colors">
                <Icon className={`w-4 h-4 ${card.accentClass}`} />
              </div>
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                {card.title}
              </h3>
            </div>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed line-clamp-2">
              {card.description}
            </p>
          </button>
        );
      })}
    </div>
  );
}
