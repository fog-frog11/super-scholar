"use client";

import {
  motion,
  useMotionValueEvent,
  useReducedMotion,
  useScroll,
  useTransform,
} from "motion/react";
import { useRef, useState } from "react";
import { cn } from "@/lib/utils";

type ScrollDirection = "up" | "down";

export function ScrollReveal({
  children,
  className,
  delay = 0,
  distance = 28,
  amount = 0.18,
  drift = 10,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  distance?: number;
  amount?: number;
  drift?: number;
}) {
  const reduced = useReducedMotion();
  const targetRef = useRef<HTMLDivElement>(null);
  const { scrollY } = useScroll();
  const { scrollYProgress } = useScroll({
    target: targetRef,
    offset: ["start end", "end start"],
  });
  const scrollDrift = useTransform(scrollYProgress, [0, 0.5, 1], [drift, 0, -drift]);
  const previous = useRef(0);
  const [direction, setDirection] = useState<ScrollDirection>("down");

  useMotionValueEvent(scrollY, "change", (latest) => {
    if (Math.abs(latest - previous.current) < 2) return;
    setDirection(latest > previous.current ? "down" : "up");
    previous.current = latest;
  });

  if (reduced) return <div className={className}>{children}</div>;

  return (
    <motion.div ref={targetRef} className={cn(className)} style={{ y: scrollDrift }}>
      <motion.div
        custom={direction}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: false, amount, margin: "-6% 0px -6% 0px" }}
        variants={{
          hidden: (dir: ScrollDirection) => ({
            opacity: 0,
            y: dir === "down" ? distance : -distance,
            scale: 0.988,
            filter: "blur(7px)",
          }),
          visible: {
            opacity: 1,
            y: 0,
            scale: 1,
            filter: "blur(0px)",
          },
        }}
        transition={{ duration: 0.5, delay, ease: [0.22, 1, 0.36, 1] }}
      >
        {children}
      </motion.div>
    </motion.div>
  );
}

export function LandingScrollProgress() {
  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll();
  if (reduced) return null;
  return (
    <motion.div
      aria-hidden="true"
      className="fixed inset-x-0 top-0 z-[70] h-[2px] origin-left bg-[linear-gradient(90deg,#5265ff,#7a62f0,#1bb3bb)]"
      style={{ scaleX: scrollYProgress }}
    />
  );
}
