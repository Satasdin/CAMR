---
name: agents
label: Agents
about: Splitting work between agents: planning first, giving each agent one job and a narrow context, and checking each result.
---
RULE Plan before building. Write down the parts of the work and their order before any part is done.
RULE Give each agent one job it can finish: write one file, answer one question, test one page. A job with "and" in it is two jobs.
RULE Give each agent only what its job needs: the brief, the plan, and the files it builds on. A long prompt buries the instruction.
RULE Write the shared facts down once, in one file every agent reads. Facts passed from agent to agent in words get changed.
RULE Decide the files and their structure before writing any of them, so each agent knows the names the others will use.
RULE Each agent's result is checked before the next one builds on it: the file exists, it is not empty, and it says what the plan asked.
RULE A failed part is tried again once with what went wrong, then the work goes on and the failure is reported. One stuck part must not stop the rest.
RULE The order follows what depends on what: the brief before the structure, the structure before the files, the files before the test.
RULE Agents ask the person only for facts nobody can work out, and all such questions come early, together.
RULE Keep a record of every decision and who made it: a rule written in the system, or the model's choice.
RULE An agent that reviews is not the agent that wrote. A fresh reader catches what the writer took for granted.
RULE Stop an agent after a fixed number of steps. An agent that has not finished by then needs a smaller job, not more steps.
RULE A change to finished work goes to the agent that owns that file, with the file as it is now.
RULE Keep the plan where the person can read it, with each part marked to do, doing, done or failed.
RULE When all parts are done, say what was made, what was checked, and what is still not right.
RULE Never let an agent's own words become a fact for the next agent. Only what the person said or gave is a fact.
CORRECTION Wrong: one agent asked to research, design, build and test a whole site in one go. Right: a plan with a part for each, done in order.
CORRECTION Wrong: every agent reads the whole conversation. Right: each reads the brief, the plan and the files its part needs.
CORRECTION Wrong: the builder guesses the class names the stylesheet uses. Right: the builder is given the list of classes the stylesheet defines.
CORRECTION Wrong: a part that failed blocks the build forever. Right: it is tried once more, then reported, and the build goes on.
CORRECTION Wrong: the agent that wrote the page also declares it tested. Right: a review part opens it in the browser and reads the report.
CORRECTION Wrong: asking the person a question in the middle of every part. Right: asking what is missing once, at the start.
CORRECTION Wrong: "the design agent decided the menu prices". Right: prices only ever come from what the person told.
CORRECTION Wrong: a plan kept in the model's head. Right: a plan written to a file, updated as each part ends.
