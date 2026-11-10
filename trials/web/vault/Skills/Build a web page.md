---
kind: skill
when: Building a web page, website, landing page, form, calculator or small web app as HTML, CSS and JavaScript. Examples: make a page that, build a website for, create a calculator page, design a landing page.
---
# Build a web page

1. Read the brief twice. List every element it names by id and every rule it states. Each one must appear in the page exactly as named.
2. Write ONE complete file: `<!DOCTYPE html>`, `<html lang="en">`, a `<head>` with charset, a viewport meta tag and a `<title>`, then `<style>`, the `<body>`, then one `<script>` at the end of the body. No outside files, fonts, images or libraries.
3. Plan the layout before styling: one centred column no wider than 720px, generous spacing, one accent colour, system font, large readable type, real words in place of filler text.
4. Make it work on a phone: widths in percent or `max-width`, `box-sizing: border-box` on everything, nothing wider than the screen at 375px.
5. In the script, look each element up once by its id, check the id matches the HTML letter for letter, and attach listeners with `addEventListener`.
6. Read numbers with `Number(...)`, do the arithmetic exactly as the brief states it, and round only where the brief says to.
7. Show results by setting `textContent`. Handle empty or invalid input with a short message, never with an error.
8. Before finishing, walk through the brief's own example by hand against your code and confirm the output matches.
9. Output the whole file in one code block and nothing after it. Keep it under 250 lines so it is never cut off.
