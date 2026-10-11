"use client";

import React from "react";

export function AmbientBackground() {
  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden z-0 select-none">
      {/* Light mode / Dark mode atmospheric radial glows */}
      <div className="absolute -top-[18%] -left-[10%] w-[55vw] h-[55vw] rounded-full bg-gradient-to-br from-[#8D79D6]/10 via-[#DDE8FF]/10 to-transparent blur-[120px] dark:from-[#927BFA]/12 dark:via-[#1E1D33]/20 dark:to-transparent" />
      <div className="absolute top-[35%] -right-[15%] w-[50vw] h-[50vw] rounded-full bg-gradient-to-tl from-[#F3DDEB]/15 via-[#B8E5DE]/8 to-transparent blur-[140px] dark:from-[#E6B8D5]/8 dark:via-[#94DED2]/6 dark:to-transparent" />
      <div className="absolute -bottom-[20%] left-[25%] w-[45vw] h-[45vw] rounded-full bg-gradient-to-t from-[#DCD3FF]/12 via-transparent to-transparent blur-[110px] dark:from-[#322F55]/20 dark:to-transparent" />
    </div>
  );
}
