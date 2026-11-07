---
name: scroll-motion
description: Write motion.js, scroll-driven motion with GSAP and ScrollTrigger (scrub, pinning, reveals), calm when reduced motion is on
---
# Scroll motion (motion.js)

motion.js is an ES module, loaded last with `<script type="module" src="motion.js">`, after
`vendor/gsap/gsap.min.js` and `vendor/gsap/ScrollTrigger.min.js`. `gsap` and `ScrollTrigger` are globals; never
import them, and never load anything from the network.

## The shape of the file

```js
const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

if (!calm) {
  gsap.registerPlugin(ScrollTrigger);

  // 1. a timeline tied to the scrollbar: scrub: true moves it exactly with the scroll
  const tl = gsap.timeline({
    scrollTrigger: { trigger: document.body, start: 'top top', end: 'bottom bottom', scrub: true },
  });
  tl.to('#hero-title', { y: -80, ease: 'none' })
    .to('#badge', { rotation: 180, ease: 'none' }, 0);   // ", 0" starts it at the same time

  // 2. every section's parts slide in as they reach the screen
  document.querySelectorAll('section').forEach((section) => {
    gsap.from(section.querySelectorAll('.reveal'), {
      y: 40, opacity: 0, duration: 0.7, stagger: 0.08, ease: 'power2.out',
      scrollTrigger: { trigger: section, start: 'top 80%', toggleActions: 'play none none reverse' },
    });
  });

  // 3. a pinned chapter: it stays still while its contents move
  gsap.timeline({
    scrollTrigger: { trigger: '#chapter-1', start: 'top top', end: '+=100%', pin: true, scrub: true },
  }).from('#chapter-1 .reveal', { x: -60, opacity: 0, stagger: 0.2 });
}
```

## Rules

- Calm first: when `calm` is true, create no ScrollTrigger, no timeline and no loop. Everything stays where it ends up,
  so `gsap.from(... opacity: 0)` must never run in the calm version: then every text is visible.
- Animate only `transform` (x, y, scale, rotation) and `opacity`; never top, left, width or height.
- `scrub: true` for anything tied to the scroll; a number (such as 0.5) only for a small lag.
- One `ScrollTrigger` per thing that moves; a timeline when several move together.
- Select only elements the page has (read index.html first): `#ids` and the classes `reveal` and `layer`.
- Text that changes on its own (a countdown, a clock) is fine in the calm version: it is not motion. Update it with
  `textContent` from `setInterval(tick, 1000)`, and call `tick()` once at the start.
- In the 3D scene, gsap can move three.js objects directly: `tl.to(rocket.rotation, { y: Math.PI * 2 })`,
  `tl.to(rocket.position, { y: 14 }, 0.6)`.
- The CSS keeps the calm version calm too:
  `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }`
