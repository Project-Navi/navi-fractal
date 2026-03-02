"""
fractal_analysis_v4.py

Audit-grade, reproducible structure diagnostics for graphs (sandbox scaling) and
finite-dimensional dynamical proxies (Creative Determinant condition checks).

This module is intentionally conservative: it will REFUSE to emit a "dimension"
unless there is positive evidence of a power-law scaling regime over a nontrivial
scale range and (optionally) stability/curvature guards do not contradict linear
scaling.

Major capabilities
------------------
1) Sandbox (mass–radius) scaling on graphs
   - Metric space is explicit: undirected graph geodesic distance.
   - Deterministic compilation: insertion-order node IDs + sorted int adjacency.
   - Scaling regime selection with:
       * degeneracy filter (⟨M(r)⟩ <= 1)
       * saturation filter (⟨M(r)⟩ >= frac * N)
       * minimum log-span in r
       * minimum response range Δy
       * linearity threshold (R²)
       * model discrimination: power-law vs exponential via ΔAICc evidence margin
       * optional curvature guard (quadratic log–log beats linear)
       * optional slope-stability guard (local slope dispersion)

   - Defaults are practical:
       * r2_min=0.85 (inclusive threshold aligned with v1.2 measurement protocol)
       * delta_power_win=1.5 (requires power-law evidence but not "only perfect regimes")

   - "Strict" analysis is achieved by raising:
       * r2_min to 0.95
       * delta_power_win to 2.0 or 5.0
       * (optionally) enabling slope_stability_guard and tightening max_slope_range

2) Creative Determinant (CD) condition utilities
   - Empirical check of CD(α, ε, δ) in log form.
   - Honest about ergodicity: we cannot certify invariance/ergodicity from finite data.
   - Multi-trajectory wrapper to flag trajectory dependence ("diversity check").

3) Multifractal spectrum estimation (NEW in v4.1)
   - Computes generalized fractal dimensions D(q) for q ∈ [q_min, q_max]
   - Based on Song et al. (2015) "Multifractal analysis of weighted networks
     by a modified sandbox algorithm" (Scientific Reports, 5:17628)
   - D(0) = box-counting/capacity dimension (matches sandbox slope in monofractal cases; can differ under multifractality or finite-size effects)
   - D(1) = information dimension
   - D(2) = correlation dimension
   - Multifractal width ΔD = D(q_min) - D(q_max) measures heterogeneity
   - τ(q) = (q-1)D(q) mass exponents

Creative Determinant: Core Theorem v1.2
---------------------------------------
The full text supplied by the user is embedded verbatim as
CREATIVE_DETERMINANT_CORE_THEOREM_V1_2 for audit traceability.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import (
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
    Literal,
)
import math
import random
from collections import deque


__all__ = [
    # Graph sandbox API
    "Graph",
    "CompiledGraph",
    "compile_to_undirected_metric_graph",
    "SandboxResult",
    "LinFit",
    "estimate_sandbox_dimension",
    "sandbox_quality_gate",
    "degree_preserving_rewire_undirected",
    "make_grid_graph",
    # Multifractal API (NEW in v4.1)
    "MultifractalResult",
    "estimate_multifractal_spectrum",
    "multifractal_width",
    # Creative Determinant API
    "CREATIVE_DETERMINANT_CORE_THEOREM_V1_2",
    "CreativeDeterminantResult",
    "CreativeDeterminantMultiResult",
    "evaluate_creative_determinant_condition",
    "evaluate_creative_determinant_condition_multi",
]


Node = Union[int, str]


# -----------------------------------------------------------------------------
# Creative Determinant Core Theorem v1.2 (verbatim reference artifact)
# -----------------------------------------------------------------------------

CREATIVE_DETERMINANT_CORE_THEOREM_V1_2: str = r"""
# The Creative Determinant: Core Theorem v1.2
## Rigorous Formalization with Explicit Scope

**Version:** 1.2  
**Date:** 2025-12-24  
**Status:** Publication-Ready Core  
**Changes from v1.1:** Finite-dimensional restriction, log formulation, corrected IFS formula, theorem/conjecture separation, Hamiltonian caveat

---

## 1. Scope and Ambient Space

### 1.1 Explicit Restriction

**In what follows, X ⊂ ℝⁿ is compact and F: X → X is C¹.**

Generalizations to:
- Infinite-dimensional Banach spaces (Fréchet derivatives, Fredholm determinants)
- Non-smooth or measure-theoretic settings

are left for future work. The finite-dimensional case suffices for:
- Codebase embeddings (n = embedding dimension)
- Graph state spaces (n = number of nodes or spectral coordinates)
- Symbolic field discretizations

### 1.2 Basic Objects

| Object | Type | Meaning |
|--------|------|---------|
| X | Compact subset of ℝⁿ | Configuration space |
| F: X → X | C¹ map | One evolution step |
| J(x) = ∇F(x) | ℝⁿˣⁿ matrix | Jacobian (coupling matrix) |
| det J(x) | ℝ | Determinant (coupling coherence) |
| μ | Probability measure on X | Ergodic F-invariant measure |
| A = supp(μ) | Compact subset of X | Attractor |

---

## 2. The Creative Determinant Condition

### 2.1 Scalar Observable

**Definition:** A scalar observable is a C¹ function φ: X → ℝ⁺ measuring "system size" or "output magnitude."

The observable φ is **fixed a priori** by the modeling context, not tuned to fit the determinant. Examples:
- φ(x) = ‖x‖ (Euclidean norm)
- φ(x) = exp(H(x)) where H is entropy
- φ(x) = code size or complexity measure

### 2.2 Log-Linear Formulation

**Definition (Creative Determinant Condition):**

A system (X, F, φ, μ) satisfies the creative determinant condition CD(α, ε, δ) if:

1. **Correlation (in logs):**
$$\text{Corr}_\mu\bigl(\log \phi(F(x)),\; \alpha \cdot \log|{\det \nabla F(x)}|\bigr) > 1 - \varepsilon$$

2. **Non-degeneracy:**
$$\text{Var}_\mu\bigl(\log|\det \nabla F(x)|\bigr) > \delta$$

3. **Ergodicity:**
μ is an ergodic F-invariant probability measure with compact support.

Where Corr is Pearson correlation:
$$\text{Corr}_\mu(f, g) = \frac{\text{Cov}_\mu(f, g)}{\sqrt{\text{Var}_\mu(f) \cdot \text{Var}_\mu(g)}}$$

### 2.3 Why Logs?

The log formulation:
- Aligns with **Lyapunov exponents** (time-averages of log|det|)
- Aligns with **multiplicative ergodic theory**
- Handles heavy-tailed determinant distributions gracefully
- Makes the exponent α a simple linear coefficient

### 2.4 Interpretation

The CD condition says:

> **The logarithm of system output is linearly correlated with the logarithm of coupling coherence.**

Equivalently: output scales as a power of the determinant:
$$\phi(F(x)) \approx c \cdot |\det \nabla F(x)|^\alpha$$

The non-degeneracy condition ensures this is non-trivial: the determinant actually varies across the attractor.

### 2.5 Strongly Creative (Aspirational)

**Conjecture (Strongly Creative):**

For certain systems, φ is not just correlated with |det|^α but is **uniquely characterized** by this relationship—i.e., φ is the unique (up to scaling) F-invariant functional satisfying the CD condition.

This remains conjectural. For practical purposes, φ is fixed by domain semantics.

---

## 3. CD Class: Formal Definition

**Definition (CD Class):**

The class CD(α, ε, δ) consists of all tuples (X, F, φ, μ) where:
- X ⊂ ℝⁿ compact
- F: X → X is C¹
- φ: X → ℝ⁺ is C¹ and fixed a priori
- μ is ergodic F-invariant with compact support
- Conditions (1), (2), (3) of §2.2 hold

**Remark:** In empirical practice, we estimate Corr and Var via Birkhoff averages along long trajectories {x_t} on the attractor:
$$\text{Corr} \approx \frac{1}{T} \sum_{t=1}^{T} (\log \phi_t - \bar{\phi})(\alpha \log d_t - \bar{d}) / (\sigma_\phi \sigma_d)$$

where φ_t = φ(F(x_t)), d_t = |det ∇F(x_t)|.

---

## 4. Connection to Fractal Structure

### 4.1 Lyapunov Exponents and Determinant

**Proposition 4.1 (Lyapunov-Determinant Link):**

For an ergodic system (X, F, μ), the sum of Lyapunov exponents equals the time-average of log|det|:

$$\sum_{i=1}^{n} \lambda_i = \lim_{T \to \infty} \frac{1}{T} \sum_{t=0}^{T-1} \log|\det \nabla F(x_t)| = \int_X \log|\det \nabla F| \, d\mu$$

*Proof:* Standard result from multiplicative ergodic theory. See Oseledets (1968). ∎

**Corollary:** CD non-degeneracy (Var(log|det|) > δ) implies the Lyapunov exponents are not all identical—the system has a non-trivial spectrum.

### 4.2 Kaplan-Yorke Dimension

**Definition:** The Kaplan-Yorke (Lyapunov) dimension is:

$$D_{KY} = j + \frac{\sum_{i=1}^{j} \lambda_i}{|\lambda_{j+1}|}$$

where λ₁ ≥ λ₂ ≥ ... ≥ λₙ are the Lyapunov exponents and j is the largest integer with Σᵢ≤ⱼ λᵢ ≥ 0.

**Proposition 4.2 (CD ⇒ Non-Integer Dimension):**

Under standard hyperbolicity and SRB measure assumptions:
- CD(α, ε, δ) with ε small implies a non-trivial Lyapunov spectrum
- A non-trivial spectrum implies D_KY is typically non-integer
- Hence the attractor A has fractal structure

*Proof sketch:* Non-degeneracy of log|det| implies non-degeneracy of Σλᵢ over trajectories. For hyperbolic attractors, this spreads the exponents, giving D_KY ∉ ℤ. ∎

### 4.3 IFS and Dimension (Corrected)

For iterated function systems {f₁, ..., fₖ} with contractions on ℝⁿ:

**Equal Contraction Case:**

If all |det ∇fᵢ| = d (identical), the Hausdorff dimension D of the attractor satisfies:

$$k \cdot d^{D/n} = 1 \quad \Rightarrow \quad D = -n \cdot \frac{\log k}{\log d}$$

**General Case:**

For unequal |det ∇fᵢ| = dᵢ, the dimension D is determined implicitly by:

$$\sum_{i=1}^{k} d_i^{D/n} = 1$$

(under standard open set / separation conditions)

There is **no simple closed-form** for D in terms of Σ log dᵢ in the general case.

**Interpretation:** The fractal dimension is controlled by the determinants of the component maps, but the relationship is implicit except in symmetric cases.

### 4.4 Summary: CD ⇒ Fractal

**Proposition 4.3 (CD Implies Fractal Structure):**

Under standard assumptions (hyperbolicity, SRB measure existence):

CD(α, ε, δ) with ε small and δ > 0 implies:
1. Non-trivial Lyapunov spectrum
2. Non-integer Kaplan-Yorke dimension
3. Fractal attractor with well-defined box-counting dimension D

This is the **rigorous core**: CD ⇒ Fractal via established dynamical systems machinery.

---

## 5. Connection to Autopoiesis

### 5.1 Operational Closure

Maturana & Varela's autopoiesis requires operational closure: the system produces components that constitute the system.

**Formalization attempt:**
- P: X → Components (production)
- C: Components → X (constitution)
- F = C ∘ P (one cycle)
- P depends only on current state x (no external input)

### 5.2 Determinant as Closure Measure

The Jacobian ∇F encodes how coordinates (components) influence each other. The determinant measures coupling tightness:
- |det| = 0: Degenerate, some coordinates don't participate
- |det| = 1: Volume-preserving, no net coherence change
- |det| varies: Non-trivial production with varying coherence

### 5.3 CD as Operational Closure (Interpretation)

