# Ground truth papers for fractal network dimension validation

**Six papers span the field from foundational box-covering to cutting-edge scaling theory, collectively providing exact analytical formulas, deterministic model benchmarks, and real-network reference values sufficient to build a rigorous test suite for navi-fractal.** The (u,v)-flower family of deterministic networks emerges as the single most important ground truth structure: its box-counting dimension **d_B = ln(u+v)/ln(u)** is analytically exact, and its multifractal τ(q) spectrum is known in closed form. Combined with classical lattice dimensions (Sierpiński gasket D = ln 3/ln 2 ≈ 1.585, 2D lattice D = 2) and empirical benchmarks from recent scaling-theory work, these papers enable test assertions covering every major feature of the library—sandbox dimension, D(q) curves, R² quality gates, and regression methodology. One important correction: the sandbox multifractal paper (Liu et al. 2015) was published in *Chaos* (AIP), not *Scientific Reports*; the weighted sandbox extension (Song et al. 2015) is the *Scientific Reports* paper.

---

## Paper 1: Self-similarity of complex networks — the paper that launched the field

**Song, C., Havlin, S. & Makse, H. A.** "Self-similarity of complex networks." *Nature* **433**(7024), 392–395 (2005). **DOI: 10.1038/nature03248**

This paper demonstrated for the first time that real-world complex networks can exhibit fractal self-similarity under a box-covering renormalization: N_B(l_B) ~ l_B^{−d_B}. It established the conceptual and methodological foundation that every subsequent fractal network paper builds upon.

**Concrete numerical ground truths:**

| Network | d_B | Notes |
|---------|-----|-------|
| WWW (nd.edu domain, ~325K pages) | **4.1** | Fractal |
| Metabolic network (*E. coli*) | **3.4** | Fractal |
| Protein interaction network (*H. sapiens*) | **2.0** | Fractal |
| Protein interaction network (*S. cerevisiae*) | **1.8** | Fractal |
| Internet (router-level) | ∞ (non-fractal) | Exponential scaling |
| Barabási–Albert model | ∞ (non-fractal) | Exponential scaling |

**Validation relevance:** These values serve as coarse real-network sanity checks. A sandbox dimension estimate on the WWW graph should land in the range **d_B ≈ 4–5** (exact value depends on dataset vintage and algorithm). More critically, the paper establishes the **fractal vs. non-fractal dichotomy**: BA model networks must yield poor R² in log-log scaling fits, providing a natural test case for navi-fractal's quality gates. If the library's R² threshold correctly rejects non-fractal networks while accepting fractal ones, it passes this validation. The paper also establishes credibility—any fractal network library that does not cite Song et al. 2005 will raise eyebrows.

---

## Paper 2: The (u,v)-flower models with exact analytical dimensions

**Rozenfeld, H. D., Havlin, S. & ben-Avraham, D.** "Fractal and transfractal recursive scale-free nets." *New Journal of Physics* **9**, 175 (2007). **DOI: 10.1088/1367-2630/9/6/175** | arXiv: cond-mat/0612330

This paper is the **single most important reference for deterministic ground truth**. It introduces the (u,v)-flower family of recursive scale-free networks with analytically exact fractal dimensions derived from the construction rule: each edge is replaced at every generation by two parallel paths of lengths u and v (with u ≤ v).

**Exact analytical formulas (u ≤ v, u ≥ 2 for the fractal case):**

The box-counting dimension is **d_B = ln(u+v) / ln(u)**. This follows because the total number of edges (and approximately nodes) grows as (u+v)^n per generation while the network diameter grows as u^n—the shortest path between hubs traverses the shorter parallel path. The degree distribution exponent is **γ = 1 + ln(u+v) / ln(2)**, since hub degree doubles each generation while node count multiplies by (u+v).

**Specific computable ground truth values:**

| (u, v) | d_B = ln(u+v)/ln(u) | Numerical d_B | γ | Regime |
|---------|---------------------|---------------|---|--------|
| (2, 2) | ln 4 / ln 2 | **2.000** | 3.000 | Fractal |
| (2, 3) | ln 5 / ln 2 | **2.322** | 3.322 | Fractal |
| (2, 4) | ln 6 / ln 2 | **2.585** | 3.585 | Fractal |
| (3, 3) | ln 6 / ln 3 | **1.631** | 3.585 | Fractal |
| (3, 5) | ln 8 / ln 3 | **1.893** | 4.000 | Fractal |
| (4, 4) | ln 8 / ln 4 | **1.500** | 4.000 | Fractal |
| (1, v) | ∞ | ∞ | varies | Transfractal (small-world) |

The (1,2)-flower is equivalent to the Dorogovtsev–Goltsev–Mendes pseudofractal scale-free web, and has infinite box-counting dimension—another useful quality-gate test case where R² should be low.

