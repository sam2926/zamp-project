import * as React from 'react'
import { useEffect, useRef } from 'react'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

import { cn } from '@/lib/utils'

if (typeof window !== 'undefined') {
  gsap.registerPlugin(ScrollTrigger)
}

// -------------------------------------------------------------------------
// 1. THEME-ADAPTIVE INLINE STYLES
// -------------------------------------------------------------------------
/*
 * Mixing happens in sRGB, not OKLCH as the source component did.
 * `color-mix(in oklch, #ffffff 40%, transparent)` resolves to
 * `oklch(0.99 0.00005 none / 0.4)` — a greyscale colour has no hue, so the hue
 * channel comes out as `none`, and gradients built from it never rasterise.
 * That made the gradient-clipped heading and the giant background text paint as
 * nothing at all. sRGB has no hue channel to be undefined; at these low
 * percentages the two spaces are visually indistinguishable anyway.
 */
const STYLES = `
.cinematic-footer-wrapper {
  /* The typeface is loaded and set globally in styles.css — the whole site
     shares it, so this component no longer imports its own. */
  font-family: var(--font);
  -webkit-font-smoothing: antialiased;

  --pill-bg-1: color-mix(in srgb, var(--foreground) 3%, transparent);
  --pill-bg-2: color-mix(in srgb, var(--foreground) 1%, transparent);
  --pill-shadow: color-mix(in srgb, var(--background) 50%, transparent);
  --pill-highlight: color-mix(in srgb, var(--foreground) 10%, transparent);
  --pill-inset-shadow: color-mix(in srgb, var(--background) 80%, transparent);
  --pill-border: color-mix(in srgb, var(--foreground) 8%, transparent);

  --pill-bg-1-hover: color-mix(in srgb, var(--foreground) 8%, transparent);
  --pill-bg-2-hover: color-mix(in srgb, var(--foreground) 2%, transparent);
  --pill-border-hover: color-mix(in srgb, var(--foreground) 20%, transparent);
  --pill-shadow-hover: color-mix(in srgb, var(--background) 70%, transparent);
  --pill-highlight-hover: color-mix(in srgb, var(--foreground) 20%, transparent);
}

@keyframes footer-breathe {
  0% { transform: translate(-50%, -50%) scale(1); opacity: 0.6; }
  100% { transform: translate(-50%, -50%) scale(1.1); opacity: 1; }
}

@keyframes footer-scroll-marquee {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}

.animate-footer-breathe { animation: footer-breathe 8s ease-in-out infinite alternate; }
.animate-footer-scroll-marquee { animation: footer-scroll-marquee 40s linear infinite; }

.footer-bg-grid {
  background-size: 60px 60px;
  background-image:
    linear-gradient(to right, color-mix(in srgb, var(--foreground) 3%, transparent) 1px, transparent 1px),
    linear-gradient(to bottom, color-mix(in srgb, var(--foreground) 3%, transparent) 1px, transparent 1px);
  mask-image: linear-gradient(to bottom, transparent, black 30%, black 70%, transparent);
  -webkit-mask-image: linear-gradient(to bottom, transparent, black 30%, black 70%, transparent);
}

.footer-aurora {
  background: radial-gradient(
    circle at 50% 50%,
    color-mix(in srgb, var(--primary) 15%, transparent) 0%,
    color-mix(in srgb, var(--secondary) 15%, transparent) 40%,
    transparent 70%
  );
}

.footer-glass-pill {
  background: linear-gradient(145deg, var(--pill-bg-1) 0%, var(--pill-bg-2) 100%);
  box-shadow:
      0 10px 30px -10px var(--pill-shadow),
      inset 0 1px 1px var(--pill-highlight),
      inset 0 -1px 2px var(--pill-inset-shadow);
  border: 1px solid var(--pill-border);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.footer-glass-pill:hover {
  background: linear-gradient(145deg, var(--pill-bg-1-hover) 0%, var(--pill-bg-2-hover) 100%);
  border-color: var(--pill-border-hover);
  box-shadow:
      0 20px 40px -10px var(--pill-shadow-hover),
      inset 0 1px 1px var(--pill-highlight-hover);
  color: var(--foreground);
}

/* The selected tab reads as pressed rather than merely hovered. */
.footer-glass-pill[data-active='true'] {
  background: linear-gradient(145deg, var(--pill-bg-1-hover) 0%, var(--pill-bg-2-hover) 100%);
  border-color: color-mix(in srgb, var(--primary) 60%, transparent);
  color: var(--foreground);
}

.footer-giant-bg-text {
  font-size: 26vw;
  line-height: 0.75;
  font-weight: 900;
  letter-spacing: -0.05em;
  color: transparent;
  -webkit-text-stroke: 1px color-mix(in srgb, var(--foreground) 5%, transparent);
  background: linear-gradient(180deg, color-mix(in srgb, var(--foreground) 10%, transparent) 0%, transparent 60%);
  -webkit-background-clip: text;
  background-clip: text;
}

.footer-text-glow {
  background: linear-gradient(180deg, var(--foreground) 0%, color-mix(in srgb, var(--foreground) 40%, transparent) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  filter: drop-shadow(0px 0px 20px color-mix(in srgb, var(--foreground) 15%, transparent));
}

@media (prefers-reduced-motion: reduce) {
  .animate-footer-breathe,
  .animate-footer-scroll-marquee { animation: none; }
  .footer-glass-pill { transition: none; }
}
`

