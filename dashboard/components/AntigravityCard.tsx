"use client";

import React, { useRef, useState, useEffect, useCallback } from "react";

interface AntigravityCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  depth?: number;
}

export function AntigravityCard({
  children,
  className = "",
  depth = 8,
  ...props
}: AntigravityCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const rectRef = useRef<{ left: number; top: number; width: number; height: number } | null>(null);
  const rafId = useRef<number | null>(null);
  const [transform, setTransform] = useState<string>("");
  const [isHovered, setIsHovered] = useState<boolean>(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReducedMotion(mediaQuery.matches);

    const listener = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);
    mediaQuery.addEventListener("change", listener);
    return () => mediaQuery.removeEventListener("change", listener);
  }, []);

  const handleMouseEnter = useCallback(() => {
    if (prefersReducedMotion) return;
    setIsHovered(true);
    // Measure layout ONCE on entry, never in mousemove loop (Category 3: Measurement)
    if (cardRef.current) {
      const r = cardRef.current.getBoundingClientRect();
      rectRef.current = { left: r.left, top: r.top, width: r.width, height: r.height };
    }
  }, [prefersReducedMotion]);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (prefersReducedMotion) return;

      const rect = rectRef.current;
      if (!rect) return;

      const clientX = e.clientX;
      const clientY = e.clientY;

      // Throttle and batch updates to the next animation frame (Category 1: Never patterns)
      if (rafId.current !== null) {
        cancelAnimationFrame(rafId.current);
      }

      rafId.current = requestAnimationFrame(() => {
        const x = clientX - rect.left;
        const y = clientY - rect.top;
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;

        const rotateX = ((y - centerY) / centerY) * -depth * 0.5;
        const rotateY = ((x - centerX) / centerX) * depth * 0.5;

        setTransform(
          `perspective(1000px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateY(-3px)`
        );
      });
    },
    [depth, prefersReducedMotion]
  );

  const handleMouseLeave = useCallback(() => {
    if (rafId.current !== null) {
      cancelAnimationFrame(rafId.current);
      rafId.current = null;
    }
    rectRef.current = null;
    setIsHovered(false);
    setTransform("perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0px)");
  }, []);

  useEffect(() => {
    return () => {
      if (rafId.current !== null) {
        cancelAnimationFrame(rafId.current);
      }
    };
  }, []);

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={{
        transform: prefersReducedMotion ? undefined : transform || undefined,
        // Category 6: Surgical will-change only while actively hovered, auto otherwise
        willChange: isHovered && !prefersReducedMotion ? "transform" : "auto",
        transition: isHovered
          ? "transform 0.08s ease-out, box-shadow 0.2s ease"
          : "transform 0.4s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.4s ease",
      }}
      className={`antigravity-card-root ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