**Validation relevance:** These are the gold-standard test assertions. For a (2,2)-flower at generation 8 (43,692 nodes), the sandbox dimension estimate should converge to **2.0 ± tolerance**. The tolerance itself is informative: Łepek et al. 2025 report d_B = 1.98 for this network using FNB, and Fronczak et al. 2024 report d_B = 2.0 using greedy coloring—so a sandbox estimate within ±0.1 is reasonable. The (u,v)-flower is also constructible purely algorithmically (no external data needed), making it ideal for automated CI/CD test suites. One additional key fact: Furuya & Yakubo (*Phys. Rev. E* **84**, 036118, 2011) derived the **analytical τ(q) formula** for (u,v)-flowers, showing they are multifractal (specifically bifractal) with nonlinear τ(q). This means the (2,2)-flower simultaneously tests sandbox dimension (d_B = 2.0) and multifractal spectrum (D(q) varies with q, τ(q) is nonlinear). For a true monofractal structure, τ(q) = (q−1)·d_B is strictly linear and D(q) is constant.

---

## Paper 3: The sandbox algorithm for multifractal network dimensions

**Liu, J.-L., Yu, Z.-G. & Anh, V.** "Determination of multifractal dimensions of complex networks by means of the sandbox algorithm." *Chaos* **25**(2), 023103 (2015). **DOI: 10.1063/1.4907557** | arXiv: 1408.4244

This is the **methodological anchor paper** for navi-fractal's sandbox implementation. Liu et al. adapted the sandbox algorithm (originally proposed by Tél, Fülöp & Vicsek, *Physica A* **159**, 155–166, 1989, for geometric fractals) to complex networks. The algorithm works as follows: for each center node i, count the mass M_i(r) within BFS radius r, then compute ⟨M_i(r)^{q−1}⟩ averaged over all centers. The generalized fractal dimension D(q) is extracted from **OLS regression of ln⟨M_i(r)^{q−1}⟩ versus (q−1)·ln(r)** across the scaling regime. The mass exponent τ(q) = (q−1)·D(q).

**Concrete numerical ground truths and benchmarks:**

The paper validates the sandbox method by computing τ(q) for (u,v)-flower networks across q = −10 to +10 (step 1) and comparing against analytical τ(q) values from Furuya & Yakubo 2011. The sandbox algorithm was found to be **"the most effective and feasible algorithm"** for computing τ(q), outperforming both the compact-box-burning (CBB) algorithm and the improved box-counting (BC) algorithm in matching theoretical values. Specific findings include that **scale-free networks exhibit genuine multifractality** (nonlinear τ(q)), **small-world networks show weak or ambiguous multifractality**, and **Erdős–Rényi random networks show essentially no multifractality** (τ(q) approximately linear). These three behavioral classes directly translate to test assertions for D(q) curve shape.

**Validation relevance:** This paper defines the algorithm that navi-fractal implements, making it the primary methodological reference. The q-range of −10 to +10, the center-node averaging procedure, and the log-log linear regression approach described here should be replicated exactly. The paper's finding that sandbox outperforms box-burning and box-counting for τ(q) accuracy also justifies the library's algorithmic choice. For test assertions: on a (u,v)-flower, the computed τ(q) curve should be nonlinear and match the Furuya–Yakubo analytical formula within tolerance; on an ER random graph of comparable size, D(q) should be approximately constant (monofractal or trivially non-fractal behavior), and R² values in the scaling regime should be lower.

---

## Paper 4: Weighted sandbox with open-access numerical benchmarks

**Song, Y.-Q., Liu, J.-L., Yu, Z.-G. & Li, B.-G.** "Multifractal analysis of weighted networks by a modified sandbox algorithm." *Scientific Reports* **5**, 17628 (2015). **DOI: 10.1038/srep17628** | PMC: PMC4669438 (open access)

This paper extends the sandbox method to weighted networks (SBw algorithm), where BFS radius is measured in weighted shortest-path distance rather than hop count. Because it is **open access**, it provides the most directly accessible numerical benchmarks in this literature.

**Concrete numerical ground truths (from Tables/Figures in the paper):**

| Weighted fractal network | Parameters | Theoretical d_f | Numerical d_f (SBw) | Std. dev. |
|--------------------------|-----------|-----------------|---------------------|-----------|
| Sierpiński WFN, generation 8 | s=3, f=1/2 | ln 3/ln 2 ≈ **1.5850** | **1.5419** | ±0.0309 |
| Sierpiński WFN, generation 8 | s=3, f=1/3 | ln 3/ln 3 = **1.0000** | **1.0169** | ±0.0148 |
| Cantor dust WFN, generation 5 | s=4, f=1/5 | ln 4/ln 5 ≈ **0.8614** | Close to theoretical | See Fig. 4 |

