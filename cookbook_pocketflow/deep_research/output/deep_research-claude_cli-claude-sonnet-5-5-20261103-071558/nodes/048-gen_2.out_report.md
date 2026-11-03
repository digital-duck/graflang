# Recent Advances in Quantum Error Correction

**Source caveat:** This report rests on background recall, not retrieved sources. Every web search failed (`ddgs` not installed), so none of the figures below has been checked against Nature or arXiv. Confidence is highest for Google's Willow result, lower for other platforms, and lowest for anything from 2025-2026. Verify before citing.

## Key Findings

### 1. Below-threshold error correction has been demonstrated
Google Quantum AI's Willow chip (105 superconducting qubits; Nature 2025) ran surface-code memories at distances 3, 5 and 7. This is the most reliable result in the notes.
- Logical error fell by a factor Λ ≈ 2.14 per distance step of 2, so adding qubits reduced errors.
- At d=7 the logical error was about 0.143% per cycle, with a cycle time of about 1.1 µs.
- The logical memory outlived its best physical qubit by about 2.4×.
- Real-time decoding at d=5 had latency of about 63 µs.

USTC (Zuchongzhi 3.x) reportedly reached d=7 with Λ ≈ 1.4. That is below threshold but with weaker suppression. Venue, date and per-cycle error are unconfirmed.

### 2. Every major platform is pursuing fault tolerance, with different trade-offs

| Platform | Strengths | Recent claims (unverified) | Main challenges |
|---|---|---|---|
| Superconducting | Fast cycles (~µs) | Willow below threshold; IBM qLDPC roadmap; AWS Ocelot and Alice & Bob cat qubits | Wiring, leakage, qLDPC connectivity |
| Neutral atoms | Reconfigurable, non-local connectivity, suits qLDPC | 48 logical qubits (2023, error detection); 2025 below-threshold and continuous-operation work, no reliable numbers | Atom loss, mid-circuit readout |
| Trapped ions | Highest fidelities, all-to-all connectivity | 12 logical qubits with Microsoft (2024, ~800× lower logical error in one test); Helios (~98 qubits, late 2025) with dozens of logical qubits, counts and codes unsure | Slow gates, scaling |
| Spin qubits | n/a | No reliable specifics | n/a |

**Comparability caveat:** Λ and per-cycle logical error are only comparable across platforms when the code, decoder and detection-versus-correction setting match. Cycle times also differ by orders of magnitude (µs for superconducting, ms or more for ions and atoms).

### 3. Decoding is now a first-class bottleneck
- **Classical decoders:** MWPM (PyMatching), union-find, and BP+OSD for qLDPC codes. IBM's gross codes use BP-OSD and later Relay-BP.
- **Neural decoders:** AlphaQubit (DeepMind, Nature, Nov 2024), a recurrent transformer pretrained on simulation and fine-tuned on Sycamore data, beat tensor-network and matching decoders at d=3 and 5. It was too slow for real time, and speed is the main open problem for neural decoders.
- **Hardware decoders:** FPGA and ASIC union-find and clustering decoders (Riverlane Deltaflow, Helios). Real-time operation needs roughly µs latency per round to avoid backlog. No trustworthy latency figures are available from memory.
- **Architectural tricks:** sliding or parallel windows, and predecoders that send only hard cases to a global decoder.

### 4. Logical operations and overhead are being reduced
- **Magic state distillation** supplies the non-Clifford gates that transversal operations cannot.
- **Magic state cultivation** (Gidney, Shutty, Jones, 2024) is a lower-overhead alternative. No experimental demonstration is known.
- **Lattice surgery** gives logical CNOT and Pauli-product measurements with nearest-neighbor interactions. No reliable recent specifics.

### 5. Algorithmic resource estimates have fallen sharply
Gidney (2025) estimated RSA-2048 factoring with under 1 million noisy qubits and about a week of runtime. The 2019 Gidney-Ekerå estimate was about 20 million qubits and 8 hours. The savings come from approximate residue arithmetic, yoked surface codes and magic state cultivation. The runtime moved from hours to days, but the qubit count fell roughly 20×.

### 6. qLDPC codes are the main route to lower overhead
IBM's roadmap (June 2025) runs Loon (2025), Kookaburra (2026), Cockatoo (2027), then Starling (~2029) with about 200 logical qubits and 100M gates. It builds on bivariate bicycle codes such as [[144,12,12]]. Only component demonstrations are known (decoding, syndrome processing), not a full below-threshold qLDPC memory. Neutral atoms and ions, with flexible connectivity, are natural fits.

## Insights

- **The field has moved from "does QEC work?" to "can it scale?"** The Willow result shows exponential suppression with distance. The open questions are decoder speed, leakage, wiring and logical gate overhead.
- **Surface codes versus qLDPC** is the central trade-off: surface codes need only local connectivity but have high overhead, while qLDPC codes promise much lower overhead but need long-range connectivity that favors atoms, ions and modular superconducting designs.
- **Overhead reductions are coming from software and architecture** (cultivation, yoked codes, better arithmetic), not only from better hardware. This shortens fault-tolerant timelines without improving physical qubits.
- **Real-time decoding is a systems problem** with classical hardware (FPGA/ASIC) that must keep pace with the qubits.

## Gaps and Items to Verify

1. Willow figures (Λ, 0.143%, 2.4×, 63 µs).
2. USTC Zuchongzhi 3.2 results and venue.
3. Whether IBM has shown a qLDPC memory, and the current roadmap dates.
4. Neutral-atom logical error rates and the 2025 architecture work.
5. Helios logical-qubit counts and codes.
6. Gidney 2025 RSA-2048 numbers.
7. Spin-qubit progress, lattice-surgery demonstrations, and anything from 2026 (nothing reliable was recalled, though today is 2026-11-03).

## Conclusion

Quantum error correction has crossed a key milestone: logical error rates that fall as codes grow, shown on superconducting hardware, with other platforms advancing in logical-qubit count and fidelity. Remaining obstacles are engineering: real-time decoding, efficient logical gates and non-Clifford resources, and scaling to the thousands of logical qubits that useful algorithms need. Falling resource estimates (RSA-2048 under a million qubits) make that target look nearer. Treat the numbers here as leads to verify, since no source was retrieved. Installing `ddgs` in the `graf` environment and rerunning the searches, or pasting in primary sources, would let me turn this into a citable report.