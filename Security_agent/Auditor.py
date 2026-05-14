import os
import json
from dotenv import load_dotenv
from openai import OpenAI 
from src.utils import get_target_files, get_clean_code

class Auditor:
    def __init__(self, api_key=None, base_url="https://openrouter.ai/api/v1"):
        load_dotenv()
        self.api_key = api_key or os.getenv("API_KEY")
        self.client = OpenAI(base_url=base_url, api_key=self.api_key)
        self.MAX_CHARS_PER_BATCH = 30000 
        
        # Get the directory where THIS script is located
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Always look for AGENT.md relative to this script
        self.instructions_path = os.path.join(self.base_dir, "AGENT.md")
        self.instructions = ""
        
        if os.path.exists(self.instructions_path):
            with open(self.instructions_path, "r") as f:
                self.instructions = f.read()

    def run_audit(self, target_dir):
        if not self.instructions:
            return {"status": "error", "message": f"AGENT.md missing at {self.instructions_path}"}

        # Resolve the target directory to an absolute path
        abs_target = os.path.abspath(target_dir)
        files = get_target_files(abs_target)
        
        if not files:
            return {"status": "error", "message": f"No valid files found in {abs_target}"}
        
        batches = []
        current_batch = []
        current_size = 0

        for filepath in files:
            content = get_clean_code(filepath)
            file_data = {"file": filepath, "content": content}
            entry_size = len(json.dumps(file_data))

            if current_size + entry_size > self.MAX_CHARS_PER_BATCH and current_batch:
                batches.append(current_batch)
                current_batch = [file_data]
                current_size = entry_size
            else:
                current_batch.append(file_data)
                current_size += entry_size
        
        if current_batch:
            batches.append(current_batch)

        all_reports = []
        try:
            for i, batch in enumerate(batches):
                messages = [
                    {"role": "system", "content": self.instructions},
                    {"role": "user", "content": f"Audit the following project code (Batch {i+1}/{len(batches)}):\n\n{json.dumps(batch)}"}
                ]
                
                response = self.client.chat.completions.create(
                    model="openai/gpt-4o-mini", 
                    messages=messages,
                    max_tokens=2500,
                    temperature=0.1
                )
                all_reports.append(response.choices[0].message.content)

            return {
                "status": "success",
                "files_analyzed": len(files),
                "batches_processed": len(batches),
                "report": "\n\n---\n\n".join(all_reports)
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}
