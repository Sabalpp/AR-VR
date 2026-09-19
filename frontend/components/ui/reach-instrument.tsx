"use client";

import { useLayoutEffect, useRef } from "react";
import gsap from "gsap";
import { DrawSVGPlugin } from "gsap/dist/DrawSVGPlugin";
import { ScrollTrigger } from "gsap/dist/ScrollTrigger";
import {
  buildTrace,
  projector,
  runs,
  toPath,
  REACH_THRESHOLD_DEG,
  RETURN_THRESHOLD_DEG,
  SAMPLE_HZ,
} from "@/lib/reach-trace";

gsap.registerPlugin(DrawSVGPlugin, ScrollTrigger);

const INK = "#193e38";
const PAPER = "#f6f7f2";
const TEAL = "#246f60";
const LIME = "#d5edac";

const W = 1200;
const H = 340;
const PAD = 34;
const GUTTER = 128;

const AXIS_DEG = [100, 140];

type Props = {
  /** Paper renders the dark-on-light variant used below the fold. */
  tone?: "ink" | "paper";
};

export default function ReachInstrument({ tone = "ink" }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const countRef = useRef<HTMLSpanElement>(null);

  const trace = buildTrace(4);
  const p = projector(trace, W, H, PAD, GUTTER);
  const segments = runs(trace.samples);

  const stroke = tone === "ink" ? PAPER : INK;
  const faint = tone === "ink" ? "rgba(246,247,242,0.16)" : "rgba(25,62,56,0.14)";
  const label = tone === "ink" ? "rgba(246,247,242,0.5)" : "rgba(25,62,56,0.5)";
  const accent = tone === "ink" ? LIME : TEAL;

  useLayoutEffect(() => {
    let safety: number | undefined;
    const ctx = gsap.context(() => {
      const reduced = window.matchMedia?.(
        "(prefers-reduced-motion: reduce)",
      )?.matches;

      if (reduced) {
        gsap.set("[data-draw]", { drawSVG: "100%" });
        gsap.set("[data-tick]", { opacity: 1, scaleY: 1 });
        if (countRef.current)
          countRef.current.textContent = String(trace.reps.length);
        return;
      }

      // Plays on mount, not on scroll. This is the hero: gating it on an
      // observer is how it ends up permanently blank.
      const tl = gsap.timeline({
        defaults: { ease: "power2.out" },
        delay: 0.15,
      });

      tl.from("[data-axis]", {
        drawSVG: "0%",
        duration: 0.7,
        stagger: 0.06,
      })
        // Grown via x2, not drawSVG: the plugin rewrites stroke-dasharray to
        // do its masking, which would destroy the dashed threshold pattern.
        .from(
          "[data-threshold]",
          { attr: { x2: PAD }, duration: 0.8, stagger: 0.12 },
          "-=0.35",
        )
        .from(
          "[data-threshold-label]",
          { opacity: 0, x: -8, duration: 0.5, stagger: 0.1 },
          "<",
        )
        // The signal writes itself left to right, at reading speed.
        .from(
          "[data-signal]",
          { drawSVG: "0%", duration: 2.4, ease: "none" },
          "-=0.2",
        )
        .from(
          "[data-gap]",
          { opacity: 0, duration: 0.4 },
          "-=1.4",
        )
        .from(
          "[data-tick]",
          { scaleY: 0, opacity: 0, duration: 0.35, stagger: 0.18 },
          "-=2.2",
        );

      // Counter advances in step with the ticks, snapped to whole reps.
      const counter = { value: 0 };
      tl.to(
        counter,
        {
          value: trace.reps.length,
          duration: 2.2,
          ease: "none",
          snap: { value: 1 },
          onUpdate: () => {
            if (countRef.current)
              countRef.current.textContent = String(Math.round(counter.value));
          },
        },
        "-=2.2",
      );

      // Safety net. GSAP runs on requestAnimationFrame, which browsers throttle
      // hard on background tabs and low-power devices. setTimeout is not tied to
      // rAF, so if the timeline has not finished well past its natural length,
      // snap it to the end rather than leave a half-drawn chart on screen.
      const expectedMs = tl.duration() * 1000 + 1200;
      safety = window.setTimeout(() => {
        if (tl.progress() < 1) tl.progress(1);
      }, expectedMs * 2);
    }, rootRef);

    return () => {
      if (safety) window.clearTimeout(safety);
      ctx.revert();
    };
  }, [trace.reps.length]);

  return (
    <div ref={rootRef} className="w-full">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label={`Elbow angle over ${Math.round(trace.duration)} seconds. ${trace.reps.length} repetitions counted. One reach discarded where tracking was lost.`}
      >
        {AXIS_DEG.map((deg) => (
          <g key={deg}>
            <line
              data-axis
              x1={PAD}
              y1={p.y(deg)}
              x2={W - GUTTER}
              y2={p.y(deg)}
              stroke={faint}
              strokeWidth={1}
            />
            <text
              x={PAD}
              y={p.y(deg) - 7}
              fill={label}
              fontSize={13}
              letterSpacing="0.08em"
            >
              {deg}°
            </text>
          </g>
        ))}

        <line
          data-threshold
          x1={PAD}
          y1={p.y(REACH_THRESHOLD_DEG)}
          x2={W - GUTTER}
          y2={p.y(REACH_THRESHOLD_DEG)}
          stroke={accent}
          strokeWidth={1.75}
          strokeDasharray="6 7"
        />
        <text
          data-threshold-label
          x={W - GUTTER + 12}
          y={p.y(REACH_THRESHOLD_DEG) + 4}
          fill={accent}
          fontSize={13}
          textAnchor="start"
          letterSpacing="0.1em"
        >
          REACH {REACH_THRESHOLD_DEG}°
        </text>

        <line
          data-threshold
          x1={PAD}
          y1={p.y(RETURN_THRESHOLD_DEG)}
          x2={W - GUTTER}
          y2={p.y(RETURN_THRESHOLD_DEG)}
          stroke={label}
          strokeWidth={1.5}
          strokeDasharray="5 6"
        />
        <text
          data-threshold-label
          x={W - GUTTER + 12}
          y={p.y(RETURN_THRESHOLD_DEG) + 4}
          fill={label}
          fontSize={13}
          textAnchor="start"
          letterSpacing="0.1em"
        >
          RETURN {RETURN_THRESHOLD_DEG}°
        </text>

        {/* Dropout band: drawn as absence, never as interpolated signal. */}
        <rect
          data-gap
          x={p.x(trace.dropout[0])}
          y={PAD - 10}
          width={Math.max(0, p.x(trace.dropout[1]) - p.x(trace.dropout[0]))}
          height={H - PAD * 2 + 20}
          fill={tone === "ink" ? "rgba(246,247,242,0.05)" : "rgba(25,62,56,0.05)"}
        />
        <text
          data-gap
          x={(p.x(trace.dropout[0]) + p.x(trace.dropout[1])) / 2}
          y={PAD + 4}
          fill={label}
          fontSize={12}
          textAnchor="middle"
          letterSpacing="0.12em"
        >
          TRACKING LOST
        </text>

        {segments.map((segment, i) =>
          segment.points.length < 2 ? null : (
            <path
              key={i}
              data-signal
              data-draw
              d={toPath(segment.points, p)}
              fill="none"
              stroke={segment.valid ? stroke : label}
              strokeWidth={segment.valid ? 2.4 : 1.4}
              strokeDasharray={segment.valid ? undefined : "3 7"}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ),
        )}

        {trace.reps.map((rep) => (
          <line
            key={rep.index}
            data-tick
            x1={p.x(rep.t)}
            y1={H - PAD + 6}
            x2={p.x(rep.t)}
            y2={H - PAD - 16}
            stroke={accent}
            strokeWidth={2.5}
            style={{ transformOrigin: `${p.x(rep.t)}px ${H - PAD + 6}px` }}
          />
        ))}
      </svg>

      <dl
        className="mt-6 flex flex-wrap gap-x-10 gap-y-4 text-[13px]"
        style={{ color: label }}
      >
        <div>
          <dt className="tracking-[0.14em]">COUNTED</dt>
          <dd
            className="mt-1 text-[28px] leading-none tabular-nums"
            style={{ color: stroke }}
          >
            <span ref={countRef}>0</span>
          </dd>
        </div>
        <div>
          <dt className="tracking-[0.14em]">DISCARDED</dt>
          <dd
            className="mt-1 text-[28px] leading-none tabular-nums"
            style={{ color: stroke }}
          >
            1
          </dd>
        </div>
        <div>
          <dt className="tracking-[0.14em]">SAMPLE RATE</dt>
          <dd
            className="mt-1 text-[28px] leading-none tabular-nums"
            style={{ color: stroke }}
          >
            {SAMPLE_HZ} Hz
          </dd>
        </div>
        <div>
          <dt className="tracking-[0.14em]">SOURCE</dt>
          <dd className="mt-1 text-[28px] leading-none" style={{ color: stroke }}>
            right elbow
          </dd>
        </div>
      </dl>
    </div>
  );
}
