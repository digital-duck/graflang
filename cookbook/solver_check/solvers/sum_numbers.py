"""A black-box solver for the solver_check example: reads {"numbers": "1,2,3", ...} on stdin, prints a line of text."""
import json
import sys

inputs = json.load(sys.stdin)
numbers = [int(x) for x in inputs["numbers"].split(",") if x.strip()]
print(f"summed {len(numbers)} numbers")
print(f"total: {sum(numbers)}")
