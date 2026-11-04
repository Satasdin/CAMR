"""The agent behind the Code screen: the local model working in a folder, with the engine as its memory.

- ``workspace``: the one folder the agent may touch, and the file tools confined to it;
- ``parse``: every tool call in a reply (``camr_engine.agent.parse``, one block at a time, for loops of several steps);
- ``gate``: the approvals a person gives in the page, one per shell command and per MCP call;
- ``shell``: running an allowed command in the workspace, with a time limit and a cleaned environment;
- ``servers``: MCP servers over stdio, added and connected by the person, never by the agent;
- ``skills`` and ``personas``: instruction files loaded on demand, and saved system prompts with their reaches;
- ``brain``: the model the loop talks to, with memory (a reach session) or without;
- ``loop``: one task, step by step, until the model answers without a tool;
- ``marks``: the memory gutter, the lines written while leaning on memory and the lines a person fixed;
- ``desk``: what the Code screen keeps between requests.

Nothing here runs a command or an MCP tool on the model's word alone: each waits for a person to allow it.
"""