// -------------------------------------------------------------------------
// 2. MAGNETIC BUTTON PRIMITIVE (Zero Dependency)
// -------------------------------------------------------------------------
export type MagneticButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> &
  React.AnchorHTMLAttributes<HTMLAnchorElement> & {
    as?: React.ElementType
  }

const MagneticButton = React.forwardRef<HTMLElement, MagneticButtonProps>(
  ({ className, children, as: Component = 'button', ...props }, forwardedRef) => {
    const localRef = useRef<HTMLElement>(null)

    useEffect(() => {
      if (typeof window === 'undefined') return
      const element = localRef.current
      if (!element) return
      // Pointer-follow is a mouse affordance; on touch it just fights the scroll.
      if (!window.matchMedia('(hover: hover)').matches) return
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

      const handleMouseMove = (e: MouseEvent) => {
        const rect = element.getBoundingClientRect()
        const h = rect.width / 2
        const w = rect.height / 2
        const x = e.clientX - rect.left - h
        const y = e.clientY - rect.top - w

        gsap.to(element, {
          x: x * 0.4,
          y: y * 0.4,
          rotationX: -y * 0.15,
          rotationY: x * 0.15,
          scale: 1.05,
          ease: 'power2.out',
          duration: 0.4,
        })
      }

      const handleMouseLeave = () => {
        gsap.to(element, {
          x: 0,
          y: 0,
          rotationX: 0,
          rotationY: 0,
          scale: 1,
          ease: 'elastic.out(1, 0.3)',
          duration: 1.2,
        })
      }

      element.addEventListener('mousemove', handleMouseMove)
      element.addEventListener('mouseleave', handleMouseLeave)

      return () => {
        element.removeEventListener('mousemove', handleMouseMove)
        element.removeEventListener('mouseleave', handleMouseLeave)
        gsap.killTweensOf(element)
      }
    }, [])

    return (
      <Component
        ref={(node: HTMLElement) => {
          ;(localRef as React.MutableRefObject<HTMLElement | null>).current = node
          if (typeof forwardedRef === 'function') forwardedRef(node)
          else if (forwardedRef)
            (forwardedRef as React.MutableRefObject<HTMLElement | null>).current = node
        }}
        className={cn('cursor-pointer', className)}
        {...props}
      >
        {children}
      </Component>
    )
  },
)
MagneticButton.displayName = 'MagneticButton'

// -------------------------------------------------------------------------
// 3. MAIN COMPONENT
// -------------------------------------------------------------------------

/** Marquee copy states what the product actually claims, so the strip is a
 *  summary rather than decoration. */
const MarqueeItem = () => (
  <div className="flex items-center space-x-12 px-6">
    <span>Calibrated Confidence</span> <span className="text-primary/60">✦</span>
    <span>Page-Level Provenance</span> <span className="text-secondary/60">✦</span>
    <span>Arithmetic Validation</span> <span className="text-primary/60">✦</span>
    <span>Deterministic Coverage</span> <span className="text-secondary/60">✦</span>
    <span>Field-Level Review</span> <span className="text-primary/60">✦</span>
  </div>
)

export interface CinematicTab {
  id: string
  label: string
}

