---
name: motion
label: Motion and 3D pages
about: Pages that move: a three.js scene, scroll-driven motion with GSAP, depth layers, a live countdown and a calm version, from what passed and failed in real builds.
---
RULE Start a 3D scroll page from a whole file that already works, then change only what the brief asks. Writing the scene from nothing is where small models break it.
RULE Load three.js, GSAP and models only from the project's vendor folder. A page that fetches them from the internet breaks offline and in the preview.
RULE For a rocket, use loadRocket(THREE, GLTFLoader) from vendor/camr-rocket.js: the detailed three-stage rocket. makeRocket is a cartoon rocket, for a cartoon look only.
RULE Move the group loadRocket returns, never its children: the model replaces a stand-in when it loads.
RULE Look the rocket's flame up where it is used, rocket.getObjectByName('flame'), not once at the start: the detailed model brings its own flame.
RULE Tie scroll motion to the scrollbar with ScrollTrigger and scrub: true, so the motion goes back when the person scrolls back.
RULE Put every gsap call inside if (!calm), where calm is prefers-reduced-motion. In the calm version nothing moves and every text is visible.
RULE A countdown is text, not motion: update it every second with setInterval in the calm version too, and call it once at the start.
RULE Give the countdown real numbers from the launch time in the brief, in UTC. Dashes or "TBA" when the date is known is a failure.
RULE Put text on a panel (a solid background) or beside the 3D model, never straight on top of it.
RULE Use at least three depth layers, each with its own data-speed, moved with transforms only.
RULE Animate only transform and opacity; never top, left, width or height.
RULE Keep one renderer and one animation loop. Outside the loop (a model loaded, a resize, the calm version) call render() once.
RULE Every word on the page comes from the brief. If a fact is missing, leave that part out rather than write a placeholder.
RULE Check a moving page in a real browser: frames a second while scrolling, a clean console, the calm version, and screenshots down the page.
CORRECTION Wrong: const scene = ... and later scene = ... again. Criticism: the script stops with a TypeError and nothing moves. Right: make each object once and change its properties. Why: a const cannot be given a new value.
CORRECTION Wrong: "Headline placeholder", "Company name" and a countdown of dashes. Criticism: the page looks finished but says nothing true. Right: the company's name, line, launch and numbers as told. Why: the facts are the page.
CORRECTION Wrong: makeRocket for a launch company's page when the detailed rocket is in the kit. Criticism: it looks like a toy. Right: loadRocket. Why: the first rocket that works is not the best one available.
CORRECTION Wrong: the section heading "The mission" sitting on the rocket as it lifts off. Criticism: unreadable where the model is busy. Right: the sections on the other side of the screen, each heading on a panel. Why: text must read on everything behind it.
CORRECTION Wrong: gsap.from(... opacity: 0) also running with reduced motion on. Criticism: the text never appears for people who asked for calm. Right: no gsap at all when calm is true. Why: the calm version must show everything as it ends up.
CORRECTION Wrong: const flame = rocket.getObjectByName('flame') at the top of the file. Criticism: the flame never shows once the detailed rocket has loaded. Right: look it up in the timeline's onUpdate and in the loop. Why: the stand-in and its flame are replaced.
