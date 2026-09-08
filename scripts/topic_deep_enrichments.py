"""Curated deep context + memory hooks for lecture note topics (L02–L05)."""

from __future__ import annotations

import re

# topic_id -> (context paragraph, remember line)
OVERRIDES: dict[str, tuple[str, str]] = {
    "L2-T02": (
        "This lecture sits in the middle of the data-science stack: pandas cleans and reshapes tables, NumPy does fast numeric work, then visualization and modeling sit on top. If the pipeline picture feels abstract, treat it as the order you will actually import libraries in real notebooks.",
        "NumPy speed comes from storing one dtype in contiguous memory — that is why lists feel fine for 10 items but hurt at millions.",
    ),
    "L2-T03": (
        "Every example in this lecture reuses the same `votes` and `costs` arrays so you can focus on syntax instead of re-reading new data. `votes` is numeric; `costs` is stored as strings on purpose — that dtype choice becomes important when stacking and aggregating later.",
        "When output looks wrong, check dtype first (`votes.dtype`, `costs.dtype`) before blaming the operation.",
    ),
    "L2-T04": (
        "Indexing answers one question: “give me the element at this position.” It is the foundation for every filter, slice, and reshape that follows. Think position number, not value.",
        "NumPy indexing returns `np.int64` scalars — not plain Python `int` — which matters when you chain operations.",
    ),
    "L2-T05": (
        "Before slicing ranges, get comfortable asking for a single element. `len()` and `.size` both report length on 1D arrays; negative indices count backward from the end.",
        "Prefer `arr[-1]` over `arr[len(arr)-1]` — same result, clearer intent.",
    ),
    "L2-T06": (
        "Direct indexing is strict: one bad position raises `IndexError` immediately. This is different from slicing (next sections), which quietly returns whatever fits.",
        "Indexing = strict; slicing = forgiving — do not mix up their error behavior in exams or debugging.",
    ),
    "L2-T07": (
        "Positive indices march left → right starting at 0. Negative indices march right → left starting at −1 for the last element. The diagram is worth memorizing because every off-by-one bug traces back here.",
        "Positive and negative indices describe the same cells — they are two coordinate systems on one array.",
    ),
    "L2-T08": (
        "Slicing means “give me a contiguous run of elements.” The stop index is **excluded**, which is the single most common NumPy mistake. `start:end` includes `start`, excludes `end`.",
        "If your slice is one element short, you probably forgot that `end` is not included.",
    ),
    "L2-T09": (
        "Fancy indexing uses a list of positions; slicing uses a start:stop range. They can return the same values but work differently — fancy allows repeats and any order.",
        "Same output does not mean same mechanism — know which tool you are using before debugging.",
    ),
    "L2-T10": (
        "Omitted `start` or `stop` means “from the beginning” or “through the end.” Combined with a step, you can reverse or stride through an array without loops.",
        "`arr[:]` copies the view logic of the full span; `arr[::-1]` reverses in one expression.",
    ),
    "L2-T11": (
        "Negative indices work inside slices too: `arr[-3:]` means “last three elements.” The slice rules (stop excluded) still apply.",
        "A negative start in a slice counts from the end, but the end index is still exclusive.",
    ),
    "L2-T12": (
        "Unlike direct indexing, slicing **never** raises `IndexError` for out-of-range bounds — NumPy clips to what exists. That makes slicing safe for “give me everything from here onward” patterns.",
        "Out-of-range slice → smaller result, not an error. Out-of-range index → error.",
    ),
    "L2-T13": (
        "`np.arange(start, stop, step)` builds evenly spaced values like `range()`, but returns a NumPy array and accepts float steps. You will use it constantly to manufacture practice data.",
        "Stop is excluded (like `range`). For floats, prefer `arange` over Python `range`.",
    ),
    "L2-T14": (
        "Python `range()` only supports integer steps. `np.arange` supports decimals — essential for grids, simulation steps, and plotting axes.",
        "Need `0.1, 0.2, …`? `arange` (or later `linspace`) — not `range`.",
    ),
    "L2-T15": (
        "A negative **step** walks backward through the array. Combine with omitted bounds to reverse or sample every second element from the end.",
        "Step sign controls direction; magnitude controls stride.",
    ),
    "L2-T16": (
        "These cells are deliberate drills — predict each output before running. They compress indexing, slicing, and `arange` into exam-style checks.",
        "Pause and write the answer on paper first; only then run the cell to verify.",
    ),
    "L2-T17": (
        "A 2D array is a grid: rows × columns. One index pair `[row, col]` pins a single cell; one index alone can return an entire row.",
        "Read shape as `(rows, columns)` — same convention as matrices in math class.",
    ),
    "L2-T18": (
        "Row selection uses the first index; column selection uses the second. `:` means “all” along that axis.",
        "`y[2, :]` and `y[2]` both touch row 2 — but they do not always return the same shape (see next topic).",
    ),
    "L2-T19": (
        "`y[2]` collapses the row dimension to 1D. `y[2:]` keeps it 2D with shape `(1, ncols)`. Shape matters when you feed data into functions expecting 2D.",
        "Single index → dimension drops; slice → dimension preserved.",
    ),
    "L2-T20": (
        "Sub-block slicing combines row and column ranges: “from this row onward AND from this column onward.” Picture a rectangle cut from the grid.",
        "Both axes slice at once — draw the rectangle before writing the brackets.",
    ),
    "L2-T21": (
        "Boolean masking filters by condition: compare the array to a threshold, get True/False per cell, pass that mask back into the array. No `for` loop required.",
        "Mask length must match array length — misaligned masks are a common silent bug.",
    ),
    "L2-T22": (
        "You can pass an explicit True/False list of the same length instead of a comparison. Comparisons are just the convenient way to **build** that mask.",
        "Mask is a parallel array of booleans — same length as the data.",
    ),
    "L2-T23": (
        "A mask built from `votes` can filter `costs` too, as long as both arrays align position-by-position. This is how you answer “costs where votes are high.”",
        "Position `i` in every aligned array refers to the same real-world row.",
    ),
    "L2-T24": (
        "Integer list indexing picks arbitrary positions — order and repeats allowed. Useful for reordering or duplicating elements without loops.",
        "List index `[3,3,3]` is valid; slice `3:3` is empty.",
    ),
    "L2-T25": (
        "A miniature analysis chain: filter → count → interpret. This is the pattern real EDA notebooks use dozens of times per session.",
        "Compose mask → filter → aggregate; each step should have one clear question.",
    ),
    "L2-T26": (
        "Combine conditions with `&` (and), `|` (or), `~` (not). **Parentheses are required** because Python operator precedence will break your expression otherwise.",
        "Never use Python `and` / `or` on NumPy arrays — use `&` / `|` with parentheses.",
    ),
    "L2-T27": (
        "`np.where(cond)` returns **all** indices where `cond` is True. Python `.index()` only finds the **first** match in a list — different job entirely.",
        "Need every match position → `np.where`; need first match in a list → `.index()`.",
    ),
    "L2-T28": (
        "This doubt session is about **plain Python lists**, not NumPy — list slicing with a negative step behaves subtly differently. Know which object type you are holding before applying rules.",
        "List slicing rules ≠ NumPy slicing rules when step is negative — check the type first.",
    ),
    "L2-T29": (
        "Full copy vs full view semantics: `arr[:]` spans the whole array with default step 1. Reversal uses step `−1`. These two patterns show up in almost every notebook.",
        "`[::-1]` is the idiomatic reverse — memorize it.",
    ),
    "L2-T30": (
        "`np.column_stack` glues 1D arrays as columns of a 2D table — like adding columns in a spreadsheet. Dtype promotion rules apply (ints + floats → float; mixing with strings → string).",
        "Stacking is how separate measurements become one analyzable table.",
    ),
    "L2-T31": (
        "When one column is strings, NumPy may promote the whole stack to string dtype — numbers become text. That breaks numeric aggregates until you cast back.",
        "Check `.dtype` after `column_stack` — string contamination is silent.",
    ),
    "L2-T32": (
        "`reshape(rows, cols)` repacks the **same** elements into a new grid. Nothing is added or removed — only the interpretation of positions changes.",
        "Total elements before reshape must equal rows × cols.",
    ),
    "L2-T33": (
        "If rows × cols ≠ total elements, NumPy raises an error. Count elements (`size`) before choosing a new shape.",
        "Multiply dimensions mentally before calling `reshape`.",
    ),
    "L2-T34": (
        "Exactly one dimension may be `-1` — NumPy computes it from the rest. Handy when you know one axis (e.g. “4 rows”) but not the other.",
        "Only one `-1` per `reshape` call.",
    ),
    "L2-T35": (
        "Reshape changes layout without moving data semantics; transpose swaps rows and columns (reflection across the diagonal). They answer different questions.",
        "Reshape = repack; transpose = flip rows ↔ columns.",
    ),
    "L2-T36": (
        "Aggregates collapse many numbers into summaries: sum, mean, min, max, std. They are the first numeric answers you report in EDA (“typical value?”, “spread?”).",
        "One aggregate = one number summarizing many cells (until you add `axis`).",
    ),
    "L2-T37": (
        "Comparisons on arrays are **element-wise** and return boolean arrays — the fuel for masking. Combine with `&`, `|`, `~`, not plain `and`/`or`.",
        "Comparison → boolean array → mask → filter. That chain is core NumPy fluency.",
    ),
    "L2-T38": (
        "Sorting rearranges values for ranking, QC, and “top N” questions. NumPy can return a new sorted array or sort in place — different side effects.",
        "`np.sort` copies; `.sort()` mutates — pick intentionally.",
    ),
    "L2-T39": (
        "Matrix multiplication combines rows of A with columns of B — not the same as `A * B` (element-wise). Shape rule: inner dimensions must match.",
        "`@` / `np.dot` / `np.matmul` for matrix product; `*` for element-wise only.",
    ),
    "L3-T02": (
        "Same `votes` and `costs` arrays from Lecture 2 — continuity lets you focus on **summarizing** and **combining** data instead of re-importing. Keep this cell open in a second tab.",
        "Lecture 3 builds on L2 arrays — do not redefine them with different values mid-notebook.",
    ),
    "L3-T03": (
        "Aggregate functions answer “what is this column like overall?” — one number from many. They are the bridge between raw arrays and business metrics (totals, averages, extremes).",
        "Aggregate first on the whole array; add `axis=` when you move to tables.",
    ),
    "L3-T04": (
        "`np.sum` and `np.mean` are the workhorses. Sum answers “how much total?”; mean answers “what is typical?” Use NumPy versions on arrays for speed.",
        "On arrays, prefer `np.sum` / `np.mean` over Python `sum` / manual loops.",
    ),
    "L3-T05": (
        "Min and max need numeric dtype. `costs` stored as strings must be cast (e.g. `.astype(float)`) before `np.min` / `np.max` behave sensibly.",
        "String dtype → cast before numeric aggregates.",
    ),
    "L3-T06": (
        "Stack votes and costs into a 2D table, then aggregate along an axis. **Axis 0** collapses rows (down); **axis 1** collapses columns (across).",
        "Draw which dimension you are squashing before picking `axis=0` vs `axis=1`.",
    ),
    "L3-T07": (
        "The “draw the bar” trick: for `axis=0`, slide a bar down each column; for `axis=1`, slide it across each row. This is the mental model instructors expect you to internalize.",
        "`axis=0` → down columns; `axis=1` → across rows.",
    ),
    "L3-T08": (
        "3D arrays extend the grid: floors × rows × columns. Each axis you aggregate removes one dimension from the result shape.",
        "More dimensions = more `axis` choices — always write the shape before and after.",
    ),
    "L3-T09": (
        "Worked examples show how `sum(axis=0)`, `sum(axis=1)`, and multi-axis sums shrink the array. Compare output shapes, not just values.",
        "After every axis operation, print `.shape` to confirm you collapsed the dimension you intended.",
    ),
    "L3-T10": (
        "Sorting orders data for ranking, deduplication checks, and joining sorted streams. NumPy sorts per axis on multidimensional arrays.",
        "Sorting answers “what comes first?” — axis decides whether rows or columns move.",
    ),
    "L3-T11": (
        "`np.sort(arr)` returns a new sorted array; `arr.sort()` mutates in place and returns `None`. Choose based on whether you still need the original order.",
        "Need original order later → `np.sort`; okay to destroy order → `.sort()`.",
    ),
    "L3-T12": (
        "`argsort` returns **indices** that would sort the array, not the sorted values themselves. Essential when two parallel arrays must stay aligned (e.g. votes and costs).",
        "Sort one array’s order via `argsort`, then apply the same index order to partners.",
    ),
    "L3-T13": (
        "On 2D arrays, `axis=1` sorts within each row; `axis=0` sorts within each column. Default is last axis (row-wise for typical tables).",
        "Say aloud: “sort each row” vs “sort each column” before picking `axis`.",
    ),
    "L3-T14": (
        "If votes and costs are separate columns, sorting votes alone scrambles the pairing. `argsort` on votes + fancy indexing on both preserves relationships — the “top 3 restaurants” pattern.",
        "Never sort two linked columns independently — sort indices once, apply everywhere.",
    ),
    "L3-T15": (
        "Python `sorted()` on strings uses lexicographic order (`\"10\"` before `\"2\"`). Cast or use a `key=` when you need numeric order. NumPy `sort` on numeric dtypes avoids this trap.",
        "String sort ≠ numeric sort — know your dtype.",
    ),
    "L3-T16": (
        "Leading spaces in strings affect sort order (`' Chris'` vs `'Amy'`). Trim or normalize strings before sorting in real datasets.",
        "Whitespace is part of the string — clean data before `sort`.",
    ),
    "L3-T17": (
        "Vectorization means applying an operation to every element without a Python `for` loop — NumPy runs the work in compiled code. This section transitions from aggregates to whole-array thinking.",
        "If you wrote `for i in range(len(arr))`, ask whether a single array expression could replace it.",
    ),
    "L3-T18": (
        "Loops are correct but slow at scale. Vectorized code is shorter, faster, and usually easier to read once you know the patterns.",
        "Readable loop today → vectorized version tomorrow as you learn the idioms.",
    ),
    "L3-T19": (
        "Element-wise operations require compatible shapes (or broadcasting). Mismatched shapes error rather than guess — that protects you from silent wrong answers.",
        "Shape mismatch error is a friend — fix shapes, do not fight with loops.",
    ),
    "L3-T20": (
        "Scalars, vectors, matrices, and tensors are the vocabulary for shape discussions ahead (broadcasting, matmul). Know which name matches which dimensionality.",
        "1D = vector; 2D = matrix/table — use the words consistently in doubts and exams.",
    ),
    "L3-T21": (
        "Matrix multiplication combines linear transformations — rows of A dot columns of B. It is not element-wise multiplication.",
        "Inner dimensions must match: `(m,n) @ (n,p) → (m,p)`.",
    ),
    "L3-T22": (
        "The only shape rule for matmul: columns of the first matrix equal rows of the second. Write shapes on paper before multiplying.",
        "Check `(?, n) @ (n, ?)` — the `n` must line up in the middle.",
    ),
    "L3-T23": (
        "`np.dot`, `np.matmul`, and `@` agree for 2D matrix multiply. Pick one style in your projects and stay consistent.",
        "For 2D matrices, `@` is the readable default in modern NumPy.",
    ),
    "L3-T24": (
        "`A * B` multiplies matching positions — useful for masking-style math, **not** for matrix product. Exam traps love this distinction.",
        "`*` = element-wise; `@` = matrix multiply.",
    ),
    "L3-T25": (
        "`dot` accepts scalars and vectors flexibly; `matmul` / `@` are stricter matrix operations. Know which API your code path uses.",
        "When shapes are weird, read the doc for `dot` vs `matmul` before guessing.",
    ),
    "L3-T26": (
        "Broadcasting lets NumPy operate on different-shaped arrays by virtually stretching smaller ones — no Python loops, no manual `tile` in simple cases.",
        "Broadcasting is not magic — it follows explicit shape rules from the rightmost dimension.",
    ),
    "L3-T27": (
        "Compare shapes from the **right**. Dimensions are compatible if equal, or one of them is 1. If neither rule holds, broadcasting fails.",
        "Align shapes from the right; 1 means “stretch me.”",
    ),
    "L3-T28": (
        "Same-shape addition is the easy case — no broadcasting needed, just element-wise math.",
        "Equal shapes → straightforward element-wise ops.",
    ),
    "L3-T29": (
        "A 1D row can broadcast across rows of a 2D array — NumPy repeats it logically, not by copying massive memory in most cases.",
        "1D + 2D often works via broadcasting — sketch shapes first.",
    ),
    "L3-T30": (
        "Column vector plus row vector broadcasts to a full grid — the outer-sum pattern. Easy to confuse with matrix multiply; addition ≠ matmul.",
        "Column + row → grid via broadcast; use `@` only when you intend matmul.",
    ),
    "L3-T31": (
        "Restaurant analytics example: align votes, ratings, and costs on compatible shapes before combining metrics — broadcasting is how you scale one metric across many stores.",
        "Business metrics on arrays almost always need shape alignment first.",
    ),
    "L3-T32": (
        "When broadcasting cannot reconcile shapes, NumPy raises a clear error. Fix by reshape, squeeze, or explicit alignment — not by ignoring the message.",
        "ValueError on broadcast → draw both shapes and find the mismatched tail dimension.",
    ),
    "L3-T33": (
        "Same-looking column × row shapes can mean broadcast **addition** (grid) or matrix **multiply** (dot product) depending on the operator. The operator chooses the meaning.",
        "`+` broadcasts; `@` contracts — same shapes, different semantics.",
    ),
    "L3-T34": (
        "Logical reductions and conditional indexing: `all`, `any`, and `where` extend boolean thinking from Lecture 2 into whole-array questions.",
        "These functions answer “every?”, “any?”, and “where?” across many cells at once.",
    ),
    "L3-T35": (
        "`np.all` is True only if **every** element passes the condition — strict QA check (“are all votes positive?”).",
        "Use `all` when a single False should fail the whole test.",
    ),
    "L3-T36": (
        "`np.any` is True if **at least one** element passes — useful for “did anything exceed the threshold?”",
        "Use `any` when one hit is enough to act.",
    ),
    "L3-T37": (
        "`np.where` has two modes: return indices of True values, or vectorized if/else with three arguments. Second form replaces loops for labeling.",
        "Two-arg `where` → positions; three-arg `where` → vectorized choice.",
    ),
    "L3-T38": (
        "Label sales (or any metric) High/Low with `np.where` — same pattern as Excel `IF` but on whole columns at once.",
        "Three-arg `where` is your vectorized IF statement.",
    ),
    "L4-T02": (
        "The `func` helper demonstrates how NumPy arrays flow through ordinary Python functions. Keep this cell — every vectorization example refers back to it.",
        "Define `func` once; reuse it to compare list vs array behavior.",
    ),
    "L4-T03": (
        "Vectorization is not “multiply everything” — it is “apply this logic across the whole iterable at once.” The lecture reframes it as mapping, not arithmetic.",
        "Ask: “Can this operation run on each element independently?” — if yes, vectorize.",
    ),
    "L4-T04": (
        "The core idea: one function, many inputs — NumPy applies it element-wise when given an array. That is the mental model for the rest of the section.",
        "Function + array → element-wise application without an explicit loop.",
    ),
    "L4-T05": (
        "Passing a NumPy array into `func` triggers element-wise behavior automatically. Passing a Python list usually does not — types matter.",
        "Array in → vectorized path; list in → often breaks or needs conversion.",
    ),
    "L4-T06": (
        "When lists fail, you have three fixes: convert to array, loop explicitly, or wrap with `np.vectorize`. Each trades speed, readability, and flexibility differently.",
        "Pick Method 1 (array) for numeric speed; Method 3 when the function is not ufunc-compatible.",
    ),
    "L4-T07": (
        "NumPy runs hot loops in C under the hood. Python loops interpret every step — fine for dozens of items, painful for millions.",
        "Interpreter overhead dominates small loops; compiled array ops dominate at scale.",
    ),
    "L4-T08": (
        "Method 1 (`np.array` first) and Method 3 (`np.vectorize`) can look similar in class demos but differ when functions are complex or dtypes mix.",
        "`vectorize` is convenience, not a guarantee of C-speed — benchmark when it matters.",
    ),
    "L4-T09": (
        "Doubt-session clarifications: conversion cost, when vectorization pays off, and what “vectorized” really means in interviews vs notebooks.",
        "Read Q&A when your loop “works but feels slow” — the answer is usually dtype + vectorize path.",
    ),
    "L4-T10": (
        "Side-by-side practice: list vs array vs vectorized wrapper on the same function. Run all three when studying — muscle memory beats memorizing definitions.",
        "Run all three paths once; note error vs output vs speed.",
    ),
    "L4-T11": (
        "Supplemental benchmark: `np.vectorize` still calls Python per element — it is not always as fast as true ufuncs. Useful, but know the limit.",
        "Vectorize ≠ always C-speed — profile if performance is critical.",
    ),
    "L4-T12": (
        "Stacking joins separate arrays into one bigger array — vertical (more rows) or horizontal (more columns). Different from math operations on aligned data.",
        "Stack when pieces share structure; merge keys when rows must match by ID.",
    ),
    "L4-T13": (
        "`vstack` piles arrays as new rows. Shapes must align on columns (for 2D). Think “append rows below.”",
        "vstack → grow downward (axis 0).",
    ),
    "L4-T14": (
        "`hstack` joins side by side along columns (for 2D). 1D arrays stack into a longer 1D vector. Check output shape after every stack.",
        "hstack → grow sideways (axis 1 for 2D).",
    ),
    "L4-T15": (
        "`vstack` works on 2D arrays too — each input becomes another row block, not only 1D vectors.",
        "vstack is not “1D only” — read shapes on 2D inputs.",
    ),
    "L4-T16": (
        "`concatenate` generalizes vstack/hstack with an explicit `axis`. One function to learn instead of memorizing every special case.",
        "When unsure, `concatenate` + explicit `axis` is the unified tool.",
    ),
    "L4-T17": (
        "In analytics pipelines, you stack daily extracts vertically or join feature columns horizontally — same mechanics as these toy arrays.",
        "Real pipelines stack time periods (rows) or features (columns) — same NumPy ideas.",
    ),
    "L4-T18": (
        "Promote 1D → 2D column via `reshape`, `[:, np.newaxis]`, or `[:, None]` — three names, one idea.",
        "Column vector shape `(n, 1)` unlocks broadcasting and `hstack` patterns.",
    ),
    "L4-T19": (
        "Quiz on `concatenate` axis with row-shaped 2D inputs — small shape change, big difference in output layout.",
        "Write input shapes, predict output shape, then run.",
    ),
    "L4-T20": (
        "`np.split` was flagged for post-read — splitting is the inverse of stacking. Skim knowing it exists; details come later.",
        "Split ↔ stack are inverse ideas — revisit after concatenate feels solid.",
    ),
    "L4-T21": (
        "Preview of `np.split` for when you need to break an array back into chunks — not covered live, but completes the stacking story.",
        "Optional preview — not exam-critical until instructor covers it.",
    ),
    "L4-T22": (
        "Pandas sits on NumPy and adds **labels** (row/column names) plus table tooling. You will live in DataFrames for EDA; NumPy stays underneath.",
        "NumPy = fast arrays; pandas = labeled tables for real datasets.",
    ),
    "L4-T23": (
        "NumPy grids are homogeneous and position-based. Real tables have column names, mixed types, and missing values — pandas exists for that gap.",
        "When you need column names or ragged types, reach for pandas.",
    ),
    "L4-T24": (
        "Series = one labeled column (or row). DataFrame = bundle of Series sharing an index. Everything in pandas builds from these two.",
        "Series → columns; DataFrame → the full spreadsheet object.",
    ),
    "L4-T25": (
        "Create a Series with data, optional index labels, and a name. The index is how `.loc` will find rows later.",
        "Name your Series when building DataFrames — it becomes the column name.",
    ),
    "L4-T26": (
        "`pd.concat` along `axis=1` glues Series into columns. Along `axis=0` stacks rows. Same function, different axis — like NumPy concatenate.",
        "concat axis=1 → wider table; axis=0 → taller table.",
    ),
    "L4-T27": (
        "Dictionary → DataFrame maps keys to column names. Fastest way to prototype small tables without CSV files.",
        "dict of lists → DataFrame is the quickest scratch-pad table.",
    ),
    "L4-T28": (
        "`read_csv` is the front door for real projects. Path, encoding, and separators matter in production; class uses a clean local CSV.",
        "After load, always `head()` + `shape` + `dtypes` before analysis.",
    ),
    "L4-T29": (
        "`head` / `tail` preview rows; `shape` reports `(rows, columns)`. These three checks should be reflex after every load.",
        "Load → head → shape → dtypes — every time.",
    ),
    "L4-T30": (
        "`.iloc` = integer position (stop excluded on slices). `.loc` = label-based (stop **included** on slices). Mixing rules causes off-by-one bugs for life if you skip this.",
        "iloc = positions, stop excluded; loc = labels, stop included.",
    ),
    "L4-T31": (
        "Set a meaningful index (e.g. restaurant name) so `.loc` searches by label. Duplicate labels return **all** matching rows — not just one.",
        "Duplicate index labels → `.loc` returns multiple rows — plan for that in mutating code.",
    ),
    "L4-T32": (
        "`reset_index` moves the index back to a normal column. `inplace=True` mutates; without it you must assign the result back.",
        "Forgot to assign? Check `inplace` — silent no-ops are common.",
    ),
    "L4-T33": (
        "Single brackets → Series; double brackets → DataFrame subset. Dot access works only for valid Python identifiers (no spaces).",
        "Need one column as Series → `df['col']`; need DataFrame → `df[['col']]`.",
    ),
    "L4-T34": (
        "Rename with a mapping dict. Wrong old name silently does nothing — verify column list after rename.",
        "Always print `df.columns` after rename to confirm it worked.",
    ),
    "L4-T35": (
        "In-class quiz recap — shape reading, concat axis, iloc/loc traps. Treat as a mini mock exam.",
        "Redo quizzes closed-book before the next lecture.",
    ),
    "L4-T36": (
        "Extra doubts from class — indexing edge cases, concat vs stack, when to reset index. Read when something from earlier topics still feels fuzzy.",
        "If a doubt sounds familiar, jump back to that topic ID — links are intentional.",
    ),
    "L4-T37": (
        "Consolidated pitfalls (supplemental) — common mistakes in one place for review night.",
        "Use as a checklist before labs — not a substitute for running code.",
    ),
    "L4-T38": (
        "Official doc links for later — bookmark when you need authoritative syntax beyond these notes.",
        "Notes teach patterns; docs settle edge cases.",
    ),
    "L5-T01": (
        "Recap ties Lecture 4 structures to today’s operations mindset: Series/DataFrame, iloc/loc, and **only load columns you need** on large data.",
        "Memory discipline starts with column subsetting — not just convenience.",
    ),
    "L5-T02": (
        "Reload the Zomato dataset and run the first inspection trio: shape, ndim, head. `ndim==2` confirms table structure.",
        "After every `read_csv`, run head + shape before transformations.",
    ),
    "L5-T03": (
        "Mixed slicing rules: `.iloc` rows and cols are positional (stop excluded). `.loc` uses labels (stop included). Never mix label slices inside `.iloc`.",
        "iloc + string column slice = error; switch accessor to match what you are selecting by.",
    ),
    "L5-T04": (
        "Custom index (restaurant name) makes `.loc` readable but introduces duplicate labels — `.loc['Jalsa']` returns **all** branches. `.iloc` still needs integers.",
        "Duplicate index → multi-row `.loc` results — dangerous when assigning.",
    ),
    "L5-T05": (
        "Three levels of uniqueness questions: list values (`unique`), count (`nunique`), frequency table (`value_counts`). Pick the one that matches the business question.",
        "unique = what values exist; nunique = how many; value_counts = how often each.",
    ),
    "L5-T06": (
        "pandas allows in-place assignment through `.iloc` / `.loc` — powerful and dangerous. One assignment can touch many rows when labels duplicate.",
        "Before assigning via `.loc`, ask: “How many rows share this label?”",
    ),
    "L5-T07": (
        "Subset columns with `df[[cols]]` to save memory; filter rows with boolean masks. Combine with `&` / `|` and parentheses.",
        "Double brackets for multiple columns; `&` not `and` for masks.",
    ),
    "L5-T08": (
        "Duplicates: detect with `.duplicated`, remove with `.drop_duplicates`. Control `subset` columns and which duplicate to `keep`.",
        "Define duplicate on business keys (e.g. order id), not accidental full-row equality only.",
    ),
    "L5-T09": (
        "Aggregations summarize columns: sum, mean, count, custom via `.agg`. Watch dtypes — strings break numeric aggregates.",
        "Inspect dtypes before `.sum()` / `.mean()` on messy CSV columns.",
    ),
    "L5-T10": (
        "`sort_values` orders rows by one or more columns. `ascending=False` for top-N leaderboards.",
        "Sort is for presentation and “top k” — not a substitute for `argsort` alignment tricks on parallel arrays.",
    ),
    "L5-T11": (
        "`pd.concat` stacks tables without a join key; `pd.merge` aligns on shared keys like SQL joins. Different questions, different tools.",
        "Stack with concat; align records with merge.",
    ),
    "L5-T12": (
        "Merge `how=` mirrors SQL: inner, left, right, outer. Think Venn diagram — which rows survive is entirely `how`.",
        "Draw the Venn before picking `how=` — inner is intersection only.",
    ),
    "L5-T13": (
        "When key column names differ, `left_on` / `right_on` pair them explicitly. Rename keys first if you want cleaner scripts.",
        "Mismatched key names need `left_on`/`right_on` — `on=` alone will not guess.",
    ),
    "L5-T14": (
        "`.apply` runs a Python function per element or row — flexible but slower than vectorized string/num ops. Use when no built-in exists.",
        "Reach for vectorized string ops first; `.apply` when logic is custom.",
    ),
    "L5-T15": (
        "Lambda + `.apply` cleans messy strings (e.g. currency symbols). Chain with `.str` accessors when possible for speed.",
        "`.str.split(...).str[i]` beats manual loops for column cleanup.",
    ),
    "L5-T16": (
        "Python `and` / `or` do not element-wise truth on Series — use `&`, `|`, `~` with parentheses. This error looks like a bug but is a language rule.",
        "Series boolean filter → `&` with parentheses, never `and`.",
    ),
    "L5-T17": (
        "Four ways to birth a DataFrame: dict, list of dicts, `read_csv`, `read_json`. Know all for interviews and quick prototypes.",
        "Pick construction method by data source: file vs in-memory vs API JSON.",
    ),
}


