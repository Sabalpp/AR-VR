"use client";
import { motion, useInView, useReducedMotion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { useRef } from "react";

const EASE = [0.16, 1, 0.3, 1] as const;

const INK = "#193e38";
const PAPER = "#f6f7f2";
const TEAL = "#246f60";
const LIME = "#d5edac";

/* ---------------- WordsPullUp ---------------- */
interface WordsPullUpProps {
  text: string;
  className?: string;
  showAsterisk?: boolean;
  style?: React.CSSProperties;
}

export function WordsPullUp({
  text,
  className = "",
  showAsterisk = false,
  style,
}: WordsPullUpProps) {
  const reduced = useReducedMotion();
  const words = text.split(" ");

  // Animates on mount, not on intersection. This is above-the-fold copy: it
  // must never depend on an observer firing to become readable.
  return (
    <span className={`inline-flex flex-wrap ${className}`} style={style}>
      {words.map((word, i) => {
        const isLast = i === words.length - 1;
        return (
          <motion.span
            key={`${word}-${i}`}
            initial={reduced ? false : { y: 24, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.7, delay: i * 0.06, ease: EASE }}
            className="relative inline-block"
            style={{ marginRight: isLast ? 0 : "0.25em" }}
          >
            {word}
            {showAsterisk && isLast && (
              <span className="absolute top-[0.55em] -right-[0.32em] text-[0.3em]">
                *
              </span>
            )}
          </motion.span>
        );
      })}
    </span>
  );
}

/* ---------------- WordsPullUpMultiStyle ---------------- */
interface Segment {
  text: string;
  className?: string;
}

interface WordsPullUpMultiStyleProps {
  segments: Segment[];
  className?: string;
  style?: React.CSSProperties;
}

export function WordsPullUpMultiStyle({
  segments,
  className = "",
  style,
}: WordsPullUpMultiStyleProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true, amount: 0.1 });
  const reduced = useReducedMotion();

  const words: { word: string; className?: string }[] = [];
  segments.forEach((seg) => {
    seg.text.split(" ").forEach((w) => {
      if (w) words.push({ word: w, className: seg.className });
    });
  });

  return (
    <span ref={ref} className={`inline-flex flex-wrap ${className}`} style={style}>
      {words.map((w, i) => (
        <motion.span
          key={`${w.word}-${i}`}
          initial={reduced ? false : { y: 24, opacity: 0 }}
          animate={isInView ? { y: 0, opacity: 1 } : {}}
          transition={{ duration: 0.7, delay: i * 0.06, ease: EASE }}
          className={`inline-block ${w.className ?? ""}`}
          style={{ marginRight: "0.25em" }}
        >
          {w.word}
        </motion.span>
      ))}
    </span>
  );
}

/* ---------------- Hero ---------------- */
const NAV_ITEMS = [
  { label: "How it works", href: "#how" },
  { label: "What it measures", href: "#measures" },
  { label: "Sign in", href: "/" },
];

