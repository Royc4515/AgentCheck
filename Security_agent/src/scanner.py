import ast
import re

class CodeScanner:
    def __init__(self):
        # Regex for specific known formats
        self.secret_patterns = {
            "OpenAI Key": r"sk-[a-zA-Z0-9]{32,}",
            "Google API Key": r"AIza[a-zA-Z0-9_-]{35}",
        }

    def scan_file(self, filepath):
        """Main entry point for scanning a single file."""
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()
            
            tree = ast.parse(code)
            
            # Combine findings into a single structure for the Auditor
            return {
                "file": filepath,
                "metadata": self._get_metadata(tree),
                "secrets": self._find_secrets(code, tree)
            }
        except Exception as e:
            return {"file": filepath, "error": str(e)}

    def _get_metadata(self, tree):
        """Extracts imports and identifies Sinks (Network, Shell, File Ops)."""
        meta = {
            "imports": [],
            "sinks": []
        }

        # Categories for the Auditor to watch
        danger_sinks = {
            'eval', 'exec', 'system', 'subprocess',  # Shell
            'post', 'get', 'request', 'send', 'connect', # Network
            'open', 'write' # File
        }

        for node in ast.walk(tree):
            # 1. Capture Imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    meta["imports"].append(alias.name)

            # 2. Capture Function Calls (Sinks)
            if isinstance(node, ast.Call):
                name = ""
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                
                if name in danger_sinks:
                    meta["sinks"].append(name)

        return meta

    def _find_secrets(self, code, tree):
        """Combines Regex and AST to find hardcoded credentials."""
        found = []

        # A. Regex Check (For sk-..., etc.)
        for label, pattern in self.secret_patterns.items():
            if re.findall(pattern, code):
                found.append(f"Confirmed {label}")

        # B. AST Check (For api_key="...", password="...")
        # This catches what Regex misses by looking at argument names
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    # Check if the parameter name looks like a secret
                    arg_name = kw.arg.lower() if kw.arg else ""
                    if any(s in arg_name for s in ['key', 'secret', 'token', 'pass']):
                        # Check if the value is a hardcoded string
                        if isinstance(kw.value, (ast.Constant, ast.Str)):
                            val = getattr(kw.value, 'value', getattr(kw.value, 's', ""))
                            if len(str(val)) > 8: # Ignore tiny strings
                                found.append(f"Hardcoded '{kw.arg}' value detected")

        return list(set(found)) # Remove duplicates