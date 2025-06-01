import os
import subprocess
import tempfile
import json
import re
from BaseAgent import BaseAgent

class RepositoryAgent(BaseAgent):
    role = "Repository Analysis Agent"
    basic_prompt_template = """
    You are an expert in analyzing Git repositories for Virtual Labs.
    
    You need to analyze the provided repository structure and identify if it's a valid Virtual Labs repository.
    
    Repository URL: {repo_url}
    Repository structure: 
    {repo_structure}
    
    Determine if this is a valid Virtual Labs repository by checking if it follows the expected structure.
    Extract the experiment name and provide a brief overview of what this experiment is about.
    
    Return your analysis in JSON format with the following fields:
    - is_valid_vlab (boolean): Whether this repository follows Virtual Labs structure
    - experiment_name (string): The name of the experiment
    - experiment_overview (string): Brief description of what this experiment is about
    - missing_components (array): List of important components that are missing
    - structure_compliance_score (number): Score from 0-10 on how well it follows the structure
    """
    
    def __init__(self, repo_url=None, repo_path=None):
        self.repo_url = repo_url
        self.repo_path = repo_path
        super().__init__(
            self.role, 
            basic_prompt=self.basic_prompt_template, 
            context=None
        )
    
    def clone_repository(self):
        """Clone the repository to a temporary directory"""
        if not self.repo_url:
            return False, "Repository URL not provided"
            
        self.repo_path = tempfile.mkdtemp()
        
        try:
            subprocess.check_call(['git', 'clone', self.repo_url, self.repo_path], 
                                 stderr=subprocess.STDOUT)
            return True, self.repo_path
        except subprocess.CalledProcessError as e:
            return False, f"Failed to clone repository: {str(e)}"
    
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
                    result += f"📁 {entry}/\n"
                    result += self._get_repo_structure(entry_path, level + 1, max_depth)
                else:
                    result += f"📄 {entry}\n"
            
            return result
        except Exception as e:
            return f"Error accessing {path}: {str(e)}"
    
    def _extract_experiment_name(self):
        """Extract experiment name from repository"""
        # Try to get from experiment-name.md
        name_file = os.path.join(self.repo_path, "experiment", "experiment-name.md")
        if os.path.exists(name_file):
            try:
                with open(name_file, 'r', encoding='utf-8') as file:
                    content = file.read().strip()
                    # Extract name from content
                    match = re.search(r'^#\s*(.*?)$', content, re.MULTILINE)
                    if match:
                        return match.group(1).strip()
                    return content
            except:
                pass
                
        # Try to infer from README.md
        readme_file = os.path.join(self.repo_path, "README.md")
        if os.path.exists(readme_file):
            try:
                with open(readme_file, 'r', encoding='utf-8') as file:
                    content = file.read()
                    # Look for heading that might be the experiment name
                    match = re.search(r'^#\s*(.*?)$', content, re.MULTILINE)
                    if match:
                        return match.group(1).strip()
            except:
                pass
                
        # Use repo name as fallback
        return os.path.basename(self.repo_path)
    
    def _get_experiment_overview(self):
        """Extract experiment overview from aim.md or README.md"""
        # Try aim.md first
        aim_file = os.path.join(self.repo_path, "experiment", "aim.md")
        if os.path.exists(aim_file):
            try:
                with open(aim_file, 'r', encoding='utf-8') as file:
                    content = file.read().strip()
                    # Remove headings
                    content = re.sub(r'^#.*$', '', content, flags=re.MULTILINE)
                    return content.strip()[:500]  # First 500 chars
            except:
                pass
                
        # Try README.md as fallback
        readme_file = os.path.join(self.repo_path, "README.md")
        if os.path.exists(readme_file):
            try:
                with open(readme_file, 'r', encoding='utf-8') as file:
                    content = file.read()
                    # Get first paragraph after first heading
                    paragraphs = content.split('\n\n')
                    if len(paragraphs) > 1:
                        return paragraphs[1].strip()[:500]  # First paragraph
            except:
                pass
                
        return "No overview available"
    
    def _check_structure_compliance(self):
        """Check compliance with expected structure"""
        expected_files = [
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
        ]
        
        expected_dirs = [
            "experiment",
            "experiment/images",
            "experiment/simulation",
            "experiment/simulation/css",
            "experiment/simulation/js",
            "pedagogy",
            "storyboard"
        ]
        
        missing_components = []
        
        for file_path in expected_files:
            full_path = os.path.join(self.repo_path, file_path)
            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                missing_components.append(file_path)
        
        for dir_path in expected_dirs:
            full_path = os.path.join(self.repo_path, dir_path)
            if not os.path.exists(full_path) or not os.path.isdir(full_path):
                missing_components.append(dir_path + "/")
        
        # Calculate compliance score
        total_components = len(expected_files) + len(expected_dirs)
        present_components = total_components - len(missing_components)
        compliance_score = min(10, (present_components / total_components) * 10)
        
        return missing_components, compliance_score
    
    def get_output(self):
        if not self.repo_path and self.repo_url:
            success, result = self.clone_repository()
            if not success:
                return {
                    "is_valid_vlab": False,
                    "experiment_name": "Unknown",
                    "experiment_overview": "Could not analyze repository",
                    "missing_components": ["Unable to access repository"],
                    "structure_compliance_score": 0,
                    "error": result
                }
        
        repo_structure = self._get_repo_structure(self.repo_path)
        
        # Extract key information
        experiment_name = self._extract_experiment_name()
        experiment_overview = self._get_experiment_overview()
        missing_components, compliance_score = self._check_structure_compliance()
        
        # Determine if it's a valid vLab
        is_valid = compliance_score >= 6.0  # At least 60% compliant
        
        # Create context with repository structure
        context = f"Repository Structure:\n{repo_structure}"
        self.context = context
        
        # Use LLM for additional insights if we have a valid repo structure
        if is_valid:
            try:
                response = super().get_output()
                
                # Try to extract JSON from response
                json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
                if json_match:
                    llm_analysis = json.loads(json_match.group(1))
                    
                    # Merge with our analysis
                    if 'experiment_name' in llm_analysis and llm_analysis['experiment_name'] != "Unknown":
                        experiment_name = llm_analysis['experiment_name']
                    
                    if 'experiment_overview' in llm_analysis and len(llm_analysis['experiment_overview']) > 20:
                        experiment_overview = llm_analysis['experiment_overview']
                        
                    # Add LLM's missing components
                    if 'missing_components' in llm_analysis and llm_analysis['missing_components']:
                        for component in llm_analysis['missing_components']:
                            if component not in missing_components:
                                missing_components.append(component)
            except:
                # If LLM analysis fails, continue with our analysis
                pass
        
        return {
            "is_valid_vlab": is_valid,
            "experiment_name": experiment_name,
            "experiment_overview": experiment_overview,
            "missing_components": missing_components,
            "structure_compliance_score": compliance_score,
            "repo_structure": repo_structure,
            "repo_path": self.repo_path
        }