The research section was empty, so this answer draws on my general knowledge of the two architectures rather than on any gathered sources. Check specific figures against the papers (Vaswani et al. 2017 for Transformers, Gu & Dao 2023 for Mamba, and Mamba-2 from 2024).

## Core mechanism

**Transformer:** Self-attention lets every token directly compare itself with every earlier token (causal masking in LLMs). The model keeps all past keys and values in a KV cache and re-reads them at each step. Context is stored losslessly, and lookup is content-based.

**Mamba:** Mamba is a selective state space model (SSM). It compresses the whole history into a fixed-size hidden state that is updated recurrently at each token. The "selective" part is that the state-transition parameters (Δ, B, C) depend on the current input. The model can therefore choose what to write into the state and what to forget, which earlier SSMs such as S4 could not do because their dynamics were input-independent.

## Key differences

| Aspect | Transformer | Mamba |
|---|---|---|
| Training compute | O(n²) in sequence length (O(n) with approximations) | O(n) |
| Inference per token | O(n): attends over the growing KV cache | O(1): updates a fixed-size state |
| Inference memory | KV cache grows linearly with context | Constant-size state |
| Training parallelism | Fully parallel across positions | Parallel via a hardware-aware scan, not plain recurrence |
| Memory of context | Exact, lossless recall of any past token | Lossy compression into a fixed state |
| Long-context scaling | Costly; needs tricks (sparse or sliding-window attention, RoPE extensions) | Efficient by construction |
| Throughput at long context | Drops as context grows | Often several times higher for long sequences |
| Maturity | Very mature ecosystem, kernels, tooling, and scaling-law evidence | Newer, with less tooling and less evidence at frontier scale |

## Strengths and weaknesses

**Transformers**
- Strong at in-context learning, precise retrieval, copying, and multi-hop lookup over the prompt.
- Heavily optimized (FlashAttention, tensor and pipeline parallelism, quantization, serving stacks like paged attention).
- Weak spot: memory and latency at very long contexts.

**Mamba**
- Efficient for very long sequences (genomics, audio, long documents) and for low-latency, memory-constrained inference.
- Competitive with similarly sized Transformers on standard language-modeling perplexity and many benchmarks in the original paper's experiments.
- Weak spot: tasks that need exact recall from context (needle-in-a-haystack, copying, some in-context learning), because the fixed state is a bottleneck. Studies have reported a gap on these tasks.

## Architectural details

- **Transformer block:** multi-head attention, then an MLP, with residual connections, layer norm, and positional encodings (RoPE and similar).
- **Mamba block:** an input projection, a short causal convolution, the selective SSM, and a gated output. There is no attention and no separate MLP, and positional encoding is not needed because order is carried by the recurrence.
- **Mamba-2:** reframes SSMs and attention as related through "structured state space duality," allowing faster training with matrix-multiply-friendly kernels and larger state sizes.

## Hybrids

The tradeoffs have pushed much work toward hybrids that interleave a few attention layers with many Mamba or SSM layers (for example Jamba from AI21, and various Nemotron-H-style and Zamba-style models). The idea is to keep attention's exact-recall ability while getting most of the SSM's memory and throughput savings. Hybrids are the most common way Mamba-style layers appear in production-scale models.

## Bottom line

Transformers trade compute and memory for exact, flexible access to all past context. Mamba trades some of that precision for linear-time training and constant-memory inference. For general-purpose LLMs, pure Transformers remain the default, and Mamba is most compelling for long-context or efficiency-critical workloads, increasingly in hybrid designs.

If you can share the research material that was meant to accompany this question, I can revise the answer to match it and cite specific results.