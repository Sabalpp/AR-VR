"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import gsap from "gsap";
import { SplitText } from "gsap/dist/SplitText";

gsap.registerPlugin(SplitText);

const INTRO_EASE = "cubic-bezier(0.25,1,0.5,1)";
const IMAGE_ENTRY_Y_PERCENT = 500;
const TEXT_ROTATE_X_START = 90;
const TEXT_TRANSFORM_PERSPECTIVE = 1000;
const IMAGE_Z_INDEX_DURATION = 0.1;
const IMAGE_Z_INDEX_STAGGER = 0.2;
const TEXT_STAGGER = 0.08;
const STACK_SCALE_STEP = 0.15;
const STACK_Y_PERCENT_STEP = 20;
const SPREAD_Y_PERCENT_STEP = 110;
const IMAGE_FADE_STAGGER = 0.08;

/** Real capture surfaces from the product, not stock imagery.
 *  The camera-unavailable capture is deliberately excluded — it is an error
 *  state, and the intro should not open on a failure screen. */
const STACK_IMAGE_SOURCES = [
  "/stack/02-therapist-assignment.png",
  "/stack/01-patient-plan.png",
  "/stack/03-session-review.png",
];

const INK = "#193e38";
const PAPER = "#f6f7f2";

function clampNumber(
  value: unknown,
  min: number,
  max: number,
  fallback: number,
) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return fallback;
  return Math.min(max, Math.max(min, numericValue));
}

interface StackToSpreadIntroProps {
  images?: readonly string[];
  leadingLabel?: string;
  trailingLabel?: string;
  caption?: string;
  imageSize?: number;
  duration?: number;
  fadeOutDuration?: number;
  backgroundColor?: string;
  onComplete?: () => void;
}

