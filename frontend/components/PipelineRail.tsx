"use client";

const STAGES = [
  { key: "router", label: "ROUTER" },
  { key: "diagnostic", label: "DIAGNOSTIC" },
  { key: "retrieval", label: "RETRIEVAL" },
  { key: "synthesis", label: "SYNTHESIS" },
] as const;

export type StageKey = (typeof STAGES)[number]["key"];

/**
 * Renders the four-agent pipeline as a horizontal trace, like a signal
 * oscilloscope. `activeIndex` (0-3) lights up stages up to and including the
 * current one, and pulses the current one — making the multi-agent handoff
 * visible instead of hiding it behind a generic spinner.
 */
export default function PipelineRail({ activeIndex }: { activeIndex: number }) {
  return (
    <div className="flex items-center gap-0 select-none" aria-label="Agent pipeline status">
      {STAGES.map((stage, i) => {
        const lit = activeIndex >= 0 && i <= activeIndex;
        const current = i === activeIndex;
        return (
          <div key={stage.key} className="flex items-center">
            <div className="flex flex-col items-center gap-1.5 w-[92px]">
              <div
                className={[
                  "h-2 w-2 rounded-full border transition-colors duration-300",
                  lit ? "bg-signal border-signal" : "bg-transparent border-border",
                  current ? "animate-pulse" : "",
                ].join(" ")}
              />
              <span
                className={[
                  "font-mono text-[10px] tracking-widest transition-colors duration-300",
                  lit ? "text-signal" : "text-muted",
                ].join(" ")}
              >
                {stage.label}
              </span>
            </div>
            {i < STAGES.length - 1 && (
              <div
                className={[
                  "h-px w-8 -mt-4 transition-colors duration-300",
                  activeIndex > i ? "bg-signal" : "bg-border",
                ].join(" ")}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
