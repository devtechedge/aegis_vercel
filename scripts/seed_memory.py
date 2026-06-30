#!/usr/bin/env python
from packages.memory.store import distill_memory
r = distill_memory("seed incident-342", {"confidence": 0.84})
print(r)
