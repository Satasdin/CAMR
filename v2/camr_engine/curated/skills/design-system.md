---
name: design-system
description: Write style.css as a small, modern design system that is readable, consistent and works on phones first
---
# Write the stylesheet

- Start with design tokens as CSS custom properties on :root, one value each: the brand colours from the brief
  (exact values, and use them: the darker one for the header, buttons and headings, the lighter one for backgrounds),
  a text colour and a background with strong contrast (at least 4.5 to 1), --space-1 to --space-5 (0.5rem, 1rem,
  1.5rem, 2rem, 3rem) and --radius (such as 0.75rem). Add no other colours of your own; when the brief has none, use
  near-black #1a1a1a on white and say so in a comment.
- Style every class ARCHITECTURE.md lists, each in its own rule. A stylesheet that styles three classes leaves the
  page plain.
- Use a modern reset: box-sizing border-box on everything, margin 0, images max-width 100% and display block.
- Type: a system font stack (system-ui, -apple-system, Segoe UI, Roboto, sans-serif) or one Google-style pairing, body at 1rem to 1.125rem with line-height 1.5 to 1.6, and headings with clamp() so they scale with the screen.
- Layout: mobile first. One column by default, max-width about 70rem centred with padding on the sides. Use CSS grid with repeat(auto-fit, minmax(16rem, 1fr)) for lists of items, and flexbox for rows of controls. Add wider layouts in @media (min-width: 48rem).
- Components: buttons are at least 44px tall, in the brand colour, with clear :hover and :focus-visible states (a
  darker shade with filter: brightness(0.9), or an outline). Cards use the radius, a subtle border or shadow, and
  padding from the scale. The header is a solid band of the brand colour with light text.
- Solid backgrounds behind text. No gradients under body text, no text on busy images.
- No external resources the page cannot load: no remote images, no remote fonts that the page depends on to be readable.