The CD condition φ(F(x)) ≈ |det ∇F(x)|^α can be read as:

> System output is determined by internal coupling structure, not external parameters.

This is a **form** of operational closure.

**Conjecture 5.1 (Autopoietic ⇒ CD):**

For systems satisfying a robust operational closure definition (production depending only on internal state, with a well-defined "size" output), there exists a natural observable φ and exponent α making them CD(α, ε, δ) for small ε.

**Status:** Conjecture. Not yet proven. Requires formalization of "robust operational closure."

### 5.4 Converse Direction

**Conjecture 5.2 (CD ⇒ Autopoietic Structure):**

CD(α, ε, δ) implies that the system's "size" evolution is controlled by internal couplings in a way that admits a production-constitution decomposition.

**Status:** Conjecture. The CD condition is a necessary step toward autopoiesis but may not be sufficient.

---

## 6. Connection to Navigability

### 6.1 Definition

**Definition (Intrinsic Navigability):**

A system is (O, ε)-navigable for observation set O ⊂ {1, ..., n} if:

$$I(x_O ; x_{O^c}) > (1 - \varepsilon) \cdot H(x_{O^c})$$

where I is mutual information and H is entropy under μ.

**Interpretation:** Observing coordinates in O almost determines the rest.

### 6.2 Fractal Structure and Navigability

**Conjecture 6.1 (Fractal ⇒ Navigable):**

For CD systems with fractal dimension D < n:
- Observation sets O with |O| ≈ D effective degrees of freedom carry high MI about the unobserved part
- The system is intrinsically navigable in the sense that partial observation enables inference about the whole

**Status:** Conjecture. Directionally supported by:
- Fractal dimension = "effective degrees of freedom"
- Self-similarity = local structure contains global information

**Note:** The specific inequality I ≥ (1 - |O|/D) H from v1.1 is **withdrawn** pending rigorous derivation. The sign and scaling require careful treatment.

### 6.3 Non-Fractal and Non-Navigability

**Conjecture 6.2 (Non-Fractal ⇒ Non-Navigable):**

Systems without well-defined fractal scaling (low R² on sandbox dimension) have:
- Each coordinate approximately independent in the scaling sense
- Low MI between observed and unobserved parts
- Require complete context for navigation

**Status:** Conjecture. Testable on random vs structured graphs/codebases.

### 6.4 Empirical Framing

For practical purposes, we test:

**Hypothesis:** Sandbox R² > 0.85 correlates with graceful AI navigation degradation; R² < 0.85 correlates with catastrophic threshold degradation.

This is an **empirical claim**, not a theorem. It follows from Conjectures 6.1-6.2 if those hold.

---

## 7. Hamiltonian Systems: A Caveat

### 7.1 Volume-Preserving Dynamics