function ReachHero() {
  const reduced = useReducedMotion();
  const rise = (delay: number) => ({
    initial: reduced ? false : { y: 26, opacity: 0 },
    animate: { y: 0, opacity: 1 },
    transition: { duration: 0.9, delay, ease: EASE },
  });

  return (
    <section
      className="relative isolate min-h-screen w-full overflow-hidden"
      style={{ background: INK, color: PAPER }}
      aria-labelledby="hero-heading"
    >
      {/* Depth: a single warm light source, top-left, plus a cool falloff. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(75% 60% at 12% 4%, rgba(36,111,96,0.62) 0%, transparent 60%)," +
            "radial-gradient(55% 45% at 92% 92%, rgba(213,237,172,0.12) 0%, transparent 62%)",
        }}
      />
      {/* Baseline rule grid — clinical, quiet, structural. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.16]"
        style={{
          backgroundImage: `linear-gradient(${PAPER}22 1px, transparent 1px)`,
          backgroundSize: "100% 7rem",
        }}
      />

      <header className="relative z-20 mx-auto flex max-w-[86rem] items-center justify-between px-6 py-7 md:px-10">
        <a href="/landing" className="flex items-baseline gap-2">
          <span className="text-lg font-semibold tracking-[-0.03em]">Reach</span>
          <span
            className="hidden text-[11px] tracking-[0.2em] sm:inline"
            style={{ color: "rgba(246,247,242,0.5)" }}
          >
            PHYSICAL THERAPY
          </span>
        </a>
        <nav aria-label="Main navigation" className="flex items-center gap-6 md:gap-9">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.label}
              href={item.href}
              className="text-[13px] transition-opacity hover:opacity-100 focus-visible:outline-2 focus-visible:outline-offset-4"
              style={{ color: "rgba(246,247,242,0.66)", outlineColor: LIME }}
            >
              {item.label}
            </a>
          ))}
        </nav>
      </header>

      <div className="relative z-10 mx-auto grid max-w-[86rem] grid-cols-12 items-center gap-x-8 gap-y-14 px-6 pb-20 pt-10 md:px-10 md:pb-28 lg:pt-16">
        <div className="col-span-12 lg:col-span-7">
          <motion.p
            {...rise(0.15)}
            className="mb-7 text-[13px] tracking-[0.2em]"
            style={{ color: LIME }}
          >
            A LITTLE FURTHER, TOGETHER
          </motion.p>

          <h1
            id="hero-heading"
            className="max-w-[16ch] text-[clamp(2.9rem,7.2vw,6rem)] font-medium leading-[0.94] tracking-[-0.045em]"
          >
            <WordsPullUp text="Care that keeps moving between appointments." />
          </h1>

          <motion.p
            {...rise(0.55)}
            className="mt-8 max-w-[52ch] text-[15px] leading-[1.6] md:text-base"
            style={{ color: "rgba(246,247,242,0.72)" }}
          >
            Your phone camera tracks a seated reach, counts the repetitions that
            actually held, and sends the session to your therapist. The work you
            do at home stops being something you have to describe from memory.
          </motion.p>

          <motion.div {...rise(0.7)} className="mt-11 flex flex-wrap items-center gap-4">
            <a
              href="/"
              className="group inline-flex items-center gap-2 rounded-full py-1.5 pl-6 pr-1.5 text-[15px] font-medium transition-all hover:gap-3"
              style={{ background: PAPER, color: INK }}
            >
              Sign in to your workspace
              <span
                className="flex h-9 w-9 items-center justify-center rounded-full transition-transform group-hover:scale-105"
                style={{ background: INK }}
              >
                <ArrowRight className="h-4 w-4" style={{ color: PAPER }} />
              </span>
            </a>
            <a
              href="#how"
              className="rounded-full border px-6 py-2.5 text-[15px] transition-colors"
              style={{
                borderColor: "rgba(246,247,242,0.26)",
                color: "rgba(246,247,242,0.86)",
              }}
            >
              See how a session works
            </a>
          </motion.div>
        </div>

        {/* Evidence, not decoration: the actual therapist review screen. */}
        <motion.figure
          {...rise(0.4)}
          className="col-span-12 lg:col-span-5"
        >
          {/* Fixed ratio: these are full-page captures of wildly different
              heights, so the frame owns the geometry, not the asset. */}
          <div
            className="aspect-[4/3] w-full overflow-hidden rounded-xl"
            style={{
              border: "1px solid rgba(246,247,242,0.14)",
              boxShadow: "0 40px 80px -40px rgba(0,0,0,0.75)",
            }}
          >
            <img
              src="/stack/03-session-review.png"
              alt="Therapist session review showing repetition count and movement trace"
              width={1440}
              height={1355}
              className="h-full w-full object-cover object-top"
            />
          </div>
          <figcaption
            className="mt-3 text-[12px]"
            style={{ color: "rgba(246,247,242,0.45)" }}
          >
            Session review — repetitions, tracking quality, and replay.
          </figcaption>
        </motion.figure>
      </div>

      <div
        className="relative z-10 mx-auto max-w-[86rem] px-6 pb-8 md:px-10"
        style={{ borderTop: "1px solid rgba(246,247,242,0.12)" }}
      >
        <p
          className="pt-5 text-[11px] tracking-[0.16em]"
          style={{ color: "rgba(246,247,242,0.4)" }}
        >
          RESEARCH PROTOTYPE · NOT A MEDICAL DEVICE · THRESHOLDS ARE
          DEMONSTRATION TARGETS, NOT CLINICAL TRUTHS
        </p>
      </div>
    </section>
  );
}

export { ReachHero, INK, PAPER, TEAL, LIME, EASE };

