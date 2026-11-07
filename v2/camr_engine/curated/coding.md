---
name: coding
label: Coding
about: Writing small, working software: files, names, structure, HTML, CSS and JavaScript, and checking that it runs.
---
RULE Keep one job in one file. A page goes in index.html, its look in style.css and its behaviour in app.js, so each can be changed without reading the others.
RULE Write the smallest thing that works, then test it, then add to it. Do not write the whole project before running any of it.
RULE Name things for what they are: totalPrice, not x; bookingForm, not form1. A good name saves a comment.
RULE Read a file before you change it. Change only the lines the task is about, and leave the rest as they were.
RULE Every link needs a target. Before you write a link to a section, make sure a section with that id exists, and when you remove a section, remove its links too.
RULE A web page starts with <!doctype html>, a lang on <html>, a <meta charset="utf-8">, a viewport meta tag and a <title>. Without the viewport tag a page is tiny on a phone.
RULE Use real elements: <button> for actions, <a> for going somewhere, <nav>, <main>, <section>, <footer> for the parts of a page. Divs give no meaning to a screen reader or a keyboard.
RULE Every form field has a <label>. A placeholder disappears when you type, so it is not a label.
RULE In JavaScript, wait for the page: put the script at the end of <body>, or use defer. A script that runs before its elements exist finds nothing.
RULE Check what a user typed before you use it. Empty, too long and not-a-number are normal input, and the page must say what is wrong instead of breaking.
RULE Do arithmetic on numbers, not on text. Values from a page are strings: Number("5") + 1 is 6, but "5" + 1 is "51".
RULE Keep money as whole units or cents, never as floating-point fractions, and format it only when showing it. 0.1 + 0.2 is not 0.3 in floating point.
RULE Put a value used twice in one place: a CSS variable for a colour, a constant for a limit. Then a change is one edit.
RULE Do not leave code you are not using: no commented-out blocks, no empty functions, no test logs in the final file.
RULE When a task has several files, write them one at a time and check each exists before you finish. Saying you will write a file is not writing it.
RULE Finish by saying what you made and how to see it, and name anything you could not do. Do not say it is done if you did not test it.
CORRECTION Wrong: <a href="#about">About</a> with no element whose id is about. Criticism: a dead link, and the user notices at once. Right: add the section with id="about", or remove the link. Why: links and targets must change together.
CORRECTION Wrong: the model said "I will now create script.js" and stopped. Criticism: nothing was made. Right: call the tool that writes the file. Why: only a tool call changes anything; words do not.
CORRECTION Wrong: rewrote all of a 200-line file to change one colour. Criticism: too much risk for a tiny change, and other parts changed by accident. Right: edit the one line. Why: small edits keep what already works.
CORRECTION Wrong: document.getElementById("total").innerText = a + b, where a and b came straight from inputs. Criticism: "2" + "3" gives 23. Right: convert with Number() first and check the result is a number. Why: everything read from a page is text.
CORRECTION Wrong: <div onclick="send()">Send</div>. Criticism: it cannot be reached with a keyboard, and a screen reader does not call it a button. Right: <button type="button">Send</button>. Why: real elements bring behaviour for free.
CORRECTION Wrong: wrote lorem ipsum and "Your text here" into the page. Criticism: a placeholder looks finished until someone reads it. Right: use the real words you were given, or leave the part out and say so. Why: placeholders ship by accident.
CORRECTION Wrong: linked style.css in the page but never wrote style.css. Criticism: the page loads with no styling and no error the user can see. Right: write every file the page links to. Why: a missing file fails quietly.
CORRECTION Wrong: asked the same read_file three times with nothing changed. Criticism: wasted steps, and the answer cannot differ. Right: use what you already read and move on. Why: a file does not change unless something wrote to it.
