"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Renders a design drawn at a fixed pixel size (the Figma frame, 1440px wide) and scales it to the available width, so the layout stays
 * identical to the mock-up at every screen size. Below the design width the whole stage shrinks; above it, it stays centered at 1:1.
 */
export default function Stage({ width, height, children }: { width: number; height: number; children: ReactNode }) {
  const outer = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);

  useEffect(() => {
    const element = outer.current;
    if (!element) return;
    const update = () => setScale(Math.min(1, element.clientWidth / width));
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, [width]);

  return (
    <div ref={outer} className="stage-fade relative mx-auto w-full overflow-hidden" style={{ maxWidth: width, height: height * scale }}>
      <div className="absolute left-0 top-0 origin-top-left" style={{ width, height, transform: `scale(${scale})` }}>
        {children}
      </div>
    </div>
  );
}
