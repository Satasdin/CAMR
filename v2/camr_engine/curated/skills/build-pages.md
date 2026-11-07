---
name: build-pages
description: Write semantic, accessible HTML pages from the brief and the architecture
---
# Write the page

- Start with <!doctype html>, <html lang="en">, <meta charset="utf-8">, <meta name="viewport" content="width=device-width, initial-scale=1">, a real <title> and a meta description from the brief.
- Link the stylesheet in <head> with <link rel="stylesheet" href="style.css">. Load behaviour at the end with <script src="app.js" defer></script>, only if ARCHITECTURE.md has an app.js.
- Use landmarks: <header>, <nav> when there are several sections, <main>, <section id="..."> for each section in ARCHITECTURE.md with an <h2>, and <footer>.
- Every fact on the page comes from BRIEF.md, copied exactly. Nothing else: no slogans, claims, testimonials, years or contact details that are not in the brief.
- Lists of items are <ul> or a grid of <article> cards. Put values that behaviour needs in data attributes, such as data-price="180" and data-name="...".
- Controls are real <button type="button"> elements with a visible label that says the action, and a data attribute
  saying what they act on (data-add="paperbacks"). No onclick or other on... attributes: app.js attaches every
  handler. Form fields have <label>s.
- Give the interactive part's moving pieces ids that app.js can find: the list (id="reading-list-items"), the total
  (id="total"), an empty message.
- Every link points to something that exists: an id on this page, or a file that is being written.
- Use the class names that style.css defines. Do not write inline styles.