const StackToSpreadIntro = forwardRef<HTMLElement, StackToSpreadIntroProps>(
  function StackToSpreadIntro(
    {
      images = STACK_IMAGE_SOURCES,
      leadingLabel = "HUMAN MOVEMENT",
      trailingLabel = "MEASURED CARE",
      caption = "Reach",
      imageSize = 1,
      duration = 1,
      fadeOutDuration = 0.8,
      backgroundColor = PAPER,
      onComplete,
    },
    ref,
  ) {
    const uid = useId().replace(/:/g, "");
    const loaderWrapperId = `loader-wrapper-${uid}`;
    const imgsWrapperId = `imgs-wrapper-${uid}`;
    const rootRef = useRef<HTMLElement | null>(null);
    const imagesRef = useRef<(HTMLDivElement | null)[]>([]);
    const text1Ref = useRef<HTMLParagraphElement | null>(null);
    const text2Ref = useRef<HTMLParagraphElement | null>(null);
    const descriptionTextRef = useRef<HTMLParagraphElement | null>(null);
    const onCompleteRef = useRef(onComplete);
    const safeImageSize = clampNumber(imageSize, 0.5, 2.5, 1);
    const safeDuration = clampNumber(duration, 0.25, 3, 1);
    const safeFadeOutDuration = clampNumber(fadeOutDuration, 0.1, 3, 0.8);

    useEffect(() => {
      onCompleteRef.current = onComplete;
    }, [onComplete]);

    useLayoutEffect(() => {
      const reduceMotion =
        window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ??
        false;

      // Reduced-motion: images already in a vertical line — opacity only.
      if (reduceMotion) {
        const ctx = gsap.context(() => {
          const imageElements = imagesRef.current.filter(Boolean);
          const sideText = [text1Ref.current, text2Ref.current].filter(Boolean);
          const description = descriptionTextRef.current;
          const totalImages = imageElements.length;
          const totalSpread =
            totalImages > 1 ? SPREAD_Y_PERCENT_STEP * (totalImages - 1) : 0;

          gsap.set(`#${imgsWrapperId}`, { yPercent: 0, opacity: 1 });
          gsap.set(imageElements, {
            opacity: 0,
            scale: 1,
            zIndex: (index: number) => index,
            yPercent: (index: number) =>
              totalImages === 1
                ? 0
                : -totalSpread / 2 + index * SPREAD_Y_PERCENT_STEP,
          });
          gsap.set(sideText, { opacity: 0, rotateX: 0 });
          if (description) gsap.set(description, { opacity: 0, rotateX: 0 });

          const tl = gsap.timeline({
            defaults: { ease: "power2.inOut" },
            onComplete: () => {
              gsap.set(rootRef.current, { display: "none" });
              onCompleteRef.current?.();
            },
          });
          tl.timeScale(1 / safeDuration);

          tl.to(imageElements, {
            opacity: 1,
            duration: 0.7,
            stagger: { each: 0.06, from: "center" },
          });
          tl.to(sideText, { opacity: 1, duration: 0.55 }, "-=0.35");
          if (description) {
            tl.to(description, { opacity: 1, duration: 0.55 }, "<");
          }
          tl.to(
            [...sideText, description].filter(Boolean),
            { opacity: 0, duration: 0.5 },
            "+=0.55",
          );
          tl.to(
            imageElements,
            {
              opacity: 0,
              duration: safeFadeOutDuration,
              stagger: { each: 0.04, from: "edges" },
            },
            "-=0.15",
          );
          tl.to(
            rootRef.current,
            { opacity: 0, duration: safeFadeOutDuration },
            "-=0.2",
          );
        }, rootRef);

        return () => ctx.revert();
      }

      const ctx = gsap.context(() => {
        const imageElements = imagesRef.current.filter(Boolean);

        const text1 = SplitText.create(text1Ref.current, { type: "words" });
        const text2 = SplitText.create(text2Ref.current, { type: "words" });
        const descriptionText = SplitText.create(descriptionTextRef.current, {
          type: "words,lines",
        });

        const animatedTextTargets = [
          text1.words,
          text2.words,
          descriptionText.lines,
        ];

        gsap.set(animatedTextTargets, {
          rotateX: TEXT_ROTATE_X_START,
          opacity: 0,
          transformPerspective: TEXT_TRANSFORM_PERSPECTIVE,
          transformOrigin: "50% 100%",
          willChange: "transform",
        });
        gsap.set(imageElements, { opacity: 0 });
        gsap.set(descriptionTextRef.current, { opacity: 1 });

        const tl = gsap.timeline();
        tl.timeScale(1 / safeDuration);

        tl.fromTo(
          `#${imgsWrapperId}`,
          { yPercent: IMAGE_ENTRY_Y_PERCENT, opacity: 0 },
          { yPercent: 0, opacity: 1, duration: 0.5, ease: INTRO_EASE },
        );

        tl.set([text1Ref.current, text2Ref.current], { opacity: 1 }, "<");

        tl.to(
          imageElements,
          { opacity: 1, duration: 0.5, ease: INTRO_EASE },
          "<",
        );

        tl.to(
          animatedTextTargets,
          {
            rotateX: 0,
            opacity: 1,
            stagger: TEXT_STAGGER,
            ease: INTRO_EASE,
          },
          "<+0.5",
        );

        imageElements.forEach((imageElement, index) => {
          tl.to(
            imageElement,
            {
              zIndex: index,
              duration: IMAGE_Z_INDEX_DURATION,
              ease: INTRO_EASE,
            },
            index * IMAGE_Z_INDEX_STAGGER,
          );
        });

        tl.to(
          imageElements,
          {
            scale: (index: number) => 1 + index * STACK_SCALE_STEP,
            yPercent: (index: number) => -(index * STACK_Y_PERCENT_STEP),
            duration: 1,
            stagger: { each: 0.01, from: "end" },
            ease: "power3.inOut",
          },
          "<",
        );

        tl.to(
          imageElements,
          {
            scale: 1,
            yPercent: (index: number, _target: unknown, elements: unknown[]) => {
              const totalImages = elements.length;
              if (totalImages === 1) return 0;
              const totalSpread = SPREAD_Y_PERCENT_STEP * (totalImages - 1);
              return -totalSpread / 2 + index * SPREAD_Y_PERCENT_STEP;
            },
            duration: 1,
            stagger: { each: 0.01, from: "end" },
            ease: "power3.inOut",
          },
          "+=0.2",
        );

        tl.to(
          descriptionText.lines,
          {
            rotateX: TEXT_ROTATE_X_START,
            transformOrigin: "top center",
            opacity: 0,
            duration: 1,
            stagger: TEXT_STAGGER,
            ease: INTRO_EASE,
          },
          "<-0.1",
        );

        tl.to(`#${imgsWrapperId}`, { yPercent: 0, ease: INTRO_EASE }, "<");

        tl.to([text1.words, text2.words], {
          opacity: 0,
          duration: 0.5,
          rotateX: TEXT_ROTATE_X_START,
          transformOrigin: "top center",
          stagger: TEXT_STAGGER,
          ease: INTRO_EASE,
        });

        tl.to(
          imageElements,
          {
            opacity: 0,
            duration: safeFadeOutDuration,
            stagger: { each: IMAGE_FADE_STAGGER, from: "end" },
            onComplete: () => {
              gsap.to(rootRef.current, {
                opacity: 0,
                duration: safeFadeOutDuration,
                ease: INTRO_EASE,
                onComplete: () => {
                  gsap.set(rootRef.current, { display: "none" });
                  onCompleteRef.current?.();
                },
              });
            },
          },
          "<+0.2",
        );

        return () => {
          text1.revert();
          text2.revert();
          descriptionText.revert();
        };
      }, rootRef);

      return () => ctx.revert();
    }, [imgsWrapperId, safeDuration, safeFadeOutDuration]);

    return (
      <section
        ref={(element) => {
          rootRef.current = element;
          if (typeof ref === "function") ref(element);
          else if (ref) ref.current = element;
        }}
        id={loaderWrapperId}
        aria-hidden="true"
        className="fixed inset-0 z-50 flex h-screen w-full items-center justify-center px-[2.5vw] max-[1025px]:px-[5vw] max-md:px-[6vw]"
        style={{ backgroundColor, color: INK }}
      >
        <div className="flex w-full items-center justify-between max-[1025px]:flex-col max-[1025px]:justify-center max-[1025px]:gap-[33vh] max-md:gap-[70vw]">
          <p
            ref={text1Ref}
            className="text-sm tracking-[0.22em] opacity-0 max-[1025px]:text-[2.8vw] max-md:text-[5vw]"
          >
            {leadingLabel}
          </p>

          <div
            id={imgsWrapperId}
            className="relative max-[1025px]:z-[99]"
            style={{
              width: `clamp(4rem, ${6.5 * safeImageSize}vw, 18rem)`,
              height: `clamp(4rem, ${6.5 * safeImageSize}vw, 18rem)`,
            }}
          >
            {images.map((src, index) => (
              <div
                key={`${src}-${index}`}
                ref={(element) => {
                  imagesRef.current[index] = element;
                }}
                className="absolute top-0 left-0 size-full overflow-hidden rounded-md opacity-0"
                style={{ boxShadow: "0 18px 40px -18px rgba(13,36,33,0.55)" }}
              >
                <img
                  src={src}
                  width={1000}
                  height={1000}
                  className="h-full w-full object-cover"
                  alt=""
                />
              </div>
            ))}
          </div>

          <p
            ref={text2Ref}
            className="text-sm tracking-[0.22em] opacity-0 max-[1025px]:text-[2.8vw] max-md:text-[4vw]"
          >
            {trailingLabel}
          </p>
        </div>

        <p
          ref={descriptionTextRef}
          className="absolute bottom-[3vw] left-1/2 w-[40vw] -translate-x-1/2 text-center leading-[1.1] opacity-0 max-[1025px]:bottom-[3vw] max-[1025px]:w-[68vw] max-[1025px]:text-[2.4vw] max-md:bottom-[6vw] max-md:w-[90%] max-md:text-[3.5vw]"
        >
          {caption}
        </p>
      </section>
    );
  },
);