def _title_fallback(title: str, lec: int) -> tuple[str, str]:
    clean = re.sub(r"\s+", " ", title).strip()
    t = clean.lower()
    if "visual" in t:
        return (
            f"Visual reference for **{clean}** — study the figure, then map each part to the code cells below.",
            "Diagram first, code second — connects abstract rules to something you can picture.",
        )
    if "quiz" in t:
        return (
            f"Practice block for **{clean}** — close the answer in your head, then execute to confirm.",
            "Prediction before execution is what turns reading into memory.",
        )
    if "setup" in t:
        return (
            f"Shared variables for Lecture {lec}. Reuse these definitions instead of inventing new arrays mid-notebook.",
            "One setup cell — many downstream examples.",
        )
    if "recap" in t:
        return (
            f"Bridge from the previous lecture — **{clean}** orients you before new material.",
            "Skim if confident; slow down if anything here feels unfamiliar.",
        )
    if "doubt" in t or "q&a" in t:
        return (
            f"Class Q&A on **{clean}** — read when your code “should work” but does not.",
            "Doubts are where most students get unstuck — do not skip these.",
        )
    return (
        f"This section covers **{clean}**. Read the explanation, run the code, then say the idea in your own words before moving on.",
        "Teach-back one sentence aloud — if you cannot, reread before the next topic.",
    )


