---
name: behaviour
description: Write app.js, small and dependable, in modern plain JavaScript with no framework and no build step
---
# Write the behaviour

- Plain modern JavaScript in one file, loaded with defer, so the page is ready when it runs. Use const and let, arrow functions and template literals. No frameworks and no imports from the network.
- Find elements once at the top with document.querySelector and querySelectorAll, using the ids and data attributes in ARCHITECTURE.md and index.html.
- Keep state in one plain object, such as const order = new Map(), and write one render() function that updates the page from the state. Every event handler changes the state and then calls render().
- Declare anything that changes later (a total, a count, a message) with let. const is only for what is never
  assigned again: `const total = 0; total += 350;` stops the whole script with a TypeError.
- Use event listeners (addEventListener), never onclick attributes. When the page has onclick attributes, take
  them out of index.html and attach the same handlers here.
- The page loads app.js as a plain script: never write require(), import, module.exports or process. The tool
  names you call (read_file, write_file) are not JavaScript; never put them in the code.
- Change only the part of the page that changes: set a total with textContent, add rows with createElement and
  append. Never replace a whole section's innerHTML, which deletes its buttons.
- Numbers: read data attributes with Number(), and keep money as whole units. Format for display only, for example with Intl.NumberFormat or by joining the currency to the number.
- Show every state: what an empty list says, the running total, and a clear way to remove items or start again.
- Make it work from the keyboard: buttons are buttons, and focus stays where a person expects.
- If the person may want their choices kept, save the state in localStorage and load it at start, inside try and catch.
- Check your work: every selector you use must exist in index.html.
