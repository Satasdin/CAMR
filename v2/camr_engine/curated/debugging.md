---
name: debugging
label: Debugging
about: Finding and fixing what is wrong: reproducing it, reading the error, changing one thing, and checking the fix.
---
RULE First make the problem happen again, on purpose. A bug you cannot repeat cannot be shown fixed.
RULE Read the whole error message. It usually names the file, the line and what was expected.
RULE Change one thing at a time, then check again. Two changes at once hide which one mattered.
RULE Find where the right value turns wrong: check it before and after each step until one step changes it.
RULE In a page, an element that "does nothing" usually means the script found no element: check the id in the HTML matches the one in the script.
RULE A script loaded before its elements exist finds nothing. Load it at the end of the body or with defer.
RULE Numbers read from the page are text. "12" + "30" is "1230"; turn them into numbers first with Number().
RULE A style that does not apply is usually a class name spelled two ways, or a rule further down the file that wins.
RULE A link that goes nowhere points at an id that does not exist. Every href="#x" needs an element with id="x".
RULE Fix the cause, not the symptom. Hiding an error message does not fix what caused it.
RULE After a fix, check the thing that was broken and the things next to it. A fix often breaks a neighbour.
RULE Keep what worked. When rewriting a file to fix it, keep every section, button and fact that was already right.
RULE When stuck, say what you expected, what happened, and what you have ruled out. Writing it down often shows the answer.
RULE Look at the simplest cause first: a typo, a missing file, a wrong path, a value never set.
RULE A fix that cannot be tested is a guess. Say so plainly rather than calling it fixed.
RULE Write down a fix that took long to find, so it is not looked for twice.
CORRECTION Wrong: rewriting the whole page because one button does not work. Right: finding the one line that is wrong and changing it.
CORRECTION Wrong: total = price + total when price is "12". Right: total = total + Number(price).
CORRECTION Wrong: document.getElementById("Cart") when the HTML says id="cart". Right: the same spelling in both.
CORRECTION Wrong: calling it fixed without trying it again. Right: repeating the steps that broke it and seeing it work.
CORRECTION Wrong: removing the error message so the page looks clean. Right: fixing what the error message named.
CORRECTION Wrong: changing three things and not knowing which fixed it. Right: one change, then a check.
CORRECTION Wrong: a fix that drops the opening hours from the page. Right: a fix that keeps everything else as it was.
CORRECTION Wrong: "it should work now". Right: "I tested it: the total now shows 950 after adding two items".
