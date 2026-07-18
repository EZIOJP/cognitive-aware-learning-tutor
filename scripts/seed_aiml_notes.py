"""Seed AIML Module 3–4 study notes + curated resources into data/notes/aiml/."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "data" / "notes" / "aiml"


def write(rel: str, body: str) -> None:
    path = NOTES / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.strip() + "\n", encoding="utf-8")
    print("wrote", path.relative_to(ROOT))


# Shared resource blocks
MML = """
### Books (local corpus)
- **Mathematics for Machine Learning** (Deisenroth, Faisal, Ong) — put PDF in `data/raw_library/linear_algebra/Mathematics_for_ML.pdf` then ingest via Knowledge Base
- Gilbert Strang — *Introduction to Linear Algebra* (optional companion)

### Web
- [3Blue1Brown Essence of Linear Algebra](https://www.3blue1brown.com/topics/linear-algebra)
- [MML book site (free PDF)](https://mml-book.github.io/)
- [Khan Academy Linear Algebra](https://www.khanacademy.org/math/linear-algebra)
- [Immersive Linear Algebra](http://immersivemath.com/ila/index.html)
"""

ISL = """
### Books
- **An Introduction to Statistical Learning (ISLR/ISLP)** — free: https://www.statlearning.com/
- **Elements of Statistical Learning (ESL)** — advanced depth: https://hastie.su.domains/ElemStatLearn/
- **Hands-On Machine Learning** (Géron) — practical sklearn/TF companion

### Web
- [scikit-learn User Guide](https://scikit-learn.org/stable/user_guide.html)
- [Google ML Crash Course](https://developers.google.com/machine-learning/crash-course)
- [StatQuest (Josh Starmer) YouTube](https://www.youtube.com/c/joshstarmer)
"""


write(
    "00_README.md",
    f"""
# AIML study path — Modules 3 & 4

Personal study track for **Maths for ML** and **ML Coding: Supervised Learning**.

## How to use in this app
1. Open **Lecture Notes** → folder `aiml/`
2. Work day-by-day notes; paste assignment answers / doubts under each day
3. Add extra links under **Your resources** in each note
4. Select a day note → **Study tools → Generate quiz** to practice
5. Ingest textbooks in **Knowledge Base** (`raw_library`) for RAG later if you turn corpus grounding on

## Modules
| Module | Folder | Days |
|--------|--------|------|
| 3 — Maths for ML | `maths_for_ml/` | Day 13–20 |
| 4 — Supervised Learning | `supervised_learning/` | Day 21–30 |

## Global resources
{MML}
{ISL}
""",
)

write(
    "maths_for_ml/00_syllabus.md",
    f"""
# Module 3 — Maths for ML (AIML)

**Focus:** Linear algebra → calculus refresher → optimisation / gradient descent  
**Progress tip:** Finish Day 13–17 LA before leaning hard into GD (Days 19–20).

## Day map
| Day | Date | Topic | Assignments |
|-----|------|-------|-------------|
| 13 | 13 Apr | Linear algebra 1 | 7 + 6 addl |
| 14 | 15 Apr | Linear Algebra 1.2 | — |
| 15 | 17 Apr | Linear algebra 2 | 6 + 3 |
| 16 | 20 Apr | Linear algebra 3 | 5 + 3 |
| 17 | 24 Apr | LA problem solving | 5 + 3 |
| 18 | 27 Apr | Calculus refresher | 5 + 3 |
| 19 | 29 Apr | Optimisation & GD 1 | 6 + 5 |
| 20 | 4 May | Optimisation & GD 2 | 5 + 3 |

## Module resources
{MML}

### Optimisation extras
- [Distill — Why Momentum Works](https://distill.pub/2017/momentum/)
- [CS231n Optimization notes](https://cs231n.github.io/optimization-1/)
- 3Blue1Brown — *Gradient descent* (Essence of Calculus / NN series)

## Your resources
<!-- Add course portal links, recorded lectures, Discord notes -->
- Course portal: _(paste)_
- Slack/Drive dump: _(paste)_
""",
)

MATH_DAYS = [
    (
        "day13_linear_algebra_1.md",
        "Day 13 — Linear algebra 1",
        "Vectors, spaces, linear maps",
        """
## Learning goals
- Vectors, scalars; geometric + algebraic view
- Linear combinations, span, basis intuition
- Matrix as linear transformation

## Core ideas (fill from lecture)
### Vectors & operations
- Addition, scalar multiplication
- Dot product → angle / projection intuition

### Matrices
- Matrix–vector product as weighted columns
- Systems $Ax = b$

## Worked sketch
```text
Projection of b onto a:
  proj = (a·b / a·a) * a
```

## Practice checklist
- [ ] Assignment 0/7
- [ ] Additional 0/6
- [ ] Self-quiz from this note

## Resources for this day
- MML book: Ch. 2 (Vectors) / early Linear Algebra chapters — https://mml-book.github.io/
- 3Blue1Brown: Vectors, linear combinations, matrices as transforms
- Khan: Vectors and spaces
""",
        "Linear Algebra",
    ),
    (
        "day14_linear_algebra_1_2.md",
        "Day 14 — Linear Algebra 1.2",
        "Continuation of LA 1",
        """
## Learning goals
- Firm up Day 13: span, dependence, solving $Ax=b$
- Rank / column space intuition (preview)

## Core ideas
- Dependent vs independent sets
- When does $Ax=b$ have 0 / 1 / ∞ solutions?

## Practice checklist
- [ ] Re-watch weak lecture segments
- [ ] Redo 3 hard Day-13 problems without notes

## Resources
- MML: systems of linear equations sections
- 3Blue1Brown: Span, basis, linear dependence
""",
        "Linear Algebra",
    ),
    (
        "day15_linear_algebra_2.md",
        "Day 15 — Linear algebra 2",
        "Matrices, inverses, determinants",
        """
## Learning goals
- Matrix multiplication as composition of transforms
- Inverse: when and why ($A^{-1}A = I$)
- Determinant as volume / invertibility signal

## Core ideas
- $(AB)x = A(Bx)$
- Singular matrices → collapse volume → no inverse
- 2×2 det formula; geometric meaning

## Practice checklist
- [ ] Assignment 0/6
- [ ] Additional 0/3

## Resources
- MML: Matrices / determinants chapters
- 3Blue1Brown: Matrix multiplication, determinants, inverse matrices
- Strang OCW 18.06 — lectures on elimination & inverse
""",
        "Linear Algebra",
    ),
    (
        "day16_linear_algebra_3.md",
        "Day 16 — Linear algebra 3",
        "Eigenvalues, eigenvectors, PCA teaser",
        """
## Learning goals
- Eigenvectors: directions unchanged by $A$ (scaled only)
- Eigenvalues: the scale factors
- Why this matters for PCA / covariance / stability

## Core ideas
- $Av = \\lambda v$
- Characteristic equation $\\det(A-\\lambda I)=0$
- Diagonalisation intuition (when possible)

## ML connection
- PCA ≈ eigen-decomposition of covariance (preview for Module 4)

## Practice checklist
- [ ] Assignment 0/5
- [ ] Additional 0/3

## Resources
- MML: Eigenvalues / PCA-related chapters
- 3Blue1Brown: Eigenvectors and eigenvalues; change of basis
- [StatQuest PCA](https://www.youtube.com/watch?v=FgakZw6K1QQ) (intuition)
""",
        "Linear Algebra",
    ),
    (
        "day17_la_problem_solving.md",
        "Day 17 — Linear algebra problem solving",
        "Mixed LA drills",
        """
## Learning goals
- Fluency: mix of systems, rank, eigen, projections
- Speed + accuracy on typical exam-style questions

## Session plan
1. Warm-up: 5×2 / 3×3 multiply + invert (2×2)
2. Solve 2 systems (unique / infinite / none)
3. One eigenproblem (2×2)
4. One projection / least-squares sketch

## Practice checklist
- [ ] Assignment 0/5
- [ ] Additional 0/3
- [ ] Generate quiz from this note in Study tools

## Resources
- Revisit weak days 13–16 notes
- MML exercises at chapter ends
- 3Blue1Brown playlist — rewatch only stuck topics
""",
        "Linear Algebra",
    ),
    (
        "day18_calculus_refresher.md",
        "Day 18 — Calculus refresher",
        "Derivatives, gradients, chain rule",
        """
## Learning goals
- Derivative as local slope / sensitivity
- Partial derivatives & gradient $\\nabla f$
- Chain rule (critical for backprop later)

## Core ideas
- $\\frac{{df}}{{dx}}$ univariate
- Gradient points steepest ascent; we descend $-\\nabla f$ for minimisation
- Multivariable Taylor / linear approximation intuition

## Practice checklist
- [ ] Assignment 0/5
- [ ] Additional 0/3
- Lecture marked done — solidify with problems

## Resources
- MML: Analytic geometry / differential calculus chapters
- 3Blue1Brown Essence of Calculus
- [Khan multivariable calculus — gradients](https://www.khanacademy.org/math/multivariable-calculus)
- CS231n: backpropagation notes (optional preview)
""",
        "Calculus",
    ),
    (
        "day19_optimisation_gd_1.md",
        "Day 19 — Optimisation and gradient descent 1",
        "Loss landscapes & GD basics",
        """
## Learning goals
- Objective / loss $L(\\theta)$
- Gradient descent update: $\\theta \\leftarrow \\theta - \\eta \\nabla_\\theta L$
- Learning rate tradeoffs; local minima intuition

## Core ideas
- Convex vs non-convex (high level)
- Batch vs SGD intuition (preview)
- When GD diverges (η too large)

## Tiny example
```text
L(w) = (w - 3)^2
dL/dw = 2(w-3)
w := w - η * 2(w-3)
```

## Practice checklist
- [ ] Assignment 0/6
- [ ] Additional 0/5

## Resources
- [CS231n Optimization](https://cs231n.github.io/optimization-1/)
- [Distill Momentum](https://distill.pub/2017/momentum/)
- MML: optimisation / continuous optimisation chapters
- 3Blue1Brown / StatQuest gradient descent videos
""",
        "Optimisation",
    ),
    (
        "day20_optimisation_gd_2.md",
        "Day 20 — Optimisation and gradient descent 2",
        "Variants & practical GD",
        """
## Learning goals
- Momentum / adaptive methods at conceptual level
- Feature scaling & conditioning
- Stopping criteria; overfitting link to training loss

## Core ideas
- SGD + mini-batches
- Momentum: accumulate velocity
- Why normalisation helps GD

## Bridge to Module 4
- Linear / logistic regression = minimise a loss with GD or closed form

## Practice checklist
- [ ] Assignment 0/5
- [ ] Additional 0/3
- Lecture done — write 5 bullet “what I will use in LR”

## Resources
- CS231n optimisation (part 2 / CNN notes intro)
- sklearn `SGDClassifier` / `SGDRegressor` docs (peek ahead)
- ISL Ch. 2–3 motivation
""",
        "Optimisation",
    ),
]

for fname, title, subtitle, body, topic in MATH_DAYS:
    write(
        f"maths_for_ml/{fname}",
        f"""
# {title}
**{subtitle}** · Module 3 · topic: `{topic}`

{body}

## Your resources
<!-- Drop Drive links, screenshots paths, friend notes -->
- 
""",
    )

write(
    "supervised_learning/00_syllabus.md",
    f"""
# Module 4 — ML Coding: Supervised Learning (~6 weeks)

**Focus:** Linear regression → sklearn pipelines → logistic regression → metrics → KNN → trees/ensembles

## Day map
| Day | Date | Topic | Assignments |
|-----|------|-------|-------------|
| 21 | 6 May | Intro ML eng + Linear regression 1 | 4 + 3 |
| 22 | 11 May | Linear regression 2 | 6 + 4 |
| 23 | 13 May | Linear regression 3 | 5 + 3 |
| 24 | 18 May | Linear Regression 3 (cont) | — |
| 25 | 20 May | Sklearn Pipelines | 5 + 5 |
| 26 | 22 May | Logistic regression 1 | 3 + 2 |
| 27 | 25 May | Logistic Regression 1 (cont) | — |
| 28 | 29 May | Classification metrics | 5 + 4 |
| 29 | 3 Jun | KNN | 6 + 4 |
| 30 | 5 Jun | Decision tree, Ensemble intro | 5 + 3 |

## Module resources
{ISL}

### Coding practice
- [Google Colab](https://colab.research.google.com/)
- [Kaggle Learn — Intro to ML](https://www.kaggle.com/learn/intro-to-machine-learning)
- Course notebooks: _(paste repo link)_

## Your resources
- 
""",
)

SL_DAYS = [
    (
        "day21_intro_ml_linreg_1.md",
        "Day 21 — Intro to ML engineering & Linear regression 1",
        """
## Learning goals
- Supervised vs unsupervised; train/test split
- Linear regression model: $\\hat{y} = w^\\top x + b$
- MSE loss; closed form vs GD

## Core ideas
- Features / labels / hypothesis class
- Bias–variance (high level)
- Normal equation sketch: $w = (X^\\top X)^{-1} X^\\top y$

## Practice checklist
- [ ] Assignment 0/4 · Additional 0/3

## Resources
- ISL Ch. 2 (overview) + Ch. 3 start — https://www.statlearning.com/
- [sklearn LinearRegression](https://scikit-learn.org/stable/modules/linear_model.html#ordinary-least-squares)
- StatQuest: Linear Regression
""",
        "Linear Regression",
    ),
    (
        "day22_linear_regression_2.md",
        "Day 22 — Linear regression 2",
        """
## Learning goals
- Multiple regression; categorical encoding intro
- Residual analysis; R² intuition
- Regularisation preview (Ridge / Lasso names)

## Practice checklist
- [ ] Assignment 0/6 · Additional 0/4

## Resources
- ISL Ch. 3 (full)
- ESL Ch. 3 (optional depth)
- sklearn `Ridge`, `Lasso` docs
""",
        "Linear Regression",
    ),
    (
        "day23_linear_regression_3.md",
        "Day 23 — Linear regression 3",
        """
## Learning goals
- Feature engineering for LR
- Polynomial features; interaction terms
- Overfitting symptoms on train vs val

## Practice checklist
- [ ] Assignment 0/5 · Additional 0/3

## Resources
- ISL polynomial regression sections
- sklearn `PolynomialFeatures`
- Géron HML — linear models chapter
""",
        "Linear Regression",
    ),
    (
        "day24_linear_regression_3_cont.md",
        "Day 24 — Linear Regression 3 (continued)",
        """
## Learning goals
- Close open loops from Day 23
- End-to-end mini project: clean → fit → evaluate → interpret coeffs

## Session plan
1. Pick one dataset (course / sklearn toy)
2. Baseline LR → residual plot
3. One improvement (poly / ridge)
4. Write 5 lines of interpretation

## Resources
- Reuse Day 21–23 links
- [sklearn supervised learning tutorial](https://scikit-learn.org/stable/supervised_learning.html)
""",
        "Linear Regression",
    ),
    (
        "day25_sklearn_pipelines.md",
        "Day 25 — Sklearn Pipelines",
        """
## Learning goals
- `Pipeline` / `ColumnTransformer` to avoid leakage
- Train-only fits for scalers & encoders
- Cross-validation with pipelines

## Core pattern
```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge

pipe = Pipeline([
    ("scale", StandardScaler()),
    ("model", Ridge(alpha=1.0)),
])
pipe.fit(X_train, y_train)
```

## Practice checklist
- [ ] Assignment 0/5 · Additional 0/5

## Resources
- [sklearn Pipeline guide](https://scikit-learn.org/stable/modules/compose.html)
- [ColumnTransformer](https://scikit-learn.org/stable/modules/compose.html#columntransformer-for-heterogeneous-data)
- Géron HML — end-to-end project / pipelines
""",
        "Sklearn",
    ),
    (
        "day26_logistic_regression_1.md",
        "Day 26 — Logistic regression 1",
        """
## Learning goals
- Binary classification; sigmoid $\\sigma(z) = 1/(1+e^{-z})$
- Log-loss / cross-entropy
- Decision threshold 0.5 (and why you might change it)

## Practice checklist
- [ ] Assignment 0/3 · Additional 0/2

## Resources
- ISL Ch. 4
- [sklearn LogisticRegression](https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression)
- StatQuest: Logistic Regression
""",
        "Logistic Regression",
    ),
    (
        "day27_logistic_regression_1_cont.md",
        "Day 27 — Logistic Regression 1 (continued)",
        """
## Learning goals
- Multiclass: OVR / softmax (high level)
- Regularisation in logistic models
- Interpret coefficients carefully (log-odds)

## Resources
- ISL Ch. 4 continued
- sklearn multiclass docs
""",
        "Logistic Regression",
    ),
    (
        "day28_classification_metrics.md",
        "Day 28 — Classification metrics",
        """
## Learning goals
- Confusion matrix; precision, recall, F1
- ROC / AUC intuition; when accuracy lies
- Class imbalance awareness

## Cheat sheet
| Metric | Care about when… |
|--------|------------------|
| Accuracy | classes balanced |
| Precision | false positives costly |
| Recall | false negatives costly |
| F1 | balance P & R |
| AUC | ranking quality |

## Practice checklist
- [ ] Assignment 0/5 · Additional 0/4

## Resources
- [sklearn metrics](https://scikit-learn.org/stable/modules/model_evaluation.html)
- Google ML Crash Course — classification
- StatQuest: ROC and AUC
""",
        "Metrics",
    ),
    (
        "day29_knn.md",
        "Day 29 — KNN",
        """
## Learning goals
- Instance-based learning; distance metrics
- Choice of $k$; curse of dimensionality
- Need for feature scaling

## Practice checklist
- [ ] Assignment 0/6 · Additional 0/4

## Resources
- ISL Ch. 4 (KNN section) / Ch. 2
- [sklearn KNeighborsClassifier](https://scikit-learn.org/stable/modules/neighbors.html)
- StatQuest KNN
""",
        "KNN",
    ),
    (
        "day30_trees_ensembles_intro.md",
        "Day 30 — Decision tree & Ensemble intro",
        """
## Learning goals
- Tree splits; impurity (Gini / entropy) intuition
- Overfitting trees; depth / pruning ideas
- Ensembles: bagging → Random Forest teaser; boosting name-drop

## Practice checklist
- [ ] Assignment 0/5 · Additional 0/3

## Resources
- ISL Ch. 8
- [sklearn ensemble](https://scikit-learn.org/stable/modules/ensemble.html)
- [sklearn tree](https://scikit-learn.org/stable/modules/tree.html)
- StatQuest: Decision Trees / Random Forests
""",
        "Trees",
    ),
]

for fname, title, body, topic in SL_DAYS:
    write(
        f"supervised_learning/{fname}",
        f"""
# {title}
Module 4 · topic: `{topic}`

{body}

## Your resources
- 
""",
    )

# Resource hub note
write(
    "RESOURCES_HUB.md",
    f"""
# AIML resource hub (books · notes · websites)

Central list — also duplicated on each day note for convenience.

## Mathematics for ML
{MML}

## Supervised Learning
{ISL}

## Local app paths
| What | Where |
|------|--------|
| These notes | `data/notes/aiml/` |
| MML PDF for RAG | `data/raw_library/linear_algebra/Mathematics_for_ML.pdf` |
| Other books | `data/raw_library/{{statistics,foundations,ml_systems}}/` |
| Ingest UI | Knowledge Base / Library Setup |

## Suggested study order this week
1. Open `maths_for_ml/day13_...` (or next incomplete day)
2. Watch 1 linked video for the stuck concept
3. Do 3 assignment problems
4. **Generate quiz** from the day note
5. Paste mistakes under **Your resources** / a `## Mistakes` heading
""",
)

print("done", len(list(NOTES.rglob('*.md'))), "markdown files")