# Post-code summaries for code-heavy topics (inserted once after the last fence).
TAKEAWAYS: dict[str, str] = {
    "L2-T05": "If `w[-1]` and `w[-2]` make sense, negative indices in slices (next topics) will feel familiar — same counting direction, different syntax.",
    "L2-T07": "Match each index label in the diagram to `w = [9,5,4,3,2]`: position `0` is `9`, position `-1` is `2`. Recite that mapping before moving on.",
    "L2-T09": "`votes[2:5]` only works for contiguous positions; `votes[[2,3,4]]` works for any order and allows repeats like `[[3,3,3]]`.",
    "L2-T10": "Open-ended slices clip silently — `votes[2:146]` equals `votes[2:]` because there is no index 146. That is why slicing feels ‘safe’ compared to indexing.",
    "L2-T11": "`votes[-1]` is the last element; `votes[-3:]` is the last three. Negative start counts from the end, but the stop index is still exclusive.",
    "L2-T12": "Compare to L2-T06: `w[5]` crashed, but `votes[2:146]` did not. Slicing never raises `IndexError` — it returns whatever fits.",
    "L2-T16": "Treat this as a mock quiz: write every answer, run the cell, mark mismatches, and redo only those lines tomorrow.",
    "L2-T17": "A 2D array is a grid of rows × columns. Shape `(3, 4)` means 3 rows and 4 columns — always read shape as `(rows, cols)`.",
    "L2-T18": "`y[row, col]` picks one cell; `y[row, :]` grabs an entire row; `y[:, col]` grabs an entire column. The colon means ‘all’ on that axis.",
    "L2-T19": "`y[2]` drops to 1D shape `(3,)`; `y[2:]` keeps 2D shape `(1, 3)`. Downstream functions may require one or the other — check `.shape`.",
    "L2-T24": "Fancy index `[0, 4, 2]` reorders freely; slice `[0:3]` cannot repeat index 0 three times. Use lists when order or repeats matter.",
    "L2-T26": "Parentheses are not optional: `(votes >= 100) & (votes <= 500)` works; `votes >= 100 & votes <= 500` does not. Same rule applies in pandas later.",
    "L3-T04": "`np.sum(votes)` answers ‘how much total?’; `np.mean(votes)` answers ‘what is typical?’. Know which question you are asking before calling the function.",
    "L3-T07": "Before every `axis=` argument, sketch the table and draw the direction you collapse. `axis=0` walks down columns; `axis=1` walks across rows.",
    "L3-T11": "`np.sort(ar1)` leaves `ar1` unchanged; `ar1.sort()` mutates it. If you still need the original order for another column, use `np.sort`.",
    "L3-T12": "`argsort` gives positions, not sorted values — use those positions to reorder partner arrays (votes and costs) without breaking alignment.",
    "L3-T19": "Element-wise math needs compatible shapes (or broadcasting). If shapes fight, NumPy errors early — that is preferable to a silently wrong vector.",
    "L3-T24": "The numbers look smaller with `*` because each cell multiplies independently. Matrix product `@` combines rows with columns — different math entirely.",
    "L3-T27": "Broadcasting compares shapes from the right: equal sizes match; size `1` stretches. If neither rule applies, stop and reshape.",
    "L3-T35": "`np.all(votes > 0)` is a single True/False for the whole array — use it for QA checks like ‘are any values invalid?’.",
    "L4-T05": "Same function, different input type: NumPy array → element-wise output; Python list → often `TypeError`. Convert with `np.array()` first.",
    "L4-T13": "`vstack` stacks arrays as additional rows — each input becomes another horizontal band in the result. Check column counts match.",
    "L4-T25": "A Series is one labeled column. The `index` you set now becomes the row labels `.loc` will search later — choose meaningful names early.",
    "L4-T30": "Rule of thumb: `.iloc` for ‘the 5th row’ (position); `.loc` for ‘row labeled Monday’ (label). Never mix label slices inside `.iloc`.",
    "L5-T02": "After every load: `shape` tells scale, `ndim` confirms 2D table, `head()` shows realistic values. Make that a three-line habit.",
    "L5-T05": "Pick the tool to match the question: `unique()` lists categories, `nunique()` counts them, `value_counts()` ranks frequency.",
    "L5-T08": "`duplicated()` flags rows; `drop_duplicates(subset=[...], keep='first')` removes them. Always specify which columns define ‘duplicate’ for your business case.",
    "L5-T11": "Stack similar tables with `concat` (no key needed); align related records with `merge` (shared key required). Wrong tool = wrong shape or missing rows.",
    "L5-T16": "Filtering two conditions: `(df['a'] > 1) & (df['b'] < 5)` — never `and`. The parentheses are part of the syntax, not optional style.",
}


