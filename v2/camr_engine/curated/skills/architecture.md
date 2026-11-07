---
name: architecture
description: Decide the files and the structure of a small web product before any code is written
---
# Plan the structure

You write ARCHITECTURE.md from BRIEF.md. A good plan is short and specific, so that each later agent knows exactly what to make.

- **Files.** A small static site is three files: index.html (structure and content), style.css (all styling) and app.js (all behaviour, only if something must happen when a person clicks or types). Add more pages only when the brief has clearly separate things to show.
- **Sections of index.html, in order.** Give each an id and a one-line purpose. The usual order is a header with the name and main action, the main content (what is offered), any interactive part, practical details (where, when, how to reach), then a footer. Only include sections the brief has facts for.
- **Interactive parts.** For each, name the elements app.js needs (with ids or data attributes, such as data-price on items) and say what happens step by step, such as "pressing Add puts the item in the list and updates the total".
- **States.** Name the empty, working and finished states of each interactive part.
- **Class names.** List every class the page will use, one line each with what it styles: a header, a hero or intro,
  a grid of items and one item card, buttons, the interactive part and its rows and total, the practical details,
  the footer. Use plain names such as site-header, item-grid, item-card, btn, list-total. The designer styles exactly
  these and the builder uses exactly these, so they must match.
- **Design tokens.** The colours from the brief (exact values) and what each is for (background, text, buttons),
  one or two typefaces, and a spacing scale.
- **Only what is known.** Plan no section for something the brief lists as not known (no e-mail, social media,
  reviews or opening hours unless the brief has them).

Write it as short headings and lists. Do not write code here.