interface StackLoaderProps {
  /** Content revealed once the loader completes — behind the loader from the start. */
  children?: ReactNode;
  onComplete?: () => void;
  images?: readonly string[];
  leadingLabel?: string;
  trailingLabel?: string;
  caption?: string;
  imageSize?: number;
  duration?: number;
  fadeOutDuration?: number;
  backgroundColor?: string;
}

const SEEN_KEY = "reach-intro-seen";

export default function StackLoader({
  children,
  onComplete,
  images = STACK_IMAGE_SOURCES,
  leadingLabel = "HUMAN MOVEMENT",
  trailingLabel = "MEASURED CARE",
  caption = "Reach",
  imageSize = 1,
  // Lower duration = faster timeline (it drives timeScale as 1/duration).
  duration = 0.3,
  fadeOutDuration = 0.35,
  backgroundColor = PAPER,
}: StackLoaderProps) {
  const uid = useId().replace(/:/g, "");
  const shellId = `stack-shell-${uid}`;
  const [introInstance, setIntroInstance] = useState(0);
  // An intro is a first impression, not a toll booth. Play it once per tab.
  const [showIntro, setShowIntro] = useState(true);

  useEffect(() => {
    let seen = false;
    try {
      seen = sessionStorage.getItem(SEEN_KEY) === "1";
    } catch {
      // Private mode or blocked storage: just play the intro.
    }
    if (seen) {
      setShowIntro(false);
      document.body.style.overflow = "";
    }
  }, []);
  const stackToSpreadIntroRef = useRef<HTMLElement | null>(null);
  const previousPropsRef = useRef<{
    imageSize: number;
    duration: number;
    fadeOutDuration: number;
    backgroundColor: string;
  } | null>(null);

  // Hold the page still while the intro owns the viewport, then hand scrolling
  // back. Restored on unmount too, so a mid-intro route change cannot strand it.
  useEffect(() => {
    if (!showIntro) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [introInstance, showIntro]);

  const handleLoaderComplete = useCallback(() => {
    document.body.style.overflow = "";
    try {
      sessionStorage.setItem(SEEN_KEY, "1");
    } catch {
      // Non-fatal: the intro simply plays again next load.
    }
    onComplete?.();
  }, [onComplete]);

  useEffect(() => {
    const next = { imageSize, duration, fadeOutDuration, backgroundColor };
    if (!previousPropsRef.current) {
      previousPropsRef.current = next;
      return;
    }
    const previous = previousPropsRef.current;
    const hasChanged = (Object.keys(next) as (keyof typeof next)[]).some(
      (key) => previous[key] !== next[key],
    );
    if (!hasChanged) return;
    previousPropsRef.current = next;
    setIntroInstance((current) => current + 1);
  }, [backgroundColor, duration, fadeOutDuration, imageSize]);

  return (
    <div
      id={shellId}
      className="relative min-h-screen w-full overflow-x-hidden"
      style={{ background: PAPER }}
    >
      {children}

      {showIntro && (
      <StackToSpreadIntro
        key={introInstance}
        ref={stackToSpreadIntroRef}
        images={images}
        leadingLabel={leadingLabel}
        trailingLabel={trailingLabel}
        caption={caption}
        imageSize={imageSize}
        duration={duration}
        fadeOutDuration={fadeOutDuration}
        backgroundColor={backgroundColor}
        onComplete={handleLoaderComplete}
      />
      )}
    </div>
  );
}