The general formula for Sierpiński weighted fractal networks is **d_f = −log(s)/log(f)**, where s is the branching factor and f is the weight scaling factor. All D(q) curves are nonlinear, confirming multifractality that depends on edge weights. The paper also applies SBw to real collaboration networks (astrophysics: 16,706 nodes; computational geometry: 7,343 nodes; high-energy theory), all showing multifractal behavior with q ranging from −3 to +3.

**Validation relevance:** If navi-fractal supports weighted networks, this paper provides direct test assertions: a Sierpiński WFN with s=3, f=1/2 at generation 8 should yield sandbox dimension **≈1.54 ± 0.05** against theoretical 1.585. The gap between numerical (1.5419) and theoretical (1.5850) is itself informative—it quantifies the expected finite-size bias at generation 8, meaning test assertions should allow ~3% tolerance. The standard deviations reported (computed from averaging over center nodes) also provide a reference for what bootstrap confidence interval widths should look like. The open-access status means reviewers can independently verify every number.

---

## Paper 5: Scaling theory unifying seven interlocking exponents

**Fronczak, A., Fronczak, P., Samsel, M. J., Makulski, K., Łepek, M. & Mrowiński, M. J.** "Scaling theory of fractal complex networks." *Scientific Reports* **14**, 9079 (2024). **DOI: 10.1038/s41598-024-59765-2** (open access)

This 2024 paper establishes a unified scaling theory for fractal networks involving **seven scaling exponents** (d_B, γ, δ, α, β, d_k, d_m) constrained by **four analytical scaling relations**, leaving only three independent exponents. This creates a rich internal-consistency framework: any library computing these exponents can cross-check them against each other.

**Concrete numerical ground truths (Table 1 in the paper):**

| Network | N | d_B | γ | δ | α (measured) | α (theory) | β (measured) | β (theory) |
|---------|---|-----|---|---|-------------|------------|-------------|------------|
| (2,2)-flower, gen 8 | 43,692 | **2.0** | 3.0 | 3.0 | 0.99 | 1.0 | ~1.0 | 1.0 |
| SHM model (s=2, a=3, n=5) | 78,126 | **1.46** | 3.32 | 3.32 | 0.82 | 0.83 | ~1.0 | 1.0 |
| WWW | 325,728 | **4.8** | 2.4 | 2.2 | 0.68 | 0.63 | 1.22 | 1.22 |
| DBLP coauthorship | 2,523 | **2.0** | 3.2 | 3.4 | 1.23 | 1.17 | 0.86 | 0.92 |
| Brain functional network | 2,920 | **2.2** | 2.8 | 2.3 | 0.57 | 0.51 | 1.39 | 1.38 |

**Analytical formulas for deterministic models:** The SHM (Song–Havlin–Makse) model with parameters (s, a, n=2s+1) has d_B = ln(n)/ln(a). For s=2, a=3: d_B = ln 5/ln 3 ≈ **1.465**. The key scaling relations are **d_B = α + β·d_k** and **β = (γ−1)/(δ−1)**, where d_k = d_B/(γ−1) is the degree dimension and d_m = d_B/(δ−1) is the mass dimension.

**Validation relevance:** This paper enables a powerful class of **cross-consistency tests**. After computing d_B via sandbox, γ from degree distribution, and δ from mass distribution, the library can verify that the four scaling relations hold within tolerance. For the (2,2)-flower, all seven exponents are analytically known (d_B = 2.0, γ = 3.0, δ = 3.0, α = 1.0, β = 1.0), providing a complete cross-validation. The measured-vs-theoretical α and β columns show typical deviations of 5–10% on real networks, calibrating what tolerance to use in assertions.

---

## Paper 6: The FNB algorithm with the most comprehensive recent benchmarks

**Łepek, M., Makulski, K., Fronczak, A. & Fronczak, P.** "Beyond traditional box-covering: Determining the fractal dimension of complex networks using a fixed number of boxes of flexible diameter." *Chaos, Solitons & Fractals* **199**(P3), 116908 (2025). **DOI: 10.1016/j.chaos.2025.116908** | arXiv: 2501.16030

This January 2025 paper introduces the FNB (Fixed-Number-of-Boxes) algorithm, which selects hub nodes as box seeds and assigns all other nodes via BFS to their nearest hub (creating graph Voronoi cells). It provides the most extensive recent benchmark table covering both deterministic models and real networks, and it achieves O(N^{1.1}) to O(N^{1.4}) complexity versus O(N²) for greedy coloring.

**Concrete numerical ground truths (Table 1 in the paper):**

