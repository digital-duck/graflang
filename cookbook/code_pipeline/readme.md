```bash
graf run code_pipeline.graph.yaml --adapter ollama
graf compile code_pipeline.graph.yaml --target rust --policy policies/safety.cedar
```