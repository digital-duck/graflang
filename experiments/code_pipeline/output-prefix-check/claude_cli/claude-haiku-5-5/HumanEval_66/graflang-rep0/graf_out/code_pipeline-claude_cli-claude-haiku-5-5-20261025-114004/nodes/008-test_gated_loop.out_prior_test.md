[PASSED]

All six spec examples produce the expected values, including the empty string. The signature, the `int` return type, and the imports (none needed) match the spec. The `TypeError` for non-`str` input goes beyond the spec, but it is documented and does not conflict with it. Non-ASCII uppercase letters are ignored by design, and the docstring states this.