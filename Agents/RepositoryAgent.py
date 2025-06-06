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

    def __init__(self, repo_path=None, repo_url=None):
        super().__init__(
            role="Repository Analysis Agent",
            basic_prompt=self.basic_prompt_template,
            context=""
        )
        self.repo_path = repo_path
        self.repo_url = repo_url  # Store the repo_url for name extraction
    
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
        
        # Priority 1: experiment-name.md (but only if it has real content, not template)
        name_file = os.path.join(self.repo_path, "experiment", "experiment-name.md")
        if os.path.exists(name_file):
            try:
                with open(name_file, 'r', encoding='utf-8') as file:
                    content = file.read().strip()
                    if content:
                        # Remove markdown heading syntax and clean up
                        experiment_name = re.sub(r'^#+\s*', '', content, flags=re.MULTILINE).strip()
                        # Remove any additional markdown formatting
                        experiment_name = re.sub(r'[*_`]', '', experiment_name).strip()
                        
                        # Check if this is template text (not real content)
                        if (experiment_name and len(experiment_name) > 3 and 
                            not re.search(r'experiment\s*name|enter.*name|add.*name|name.*here|template|placeholder|fill.*name', 
                                        experiment_name, re.IGNORECASE)):
                            return experiment_name
            except:
                pass
        
        # Priority 2: Clean repo name from URL or directory - IMPROVED LOGIC
        try:
            repo_name = None
            
            # First try to get from URL if available
            if hasattr(self, 'repo_url') and self.repo_url:
                # Extract from GitHub URL: https://github.com/virtual-labs/exp-transmissivity-aquifer-nitk
                parts = self.repo_url.rstrip('/').split('/')
                if len(parts) >= 2:
                    repo_name = parts[-1]  # Get the last part (repo name)
                    
                    # Remove .git extension if present
                    if repo_name.endswith('.git'):
                        repo_name = repo_name[:-4]
            
            # Fallback to directory name if URL not available
            if not repo_name:
                repo_name = os.path.basename(self.repo_path)
            
            if repo_name:
                # Clean the repo name for experiment name
                clean_name = repo_name
                
                # Remove common prefixes like 'exp-'
                clean_name = re.sub(r'^exp-', '', clean_name, flags=re.IGNORECASE)
                
                # Split by hyphens and remove the LAST word (institute name)
                parts = clean_name.split('-')
                if len(parts) > 1:
                    # Remove the last part (institute name like nitk, iiith, etc.)
                    clean_name = '-'.join(parts[:-1])
                
                # Replace remaining hyphens and underscores with spaces
                clean_name = clean_name.replace('-', ' ').replace('_', ' ')
                
                # Remove any remaining common prefixes/suffixes
                clean_name = re.sub(r'\b(virtual|lab|experiment|vlab|exp)\b', '', clean_name, flags=re.IGNORECASE)
                
                # Clean up extra spaces and capitalize each word
                clean_name = ' '.join(word.capitalize() for word in clean_name.split() if word.strip())
                
                if clean_name and len(clean_name) > 3:
                    return clean_name
                    
        except Exception as e:
            print(f"Error cleaning repo name: {str(e)}")
        
        # If all else fails, return a default name
        return "Virtual Lab Experiment"
    
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
        
        # Extract key information - use our reliable extraction method
        experiment_name = self._extract_experiment_name()
        experiment_overview = self._get_experiment_overview()
        missing_components, compliance_score = self._check_structure_compliance()
        
        # Determine if it's a valid vLab
        is_valid = compliance_score >= 6.0  # At least 60% compliant
        
        # Create context with repository structure for LLM analysis
        context = f"Repository Structure:\n{repo_structure}"
        self.context = context
        
        # Use LLM for additional insights about overview only (not experiment name)
        llm_analysis = None
        if is_valid:
            try:
                response = super().get_output()
                
                # Try to extract JSON from response
                json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
                if json_match:
                    llm_analysis = json.loads(json_match.group(1))
            except Exception as e:
                print(f"Error in LLM analysis: {str(e)}")
        
        # Don't override experiment name from LLM - trust our extraction logic
        # Only use LLM for better overview if available
        final_overview = experiment_overview
        if llm_analysis and 'experiment_overview' in llm_analysis and llm_analysis['experiment_overview']:
            if len(llm_analysis['experiment_overview']) > len(experiment_overview):
                final_overview = llm_analysis['experiment_overview']
        
        # Return the structured output with our extracted experiment name
        return {
            "is_valid_vlab": is_valid,
            "experiment_name": experiment_name,
            "experiment_overview": final_overview,
            "missing_components": missing_components,
            "structure_compliance_score": compliance_score,
            "repo_structure": repo_structure,
            "repo_path": self.repo_path
        }