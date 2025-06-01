import os
import json
import re
from BaseAgent import BaseAgent

class StructureComplianceAgent(BaseAgent):
    role = "Structure Compliance Evaluator"
    basic_prompt_template = """
    You are an expert in evaluating Virtual Labs repository structure compliance.
    
    Expected structure for a Virtual Labs repository:
    ```
    root/
    ├── LICENSE
    ├── README.md
    ├── experiment/
    │ ├── aim.md
    │ ├── contributors.md
    │ ├── experiment-name.md
    │ ├── pretest.json
    │ ├── posttest.json
    │ ├── procedure.md
    │ ├── theory.md
    │ ├── references.md
    │ ├── README.md
    │ ├── images/
    │ ├── simulation/
    │   ├── index.html
    │   ├── css/
    │   ├── js/
    │   ├── images/
    ├── pedagogy/
    └── storyboard/
    ```
    
    Current repository structure:
    {repo_structure}
    
    Check if the repository follows the expected structure. List any missing required files or directories.
    
    Return your evaluation in JSON format with the following fields:
    - compliance_score (number): Score from 0-10 where 10 is perfect compliance
    - missing_files (array): List of required files that are missing
    - missing_directories (array): List of required directories that are missing
    - structure_status (string): "Compliant", "Partially Compliant", or "Non-Compliant"
    - recommendations (array): List of suggestions to improve structure compliance
    ```
    """
    
    def __init__(self, repo_path):
        self.repo_path = repo_path
        super().__init__(
            self.role, 
            basic_prompt=self.basic_prompt_template, 
            context=None
        )
        
    def _get_repo_structure(self, path, level=0, max_depth=4):
        """Generate a string representation of the repository structure"""
        if level > max_depth:
            return "..."
        
        result = ""
        try:
            entries = os.listdir(path)
            for entry in sorted(entries):
                if entry.startswith('.git') or entry == 'node_modules':
                    continue
                
                entry_path = os.path.join(path, entry)
                is_dir = os.path.isdir(entry_path)
                
                result += "  " * level
                if is_dir:
                    result += f"{entry}/\n"
                    result += self._get_repo_structure(entry_path, level + 1, max_depth)
                else:
                    result += f"{entry}\n"
            
            return result
        except Exception as e:
            return f"Error accessing {path}: {str(e)}"
    
    def _check_required_files(self):
        """Check if all required files and directories exist"""
        required_files = [
            "LICENSE",
            "README.md",
            "experiment/aim.md",
            "experiment/contributors.md",
            "experiment/experiment-name.md",
            "experiment/pretest.json",
            "experiment/posttest.json",
            "experiment/procedure.md",
            "experiment/theory.md",
            "experiment/references.md",
            "experiment/README.md",
            "experiment/simulation/index.html",
            "pedagogy/README.md",
            "storyboard/README.md"
        ]
        
        required_dirs = [
            "experiment",
            "experiment/images",
            "experiment/simulation",
            "experiment/simulation/css",
            "experiment/simulation/js",
            "pedagogy",
            "storyboard"
        ]
        
        missing_files = []
        missing_dirs = []
        
        for file_path in required_files:
            full_path = os.path.join(self.repo_path, file_path)
            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                missing_files.append(file_path)
        
        for dir_path in required_dirs:
            full_path = os.path.join(self.repo_path, dir_path)
            if not os.path.exists(full_path) or not os.path.isdir(full_path):
                missing_dirs.append(dir_path)
        
        return missing_files, missing_dirs
    
    def _check_json_validity(self):
        """Check if JSON files are valid"""
        json_files = ["experiment/pretest.json", "experiment/posttest.json"]
        invalid_json_files = []
        
        for file_path in json_files:
            full_path = os.path.join(self.repo_path, file_path)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        json.load(f)
                except:
                    invalid_json_files.append(file_path)
        
        return invalid_json_files
        
    def _extract_json_from_text(self, text):
        """Extract JSON from text that may contain other content"""
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except:
                pass
                
        # Try finding any JSON object in the text
        json_pattern = r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})'
        match = re.search(json_pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        
        return None
        
    def get_output(self):
        repo_structure = self._get_repo_structure(self.repo_path)
        missing_files, missing_dirs = self._check_required_files()
        invalid_json_files = self._check_json_validity()
        
        # Calculate compliance score based on missing files and directories
        total_required = 14 + 7  # Files + Dirs
        missing_count = len(missing_files) + len(missing_dirs) + len(invalid_json_files)
        compliance_score = max(0, min(10, 10 * (1 - (missing_count / total_required))))
        
        # Set context with repo structure
        self.context = f"Repository Structure:\n{repo_structure}"
        
        # Get AI evaluation using the parent class method
        prompt = self.basic_prompt_template.format(repo_structure=repo_structure)
        ai_evaluation = super().get_output()
        
        # Try to extract JSON from the AI evaluation
        json_data = self._extract_json_from_text(ai_evaluation)
        
        # Default recommendations
        recommendations = [
            f"Add missing file: {file}" for file in missing_files[:5]  # Limit to first 5
        ] + [
            f"Create missing directory: {directory}" for directory in missing_dirs[:3]  # Limit to first 3
        ] + [
            f"Fix invalid JSON in: {json_file}" for json_file in invalid_json_files
        ]
        
        # Determine structure status based on compliance score
        if compliance_score >= 8:
            structure_status = "Compliant"
        elif compliance_score >= 5:
            structure_status = "Partially Compliant"
        else:
            structure_status = "Non-Compliant"
        
        # If we got JSON data from the AI, use its recommendations
        if json_data and isinstance(json_data, dict) and "recommendations" in json_data:
            ai_recommendations = json_data.get("recommendations", [])
            if ai_recommendations and len(ai_recommendations) > 0:
                recommendations = ai_recommendations
        
        issues = []
        
        # Add file issues
        for file in missing_files:
            severity = "High" if "simulation" in file or file.endswith("md") else "Medium"
            if file.endswith("json"):
                severity = "Medium"
                
            issues.append({
                "type": "file",
                "item": file,
                "status": "Missing",
                "severity": severity
            })
        
        # Add directory issues
        for directory in missing_dirs:
            severity = "High" if "simulation" in directory else "Medium"
            issues.append({
                "type": "directory",
                "item": directory,
                "status": "Missing",
                "severity": severity
            })
        
        # Add invalid JSON issues
        for json_file in invalid_json_files:
            issues.append({
                "type": "file",
                "item": json_file,
                "status": "Invalid JSON",
                "severity": "Medium"
            })
        
        return {
            "compliance_score": compliance_score,
            "missing_files": missing_files,
            "missing_directories": missing_dirs,
            "invalid_json_files": invalid_json_files,
            "structure_status": structure_status,
            "recommendations": recommendations,
            "issues": issues
        }