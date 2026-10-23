```bash
grafr run code_pipeline.graph.yaml --adapter ollama
grafc compile code_pipeline.graph.yaml --target rust --policy policies/safety.cedar
```