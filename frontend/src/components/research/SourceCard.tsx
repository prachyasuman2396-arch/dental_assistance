"use client";

import React from "react";
import { ExternalLink, Bookmark, Award } from "lucide-react";
import { CitationItem } from "@/services/api";

interface SourceCardProps {
  source: CitationItem;
}

export function SourceCard({ source }: SourceCardProps) {
  const isDoc = !!source.filename;

  return (
    <div className="group relative p-3.5 rounded-xl glass-panel transition-all duration-200 hover:border-violet-400/40 hover:shadow-md text-xs">
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-1.5 font-medium text-[var(--primary-violet)] dark:text-[var(--primary-lavender)]">
          {isDoc ? (
            <>
              <Bookmark className="w-3.5 h-3.5 flex-shrink-0" />
              <span className="truncate max-w-[200px]">{source.filename}</span>
            </>
          ) : (
            <>
              <Award className="w-3.5 h-3.5 flex-shrink-0 text-amber-500/80" />
              <span className="truncate max-w-[200px]">{source.journal || "Biomedical Journal"}</span>
            </>
          )}
        </div>

        {source.evidence_level && (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-violet-100 dark:bg-violet-950/60 text-violet-700 dark:text-violet-300 border border-violet-200/50 dark:border-violet-800/40 flex-shrink-0">
            {source.evidence_level}
          </span>
        )}
      </div>

      <div className="font-medium text-[var(--text-primary)] line-clamp-2 leading-relaxed mb-1">
        {isDoc ? `Page ${source.page_number}` : source.title}
      </div>

      {source.authors && (
        <div className="text-[var(--text-muted)] text-[11px] truncate mb-2">
          {source.authors} {source.pub_date ? `(${source.pub_date})` : ""}
        </div>
      )}

      {/* Metadata links */}
      <div className="flex items-center gap-3 pt-1 border-t border-[var(--border-light)] text-[10px] text-[var(--text-secondary)]">
        {source.pmid && (
          <span className="font-mono">PMID: {source.pmid}</span>
        )}
        {source.doi && (
          <span className="font-mono truncate max-w-[120px]">DOI: {source.doi}</span>
        )}
        {source.url && (
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto inline-flex items-center gap-1 text-[var(--primary-violet)] dark:text-[var(--primary-lavender)] hover:underline"
          >
            Read Source <ExternalLink className="w-2.5 h-2.5" />
          </a>
        )}
      </div>
    </div>
  );
}