Hamiltonian systems satisfy det(∇F) = 1 everywhere (Liouville's theorem).

By the CD definition:
- Var(log|det|) = 0
- Non-degeneracy fails
- System is **not in CD class**

### 7.2 But Hamiltonian Systems Can Be Structured

Hamiltonian systems can have:
- Fractal structures in Poincaré sections
- Complex invariant sets
- High navigability via conserved quantities

**Clarification:** CD does not claim to characterize **all** forms of structure and navigability. It characterizes the **autopoietic/self-generating** kind where coupling coherence varies.

Hamiltonian systems are structured through **conservation laws**, not through varying coupling determinants. They are outside CD by definition, not by oversight.

---

## 8. The Hard Core: Summary Box

### 8.1 Definition (Rigorous)

**Creative Determinant Class CD(α, ε, δ):**

Let X ⊂ ℝⁿ compact, F: X → X be C¹, φ: X → ℝ⁺ be a fixed observable, μ an ergodic F-invariant measure. The system is in CD(α, ε, δ) if:

$$\text{Corr}_\mu(\log \phi \circ F,\; \alpha \log|\det \nabla F|) > 1 - \varepsilon$$
$$\text{Var}_\mu(\log|\det \nabla F|) > \delta$$

### 8.2 Proposition (Rigorous)

**CD ⇒ Fractal Structure:**

Under standard hyperbolicity / SRB assumptions, CD(α, ε, δ) implies:
- Non-trivial Lyapunov spectrum
- Non-integer Kaplan-Yorke dimension
- Fractal attractor with well-defined dimension D

*Via:* Oseledets theorem + Kaplan-Yorke formula.

### 8.3 Conjecture 1 (Fractal ⇒ CD)

For systems where the attractor is generated predominantly by internal dynamics, fractal scaling with R² > τ implies the existence of φ and α making the CD condition hold with small ε.

### 8.4 Conjecture 2 (CD ⇒ Navigable)

For CD systems with fractal dimension D, typical observation sets of size ~D are sufficient for high MI and successful navigation.

### 8.5 Conjecture 3 (Autopoietic ⇔ CD)

Robust operational closure (autopoiesis) implies CD for a natural observable; conversely, CD implies a production-constitution structure.

### 8.6 Empirical Hypothesis

Sandbox dimension R² > 0.85 predicts graceful AI navigation degradation.
Sandbox dimension R² < 0.85 predicts catastrophic threshold degradation.

---

## 9. Measurement Protocol

### 9.1 Sandbox Dimension (Fractal Detector)

Given graph G = (V, E):

1. Select random centers C ⊂ V, |C| = 256
2. For each c ∈ C, compute M_c(r) = |{v : d(c,v) ≤ r}| via BFS
3. Average: ⟨M(r)⟩ = (1/|C|) Σ_c M_c(r)
4. Find window [r_min, r_max] maximizing R² for log⟨M(r)⟩ ~ D log(r)
5. Report D (slope) and R² (fit quality)

**Interpretation:**
- R² > 0.85: Candidate for CD class (necessary but not sufficient)
- R² < 0.85: Not CD class, likely allopoietic
- D ≤ 0: Degenerate

### 9.2 Jacobian Estimation (Practical Note)

In graph/code settings, F and ∇F are not directly available. Approaches:
- Define a dynamical process (embedding evolution, refactoring simulation)
- Approximate Jacobian numerically via finite differences
- Learn surrogate models that estimate local sensitivities

The "Jacobian" in practice is often an approximation or model. This does not invalidate the theory but requires honest acknowledgment.

### 9.3 Determinant Variance (Aliveness Detector)

Given trajectory {x_1, ..., x_T}:

1. Estimate log-determinant: ℓ_t = log|det ∇F(x_t)|
2. Compute variance: Var(ℓ) = (1/T) Σ (ℓ_t - ⟨ℓ⟩)²

**Interpretation:**
- Var(ℓ) > δ: System is alive (varying coupling)
- Var(ℓ) < δ: System is grinding (frozen coupling)

---

## 10. Taxonomy of Systems

| Type | |det ∇F| | Var | R² | CD Status |
|------|---------|-----|-----|-----------|
| Trivial-constant | 0 | 0 | N/A | Excluded |
| Trivial-linear | const | 0 | Any | Degenerate |
| Volume-preserving (Hamiltonian) | 1 | 0 | May have structure | Not CD (but structured via conservation) |
| Uniformly contracting | c < 1 | 0 | Variable | Weakly CD at best |
| **Genuinely creative** | Varies | > δ | > 0.85 | Full CD |
| Random/allopoietic | Varies | > 0 | < 0.85 | Not CD |

---

## 11. Open Questions

### 11.1 The Exponent α

Is there a universal or canonical α?

Candidates:
- α = 1/n (geometric mean interpretation)
- α = 1 (direct proportionality)
- α = D/n (dimension-dependent)
- α learned from data

### 11.2 Multifractal Extension

Real systems may be multifractal. Extension:
$$\phi_q(F(x)) \approx |\det \nabla F(x)|^{\alpha(q)}$$

where q indexes moment order and α(q) is a spectrum.

**Implementation Note (v4.1):** The multifractal spectrum D(q) is now computable
via `estimate_multifractal_spectrum()`. Key quantities:
- D(0): Box-counting dimension (matches sandbox slope in monofractal cases; can differ under multifractality or finite-size effects)
- D(1): Information dimension  
- D(2): Correlation dimension
- ΔD = D(q_min) - D(q_max): Multifractal width (heterogeneity measure)

**Interpretation for navigability:**
- Monofractal (ΔD ≈ 0): Uniform structure, local rules generalize globally
- Moderately multifractal (ΔD ~ 0.2-0.5): Rich structure with consistent scaling
- Highly multifractal (ΔD > 0.5): Local patterns may not generalize

**Reference:** Song et al. (2015) "Multifractal analysis of weighted networks
by a modified sandbox algorithm" Scientific Reports 5:17628

### 11.3 Continuous-Time Formulation

For flows with vector field v:
$$\frac{d \log \phi}{dt} = \alpha \cdot \text{div}(v)$$

Connects to Liouville's equation for phase-space density.

### 11.4 Rigorous Navigability Bounds

The conjectured MI bounds need:
- Precise assumptions on μ
- Connection to rate-distortion or compression theory
- Possible restriction to exact self-similar measures

---

## 12. Conclusion

### What Is Rigorous

- **CD class definition:** Well-typed, checkable, non-trivial
- **CD ⇒ Fractal:** Via Lyapunov exponents and Kaplan-Yorke dimension
- **Measurement protocol:** Implementable sandbox dimension + R²

### What Is Conjectured

- **Fractal ⇒ CD:** Plausible for self-generated attractors
- **CD ⇔ Autopoietic:** Interpretation + formalization needed
- **CD ⇒ Navigable:** Directionally supported, bounds not yet derived

### What Is Empirical

- **R² threshold (0.85):** Needs calibration on real systems
- **Navigation degradation curves:** Testable on AI + codebases

### Next Steps

1. **Pilot empirical test:** Sandbox dimension on 3-5 codebases, correlate with LLM navigation
2. **Rigorous derivation:** Attempt MI bounds for self-similar measures
3. **Formalize autopoiesis:** Define "robust operational closure" precisely enough to prove Conjecture 5.1

---

*End of v1.2 Core*

**Status:** The hard core is now publishable as a research program with:
- Clear rigorous results
- Explicit conjectures
- Testable empirical hypotheses
"""


# =============================================================================
# Graph (input)
# =============================================================================

class Graph:
    """
    Input graph container.

    Neighbor storage uses sets for convenient construction. Determinism is enforced
    by compiling to a CompiledGraph before analysis.

    Notes:
    - Nodes may be int or str (or any stable hashable, but the public typing is strict).
    - Self-loops are ignored by construction.
    """

    def __init__(self, directed: bool = True) -> None:
        self.directed = directed
        self._adj_out: Dict[Node, Set[Node]] = {}

    def add_node(self, u: Node) -> None:
        if u not in self._adj_out:
            self._adj_out[u] = set()

    def add_edge(self, u: Node, v: Node) -> None:
        if u == v:
            self.add_node(u)
            return
        self.add_node(u)
        self.add_node(v)
        self._adj_out[u].add(v)
        if not self.directed:
            self._adj_out[v].add(u)

    def nodes_insertion_order(self) -> Tuple[Node, ...]:
        return tuple(self._adj_out.keys())

    @property
    def n_nodes(self) -> int:
        return len(self._adj_out)

    @property
    def n_edges(self) -> int:
        total = sum(len(vs) for vs in self._adj_out.values())
        return total if self.directed else total // 2

    def out_neighbors_set(self, u: Node) -> Set[Node]:
        return self._adj_out.get(u, set())

    def symmetrized_preserve_nodes(self) -> "Graph":
        """
        Undirected symmetrization that preserves isolated nodes.
        """
        g = Graph(directed=False)
        for u in self._adj_out.keys():
            g.add_node(u)
        for u, vs in self._adj_out.items():
            for v in vs:
                g.add_edge(u, v)
        return g

    @staticmethod
    def from_edges(edges: Iterable[Tuple[Node, Node]], directed: bool = True) -> "Graph":
        g = Graph(directed=directed)
        for u, v in edges:
            g.add_edge(u, v)
        return g


# =============================================================================
# Compiled graph (deterministic metric space)
# =============================================================================

@dataclass(frozen=True)
class CompiledGraph:
    """
    Deterministic representation for traversal / metric computations:
      - nodes indexed 0..n-1 in insertion order
      - adjacency lists are sorted integer tuples
      - undirected by construction for geodesic distance
    """
    nodes: Tuple[Node, ...]
    adj: Tuple[Tuple[int, ...], ...]
    n_edges: int

    @property
    def n_nodes(self) -> int:
        return len(self.nodes)


def compile_to_undirected_metric_graph(g: Graph) -> CompiledGraph:
    """
    Compile an input Graph into a deterministic undirected metric graph.

    Reproducibility guarantees:
    - node IDs follow insertion order in the input graph
    - neighbor iteration is deterministic because adjacency is sorted
    """
    if g.directed:
        gu = g.symmetrized_preserve_nodes()
    else:
        gu = g

    nodes = gu.nodes_insertion_order()
    node_id = {u: i for i, u in enumerate(nodes)}
    n = len(nodes)

    edge_set: Set[Tuple[int, int]] = set()
    for u in nodes:
        iu = node_id[u]
        for v in gu.out_neighbors_set(u):
            iv = node_id[v]
            if iu == iv:
                continue
            a, b = (iu, iv) if iu < iv else (iv, iu)
            edge_set.add((a, b))

    adj_sets: List[Set[int]] = [set() for _ in range(n)]
    for a, b in edge_set:
        adj_sets[a].add(b)
        adj_sets[b].add(a)

    adj_sorted = tuple(tuple(sorted(s)) for s in adj_sets)
    return CompiledGraph(nodes=nodes, adj=adj_sorted, n_edges=len(edge_set))


# =============================================================================
# Connected components (largest CC)
# =============================================================================

def largest_connected_component_ids(cg: CompiledGraph) -> Set[int]:
    n = cg.n_nodes
    seen = [False] * n
    best: Set[int] = set()

    for start in range(n):
        if seen[start]:
            continue
        comp: Set[int] = set()
        q = deque([start])
        seen[start] = True
        comp.add(start)
        while q:
            u = q.popleft()
            for v in cg.adj[u]:
                if not seen[v]:
                    seen[v] = True
                    comp.add(v)
                    q.append(v)
        if len(comp) > len(best):
            best = comp
    return best


def induced_subgraph_ids(cg: CompiledGraph, keep: Set[int]) -> CompiledGraph:
    old_to_new: Dict[int, int] = {}
    new_nodes: List[Node] = []
    for old in range(cg.n_nodes):
        if old in keep:
            old_to_new[old] = len(new_nodes)
            new_nodes.append(cg.nodes[old])

    n_new = len(new_nodes)
    if n_new == 0:
        return CompiledGraph(nodes=tuple(), adj=tuple(), n_edges=0)

    edge_set: Set[Tuple[int, int]] = set()
    for old_u in keep:
        new_u = old_to_new[old_u]
        for old_v in cg.adj[old_u]:
            if old_v in keep:
                new_v = old_to_new[old_v]
                if new_u == new_v:
                    continue
                a, b = (new_u, new_v) if new_u < new_v else (new_v, new_u)
                edge_set.add((a, b))

    adj_sets: List[Set[int]] = [set() for _ in range(n_new)]
    for a, b in edge_set:
        adj_sets[a].add(b)
        adj_sets[b].add(a)

    new_adj = tuple(tuple(sorted(s)) for s in adj_sets)
    return CompiledGraph(nodes=tuple(new_nodes), adj=new_adj, n_edges=len(edge_set))


# =============================================================================
# BFS ball sizes
# =============================================================================

def bfs_layer_counts(cg: CompiledGraph, center: int, r_max: int) -> List[int]:
    if r_max < 0:
        raise ValueError("r_max must be >= 0")
    if not (0 <= center < cg.n_nodes):
        raise ValueError("center out of range")

    layer_counts = [0] * (r_max + 1)
    layer_counts[0] = 1

    n = cg.n_nodes
    dist = [-1] * n
    dist[center] = 0
    q = deque([center])

    while q:
        u = q.popleft()
        du = dist[u]
        if du == r_max:
            continue
        nd = du + 1
        for v in cg.adj[u]:
            if dist[v] == -1:
                dist[v] = nd
                layer_counts[nd] += 1
                if nd < r_max:
                    q.append(v)

    return layer_counts


def masses_from_layers(layer_counts: List[int], radii: Sequence[int]) -> List[int]:
    radii_sorted = sorted(set(int(r) for r in radii))
    if not radii_sorted or radii_sorted[0] < 1:
        raise ValueError("radii must be >=1 and non-empty")
    r_max = len(layer_counts) - 1
    if radii_sorted[-1] > r_max:
        raise ValueError("radii exceed r_max")

    out: List[int] = []
    cumulative = 0
    d = 0
    for r in radii_sorted:
        while d <= r:
            cumulative += layer_counts[d]
            d += 1
        out.append(cumulative)
    return out


# =============================================================================
# Diameter estimate
# =============================================================================

def farthest_from(cg: CompiledGraph, start: int) -> Tuple[int, int]:
    n = cg.n_nodes
    dist = [-1] * n
    dist[start] = 0
    q = deque([start])

    while q:
        u = q.popleft()
        for v in cg.adj[u]:
            if dist[v] == -1:
                dist[v] = dist[u] + 1
                q.append(v)

    max_d = max(dist)
    far = min(i for i, d in enumerate(dist) if d == max_d)
    return far, max_d


def two_sweep_diameter_estimate(cg: CompiledGraph, rng: random.Random) -> int:
    n = cg.n_nodes
    if n == 0:
        return 0
    start = rng.randrange(n)
    u, _ = farthest_from(cg, start)
    _, d = farthest_from(cg, u)
    return d


# =============================================================================
# Regression and information criteria
# =============================================================================

@dataclass(frozen=True)
class LinFit:
    slope: float
    intercept: float
    r2: float
    slope_stderr: float
    sse: float
    n: int
    weighted: bool

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def linear_fit_ols(x: Sequence[float], y: Sequence[float]) -> LinFit:
    if len(x) != len(y):
        raise ValueError("x,y length mismatch")
    n = len(x)
    if n < 2:
        raise ValueError("need >=2 points")

    mx = sum(x) / n
    my = sum(y) / n
    sxx = sum((xi - mx) ** 2 for xi in x)
    if sxx == 0:
        raise ValueError("x variance is zero")

    sxy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    slope = sxy / sxx
    intercept = my - slope * mx

    residuals = [yi - (intercept + slope * xi) for xi, yi in zip(x, y)]
    sse = sum(r * r for r in residuals)
    ss_tot = sum((yi - my) ** 2 for yi in y)
    r2 = 1.0 - (sse / ss_tot) if ss_tot > 0 else 0.0

    if n > 2:
        mse = sse / (n - 2)
        slope_stderr = math.sqrt(mse / sxx)
    else:
        slope_stderr = float("inf")

    return LinFit(
        slope=float(slope),
        intercept=float(intercept),
        r2=float(r2),
        slope_stderr=float(slope_stderr),
        sse=float(sse),
        n=n,
        weighted=False,
    )


def linear_fit_wls(x: Sequence[float], y: Sequence[float], w: Sequence[float]) -> LinFit:
    if len(x) != len(y) or len(x) != len(w):
        raise ValueError("x,y,w length mismatch")
    n = len(x)
    if n < 2:
        raise ValueError("need >=2 points")

    W = sum(wi for wi in w if wi > 0)
    if W <= 0:
        raise ValueError("nonpositive total weight")

    mx = sum(wi * xi for wi, xi in zip(w, x)) / W
    my = sum(wi * yi for wi, yi in zip(w, y)) / W

    sxx = sum(wi * (xi - mx) ** 2 for wi, xi in zip(w, x))
    if sxx <= 0:
        raise ValueError("weighted x variance is zero")

    sxy = sum(wi * (xi - mx) * (yi - my) for wi, xi, yi in zip(w, x, y))
    slope = sxy / sxx
    intercept = my - slope * mx

    residuals = [yi - (intercept + slope * xi) for xi, yi in zip(x, y)]
    sse = sum(wi * (ri * ri) for wi, ri in zip(w, residuals))
    ss_tot = sum(wi * (yi - my) ** 2 for wi, yi in zip(w, y))
    r2 = 1.0 - (sse / ss_tot) if ss_tot > 0 else 0.0

    if n > 2:
        mse = sse / (n - 2)
        slope_stderr = math.sqrt(mse / sxx)
    else:
        slope_stderr = float("inf")

    return LinFit(
        slope=float(slope),
        intercept=float(intercept),
        r2=float(r2),
        slope_stderr=float(slope_stderr),
        sse=float(sse),
        n=n,
        weighted=True,
    )


def aicc_for_ols(sse: float, n: int, k: int) -> float:
    # Common-variance Gaussian OLS (constants dropped)
    if n <= k + 1:
        return float("inf")
    if sse <= 0:
        sse = 1e-12
    aic = n * math.log(sse / n) + 2 * k
    return float(aic + (2 * k * (k + 1)) / (n - k - 1))


def aicc_for_wls(chi2: float, n: int, k: int) -> float:
    """
    Quasi-AICc for WLS when weights approximate inverse variances.
    Uses chi2 = Σ w_i * residual_i^2 as a deviance proxy.

    Comparisons are meaningful for the *same window* (same points/weights).
    """
    if n <= k + 1:
        return float("inf")
    return float(chi2 + 2 * k + (2 * k * (k + 1)) / (n - k - 1))


# =============================================================================
# Auto-radii
# =============================================================================

def auto_radii(
    diam_est: int,
    *,
    r_cap: int = 32,
    dense_prefix: int = 6,
    log_points: int = 10,
    diam_frac: float = 0.3,
    min_r_max: int = 12,
) -> List[int]:
    if diam_est <= 1:
        return []
    r_max = int(max(min_r_max, diam_frac * diam_est))
    r_max = min(r_cap, max(1, r_max))
    r_max = min(r_max, max(1, diam_est))  # never exceed actual diameter
    if r_max < 2:
        return [1]

    radii: Set[int] = set(range(1, min(dense_prefix, r_max) + 1))
    if r_max > dense_prefix:
        lo = max(dense_prefix + 1, 2)
        hi = r_max
        log_lo = math.log(lo)
        log_hi = math.log(hi)
        for i in range(log_points):
            t = i / max(1, (log_points - 1))
            r = int(round(math.exp(log_lo + t * (log_hi - log_lo))))
            r = max(1, min(r_max, r))
            radii.add(r)

    return sorted(radii)


# =============================================================================
# Sandbox result type
# =============================================================================

@dataclass(frozen=True)
class SandboxResult:
    method: str
    dimension: Optional[float]
    reason: str

    model_preference: str                 # "powerlaw" | "none"
    delta_aicc: Optional[float]           # AICc_exp - AICc_pow on chosen window

    powerlaw_fit: Optional[LinFit]
    exponential_fit: Optional[LinFit]

    window_i: Optional[int]
    window_j: Optional[int]
    window_r_min: Optional[int]
    window_r_max: Optional[int]
    window_log_span: Optional[float]
    window_delta_y: Optional[float]

    # Optional guard diagnostics
    window_slope_range: Optional[float]
    window_aicc_quad_minus_lin: Optional[float]

    # WLS diagnostics
    used_wls: bool
    var_floor: float

    # Bootstrap diagnostics (if enabled)
    bootstrap_reps: int
    dimension_ci: Optional[Tuple[float, float]]
    delta_aicc_ci: Optional[Tuple[float, float]]
    bootstrap_valid_reps: int

    radii_eval: Tuple[int, ...]
    mean_mass_eval: Tuple[float, ...]
    y_eval: Tuple[float, ...]
    y_mode: str

    n_nodes_original: int
    n_nodes_measured: int
    component_policy: str
    retained_fraction: float
    n_edges_measured: int
    n_centers: int
    seed: int
    notes: str

    def to_dict(self) -> Dict[str, object]:
        d = asdict(self)
        if self.powerlaw_fit is not None:
            d["powerlaw_fit"] = self.powerlaw_fit.to_dict()
        if self.exponential_fit is not None:
            d["exponential_fit"] = self.exponential_fit.to_dict()
        return d


# =============================================================================
# Quadratic fit (for curvature guard)
# =============================================================================

def _solve_3x3(A: List[List[float]], b: List[float]) -> Tuple[float, float, float]:
    M = [row[:] + [rhs] for row, rhs in zip(A, b)]
    n = 3
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[pivot][col]) < 1e-15:
            raise ValueError("singular matrix")
        if pivot != col:
            M[col], M[pivot] = M[pivot], M[col]
        piv = M[col][col]
        for j in range(col, n + 1):
            M[col][j] /= piv
        for r in range(n):
            if r == col:
                continue
            fac = M[r][col]
            for j in range(col, n + 1):
                M[r][j] -= fac * M[col][j]
    return (M[0][3], M[1][3], M[2][3])


def quadratic_fit_sse_ols(x: Sequence[float], y: Sequence[float]) -> float:
    if len(x) != len(y):
        raise ValueError("length mismatch")
    n = len(x)
    if n < 3:
        raise ValueError("need >=3 points")

    sx0 = float(n)
    sx1 = sum(xi for xi in x)
    sx2 = sum(xi * xi for xi in x)
    sx3 = sum(xi ** 3 for xi in x)
    sx4 = sum(xi ** 4 for xi in x)

    sy0 = sum(yi for yi in y)
    sy1 = sum(xi * yi for xi, yi in zip(x, y))
    sy2 = sum((xi * xi) * yi for xi, yi in zip(x, y))

    A = [
        [sx0, sx1, sx2],
        [sx1, sx2, sx3],
        [sx2, sx3, sx4],
    ]
    bvec = [sy0, sy1, sy2]
    a, b1, c = _solve_3x3(A, bvec)

    residuals = [yi - (a + b1 * xi + c * xi * xi) for xi, yi in zip(x, y)]
    return float(sum(r * r for r in residuals))


def quadratic_fit_sse_wls(x: Sequence[float], y: Sequence[float], w: Sequence[float]) -> float:
    if len(x) != len(y) or len(x) != len(w):
        raise ValueError("length mismatch")
    n = len(x)
    if n < 3:
        raise ValueError("need >=3 points")

    S0 = sum(wi for wi in w)
    S1 = sum(wi * xi for wi, xi in zip(w, x))
    S2 = sum(wi * xi * xi for wi, xi in zip(w, x))
    S3 = sum(wi * (xi ** 3) for wi, xi in zip(w, x))
    S4 = sum(wi * (xi ** 4) for wi, xi in zip(w, x))

    T0 = sum(wi * yi for wi, yi in zip(w, y))
    T1 = sum(wi * xi * yi for wi, xi, yi in zip(w, x, y))
    T2 = sum(wi * (xi * xi) * yi for wi, xi, yi in zip(w, x, y))

    A = [
        [S0, S1, S2],
        [S1, S2, S3],
        [S2, S3, S4],
    ]
    bvec = [T0, T1, T2]
    a, b1, c = _solve_3x3(A, bvec)

    residuals = [yi - (a + b1 * xi + c * xi * xi) for xi, yi in zip(x, y)]
    return float(sum(wi * (ri * ri) for wi, ri in zip(w, residuals)))


def slope_range_over_subwindows(
    x: Sequence[float],
    y: Sequence[float],
    *,
    sub_len: int,
    use_wls: bool,
    w: Optional[Sequence[float]] = None,
) -> float:
    n = len(x)
    if sub_len < 2 or sub_len > n:
        raise ValueError("invalid subwindow length")
    slopes: List[float] = []
    for i in range(0, n - sub_len + 1):
        xs = x[i:i + sub_len]
        ys = y[i:i + sub_len]
        if use_wls:
            if w is None:
                raise ValueError("weights required for WLS slope stability")
            ws = w[i:i + sub_len]
            fit = linear_fit_wls(xs, ys, ws)
        else:
            fit = linear_fit_ols(xs, ys)
        slopes.append(fit.slope)
    return float(max(slopes) - min(slopes)) if slopes else float("inf")


# =============================================================================
# Moment aggregation across centers (for WLS and bootstrap)
# =============================================================================

def _moments_from_center_masses(
    center_masses: Sequence[Sequence[int]],
) -> Tuple[List[float], List[float], List[float], List[float]]:
    """
    Given per-center masses (shape: [n_centers][n_radii]), compute:
      mean_M, var_M (sample), mean_logM, var_logM (sample)
    """
    n_centers = len(center_masses)
    if n_centers == 0:
        raise ValueError("no centers")

    R = len(center_masses[0])
    sum_M = [0.0] * R
    sum_M2 = [0.0] * R
    sum_logM = [0.0] * R
    sum_logM2 = [0.0] * R

    for masses in center_masses:
        if len(masses) != R:
            raise ValueError("center mass length mismatch")
        for i, m in enumerate(masses):
            mm = float(max(1, int(m)))
            lm = math.log(mm)
            sum_M[i] += mm
            sum_M2[i] += mm * mm
            sum_logM[i] += lm
            sum_logM2[i] += lm * lm

    mean_M = [s / n_centers for s in sum_M]
    mean_logM = [s / n_centers for s in sum_logM]

    if n_centers > 1:
        var_M = [
            max(0.0, (sum_M2[i] - n_centers * (mean_M[i] ** 2)) / (n_centers - 1))
            for i in range(R)
        ]
        var_logM = [
            max(0.0, (sum_logM2[i] - n_centers * (mean_logM[i] ** 2)) / (n_centers - 1))
            for i in range(R)
        ]
    else:
        var_M = [0.0] * R
        var_logM = [0.0] * R

    return mean_M, var_M, mean_logM, var_logM


def _y_and_weights(
    *,
    mean_mode: Literal["geometric", "arithmetic"],
    mean_M: Sequence[float],
    var_M: Sequence[float],
    mean_logM: Sequence[float],
    var_logM: Sequence[float],
    n_centers: int,
    use_wls: bool,
    var_floor: float,
) -> Tuple[List[float], Optional[List[float]]]:
    """
    Return y_eval and (optional) weights w for each radius.

    Geometric:
      y = E[log M]
      Var(y) = Var(log M) / n_centers

    Arithmetic:
      y = log(E[M])
      Var(y) approx (Var(M)/n_centers) / (E[M]^2)   (delta method)
    """
    y: List[float] = []
    w: Optional[List[float]] = [] if use_wls else None

    for i in range(len(mean_M)):
        if mean_mode == "geometric":
            yi = float(mean_logM[i])
            y.append(yi)
            if use_wls:
                vy = (float(var_logM[i]) / max(1, n_centers))
                vy = max(vy, var_floor)
                w.append(1.0 / vy)
        else:
            # arithmetic
            mi = float(mean_M[i])
            yi = float(math.log(mi))
            y.append(yi)
            if use_wls:
                # delta method
                vy = (float(var_M[i]) / max(1, n_centers)) / max(mi * mi, 1e-30)
                vy = max(vy, var_floor)
                w.append(1.0 / vy)

    return y, w


def _percentile(sorted_vals: List[float], q: float) -> float:
    """
    q in [0,1]. Linear interpolation between adjacent ranks.
    """
    if not sorted_vals:
        return float("nan")
    if q <= 0:
        return float(sorted_vals[0])
    if q >= 1:
        return float(sorted_vals[-1])
    n = len(sorted_vals)
    pos = (n - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_vals[lo])
    t = pos - lo
    return float((1 - t) * sorted_vals[lo] + t * sorted_vals[hi])


# =============================================================================
# Sandbox estimator
# =============================================================================

def estimate_sandbox_dimension(
    g: Graph,
    *,
    seed: int = 0,
    n_centers: int = 256,
    component_policy: Literal["giant", "all"] = "giant",
    mean_mode: Literal["geometric", "arithmetic"] = "geometric",
    radii: Optional[Sequence[int]] = None,

    # Regime filters (defaults aligned with v1.2 inclusivity)
    min_points: int = 6,
    min_log_span: float = math.log(3.0),
    r2_min: float = 0.85,
    max_saturation_frac: float = 0.95,
    min_delta_y: float = 0.5,

    # Model evidence: accept only if power-law wins by margin
    delta_power_win: float = 1.5,
    require_positive_slope: bool = True,

    # WLS + robustness
    use_wls: bool = True,
    var_floor: float = 1e-6,

    # Optional guards
    curvature_guard: bool = True,
    delta_quadratic_win: float = 3.0,
    slope_stability_guard: bool = False,
    slope_stability_sub_len: Optional[int] = None,
    max_slope_range: float = 0.5,

    # Bootstrap on chosen window
    bootstrap_reps: int = 0,
    bootstrap_seed: Optional[int] = None,

    # Auto-radii safety
    r_cap: int = 32,
    notes: str = "",
) -> SandboxResult:
    """
    Estimate sandbox (mass–radius) dimension D from ⟨M(r)⟩ ~ r^D over a scaling regime.

    Returns dimension=None with a refusal reason unless a credible regime is found.

    Practical defaults:
    - r2_min=0.85: inclusive threshold (finite-size/noisy systems often land 0.85–0.93)
    - delta_power_win=1.5: requires power-law to be *meaningfully* better than exponential
    - curvature_guard=True with delta_quadratic_win=3.0: avoids obvious curved impostors
    - use_wls=True: weights points by estimated uncertainty across centers

    Strict mode suggestion:
        r2_min=0.95
        delta_power_win=2.0 or 5.0
        slope_stability_guard=True, max_slope_range smaller (e.g. 0.2)
    """
    rng = random.Random(seed)

    # Deterministic compile to metric graph
    cg_full = compile_to_undirected_metric_graph(g)
    n_original = cg_full.n_nodes
    if n_original == 0:
        return SandboxResult(
            method="sandbox",
            dimension=None,
            reason="refused: empty graph",
            model_preference="none",
            delta_aicc=None,
            powerlaw_fit=None,
            exponential_fit=None,
            window_i=None,
            window_j=None,
            window_r_min=None,
            window_r_max=None,
            window_log_span=None,
            window_delta_y=None,
            window_slope_range=None,
            window_aicc_quad_minus_lin=None,
            used_wls=bool(use_wls),
            var_floor=float(var_floor),
            bootstrap_reps=int(bootstrap_reps),
            dimension_ci=None,
            delta_aicc_ci=None,
            bootstrap_valid_reps=0,
            radii_eval=tuple(),
            mean_mass_eval=tuple(),
            y_eval=tuple(),
            y_mode=str(mean_mode),
            n_nodes_original=0,
            n_nodes_measured=0,
            component_policy=str(component_policy),
            retained_fraction=0.0,
            n_edges_measured=0,
            n_centers=0,
            seed=seed,
            notes=notes,
        )

    if component_policy not in ("giant", "all"):
        raise ValueError("component_policy must be 'giant' or 'all'")

    cg = cg_full
    if component_policy == "giant":
        keep = largest_connected_component_ids(cg_full)
        cg = induced_subgraph_ids(cg_full, keep)

    n_measured = cg.n_nodes
    retained = (n_measured / n_original) if n_original > 0 else 0.0
    if n_measured < 2:
        return SandboxResult(
            method="sandbox",
            dimension=None,
            reason="refused: trivial measured component (n<2)",
            model_preference="none",
            delta_aicc=None,
            powerlaw_fit=None,
            exponential_fit=None,
            window_i=None,
            window_j=None,
            window_r_min=None,
            window_r_max=None,
            window_log_span=None,
            window_delta_y=None,
            window_slope_range=None,
            window_aicc_quad_minus_lin=None,
            used_wls=bool(use_wls),
            var_floor=float(var_floor),
            bootstrap_reps=int(bootstrap_reps),
            dimension_ci=None,
            delta_aicc_ci=None,
            bootstrap_valid_reps=0,
            radii_eval=tuple(),
            mean_mass_eval=tuple(),
            y_eval=tuple(),
            y_mode=str(mean_mode),
            n_nodes_original=n_original,
            n_nodes_measured=n_measured,
            component_policy=str(component_policy),
            retained_fraction=float(retained),
            n_edges_measured=cg.n_edges,
            n_centers=0,
            seed=seed,
            notes=notes,
        )

    # Radii selection
    if radii is None:
        diam_est = two_sweep_diameter_estimate(cg, rng)
        radii_eval = auto_radii(diam_est, r_cap=r_cap)
        if len(radii_eval) < min_points:
            return SandboxResult(
                method="sandbox",
                dimension=None,
                reason=f"refused: auto radii has < min_points ({len(radii_eval)} < {min_points}); diam_est={diam_est}",
                model_preference="none",
                delta_aicc=None,
                powerlaw_fit=None,
                exponential_fit=None,
                window_i=None,
                window_j=None,
                window_r_min=None,
                window_r_max=None,
                window_log_span=None,
                window_delta_y=None,
                window_slope_range=None,
                window_aicc_quad_minus_lin=None,
                used_wls=bool(use_wls),
                var_floor=float(var_floor),
                bootstrap_reps=int(bootstrap_reps),
                dimension_ci=None,
                delta_aicc_ci=None,
                bootstrap_valid_reps=0,
                radii_eval=tuple(radii_eval),
                mean_mass_eval=tuple(),
                y_eval=tuple(),
                y_mode=str(mean_mode),
                n_nodes_original=n_original,
                n_nodes_measured=n_measured,
                component_policy=str(component_policy),
                retained_fraction=float(retained),
                n_edges_measured=cg.n_edges,
                n_centers=0,
                seed=seed,
                notes=notes,
            )
    else:
        radii_eval = sorted(set(int(r) for r in radii if int(r) >= 1))
        if len(radii_eval) < min_points:
            return SandboxResult(
                method="sandbox",
                dimension=None,
                reason=f"refused: provided radii < min_points ({len(radii_eval)} < {min_points})",
                model_preference="none",
                delta_aicc=None,
                powerlaw_fit=None,
                exponential_fit=None,
                window_i=None,
                window_j=None,
                window_r_min=None,
                window_r_max=None,
                window_log_span=None,
                window_delta_y=None,
                window_slope_range=None,
                window_aicc_quad_minus_lin=None,
                used_wls=bool(use_wls),
                var_floor=float(var_floor),
                bootstrap_reps=int(bootstrap_reps),
                dimension_ci=None,
                delta_aicc_ci=None,
                bootstrap_valid_reps=0,
                radii_eval=tuple(radii_eval),
                mean_mass_eval=tuple(),
                y_eval=tuple(),
                y_mode=str(mean_mode),
                n_nodes_original=n_original,
                n_nodes_measured=n_measured,
                component_policy=str(component_policy),
                retained_fraction=float(retained),
                n_edges_measured=cg.n_edges,
                n_centers=0,
                seed=seed,
                notes=notes,
            )

    radii_eval = sorted(radii_eval)
    r_max = radii_eval[-1]

    # Sample centers deterministically (seeded RNG)
    centers = [rng.randrange(n_measured) for _ in range(max(1, n_centers))]

    # Store per-center masses for bootstrap
    center_masses: List[List[int]] = []

    for c in centers:
        layers = bfs_layer_counts(cg, c, r_max)
        masses = masses_from_layers(layers, radii_eval)
        center_masses.append([int(m) for m in masses])

    valid = len(center_masses)

    # Aggregate moments across centers
    mean_M, var_M, mean_logM, var_logM = _moments_from_center_masses(center_masses)
    y_eval, w_eval = _y_and_weights(
        mean_mode=mean_mode,
        mean_M=mean_M,
        var_M=var_M,
        mean_logM=mean_logM,
        var_logM=var_logM,
        n_centers=valid,
        use_wls=use_wls,
        var_floor=var_floor,
    )

    x_log_r = [math.log(float(r)) for r in radii_eval]
    x_r = [float(r) for r in radii_eval]

    # Filter degenerate + saturated indices
    sat_thresh = max_saturation_frac * float(n_measured)
    keep_idx: List[int] = []
    for i in range(len(mean_M)):
        mean_mass_eff = math.exp(mean_logM[i]) if mean_mode == "geometric" else mean_M[i]
        if mean_mass_eff <= 1.0:
            continue
        if mean_mass_eff >= sat_thresh:
            continue
        keep_idx.append(i)

    if len(keep_idx) < min_points:
        return SandboxResult(
            method="sandbox",
            dimension=None,
            reason="refused: insufficient non-degenerate, non-saturated points",
            model_preference="none",
            delta_aicc=None,
            powerlaw_fit=None,
            exponential_fit=None,
            window_i=None,
            window_j=None,
            window_r_min=None,
            window_r_max=None,
            window_log_span=None,
            window_delta_y=None,
            window_slope_range=None,
            window_aicc_quad_minus_lin=None,
            used_wls=bool(use_wls),
            var_floor=float(var_floor),
            bootstrap_reps=int(bootstrap_reps),
            dimension_ci=None,
            delta_aicc_ci=None,
            bootstrap_valid_reps=0,
            radii_eval=tuple(radii_eval),
            mean_mass_eval=tuple(mean_M),
            y_eval=tuple(y_eval),
            y_mode=str(mean_mode),
            n_nodes_original=n_original,
            n_nodes_measured=n_measured,
            component_policy=str(component_policy),
            retained_fraction=float(retained),
            n_edges_measured=cg.n_edges,
            n_centers=valid,
            seed=seed,
            notes=notes,
        )

    # Window search over consecutive kept points (no holes)
    best = None
    sub_len = slope_stability_sub_len if slope_stability_sub_len is not None else min_points

    # Choose fit/aicc functions
    fit_fn = (lambda xx, yy, ww: linear_fit_wls(xx, yy, ww)) if use_wls else (lambda xx, yy, ww: linear_fit_ols(xx, yy))
    aicc_fn = aicc_for_wls if use_wls else aicc_for_ols

    for a in range(0, len(keep_idx) - min_points + 1):
        for b in range(a + min_points - 1, len(keep_idx)):
            i = keep_idx[a]
            j = keep_idx[b]

            # no holes in kept indices
            if (keep_idx[b] - keep_idx[a]) != (b - a):
                continue

            span = x_log_r[j] - x_log_r[i]
            if span < min_log_span:
                continue

            yw = y_eval[i:j + 1]
            delta_y = max(yw) - min(yw)
            if delta_y < min_delta_y:
                continue

            xw = x_log_r[i:j + 1]
            ww = w_eval[i:j + 1] if (use_wls and w_eval is not None) else None

            try:
                fit_pow = fit_fn(xw, yw, ww)  # type: ignore[arg-type]
            except Exception:
                continue

            if require_positive_slope and fit_pow.slope <= 0:
                continue
            if fit_pow.r2 < r2_min:
                continue

            # exponential alternative on same window: y ~ a + α r
            xr_w = x_r[i:j + 1]
            try:
                fit_exp = fit_fn(xr_w, yw, ww)  # type: ignore[arg-type]
            except Exception:
                fit_exp = None

            aicc_pow = aicc_fn(fit_pow.sse, fit_pow.n, k=2)
            aicc_exp = aicc_fn(fit_exp.sse, fit_exp.n, k=2) if fit_exp is not None else float("inf")
            delta = aicc_exp - aicc_pow  # positive => powerlaw better

            if delta < delta_power_win:
                continue

            # curvature guard: quadratic beats linear in log–log?
            aicc_quad_minus_lin: Optional[float] = None
            if curvature_guard and (j - i + 1) >= 3:
                try:
                    if use_wls and ww is not None:
                        sse_quad = quadratic_fit_sse_wls(xw, yw, ww)
                        aicc_quad = aicc_for_wls(sse_quad, len(xw), k=3)
                    else:
                        sse_quad = quadratic_fit_sse_ols(xw, yw)
                        aicc_quad = aicc_for_ols(sse_quad, len(xw), k=3)

                    aicc_quad_minus_lin = float(aicc_quad - aicc_pow)

                    # reject if quadratic is better by delta_quadratic_win
                    if aicc_quad + delta_quadratic_win < aicc_pow:
                        continue
                except Exception:
                    aicc_quad_minus_lin = None

            slope_range: Optional[float] = None
            if slope_stability_guard:
                try:
                    slope_range = slope_range_over_subwindows(
                        xw, yw, sub_len=sub_len, use_wls=use_wls, w=ww
                    )
                except Exception:
                    slope_range = float("inf")
                if slope_range is None or slope_range > max_slope_range:
                    continue

            score = (span, fit_pow.r2, -fit_pow.slope_stderr)
            cand = (score, i, j, fit_pow, fit_exp, delta, slope_range, aicc_quad_minus_lin)
            if best is None or cand[0] > best[0]:
                best = cand

    if best is None:
        return SandboxResult(
            method="sandbox",
            dimension=None,
            reason="refused: no window passes scaling criteria + powerlaw evidence (and optional guards)",
            model_preference="none",
            delta_aicc=None,
            powerlaw_fit=None,
            exponential_fit=None,
            window_i=None,
            window_j=None,
            window_r_min=None,
            window_r_max=None,
            window_log_span=None,
            window_delta_y=None,
            window_slope_range=None,
            window_aicc_quad_minus_lin=None,
            used_wls=bool(use_wls),
            var_floor=float(var_floor),
            bootstrap_reps=int(bootstrap_reps),
            dimension_ci=None,
            delta_aicc_ci=None,
            bootstrap_valid_reps=0,
            radii_eval=tuple(radii_eval),
            mean_mass_eval=tuple(mean_M),
            y_eval=tuple(y_eval),
            y_mode=str(mean_mode),
            n_nodes_original=n_original,
            n_nodes_measured=n_measured,
            component_policy=str(component_policy),
            retained_fraction=float(retained),
            n_edges_measured=cg.n_edges,
            n_centers=valid,
            seed=seed,
            notes=notes,
        )

    (_, wi, wj, fit_pow, fit_exp, delta, slope_range, aicc_quad_minus_lin) = best

    # Bootstrap CI on the chosen window (do NOT re-search windows)
    dim_ci: Optional[Tuple[float, float]] = None
    delta_ci: Optional[Tuple[float, float]] = None
    boot_ok = 0

    if bootstrap_reps > 0:
        brng = random.Random(seed if bootstrap_seed is None else bootstrap_seed)
        Ds: List[float] = []
        deltas: List[float] = []

        for _ in range(int(bootstrap_reps)):
            idxs = [brng.randrange(valid) for _ in range(valid)]
            boot_masses = [center_masses[k] for k in idxs]
            b_mean_M, b_var_M, b_mean_logM, b_var_logM = _moments_from_center_masses(boot_masses)
            b_y, b_w = _y_and_weights(
                mean_mode=mean_mode,
                mean_M=b_mean_M,
                var_M=b_var_M,
                mean_logM=b_mean_logM,
                var_logM=b_var_logM,
                n_centers=valid,
                use_wls=use_wls,
                var_floor=var_floor,
            )

            xw = x_log_r[wi:wj + 1]
            yw = b_y[wi:wj + 1]
            ww = b_w[wi:wj + 1] if (use_wls and b_w is not None) else None

            try:
                b_fit_pow = fit_fn(xw, yw, ww)  # type: ignore[arg-type]
                b_aicc_pow = aicc_fn(b_fit_pow.sse, b_fit_pow.n, k=2)

                xr_w = x_r[wi:wj + 1]
                b_fit_exp = fit_fn(xr_w, yw, ww)  # type: ignore[arg-type]
                b_aicc_exp = aicc_fn(b_fit_exp.sse, b_fit_exp.n, k=2)

                b_delta = b_aicc_exp - b_aicc_pow
                Ds.append(float(b_fit_pow.slope))
                deltas.append(float(b_delta))
                boot_ok += 1
            except Exception:
                continue

        if boot_ok >= max(10, int(0.2 * bootstrap_reps)):
            Ds_sorted = sorted(Ds)
            deltas_sorted = sorted(deltas)
            dim_ci = (_percentile(Ds_sorted, 0.025), _percentile(Ds_sorted, 0.975))
            delta_ci = (_percentile(deltas_sorted, 0.025), _percentile(deltas_sorted, 0.975))

    return SandboxResult(
        method="sandbox",
        dimension=float(fit_pow.slope),
        reason="accepted: credible scaling window + positive powerlaw evidence",
        model_preference="powerlaw",
        delta_aicc=float(delta),
        powerlaw_fit=fit_pow,
        exponential_fit=fit_exp,
        window_i=int(wi),
        window_j=int(wj),
        window_r_min=int(radii_eval[wi]),
        window_r_max=int(radii_eval[wj]),
        window_log_span=float(x_log_r[wj] - x_log_r[wi]),
        window_delta_y=float(max(y_eval[wi:wj + 1]) - min(y_eval[wi:wj + 1])),
        window_slope_range=float(slope_range) if slope_range is not None else None,
        window_aicc_quad_minus_lin=float(aicc_quad_minus_lin) if aicc_quad_minus_lin is not None else None,
        used_wls=bool(use_wls),
        var_floor=float(var_floor),
        bootstrap_reps=int(bootstrap_reps),
        dimension_ci=dim_ci,
        delta_aicc_ci=delta_ci,
        bootstrap_valid_reps=int(boot_ok),
        radii_eval=tuple(radii_eval),
        mean_mass_eval=tuple(mean_M),
        y_eval=tuple(y_eval),
        y_mode=str(mean_mode),
        n_nodes_original=n_original,
        n_nodes_measured=n_measured,
        component_policy=str(component_policy),
        retained_fraction=float(retained),
        n_edges_measured=cg.n_edges,
        n_centers=valid,
        seed=seed,
        notes=notes,
    )


def sandbox_quality_gate(
    res: SandboxResult,
    *,
    preset: Literal["inclusive", "strict"] = "inclusive",
    # override knobs:
    r2_min: Optional[float] = None,
    slope_stderr_max: Optional[float] = None,
    min_log_span: Optional[float] = None,
    delta_aicc_min: Optional[float] = None,
) -> Tuple[bool, str]:
    """
    Downstream acceptance policy. Use 'inclusive' to match v1.2 protocol
    tendencies; use 'strict' to accept only very clean regimes.

    inclusive defaults:
      r2_min=0.85, slope_stderr_max=0.25, min_log_span=log(3), delta_aicc_min=1.5
    strict defaults:
      r2_min=0.95, slope_stderr_max=0.20, min_log_span=log(4), delta_aicc_min=2.0
    """
    if res.dimension is None or res.powerlaw_fit is None:
        return False, "reject: dimension is None (estimator refused or failed)"

    if preset == "inclusive":
        _r2 = 0.85
        _se = 0.25
        _span = math.log(3.0)
        _daic = 1.5
    else:
        _r2 = 0.95
        _se = 0.20
        _span = math.log(4.0)
        _daic = 2.0

    if r2_min is not None:
        _r2 = float(r2_min)
    if slope_stderr_max is not None:
        _se = float(slope_stderr_max)
    if min_log_span is not None:
        _span = float(min_log_span)
    if delta_aicc_min is not None:
        _daic = float(delta_aicc_min)

    if res.powerlaw_fit.r2 < _r2:
        return False, f"reject: R²={res.powerlaw_fit.r2:.3f} < {_r2:.3f}"
    if not math.isfinite(res.powerlaw_fit.slope_stderr) or res.powerlaw_fit.slope_stderr > _se:
        return False, f"reject: slope_stderr={res.powerlaw_fit.slope_stderr:.3f} > {_se:.3f}"
    if res.window_log_span is None or res.window_log_span < _span:
        return False, f"reject: window_log_span={res.window_log_span} < {_span:.3f}"
    if res.delta_aicc is None or res.delta_aicc < _daic:
        return False, f"reject: ΔAICc={res.delta_aicc} < {_daic:.3f}"

    return True, f"accept: passed {preset} quality gates"


# =============================================================================
# Degree-preserving null model (deterministic)
# =============================================================================

def degree_preserving_rewire_undirected(
    g_undirected: Graph,
    *,
    n_swaps: int,
    seed: int = 0,
    verify_degrees: bool = True,
    max_attempts_factor: int = 50,
) -> Graph:
    if g_undirected.directed:
        raise ValueError("expects undirected graph")

    rng = random.Random(seed)
    nodes = g_undirected.nodes_insertion_order()
    node_id = {u: i for i, u in enumerate(nodes)}
    n = len(nodes)

    edge_set: Set[Tuple[int, int]] = set()
    for u in nodes:
        iu = node_id[u]
        for v in g_undirected.out_neighbors_set(u):
            iv = node_id[v]
            if iu == iv:
                continue
            a, b = (iu, iv) if iu < iv else (iv, iu)
            edge_set.add((a, b))

    edges: List[Tuple[int, int]] = sorted(edge_set)
    m = len(edges)
    if n < 4 or m < 2:
        return g_undirected

    def degree_seq(eset: Set[Tuple[int, int]]) -> List[int]:
        deg = [0] * n
        for a, b in eset:
            deg[a] += 1
            deg[b] += 1
        deg.sort()
        return deg

    deg_before = degree_seq(edge_set) if verify_degrees else []

    swaps_done = 0
    attempts = 0
    max_attempts = max(max_attempts_factor * n_swaps, 2000)

    while swaps_done < n_swaps and attempts < max_attempts:
        attempts += 1
        i1 = rng.randrange(m)
        i2 = rng.randrange(m)
        if i1 == i2:
            continue

        (a, b) = edges[i1]
        (c, d) = edges[i2]
        if len({a, b, c, d}) < 4:
            continue

        if rng.random() < 0.5:
            e1, e2 = (a, d), (c, b)
        else:
            e1, e2 = (a, c), (b, d)

        x1, y1 = e1 if e1[0] < e1[1] else (e1[1], e1[0])
        x2, y2 = e2 if e2[0] < e2[1] else (e2[1], e2[0])

        if x1 == y1 or x2 == y2:
            continue
        if (x1, y1) in edge_set or (x2, y2) in edge_set:
            continue

        edge_set.remove((a, b))
        edge_set.remove((c, d))
        edge_set.add((x1, y1))
        edge_set.add((x2, y2))
        edges[i1] = (x1, y1)
        edges[i2] = (x2, y2)
        swaps_done += 1

    out = Graph(directed=False)
    for u in nodes:
        out.add_node(u)
    for a, b in edge_set:
        out.add_edge(nodes[a], nodes[b])

    if verify_degrees and degree_seq(edge_set) != deg_before:
        raise AssertionError("degree sequence changed after rewiring (should not happen)")

    return out


# =============================================================================
# Creative Determinant checks
# =============================================================================

@dataclass(frozen=True)
class CreativeDeterminantResult:
    passed: bool
    reason: str

    alpha: float
    epsilon: float
    delta: float

    corr: float
    var_logdet: float
    n_samples: int

    fit_logphi_on_logdet: Optional[LinFit]
    notes: str

    def to_dict(self) -> Dict[str, object]:
        d = asdict(self)
        if self.fit_logphi_on_logdet is not None:
            d["fit_logphi_on_logdet"] = self.fit_logphi_on_logdet.to_dict()
        return d


@dataclass(frozen=True)
class CreativeDeterminantMultiResult:
    passed: bool
    reason: str
    per_trajectory: Tuple[CreativeDeterminantResult, ...]
    alpha_mean: Optional[float]
    alpha_std: Optional[float]
    notes: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "alpha_mean": self.alpha_mean,
            "alpha_std": self.alpha_std,
            "per_trajectory": [r.to_dict() for r in self.per_trajectory],
            "notes": self.notes,
        }


def _pearson_corr(x: Sequence[float], y: Sequence[float]) -> float:
    if len(x) != len(y):
        raise ValueError("length mismatch")
    n = len(x)
    if n < 2:
        return float("nan")
    mx = sum(x) / n
    my = sum(y) / n
    vx = sum((xi - mx) ** 2 for xi in x)
    vy = sum((yi - my) ** 2 for yi in y)
    if vx <= 0 or vy <= 0:
        return float("nan")
    cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    return float(cov / math.sqrt(vx * vy))


def evaluate_creative_determinant_condition(
    log_phi_next: Sequence[float],
    log_abs_det_jac: Sequence[float],
    *,
    alpha: Optional[float] = None,
    epsilon: float = 0.05,
    delta: float = 1e-6,
    min_samples: int = 30,
    require_positive_alpha: bool = False,
    notes: str = "",
) -> CreativeDeterminantResult:
    """
    Empirical check of CD(α, ε, δ) in log form.

    IMPORTANT:
    - This function does NOT certify ergodicity or invariance.
    - A "pass" is conditional: it means the provided samples satisfy the CD inequalities.
      For confidence, evaluate across multiple trajectories / initial conditions.
    """
    if len(log_phi_next) != len(log_abs_det_jac):
        raise ValueError("length mismatch")

    xs: List[float] = []
    ds: List[float] = []
    for lp, ld in zip(log_phi_next, log_abs_det_jac):
        if math.isfinite(lp) and math.isfinite(ld):
            xs.append(float(lp))
            ds.append(float(ld))

    n = len(xs)
    if n < min_samples:
        return CreativeDeterminantResult(
            passed=False,
            reason=f"refused: insufficient samples after filtering (n={n} < {min_samples})",
            alpha=float(alpha) if alpha is not None else float("nan"),
            epsilon=float(epsilon),
            delta=float(delta),
            corr=float("nan"),
            var_logdet=float("nan"),
            n_samples=n,
            fit_logphi_on_logdet=None,
            notes=notes,
        )

    md = sum(ds) / n
    var_d = sum((d - md) ** 2 for d in ds) / n
    if var_d <= float(delta):
        return CreativeDeterminantResult(
            passed=False,
            reason=f"failed: Var(log|det|)={var_d:.6g} <= delta={delta:.6g}",
            alpha=float(alpha) if alpha is not None else float("nan"),
            epsilon=float(epsilon),
            delta=float(delta),
            corr=float("nan"),
            var_logdet=float(var_d),
            n_samples=n,
            fit_logphi_on_logdet=None,
            notes=notes,
        )

    fit: Optional[LinFit] = None
    alpha_eff: float
    if alpha is None:
        fit = linear_fit_ols(ds, xs)   # regress log φ on log|det|
        alpha_eff = float(fit.slope)
    else:
        alpha_eff = float(alpha)

    if require_positive_alpha and not (alpha_eff > 0):
        return CreativeDeterminantResult(
            passed=False,
            reason=f"failed: alpha={alpha_eff:.6g} is not positive",
            alpha=float(alpha_eff),
            epsilon=float(epsilon),
            delta=float(delta),
            corr=float("nan"),
            var_logdet=float(var_d),
            n_samples=n,
            fit_logphi_on_logdet=fit,
            notes=notes,
        )

    corr = _pearson_corr(xs, [alpha_eff * d for d in ds])
    if not math.isfinite(corr):
        return CreativeDeterminantResult(
            passed=False,
            reason="failed: correlation undefined (zero variance in one signal)",
            alpha=float(alpha_eff),
            epsilon=float(epsilon),
            delta=float(delta),
            corr=float("nan"),
            var_logdet=float(var_d),
            n_samples=n,
            fit_logphi_on_logdet=fit,
            notes=notes,
        )

    threshold = 1.0 - float(epsilon)
    if corr <= threshold:
        return CreativeDeterminantResult(
            passed=False,
            reason=f"failed: Corr={corr:.6g} <= 1-epsilon={threshold:.6g}",
            alpha=float(alpha_eff),
            epsilon=float(epsilon),
            delta=float(delta),
            corr=float(corr),
            var_logdet=float(var_d),
            n_samples=n,
            fit_logphi_on_logdet=fit,
            notes=notes,
        )

    return CreativeDeterminantResult(
        passed=True,
        reason="passed: CD correlation + non-degeneracy criteria satisfied (ergodicity not certified)",
        alpha=float(alpha_eff),
        epsilon=float(epsilon),
        delta=float(delta),
        corr=float(corr),
        var_logdet=float(var_d),
        n_samples=n,
        fit_logphi_on_logdet=fit,
        notes=notes,
    )


def evaluate_creative_determinant_condition_multi(
    trajectories: Sequence[Tuple[Sequence[float], Sequence[float]]],
    *,
    alpha: Optional[float] = None,
    epsilon: float = 0.05,
    delta: float = 1e-6,
    min_samples: int = 30,
    require_positive_alpha: bool = False,
    # diversity check (only meaningful if alpha is inferred per-trajectory)
    alpha_std_max: float = 0.25,
    notes: str = "",
) -> CreativeDeterminantMultiResult:
    """
    Evaluate CD condition across multiple trajectories / initial conditions.

    Policy:
    - Compute per-trajectory CD results.
    - If any trajectory fails => overall fail.
    - If alpha is inferred (alpha=None), also flag instability if std(alpha) is large.
      This is a simple "trajectory diversity" red-flag: passing on one trajectory
      and failing on another is a warning sign for non-representative sampling.
    """
    results: List[CreativeDeterminantResult] = []
    alphas: List[float] = []

    for i, (log_phi, log_det) in enumerate(trajectories):
        r = evaluate_creative_determinant_condition(
            log_phi,
            log_det,
            alpha=alpha,
            epsilon=epsilon,
            delta=delta,
            min_samples=min_samples,
            require_positive_alpha=require_positive_alpha,
            notes=(notes + f" | traj={i}") if notes else f"traj={i}",
        )
        results.append(r)
        if alpha is None and math.isfinite(r.alpha):
            alphas.append(float(r.alpha))

    passed_all = all(r.passed for r in results)
    if not passed_all:
        return CreativeDeterminantMultiResult(
            passed=False,
            reason="failed: at least one trajectory failed CD criteria (sampling not robust)",
            per_trajectory=tuple(results),
            alpha_mean=(sum(alphas) / len(alphas)) if alphas else None,
            alpha_std=(math.sqrt(sum((a - (sum(alphas) / len(alphas))) ** 2 for a in alphas) / len(alphas))) if len(alphas) >= 2 else None,
            notes=notes,
        )

    if alpha is None and len(alphas) >= 2:
        am = sum(alphas) / len(alphas)
        av = sum((a - am) ** 2 for a in alphas) / len(alphas)
        astd = math.sqrt(av)
        if astd > alpha_std_max:
            return CreativeDeterminantMultiResult(
                passed=False,
                reason=f"failed: alpha unstable across trajectories (std={astd:.3f} > {alpha_std_max:.3f})",
                per_trajectory=tuple(results),
                alpha_mean=float(am),
                alpha_std=float(astd),
                notes=notes,
            )
        return CreativeDeterminantMultiResult(
            passed=True,
            reason="passed: all trajectories pass CD criteria and alpha is stable",
            per_trajectory=tuple(results),
            alpha_mean=float(am),
            alpha_std=float(astd),
            notes=notes,
        )

    # alpha fixed or only one trajectory
    return CreativeDeterminantMultiResult(
        passed=True,
        reason="passed: all trajectories pass CD criteria (ergodicity still not certified)",
        per_trajectory=tuple(results),
        alpha_mean=None,
        alpha_std=None,
        notes=notes,
    )


# =============================================================================
# Multifractal Spectrum Estimation (NEW in v4.1)
# =============================================================================
# Based on: Song et al. (2015) "Multifractal analysis of weighted networks
# by a modified sandbox algorithm" Scientific Reports 5:17628
#
# The generalized fractal dimension D(q) is defined via:
#   ⟨[M(r)/M(0)]^(q-1)⟩ ~ (r/d)^((q-1)D(q))
#
# where M(r) is the mass in a sandbox of radius r, M(0) is total nodes,
# d is the network diameter, and ⟨·⟩ denotes average over sandbox centers.
#
# Key quantities:
#   D(0) = box-counting/capacity dimension (matches sandbox slope in monofractal cases; can differ under multifractality or finite-size effects)
#   D(1) = information dimension (limit as q→1)
#   D(2) = correlation dimension
#   τ(q) = (q-1)D(q) = mass exponents
#   ΔD = D(q_min) - D(q_max) = multifractal width
# =============================================================================

@dataclass(frozen=True)
class MultifractalResult:
    """
    Result of multifractal spectrum estimation.
    
    Key fields:
    - D_q: Dict mapping q values to generalized dimension D(q)
    - tau_q: Dict mapping q values to mass exponent τ(q) = (q-1)D(q)
    - D_q_stderr: Dict mapping q values to standard error of D(q)
    - delta_D: Multifractal width D(q_min) - D(q_max)
    - is_multifractal: True if delta_D > threshold (default 0.1)
    
    Special dimensions:
    - D_0: Box-counting/capacity dimension (matches sandbox slope in monofractal cases; can differ otherwise)
    - D_1: Information dimension
    - D_2: Correlation dimension
    """
    method: str
    
    # Core results
    D_q: Dict[float, float]           # q -> D(q)
    tau_q: Dict[float, float]         # q -> τ(q) = (q-1)D(q)
    D_q_stderr: Dict[float, float]    # q -> stderr of D(q)
    D_q_r2: Dict[float, float]        # q -> R² of fit for D(q)
    
    # Special dimensions
    D_0: Optional[float]              # Box-counting dimension
    D_1: Optional[float]              # Information dimension  
    D_2: Optional[float]              # Correlation dimension
    
    # Multifractal characterization
    delta_D: Optional[float]          # D(q_min) - D(q_max)
    is_multifractal: bool             # delta_D > threshold
    multifractal_threshold: float     # threshold used
    
    # Metadata
    q_values: Tuple[float, ...]
    n_nodes: int
    n_centers: int
    diameter: int
    radii_used: Tuple[int, ...]
    seed: int
    notes: str

    # Q-value filtering audit trail
    requested_q_values: Tuple[float, ...] = ()
    accepted_q_values: Tuple[float, ...] = ()
    rejected_q: Dict[float, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _compute_moment_avg(
    center_masses: List[List[int]],
    radius_idx: int,
    q: float,
    total_nodes: int,
) -> float:
    """
    Compute ⟨[M(r)/N]^(q-1)⟩ for a given radius index and q value.
    
    For q=1, returns exp(⟨log(M(r)/N)⟩) as a continuous extension.
    """
    n_centers = len(center_masses)
    if n_centers == 0:
        return float("nan")
    
    if abs(q - 1.0) < 1e-10:
        # q ≈ 1: use log formulation to avoid 0^0
        log_sum = 0.0
        valid = 0
        for masses in center_masses:
            m = float(max(1, masses[radius_idx]))
            if m > 0 and total_nodes > 0:
                log_sum += math.log(m / total_nodes)
                valid += 1
        if valid == 0:
            return float("nan")
        return math.exp(log_sum / valid)
    else:
        # General q
        power = q - 1.0
        total = 0.0
        valid = 0
        for masses in center_masses:
            m = float(max(1, masses[radius_idx]))
            ratio = m / max(1, total_nodes)
            if ratio > 0:
                total += ratio ** power
                valid += 1
        if valid == 0:
            return float("nan")
        return total / valid


def estimate_multifractal_spectrum(
    g: Graph,
    *,
    q_min: float = -10.0,
    q_max: float = 10.0,
    q_steps: int = 21,
    seed: int = 0,
    n_centers: int = 256,
    component_policy: Literal["giant", "all"] = "giant",
    radii: Optional[Sequence[int]] = None,
    sandbox_window: Optional[Tuple[int, int]] = None,  # (r_min, r_max) from sandbox

    # Fit quality thresholds
    min_points: int = 4,
    r2_min: float = 0.80,

    # Multifractal detection
    multifractal_threshold: float = 0.1,

    # Auto-radii
    r_cap: int = 32,
    notes: str = "",
) -> MultifractalResult:
    """
    Estimate the multifractal spectrum D(q) for a graph.
    
    Based on Song et al. (2015) "Multifractal analysis of weighted networks
    by a modified sandbox algorithm" Scientific Reports 5:17628.
    
    The generalized fractal dimension D(q) is computed via:
        ⟨[M(r)/N]^(q-1)⟩ ~ (r/d)^((q-1)D(q))
    
    where M(r) is sandbox mass at radius r, N is total nodes, d is diameter.
    
    Parameters:
    -----------
    g : Graph
        Input graph (will be compiled to undirected metric graph)
    q_min, q_max : float
        Range of q values to compute D(q) for
    q_steps : int
        Number of q values (linearly spaced from q_min to q_max)
    n_centers : int
        Number of random sandbox centers
    r2_min : float
        Minimum R² to accept a D(q) estimate
    multifractal_threshold : float
        delta_D > this threshold implies multifractal structure
        
    Returns:
    --------
    MultifractalResult with D(q), τ(q), and characterization metrics
    
    Interpretation:
    ---------------
    - If D(q) is constant for all q → monofractal (uniform scaling)
    - If D(q) varies with q → multifractal (heterogeneous scaling)
    - delta_D = D(q_min) - D(q_max) measures multifractal width
    - Larger delta_D indicates more spatial heterogeneity
    
    For navigability assessment:
    - Monofractal (delta_D ≈ 0): Local rules generalize globally
    - Moderately multifractal (0.1 < delta_D < 0.5): Rich but consistent structure
    - Highly multifractal (delta_D > 0.5): Local patterns may not generalize
    """
    rng = random.Random(seed)
    
    # Generate q values
    if q_steps < 2:
        q_steps = 2
    q_values = [q_min + (q_max - q_min) * i / (q_steps - 1) for i in range(q_steps)]
    
    # Ensure q=0, q=1, q=2 are included for special dimensions
    special_qs = [0.0, 1.0, 2.0]
    for sq in special_qs:
        if q_min <= sq <= q_max and sq not in q_values:
            q_values.append(sq)
    q_values = sorted(set(q_values))
    
    # Compile graph
    cg_full = compile_to_undirected_metric_graph(g)
    n_original = cg_full.n_nodes
    
    if n_original == 0:
        return MultifractalResult(
            method="multifractal_sandbox",
            D_q={},
            tau_q={},
            D_q_stderr={},
            D_q_r2={},
            D_0=None,
            D_1=None,
            D_2=None,
            delta_D=None,
            is_multifractal=False,
            multifractal_threshold=float(multifractal_threshold),
            q_values=tuple(q_values),
            n_nodes=0,
            n_centers=0,
            diameter=0,
            radii_used=tuple(),
            seed=seed,
            notes=notes + " | empty graph",
        )
    
    cg = cg_full
    if component_policy == "giant":
        keep = largest_connected_component_ids(cg_full)
        cg = induced_subgraph_ids(cg_full, keep)
    
    n_nodes = cg.n_nodes
    if n_nodes < 2:
        return MultifractalResult(
            method="multifractal_sandbox",
            D_q={},
            tau_q={},
            D_q_stderr={},
            D_q_r2={},
            D_0=None,
            D_1=None,
            D_2=None,
            delta_D=None,
            is_multifractal=False,
            multifractal_threshold=float(multifractal_threshold),
            q_values=tuple(q_values),
            n_nodes=n_nodes,
            n_centers=0,
            diameter=0,
            radii_used=tuple(),
            seed=seed,
            notes=notes + " | trivial component",
        )
    
    # Estimate diameter and select radii
    diameter = two_sweep_diameter_estimate(cg, rng)
    
    if radii is None:
        radii_eval = auto_radii(diameter, r_cap=r_cap, min_r_max=max(6, min(diameter, 12)))
        # Hard-cap to diameter to avoid saturation regime
        radii_eval = [r for r in radii_eval if r <= diameter]
    else:
        radii_eval = sorted(set(int(r) for r in radii if 1 <= int(r) <= diameter))

    # Apply sandbox scaling window if provided
    if sandbox_window is not None:
        r_min, r_max = sandbox_window
        radii_eval = [r for r in radii_eval if r_min <= r <= r_max]

    if len(radii_eval) < min_points:
        return MultifractalResult(
            method="multifractal_sandbox",
            D_q={},
            tau_q={},
            D_q_stderr={},
            D_q_r2={},
            D_0=None,
            D_1=None,
            D_2=None,
            delta_D=None,
            is_multifractal=False,
            multifractal_threshold=float(multifractal_threshold),
            q_values=tuple(q_values),
            n_nodes=n_nodes,
            n_centers=0,
            diameter=diameter,
            radii_used=tuple(radii_eval),
            seed=seed,
            notes=notes + f" | insufficient radii ({len(radii_eval)} < {min_points})",
        )
    
    r_max = radii_eval[-1]
    
    # Sample centers and compute masses
    centers = [rng.randrange(n_nodes) for _ in range(max(1, n_centers))]
    center_masses: List[List[int]] = []
    
    for c in centers:
        layers = bfs_layer_counts(cg, c, r_max)
        masses = masses_from_layers(layers, radii_eval)
        center_masses.append([int(m) for m in masses])
    
    n_centers_actual = len(center_masses)

    # Filter saturated radii (moment fraction approaching 1.0)
    MFA_SATURATION_THRESHOLD = 0.99
    valid_radii_idx = []
    for ri, r in enumerate(radii_eval):
        # Check median mass fraction across centers
        mass_fracs = [center_masses[ci][ri] / max(1, n_nodes) for ci in range(len(center_masses))]
        median_frac = sorted(mass_fracs)[len(mass_fracs) // 2]
        if median_frac < MFA_SATURATION_THRESHOLD:
            valid_radii_idx.append(ri)

    # Apply saturation filter
    if len(valid_radii_idx) < min_points:
        # All radii saturated - can't fit
        return MultifractalResult(
            method="multifractal_sandbox",
            D_q={}, tau_q={}, D_q_stderr={}, D_q_r2={},
            D_0=None, D_1=None, D_2=None, delta_D=None,
            is_multifractal=False, multifractal_threshold=multifractal_threshold,
            q_values=tuple(q_values), n_nodes=n_nodes, n_centers=len(center_masses),
            diameter=diameter, radii_used=tuple(radii_eval), seed=seed,
            notes=f"All radii saturated (threshold={MFA_SATURATION_THRESHOLD})"
        )
    radii_eval = [radii_eval[i] for i in valid_radii_idx]
    center_masses = [[masses[i] for i in valid_radii_idx] for masses in center_masses]

    # Compute D(q) for each q
    D_q: Dict[float, float] = {}
    tau_q: Dict[float, float] = {}
    D_q_stderr: Dict[float, float] = {}
    D_q_r2: Dict[float, float] = {}
    rejected_q_dict: Dict[float, str] = {}

    # x values: log(r/d) for regression
    x_log_r_over_d = [math.log(r / max(1, diameter)) for r in radii_eval]

    for q in q_values:
        # Compute ⟨[M(r)/N]^(q-1)⟩ for each radius
        moment_avgs = []
        for ri in range(len(radii_eval)):
            avg = _compute_moment_avg(center_masses, ri, q, n_nodes)
            moment_avgs.append(avg)
        
        # Filter valid points (non-NaN, positive)
        valid_x = []
        valid_y = []
        for xi, yi in zip(x_log_r_over_d, moment_avgs):
            if math.isfinite(yi) and yi > 0:
                valid_x.append(xi)
                valid_y.append(math.log(yi))
        
        if len(valid_x) < min_points:
            rejected_q_dict[q] = f"insufficient_points ({len(valid_x)} < {min_points})"
            continue

        # Linear regression: log(moment_avg) ~ (q-1)D(q) * log(r/d)
        try:
            fit = linear_fit_ols(valid_x, valid_y)
        except Exception as e:
            rejected_q_dict[q] = f"fit_failed ({type(e).__name__})"
            continue

        if fit.r2 < r2_min:
            rejected_q_dict[q] = f"poor_fit (R²={fit.r2:.3f} < {r2_min})"
            continue
        
        # Extract D(q) from slope
        # Regression gives: log(moment) = (q-1)D(q) * log(r/d)
        # So slope = (q-1)D(q), thus D(q) = slope / (q-1) for q ≠ 1
        if abs(q - 1.0) < 1e-10:
            # For q=1, D(1) = slope because _compute_moment_avg uses the
            # correct q→1 continuous extension (geometric mean of log(M/N)).
            D_q[q] = fit.slope
            D_q_stderr[q] = fit.slope_stderr
        else:
            D_q[q] = fit.slope / (q - 1.0)
            D_q_stderr[q] = fit.slope_stderr / abs(q - 1.0)

        D_q_r2[q] = fit.r2

        # τ(q) = (q-1)D(q)
        if abs(q - 1.0) < 1e-10:
            tau_q[q] = 0.0  # τ(1) = 0 by definition: (1-1)*D(1) = 0
        else:
            tau_q[q] = fit.slope  # τ(q) = (q-1)D(q) = slope
    
    # Extract special dimensions
    D_0 = D_q.get(0.0)
    D_1 = D_q.get(1.0)
    D_2 = D_q.get(2.0)
    
    # Compute multifractal width
    delta_D: Optional[float] = None
    is_multifractal = False
    
    if D_q:
        q_min_actual = min(D_q.keys())
        q_max_actual = max(D_q.keys())
        if q_min_actual < q_max_actual:
            D_at_qmin = D_q.get(q_min_actual)
            D_at_qmax = D_q.get(q_max_actual)
            if D_at_qmin is not None and D_at_qmax is not None:
                delta_D = D_at_qmin - D_at_qmax
                is_multifractal = abs(delta_D) > multifractal_threshold
    
    return MultifractalResult(
        method="multifractal_sandbox",
        D_q=D_q,
        tau_q=tau_q,
        D_q_stderr=D_q_stderr,
        D_q_r2=D_q_r2,
        D_0=D_0,
        D_1=D_1,
        D_2=D_2,
        delta_D=delta_D,
        is_multifractal=is_multifractal,
        multifractal_threshold=float(multifractal_threshold),
        q_values=tuple(sorted(D_q.keys())),
        n_nodes=n_nodes,
        n_centers=n_centers_actual,
        diameter=diameter,
        radii_used=tuple(radii_eval),
        seed=seed,
        notes=notes,
        requested_q_values=tuple(q_values),
        accepted_q_values=tuple(sorted(D_q.keys())),
        rejected_q=rejected_q_dict,
    )


def multifractal_width(mf: MultifractalResult) -> Optional[float]:
    """
    Convenience function to extract multifractal width ΔD from result.
    
    Returns D(q_min) - D(q_max), or None if not computable.
    
    Interpretation:
    - ΔD ≈ 0: Monofractal (uniform scaling)
    - ΔD ~ 0.1-0.3: Weak multifractality
    - ΔD ~ 0.3-0.5: Moderate multifractality  
    - ΔD > 0.5: Strong multifractality (highly heterogeneous)
    """
    return mf.delta_D


# =============================================================================
# Minimal sanity helpers
# =============================================================================

def make_grid_graph(m: int, n: int) -> Graph:
    g = Graph(directed=False)

    def idx(i: int, j: int) -> int:
        return i * n + j

    for i in range(m):
        for j in range(n):
            u = idx(i, j)
            if i + 1 < m:
                g.add_edge(u, idx(i + 1, j))
            if j + 1 < n:
                g.add_edge(u, idx(i, j + 1))
    return g


if __name__ == "__main__":
    print("=" * 60)
    print("Fractal Analysis v4.1 - Sanity Check")
    print("=" * 60)
    
    # Test 1: Sandbox dimension on grid
    print("\n[1] Grid 30x30 - Sandbox Dimension")
    grid = make_grid_graph(30, 30)
    est = estimate_sandbox_dimension(
        grid,
        seed=42,
        n_centers=512,
        component_policy="giant",
        mean_mode="geometric",
        r2_min=0.90,
        delta_power_win=1.5,
        bootstrap_reps=200,
        curvature_guard=True,
        notes="grid sanity",
    )
    if est.dimension is not None:
        print(f"  Dimension: {est.dimension:.3f}")
        print(f"  R²: {est.powerlaw_fit.r2:.4f}")
        print(f"  Window: r ∈ [{est.window_r_min}, {est.window_r_max}]")
        if est.dimension_ci:
            print(f"  95% CI: ({est.dimension_ci[0]:.3f}, {est.dimension_ci[1]:.3f})")
    else:
        print(f"  Status: {est.reason}")
    
    # Test 2: Multifractal spectrum on grid
    print("\n[2] Grid 30x30 - Multifractal Spectrum")
    mf = estimate_multifractal_spectrum(
        grid,
        seed=42,
        n_centers=512,
        q_min=-5,
        q_max=5,
        q_steps=11,
        notes="grid multifractal",
    )
    print(f"  D(0) = {mf.D_0:.3f}" if mf.D_0 is not None else "  D(0) = N/A")
    print(f"  D(1) = {mf.D_1:.3f}" if mf.D_1 is not None else "  D(1) = N/A")
    print(f"  D(2) = {mf.D_2:.3f}" if mf.D_2 is not None else "  D(2) = N/A")
    print(f"  ΔD = {mf.delta_D:.3f}" if mf.delta_D is not None else "  ΔD = N/A")
    print(f"  Multifractal: {mf.is_multifractal}")
    if mf.D_q:
        qs = list(mf.D_q.keys())[:5]
        ds = [mf.D_q[q] for q in qs]
        print(f"  D(q) for q in {qs}: {[f'{d:.2f}' for d in ds]}")
    
    # Test 3: Rewired null model
    print("\n[3] Rewired Grid (Null Model)")
    rewired = degree_preserving_rewire_undirected(grid, n_swaps=3000, seed=7, verify_degrees=True)
    est_null = estimate_sandbox_dimension(
        rewired,
        seed=42,
        n_centers=512,
        component_policy="giant",
        mean_mode="geometric",
        r2_min=0.90,
        delta_power_win=1.5,
        bootstrap_reps=200,
        curvature_guard=True,
        notes="rewired null sanity",
    )
    if est_null.dimension is not None:
        print(f"  Dimension: {est_null.dimension:.3f}")
        print(f"  R²: {est_null.powerlaw_fit.r2:.4f}")
    else:
        print(f"  Status: REFUSED")
        print(f"  Reason: {est_null.reason}")
    
    # Test 4: Multifractal on rewired graph
    print("\n[4] Rewired Grid - Multifractal Spectrum")
    mf_null = estimate_multifractal_spectrum(
        rewired,
        seed=42,
        n_centers=512,
        q_min=-5,
        q_max=5,
        q_steps=11,
        notes="rewired multifractal",
    )
    print(f"  D(0) = {mf_null.D_0:.3f}" if mf_null.D_0 else "  D(0) = N/A")
    print(f"  ΔD = {mf_null.delta_D:.3f}" if mf_null.delta_D is not None else "  ΔD = N/A")
    print(f"  Multifractal: {mf_null.is_multifractal}")
    
    print("\n" + "=" * 60)
    print("Sanity check complete.")
    print("=" * 60)
