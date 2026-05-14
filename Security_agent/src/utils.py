import os
import ast

def get_target_files(directory):
    target_files = []
    skip_dirs = {'.venv', 'node_modules', '__pycache__', '.git', 'venv', 'env'}
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for file in files:
            if file.endswith(('.py', '.yaml', '.json', '.env')):
                target_files.append(os.path.join(root, file))
    return target_files

def get_clean_code(filepath):
    """Reads a file, strips all comments and docstrings, and returns tight code."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()
        
        # Handle non-python files normally
        if not filepath.endswith('.py'):
            return source.strip()

        # Parse the Python code
        tree = ast.parse(source)
        
        # Remove docstrings
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                if (node.body and isinstance(node.body[0], ast.Expr) and 
                    isinstance(node.body[0].value, (ast.Str, ast.Constant))):
                    node.body.pop(0)

        # Convert back to code (strips comments automatically)
        clean_code = ast.unparse(tree)
        
        # Remove extra whitespace/empty lines
        return "\n".join([line for line in clean_code.splitlines() if line.strip()])
        
    except Exception as e:
        return f"Error cleaning {filepath}: {str(e)}"