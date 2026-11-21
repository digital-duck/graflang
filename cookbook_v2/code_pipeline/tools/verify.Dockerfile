# The image the verify step runs the generated project in (no network, read-only root, 1 GB, see build/build.graph.yaml). Build it once:
#   docker build -t graflang-verify:py3.12 -f cookbook_v2/code_pipeline/tools/verify.Dockerfile cookbook_v2/code_pipeline/tools
# The container has no network at run time, so every library a generated project may import must be in here. Add yours and rebuild.
FROM python:3.12-slim
RUN pip install --no-cache-dir pytest click streamlit networkx pyyaml jinja2 markdown requests rich flask fastapi httpx pydantic numpy pandas
