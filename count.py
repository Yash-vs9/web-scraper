import ast

# read your file (replace 'webcrawler.py' with your actual file name)
filename = "webScraper.py"

with open(filename, "r", encoding="utf-8") as f:
    code = f.read()

# parse the code into an AST
tree = ast.parse(code)

# store variable names
vars_set = set()

# walk through all nodes
for node in ast.walk(tree):
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
        vars_set.add(node.id)

print("📦 Variables found:", sorted(vars_set))
print("🔢 Total variables:", len(vars_set))