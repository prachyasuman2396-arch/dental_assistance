"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Copy, Check, Sparkles, BookOpen, Clock, Cpu } from "lucide-react";
import { CitationsMetadata } from "@/services/api";
import { SourceCard } from "@/components/research/SourceCard";

interface AssistantMessageProps {
  content: string;
  provider?: string;
  model?: string;
  latencyMs?: number;
  citations?: CitationsMetadata;
}

export function AssistantMessage({
  content,
  provider,
  model,
  latencyMs,
  citations,
}: AssistantMessageProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const hasCitations =
    (citations?.documents && citations.documents.length > 0) ||
    (citations?.research_papers && citations.research_papers.length > 0);

  return (
    <div className="flex flex-col w-full mb-8">
      {/* Sristi AI Avatar */}
      <div className="flex items-center justify-between mb-2 px-1">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-gradient-to-tr from-violet-600 via-indigo-500 to-purple-400 flex items-center justify-center text-white shadow-sm">
            <Sparkles className="w-3.5 h-3.5" />
          </div>
          <span className="text-xs font-semibold tracking-wide text-[var(--text-primary)]">
            Sristi AI
          </span>
        </div>

        <button
          onClick={handleCopy}
          aria-label="Copy response"
          className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-black/5 dark:hover:bg-white/5 transition-colors cursor-pointer"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Structured Answer Body */}
      <div className="prose-dental text-sm md:text-[15px] text-[var(--text-primary)] leading-relaxed pl-1 pr-2">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      </div>

      {/* Sourced Research Evidence Cards */}
      {hasCitations && (
        <div className="mt-5 pt-4 border-t border-[var(--border-light)]">
          <div className="flex items-center gap-2 mb-3 text-xs font-semibold text-[var(--text-secondary)]">
            <BookOpen className="w-3.5 h-3.5 text-[var(--primary-violet)] dark:text-[var(--primary-lavender)]" />
            <span>Sourced Evidence & Academic References</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {citations?.documents?.map((doc, idx) => (
              <SourceCard key={`doc-${idx}`} source={doc} />
            ))}
            {citations?.research_papers?.map((paper, idx) => (
              <SourceCard key={`paper-${idx}`} source={paper} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