| Network | N | d_B (FNB) | d_B (Greedy Coloring) | d_B (exact/expected) |
|---------|---|-----------|----------------------|---------------------|
| (2,2)-flower, gen 8 | 43,692 | **1.98** | 2.0 | **2.0 (exact)** |
| SHM model (m=2, p=1, iter 7) | 78,126 | **1.44** | 1.46 | **≈1.46 (= ln 5/ln 3)** |
| Google web graph | 855,802 | **3.9** | 3.7 | — |
| Brain functional network | 3,626 | **2.6** | 2.2 | — |
| DBLP coauthorship | 2,523 | **2.1** | 2.0 | — |
| Protein interaction | 11,693 | **3.4** | Failed | — |
| AS-CAIDA (Internet) | 26,475 | **5.1** | Failed | — |
| AS-Rossi (Internet) | 40,164 | **6.0** | Failed | — |

A notable finding: FNB detects fractality in protein interaction and Internet AS-level networks where greedy coloring fails entirely, suggesting these networks have fractal structure that was previously missed.

**Validation relevance:** This paper provides the freshest cross-algorithm comparison. Sandbox dimension estimates from navi-fractal should fall within the range spanned by FNB and GC estimates for each network. The (2,2)-flower result of 1.98 (FNB) vs. 2.0 (GC) vs. 2.0 (exact) calibrates the expected algorithm-dependent variance at ~1%. For real networks where no exact value exists, the FNB/GC range defines the plausible interval. The paper's open arXiv preprint makes it accessible for verification.

---

## How these six papers map to navi-fractal's feature set

**Sandbox dimension estimation (BFS-based mass-radius scaling):** Papers 2, 3, and 4 provide the algorithm definition and deterministic ground truths. The (2,2)-flower at generation 8 with d_B = 2.0 is the primary assertion. The Sierpiński WFN with d_f ≈ 1.585 tests the weighted variant.

**Multifractal spectrum analysis (D(q) for range of q):** Paper 3 defines the sandbox approach for D(q). Papers 2 and 3 together establish that (u,v)-flowers are bifractal/multifractal with nonlinear τ(q). The analytical τ(q) formula from Furuya & Yakubo (*Phys. Rev. E* **84**, 036118, 2011)—used as ground truth by Liu et al.—provides exact D(q) curves. For monofractal structures (regular lattices, Sierpiński gasket treated as a graph), τ(q) = (q−1)·d_B is linear and D(q) is constant across all q.

**Quality gates (R² thresholds):** Paper 1 establishes the fractal/non-fractal dichotomy. BA model networks and ER random graphs should yield poor R² in log-log mass-radius fits, while (u,v)-flowers and real fractal networks should yield R² > 0.95. Paper 3 explicitly finds sandbox scaling quality degrades for random and small-world networks.

**Bootstrap confidence intervals:** Paper 4 reports standard deviations from center-node averaging (e.g., ±0.031 for Sierpiński WFN), providing a reference for expected CI widths. Bootstrap CIs should be comparable to or tighter than these center-node standard deviations.

**OLS/WLS regression for log-log fits:** Paper 3 uses OLS regression of ln⟨M^{q−1}⟩ vs. (q−1)·ln(r). The known analytical dimensions from Paper 2 allow testing whether WLS (which downweights noisy large-radius points) improves convergence to the true value compared to OLS.

---

## Supplementary references worth noting in the test suite

Three additional papers, while not among the primary six, deserve mention in test-suite documentation. **Furuya, S. & Yakubo, K.** "Multifractality of complex networks" (*Phys. Rev. E* **84**, 036118, 2011) provides the analytical τ(q) formula for (u,v)-flowers that serves as ground truth in Paper 3. **Song, C., Gallos, L. K., Havlin, S. & Makse, H. A.** "How to calculate the fractal dimension of a complex network: the box covering algorithm" (*J. Stat. Mech.* **2007**, P03006, DOI: 10.1088/1742-5468/2007/03/P03006) provides the algorithmic details of box-covering. **Ding, Y., Liu, J.-L., Li, X., Tian, Y.-C. & Yu, Z.-G.** "Computationally efficient sandbox algorithm for multifractal analysis of large-scale complex networks" (*Phys. Rev. E* **103**, 043303, 2021, DOI: 10.1103/PhysRevE.103.043303) extends the sandbox method to networks with tens of millions of nodes and validates that MFA accuracy improves with network size—relevant for scaling tests.

## Conclusion

The six-paper canon assembled here creates a **three-layer validation architecture**: exact analytical values from deterministic constructions (Papers 2, 5, 6), algorithmic methodology validation (Papers 3, 4), and real-network plausibility checks (Papers 1, 5, 6). The (u,v)-flower with d_B = ln(u+v)/ln(u) is the indispensable centerpiece—it is constructible without external data, has exact dimension, exhibits multifractality, and has been validated across every major algorithm in the field. Any test suite anchored in these references will immediately signal to the fractal network research community that navi-fractal takes scientific rigor seriously.