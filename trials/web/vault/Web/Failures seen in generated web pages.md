---
kind: bug
---
# Failures seen in generated web pages, and how each is avoided

These are mistakes a model makes when it writes a web page in one go.

- **The file is cut off.** The page is too long and the closing `</script>` and `</html>` never arrive, so nothing runs. Keep the page short and write the script compactly. Close every tag.
- **An id in the script does not exist in the HTML.** `getElementById` returns null and the first click throws. Use the ids from the brief, spelled the same in both places.
- **The script runs before the elements exist.** Put the one `<script>` at the very end of `<body>`.
- **Numbers are joined as text.** `"50" + 12` gives `"5012"`. Convert every input with `Number()` first.
- **Rounding is done too early or the wrong way.** Compute with full precision and round once at the end with `Math.round`.
- **A button inside a `<form>` reloads the page.** Give buttons `type="button"`, or call `event.preventDefault()`.
- **A count or list on screen goes stale.** Keep the data in one array and redraw the list, the count and the current item from it in one `render()` function after every change.
- **Saved data is not restored.** Read `localStorage` once at start with a fallback of an empty array, and save after every change.
- **Thousands separators are missing or wrong.** Use `toLocaleString("en-US")` for "5,000".
- **A menu that should hide on a phone never hides.** Toggle the `hidden` attribute, and add `[hidden] { display: none !important; }` to the CSS.
- **The page scrolls sideways on a phone.** Add the viewport meta tag and never give anything a fixed width above 100%.
- **Filler text and broken image links.** Write real words for the subject and use no images.
