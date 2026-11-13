import { useEffect } from "react";

// Blocks that fade and slide in when they scroll into view, on every page.
const SELECTOR = ".page > *:not(.roles), .roles > *, tbody tr";
const STAGGER_MS = 70;
const MAX_STAGGER = 6;

/*
 * Smooth reveal: marks matching elements with data-reveal (hidden by CSS) and adds
 * .revealed when they enter the viewport. Watches the DOM so content that loads
 * later (API data, polling, route changes) is revealed too.
 */
export default function useReveal(rootRef, routeKey) {
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce || !("IntersectionObserver" in window)) return;

    const io = new IntersectionObserver(
      (entries) => {
        let i = 0;
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const el = entry.target;
          el.style.transitionDelay = `${Math.min(i++, MAX_STAGGER) * STAGGER_MS}ms`;
          el.classList.add("revealed");
          el.addEventListener("transitionend", () => { el.style.transitionDelay = ""; }, { once: true });
          io.unobserve(el);
        }
      },
      { rootMargin: "0px 0px -6% 0px", threshold: 0.05 }
    );

    // Watch every element that is not revealed yet. Elements marked by an earlier
    // run of this effect (React StrictMode runs it twice) must be observed again,
    // or they would stay hidden.
    const watched = new WeakSet();
    const scan = () => {
      root.querySelectorAll(SELECTOR).forEach((el) => {
        if (watched.has(el) || el.classList.contains("revealed")) return;
        watched.add(el);
        el.setAttribute("data-reveal", "");
        io.observe(el);
      });
    };

    scan();
    const mo = new MutationObserver(scan);
    mo.observe(root, { childList: true, subtree: true });

    return () => { mo.disconnect(); io.disconnect(); };
  }, [rootRef, routeKey]);
}