export function CinematicFooter({
  tabs,
  onSelectTab,
}: {
  tabs: CinematicTab[]
  onSelectTab: (id: string) => void
}) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const giantTextRef = useRef<HTMLDivElement>(null)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const linksRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (typeof window === 'undefined') return
    if (!wrapperRef.current) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    const ctx = gsap.context(() => {
      gsap.fromTo(
        giantTextRef.current,
        { y: '10vh', scale: 0.8, opacity: 0 },
        {
          y: '0vh',
          scale: 1,
          opacity: 1,
          ease: 'power1.out',
          // The reveal finishes when the section reaches the top of the viewport,
          // i.e. the moment it becomes fully pinned. Scrubbing to `bottom bottom`
          // would spread the fade across the whole 160vh wrapper and leave the
          // section looking empty for most of the time it is on screen.
          scrollTrigger: {
            trigger: wrapperRef.current,
            start: 'top 90%',
            end: 'top top',
            scrub: 1,
          },
        },
      )

      gsap.fromTo(
        [headingRef.current, linksRef.current],
        { y: 50, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          stagger: 0.15,
          ease: 'power3.out',
          scrollTrigger: {
            trigger: wrapperRef.current,
            start: 'top 75%',
            end: 'top top',
            scrub: 1,
          },
        },
      )
    }, wrapperRef)

    return () => ctx.revert()
  }, [])

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: STYLES }} />

      {/*
        The pinned reveal.
        The original used `position: fixed` inside a `clip-path` wrapper. That
        combination hit-tests correctly but never paints in Chromium — the fixed
        layer gets promoted and the ancestor's clip is applied in the wrong
        coordinate space, so the section renders as a blank gap.
        `sticky` gives the identical pinned effect with no clip and no promoted
        layer. The wrapper is taller than the viewport; the difference is how far
        the section stays pinned while you scroll past it.
      */}
      <div ref={wrapperRef} className="relative h-[160vh] w-full">
        <footer className="cinematic-footer-wrapper sticky top-0 flex h-screen w-full flex-col justify-between overflow-hidden bg-background text-foreground">
          {/* Ambient Light & Grid Background */}
          <div className="footer-aurora pointer-events-none absolute left-1/2 top-1/2 z-0 h-[60vh] w-[80vw] -translate-x-1/2 -translate-y-1/2 animate-footer-breathe rounded-[50%] blur-[80px]" />
          <div className="footer-bg-grid pointer-events-none absolute inset-0 z-0" />

          <div
            ref={giantTextRef}
            className="footer-giant-bg-text pointer-events-none absolute -bottom-[5vh] left-1/2 z-0 -translate-x-1/2 select-none whitespace-nowrap"
          >
            INVOICES
          </div>

          {/* 1. Diagonal Sleek Marquee */}
          <div className="absolute left-0 top-12 z-10 w-full -rotate-2 scale-110 overflow-hidden border-y border-border/50 bg-background/60 py-4 shadow-2xl backdrop-blur-md">
            <div className="flex w-max animate-footer-scroll-marquee text-xs font-bold uppercase tracking-[0.3em] text-muted-foreground md:text-sm">
              <MarqueeItem />
              <MarqueeItem />
            </div>
          </div>

          {/* 2. Main Center Content */}
          <div className="relative z-10 mx-auto mt-20 flex w-full max-w-5xl flex-1 flex-col items-center justify-center px-6">
            <h2
              ref={headingRef}
              className="footer-text-glow mb-12 text-center text-5xl font-black tracking-tighter md:text-8xl"
            >
              Ready to begin?
            </h2>

            {/* The three pills are navigation — each leaves for its own page. */}
            <div ref={linksRef} className="flex w-full flex-col items-center gap-6">
              <nav
                className="mt-2 flex w-full flex-wrap justify-center gap-3 md:gap-6"
                aria-label="Sections"
              >
                {tabs.map((tab) => (
                  <MagneticButton
                    key={tab.id}
                    as="button"
                    type="button"
                    onClick={() => onSelectTab(tab.id)}
                    className="footer-glass-pill rounded-full px-6 py-3 text-xs font-medium text-muted-foreground hover:text-foreground md:text-sm"
                  >
                    {tab.label}
                  </MagneticButton>
                ))}
              </nav>
            </div>
          </div>

          {/* 3. Bottom Bar */}
          <div className="relative z-20 flex w-full flex-col items-center justify-between gap-6 px-6 pb-8 md:flex-row md:px-12">
            <div className="order-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground md:order-1 md:text-xs">
              Invoice extraction · DocILE evaluation build
            </div>

            <MagneticButton
              as="button"
              type="button"
              onClick={scrollToTop}
              aria-label="Back to top"
              className="footer-glass-pill order-3 flex h-12 w-12 items-center justify-center rounded-full text-muted-foreground hover:text-foreground group"
            >
              <svg
                className="h-5 w-5 transform transition-transform duration-300 group-hover:-translate-y-1.5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M5 10l7-7m0 0l7 7m-7-7v18"
                />
              </svg>
            </MagneticButton>
          </div>
        </footer>
      </div>
    </>
  )
}
