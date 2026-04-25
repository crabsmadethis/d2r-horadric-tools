# Glama-compatible MCP server image.
#
# The server starts and lists its 23 tools without requiring extracted D2R
# game data (lookups/chargen/save/mod tools return a typed "data not
# extracted" envelope at call time). This is what Glama's check needs.
#
# To actually USE the lookup/save/mod tools with real content, mount a D2R
# install and run `d2r-mod extract` inside the container, or mount the
# pre-generated data directory into /app/d2r_chargen/data.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY d2r_chargen ./d2r_chargen
COPY d2r_mod ./d2r_mod
COPY d2r_mcp ./d2r_mcp

RUN pip install --no-cache-dir -e .

CMD ["python3", "-m", "d2r_mcp"]
