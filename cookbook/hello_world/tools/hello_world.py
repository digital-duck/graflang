import json
import re
import sys

# Deterministic programs for solver mode. Reads one JSON object on stdin ({"language": ..., "name": ...}),
# prints one line of JSON: {"program": "<source code>"}. Unknown language or bad name: message on stderr, exit 1.

TEMPLATES = {
    "python": 'print("Hello, {name}!")\n',
    "javascript": 'console.log("Hello, {name}!");\n',
    "ruby": 'puts "Hello, {name}!"\n',
    "go": 'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("Hello, {name}!")\n}\n',
    "rust": 'fn main() {\n    println!("Hello, {name}!");\n}\n',
    "c": '#include <stdio.h>\n\nint main(void) {\n    printf("Hello, {name}!\\n");\n    return 0;\n}\n',
    "java": 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello, {name}!");\n    }\n}\n',
}

ALIASES = {"js": "javascript", "node": "javascript", "golang": "go", "rs": "rust"}

# Letters, digits, spaces, dots, apostrophes, hyphens: safe inside a double-quoted string in every template.
NAME_OK = re.compile(r"^[\w .'-]{1,60}$")


def fail(message):
    sys.stderr.write(message + "\n")
    sys.exit(1)


def main():
    data = json.load(sys.stdin)
    language = str(data.get("language", "")).strip().lower()
    language = ALIASES.get(language, language)
    name = str(data.get("name", "")).strip()

    if not NAME_OK.match(name):
        fail("name must be 1-60 letters, digits, spaces, dots, apostrophes or hyphens")
    if language not in TEMPLATES:
        fail("unsupported language: " + language + "; solver mode supports: " + ", ".join(sorted(TEMPLATES)))

    print(json.dumps({"program": TEMPLATES[language].replace("{name}", name)}))


if __name__ == "__main__":
    main()
