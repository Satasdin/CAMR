---
name: notebooks
description: Write a Jupyter notebook that answers a question about data, in small clean cells, then run it and fix what fails
---
# Write the notebook

You write the notebook with `notebook_write`: a list of cells, each `{"kind": "code" | "markdown", "source": "..."}`.
Write each cell's source as plain Python or Markdown; the tool builds the .ipynb file. Then call `notebook_run` and
read what every cell printed.

- Start with one Markdown cell: a `# Title` and one sentence saying what the notebook answers.
- One idea per cell, a few lines each: load the data; look at it; clean it; compute one thing; draw one chart.
  A Markdown cell of one or two sentences before each step says what it does.
- The first code cell does all the imports: `import pandas as pd`, `import matplotlib.pyplot as plt` (and
  `import numpy as np` when needed). Only these packages are there; there is no network, so nothing can be
  installed or downloaded.
- Read files from the project folder only, by the path as listed (`pd.read_csv("sales.csv")`). Never an absolute
  path, never a URL. Write files (a cleaned CSV, a chart as PNG) only into the project folder.
- Show every result: end the cell with the value (`df.head()`, `totals`) or `print(...)` it with a few words saying
  what it is. A number nobody sees answers nothing.
- A chart: `fig, ax = plt.subplots(figsize=(7, 4))`, then plot, give it a title and axis labels, then `plt.show()`.
  To keep it as a file too, call `fig.savefig("chart.png", dpi=120, bbox_inches="tight")` before `plt.show()`.
- Keep printed output short: `df.head()`, not the whole table; round numbers (`round(x, 2)`).
- Use only columns that are really in the data (the first lines of each file are in your notes). If the request
  needs data the user did not give, make a small example in the notebook and say plainly in Markdown that it is an
  example.
- End with a Markdown cell: the answer in two or three plain sentences, from the numbers the cells printed.

## When a cell fails

`notebook_run` shows the failing cell with its line numbers and the error. Fix that cell with
`notebook_edit_cell` (its index from 0, and its whole new source), then run the notebook again. Change only what
the error points at. A `KeyError` or `NameError` usually means a column or variable name differs from the data:
check the first lines of the file in your notes.
