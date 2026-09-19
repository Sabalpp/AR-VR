"use client";

import { useLayoutEffect, useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/dist/ScrollTrigger";
import ReachInstrument from "@/components/ui/reach-instrument";
import {
  HOLD_MS,
  REACH_THRESHOLD_DEG,
  RETURN_THRESHOLD_DEG,
  SAMPLE_HZ,
} from "@/lib/reach-trace";

gsap.registerPlugin(ScrollTrigger);

const INK = "#193e38";
const PAPER = "#f6f7f2";
const TEAL = "#246f60";
const LIME = "#d5edac";
const MUTED = "#71827b";
const LINE = "#dfe5dc";

/* The counter rule, stated in the same terms the backend enforces. */
const RULE = [
  {
    k: "arm",
    head: `Return below ${RETURN_THRESHOLD_DEG}°, held ${HOLD_MS} ms`,
    body: "The counter arms. Until it does, a reach counts for nothing.",
  },
  {
    k: "reach",
    head: `Reach past ${REACH_THRESHOLD_DEG}°, held ${HOLD_MS} ms`,
    body: "Cross it and drop straight back and the hold fails. The position has to stay.",
  },
  {
    k: "close",
    head: `Return below ${RETURN_THRESHOLD_DEG}°, held ${HOLD_MS} ms`,
    body: "Now it is one repetition. The count moves on the return, not the reach.",
  },
];

const RESET = [
  "A frame the tracker was not confident in",
  "A gap longer than the configured limit",
  "A timestamp that arrived out of order",
  "Any pause, until the session resumes",
];

const NOT_INFERRED = [
  ["Depth", "A phone camera has none. Nothing is treated as a calibrated distance."],
  ["Form", "No compensation score, no quality grade, no judgement of technique."],
  ["Diagnosis", "This is an observational count, not a clinical assessment."],
  ["Gaps", "Missing frames stay missing. Nothing is interpolated across them."],
];

function useReveal() {
  const ref = useRef<HTMLElement>(null);
  useLayoutEffect(() => {
    const ctx = gsap.context(() => {
      const reduced = window.matchMedia?.(
        "(prefers-reduced-motion: reduce)",
      )?.matches;
      const targets = gsap.utils.toArray<HTMLElement>("[data-reveal]");
      if (!targets.length) return;
      if (reduced) {
        gsap.set(targets, { opacity: 1, y: 0 });
        return;
      }
      targets.forEach((el) => {
        gsap.from(el, {
          opacity: 0,
          y: 22,
          duration: 0.8,
          ease: "power3.out",
          scrollTrigger: { trigger: el, start: "top bottom", once: true },
        });
      });
      // Images and web fonts settle after mount and move every trigger point.
      ScrollTrigger.refresh();
    }, ref);
    return () => ctx.revert();
  }, []);
  return ref;
}

export default function LandingExperience() {
  const ref = useReveal();

  return (
    <main ref={ref} style={{ background: PAPER, color: INK }}>
      {/* ---------------- instrument ---------------- */}
      <section
        className="relative min-h-screen w-full overflow-hidden"
        style={{ background: INK, color: PAPER }}
      >
        <header className="mx-auto flex max-w-[84rem] items-center justify-between px-6 py-6 md:px-10">
          <span className="text-[15px] font-semibold tracking-[-0.02em]">
            Reach
          </span>
          <nav className="flex items-center gap-7 text-[13px]">
            <a href="#rule" style={{ color: "rgba(246,247,242,0.6)" }}>
              The rule
            </a>
            <a href="#limits" style={{ color: "rgba(246,247,242,0.6)" }}>
              Limits
            </a>
            <a href="/" style={{ color: PAPER }}>
              Sign in
            </a>
          </nav>
        </header>

        <div className="mx-auto max-w-[84rem] px-6 pb-16 pt-6 md:px-10 md:pt-10">
          <p
            className="text-[12px] tracking-[0.18em]"
            style={{ color: "rgba(246,247,242,0.45)" }}
          >
            SEATED REACH · RIGHT ELBOW · PROJECTED 2D ANGLE
          </p>

          <h1 className="mt-5 max-w-[19ch] text-[clamp(2.4rem,5.4vw,4.4rem)] font-medium leading-[1.02] tracking-[-0.04em]">
            Seated reach, measured at home.
          </h1>

          <p
            className="mt-6 max-w-[62ch] text-[16px] leading-[1.6]"
            style={{ color: "rgba(246,247,242,0.7)" }}
          >
            The phone camera samples your right elbow angle {SAMPLE_HZ} times a
            second. A repetition is counted only when the reach is held past the
            threshold and the return is held back below it. Everything below is
            the signal that produces the count.
          </p>

          <div className="mt-14">
            <ReachInstrument tone="ink" />
          </div>

          <div className="mt-14 flex flex-wrap items-center gap-4">
            <a
              href="/"
              className="rounded-full px-7 py-3 text-[15px] font-medium"
              style={{ background: PAPER, color: INK }}
            >
              Sign in
            </a>
            <a
              href="#rule"
              className="rounded-full border px-7 py-3 text-[15px]"
              style={{
                borderColor: "rgba(246,247,242,0.28)",
                color: "rgba(246,247,242,0.88)",
              }}
            >
              Read the counting rule
            </a>
          </div>
        </div>
      </section>

      {/* ---------------- the rule ---------------- */}
      <section id="rule" className="px-6 py-24 md:px-10 md:py-32">
        <div className="mx-auto max-w-[84rem]">
          <h2
            data-reveal
            className="text-[clamp(1.8rem,3.6vw,2.8rem)] font-medium leading-[1.06] tracking-[-0.035em]"
          >
            The counting rule
          </h2>
          <p
            data-reveal
            className="mt-4 max-w-[58ch] text-[15px] leading-[1.6]"
            style={{ color: MUTED }}
          >
            It runs on the server, not in the browser, so the count does not
            depend on the phone being honest.
          </p>

          <ol className="mt-14">
            {RULE.map((item, i) => (
              <li
                key={item.k}
                data-reveal
                className="flex flex-col gap-3 py-8 md:flex-row md:items-baseline md:gap-10"
                style={{ borderTop: `1px solid ${LINE}` }}
              >
                <span
                  className="text-[13px] tabular-nums md:w-8 md:shrink-0"
                  style={{ color: TEAL }}
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
                <h3 className="text-[clamp(1.15rem,2vw,1.5rem)] font-medium leading-[1.2] tracking-[-0.02em] md:w-[38%] md:shrink-0">
                  {item.head}
                </h3>
                <p
                  className="max-w-[46ch] text-[15px] leading-[1.6] md:flex-1"
                  style={{ color: MUTED }}
                >
                  {item.body}
                </p>
              </li>
            ))}
          </ol>

          <div
            data-reveal
            className="mt-10 pt-8"
            style={{ borderTop: `1px solid ${LINE}` }}
          >
            <p className="text-[13px] tracking-[0.16em]" style={{ color: TEAL }}>
              WHAT SENDS IT BACK TO THE START
            </p>
            <ul className="mt-5 flex flex-wrap gap-x-10 gap-y-3">
              {RESET.map((item) => (
                <li key={item} className="text-[15px]" style={{ color: MUTED }}>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ---------------- limits ---------------- */}
      <section
        id="limits"
        className="px-6 py-24 md:px-10 md:py-32"
        style={{ background: INK, color: PAPER }}
      >
        <div className="mx-auto max-w-[84rem]">
          <h2
            data-reveal
            className="max-w-[20ch] text-[clamp(1.8rem,3.6vw,2.8rem)] font-medium leading-[1.06] tracking-[-0.035em]"
          >
            Four things this does not know
          </h2>

          <dl className="mt-14">
            {NOT_INFERRED.map(([term, detail]) => (
              <div
                key={term}
                data-reveal
                className="flex flex-col gap-2 py-7 md:flex-row md:items-baseline md:gap-10"
                style={{ borderTop: "1px solid rgba(246,247,242,0.16)" }}
              >
                <dt className="text-[clamp(1.15rem,2vw,1.5rem)] font-medium tracking-[-0.02em] md:w-[28%] md:shrink-0">
                  {term}
                </dt>
                <dd
                  className="max-w-[56ch] text-[15px] leading-[1.6] md:flex-1"
                  style={{ color: "rgba(246,247,242,0.62)" }}
                >
                  {detail}
                </dd>
              </div>
            ))}
          </dl>

          <p
            data-reveal
            className="mt-12 text-[12px] tracking-[0.16em]"
            style={{ color: "rgba(246,247,242,0.38)" }}
          >
            RESEARCH PROTOTYPE · NOT A MEDICAL DEVICE · THRESHOLDS ARE
            DEMONSTRATION TARGETS
          </p>
        </div>
      </section>

      {/* ---------------- close ---------------- */}
      <footer className="px-6 py-24 md:px-10 md:py-28">
        <div className="mx-auto max-w-[84rem]">
          <div data-reveal className="flex flex-wrap items-end justify-between gap-8">
            <h2 className="max-w-[12ch] text-[clamp(1.9rem,4.2vw,3.2rem)] font-medium leading-[1.02] tracking-[-0.04em]">
              Open your plan.
            </h2>
            <a
              href="/"
              className="rounded-full px-7 py-3 text-[15px] font-medium"
              style={{ background: INK, color: PAPER }}
            >
              Sign in
            </a>
          </div>
          <div
            className="mt-16 flex flex-col gap-2 pt-6 text-[12px] md:flex-row md:justify-between"
            style={{ borderTop: `1px solid ${LINE}`, color: MUTED }}
          >
            <p>Reach · connected physical therapy</p>
            <p>Demo accounts are fictional. Camera sessions capture real movement.</p>
          </div>
        </div>
      </footer>
    </main>
  );
}