def deep_enrichment(topic_id: str, title: str) -> tuple[str, str]:
    tid = topic_id.upper()
    if tid in OVERRIDES:
        return OVERRIDES[tid]
    lec_m = re.match(r"L(\d+)-", tid)
    lec = int(lec_m.group(1)) if lec_m else 0
    return _title_fallback(title, lec)


# Optional syntax lines (shown in **Syntax:** before code).
SYNTAX: dict[str, str] = {
    "L2-T04": "`arr[i]` — integer position; `arr[-1]` last element.",
    "L2-T05": "`len(arr)`, `arr.size`, `arr[-1]`, `arr[-2]`.",
    "L2-T08": "`array[start:end]` — stop index is **excluded**; optional `array[start:end:step]`.",
    "L2-T09": "Fancy: `arr[[i, j, k]]` vs slice: `arr[start:stop]`.",
    "L2-T13": "`np.arange(start, stop, step)` — stop excluded; step may be float.",
    "L2-T21": "`arr[boolean_mask]` or `arr[arr >= threshold]`.",
    "L2-T26": "`(cond1) & (cond2)` — parentheses required; use `|` for OR, `~` for NOT.",
    "L2-T32": "`arr.reshape(rows, cols)` or `arr.reshape(rows, -1)`.",
    "L3-T04": "`np.sum(arr)`, `np.mean(arr)`.",
    "L3-T11": "`np.sort(arr)` new array; `arr.sort()` in-place.",
    "L3-T12": "`np.argsort(arr)` → index order that would sort the array.",
    "L3-T21": "`A @ B`, `np.dot(A, B)`, `np.matmul(A, B)` for matrix product.",
    "L3-T24": "`A * B` element-wise only — **not** matrix multiply.",
    "L4-T13": "`np.vstack([a, b])` — stack as new rows.",
    "L4-T14": "`np.hstack([a, b])` — join side-by-side.",
    "L4-T16": "`np.concatenate([a, b], axis=0|1)`.",
    "L4-T30": "`.iloc[row, col]` positions; `.loc[row, col]` labels.",
    "L5-T03": "`.iloc[r1:r2, c1:c2]` stop excluded; `.loc[r1:r2, 'a':'c']` stop included.",
    "L5-T05": "`series.unique()`, `series.nunique()`, `series.value_counts()`.",
    "L5-T08": "`df.duplicated()`, `df.drop_duplicates(subset=[...], keep='first'|'last')`.",
    "L5-T11": "`pd.concat([df1, df2], axis=0|1)` vs `pd.merge(df1, df2, on=..., how=...)`.",
    "L5-T16": "`(cond1) & (cond2)` on Series — never Python `and` / `or`.",
}


