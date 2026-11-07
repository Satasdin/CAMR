---
name: deployment
label: Deployment
about: Getting what was built in front of people safely: static hosting, checks before publishing, and rolling back.
---
RULE A small site of HTML, CSS and JavaScript needs no server: any static host serves the folder as it is.
RULE Before publishing, open the page from the folder itself and check every link, image and script loads.
RULE Use relative paths (style.css, images/logo.png), never paths on your own computer. A path with /Users/ in it breaks for everyone else.
RULE Keep secrets out of anything that is published: no keys, passwords or tokens in HTML or JavaScript. Anything sent to a browser can be read.
RULE Check the page at phone width before publishing. Most visitors arrive on a phone.
RULE Give the page a real title and a meta description: they are what a search result and a shared link show.
RULE Keep the last version that worked, so a bad publish can be undone in one step.
RULE Change one thing per publish, so when something breaks you know what broke it.
RULE After publishing, open the live address and check it, not the copy on your computer.
RULE Files that change often (style.css, app.js) are cached by browsers; after a change, reload without the cache to see it.
RULE Ask the person before publishing anything. Putting something on the internet cannot be fully taken back.
RULE Write down how the site is published, in a few lines, so the next person can do it again.
RULE Compress large images before publishing; a photo straight from a camera is many times bigger than a page needs.
RULE A form that sends data needs somewhere to send it. A static site alone cannot receive a form; say so rather than pretending it works.
RULE Use HTTPS. Every modern host offers it, and browsers warn people away from pages without it.
RULE Keep the folder tidy: only the files the site needs, nothing private, no drafts.
CORRECTION Wrong: <link href="/Users/me/site/style.css">. Right: <link href="style.css">.
CORRECTION Wrong: an API key pasted into app.js "just for now". Right: no key in the page at all.
CORRECTION Wrong: publishing straight after writing. Right: testing the page first, then asking the person.
CORRECTION Wrong: a contact form that does nothing when sent. Right: a phone number and e-mail link, or saying the form needs a service.
CORRECTION Wrong: checking only the copy on your computer. Right: checking the live address after publishing.
CORRECTION Wrong: changing the layout, the prices and the script in one publish. Right: one change, checked, then the next.
CORRECTION Wrong: a 6 MB photo as the page's banner. Right: a resized image of a few hundred kilobytes.
CORRECTION Wrong: no way back after a bad publish. Right: the last working version kept.
