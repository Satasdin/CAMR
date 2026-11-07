---
name: layers
description: Parallax depth layers that move at different speeds while scrolling, with transforms, will-change and a clear z-order
---
# Depth layers (parallax)

Layers are empty divs behind the content, each moving at its own speed as the page scrolls: far ones slowly, near
ones faster. They are decoration, so they are `aria-hidden`.

## In index.html (first thing in the body)

```html
<div class="sky" aria-hidden="true">
  <div class="layer layer-far" data-speed="0.2"></div>
  <div class="layer layer-mid" data-speed="0.5"></div>
  <div class="layer layer-near" data-speed="0.9"></div>
</div>
```

## In the stylesheet

```css
.sky { position: fixed; inset: 0; z-index: 0; overflow: hidden; pointer-events: none; }
.layer { position: absolute; left: 0; right: 0; top: -20vh; height: 160vh; will-change: transform; }
.layer-far  { background: radial-gradient(ellipse at 50% 80%, #1b2a6b, #050816 70%); }
.layer-mid  { background-image: radial-gradient(1px 1px at 20px 30px, #fff 50%, transparent 51%); background-size: 180px 180px; }
.layer-near { background-image: radial-gradient(2px 2px at 40px 60px, #fff 50%, transparent 51%); background-size: 260px 260px; }
main { position: relative; z-index: 2; }
```

Each layer is taller than the screen (160vh, starting 20vh above it), so moving it never shows an edge. Order on
screen is the order of z-index: the sky (0), the 3D canvas if there is one (1), the content (2).

## In motion.js

```js
if (!calm) {
  document.querySelectorAll('.layer').forEach((layer) => {
    const speed = Number(layer.dataset.speed);
    gsap.to(layer, {
      y: () => -speed * window.innerHeight * 0.5, ease: 'none',
      scrollTrigger: { trigger: document.body, start: 'top top', end: 'bottom bottom', scrub: true,
                       invalidateOnRefresh: true },
    });
  });
}
```

## Rules

- Move layers only with transforms (gsap's `y`), never with `top` or `background-position`.
- At least three layers, each with a different `data-speed`: the check counts the different speeds.
- `will-change: transform` on the layers only, not on everything.
- In the calm version (reduced motion) the layers do not move at all: no ScrollTrigger is made for them.