def _infer_when_to_use(title: str) -> str:
    t = title.lower()
    if "iloc" in t or ".loc" in t:
        return "When selecting rows/columns by integer position (`.iloc`) vs labels (`.loc`)."
    if "slicing" in t or "slice" in t:
        return "When you need a contiguous subset without listing every index by hand."
    if "fancy" in t or "mask" in t or "boolean" in t:
        return "When you filter or reorder by condition or arbitrary positions."
    if "index" in t and "visual" not in t:
        return "When you need exactly one element at a known position."
    if "visual" in t or "diagram" in t:
        return "When you want a picture of index direction before writing slice expressions."
    if "quiz" in t:
        return "When you want to verify indexing rules before moving on — predict, then run."
    if "setup" in t:
        return "At the start of the lecture — reuse these variables in every example below."
    if "recap" in t:
        return "When bridging from the prior lecture or orienting before new material."
    if "aggregate" in t or "sum" in t or "mean" in t:
        return "When you need one summary number (total, average, min, max) from many values."
    if "axis" in t:
        return "When a 2D (or higher) array needs row-wise vs column-wise collapse."
    if "sort" in t:
        return "When ranking values or preparing data for top-N / ordered analysis."
    if "broadcast" in t:
        return "When operating on arrays of different but compatible shapes without loops."
    if "matrix" in t or "matmul" in t or "dot" in t:
        return "When combining linear transformations — not for element-wise scaling."
    if "vectoriz" in t:
        return "When the same function should run on every element without a Python loop."
    if "stack" in t or "vstack" in t or "hstack" in t or "concatenate" in t:
        return "When joining separate arrays into one table-like structure."
    if "pandas" in t or "series" in t or "dataframe" in t:
        return "When labeled tables, CSV data, or column names matter more than raw positions."
    if "iloc" in t or ".loc" in t:
        return "When selecting rows/columns by position (iloc) or by label (loc)."
    if "merge" in t or "concat" in t:
        return "When combining multiple tables — stack similar rows or join on keys."
    if "unique" in t or "duplicate" in t:
        return "When exploring categories, counts, or cleaning repeated rows."
    if "apply" in t or "lambda" in t:
        return "When row/cell logic has no built-in vectorized equivalent."
    if "reshape" in t or "transpose" in t:
        return "When you need to change layout (grid shape) without changing values."
    return "When this concept appears in the notebook example — read the prose, then run the code to lock it in."


def pedagogy_for(topic_id: str, title: str) -> dict[str, str]:
    """Structured intro fields for a topic (prose before code)."""
    tid = topic_id.upper()
    context, remember = deep_enrichment(tid, title)
    out: dict[str, str] = {
        "what_it_is": context,
        "key_rule": remember,
        "when_to_use": _infer_when_to_use(title),
    }
    if tid in SYNTAX:
        out["syntax"] = SYNTAX[tid]
    return out


def format_pedagogy_intro(p: dict[str, str]) -> str:
    parts: list[str] = []
    if p.get("what_it_is"):
        parts.append(f"**What it is:** {p['what_it_is'].strip()}")
    if p.get("key_rule"):
        parts.append(f"**Key rule:** {p['key_rule'].strip()}")
    if p.get("syntax"):
        parts.append(f"**Syntax:** {p['syntax'].strip()}")
    if p.get("when_to_use"):
        parts.append(f"**When to use it:** {p['when_to_use'].strip()}")
    return "\n\n".join(parts) + "\n"
