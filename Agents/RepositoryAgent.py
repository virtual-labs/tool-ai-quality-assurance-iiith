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

Repository URL: {repo_url}
Experiment Name: {experiment_name}
Experiment Overview: {experiment_overview}

Enhance the experiment overview with better description and educational context.
Provide a more comprehensive and educational description of what this experiment teaches.

Return your analysis in JSON format:
{{
  "enhanced_overview": "Enhanced educational description of the experiment",
  "learning_objectives": ["objective1", "objective2", "objective3"],
  "subject_area": "Physics/Chemistry/Biology/etc"
}}
"""
    
    def __init__(self, repo_path=None, repo_url=None):
        super().__init__(
            role="Repository Analysis Agent",
            basic_prompt=self.basic_prompt_template,
            context=""
        )
        self.repo_path = repo_path
        self.repo_url = repo_url
        
        # Validate URL if provided
        if repo_url:
            is_valid, message = self.validate_repo_url(repo_url)
            if not is_valid:
                print(f"Warning: {message}")
    
    def validate_repo_url(self, url):
        """
        Validate if the URL follows the Virtual Labs repository pattern
        Expected pattern: https://github.com/virtual-labs/exp-{exp-name}-{inst-name}
        """
        if not url:
            return False, "No URL provided"
        
        # Define the expected pattern
        vlab_pattern = r'^https://github\.com/virtual-labs/exp-[a-zA-Z0-9\-_]+-[a-zA-Z0-9\-_]+(?:\.git)?/?$'
        
        if re.match(vlab_pattern, url.strip()):
            return True, "Valid Virtual Labs repository URL"
        else:
            return False, "URL does not follow Virtual Labs pattern: https://github.com/virtual-labs/exp-{exp-name}-{inst-name}"

    def extract_experiment_details_from_url(self, url):
        """Extract experiment name and institution from URL"""
        if not url:
            return None, None
        
        # Remove .git suffix and trailing slash if present
        clean_url = url.rstrip('/').replace('.git', '')
        
        # Extract the repository name
        repo_name = clean_url.split('/')[-1]
        
        # Match the pattern exp-{exp-name}-{inst-name}
        match = re.match(r'^exp-(.+)-([a-zA-Z0-9]+)$', repo_name)
        
        if match:
            exp_name = match.group(1).replace('-', ' ').title()
            inst_name = match.group(2).upper()
            return exp_name, inst_name
        
        return None, None
    
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
    
    def _extract_experiment_name(self):
        """Extract experiment name from repository"""
        
        # Priority 1: Extract from URL pattern (most reliable for Virtual Labs)
        if hasattr(self, 'repo_url') and self.repo_url:
            exp_name, inst_name = self.extract_experiment_details_from_url(self.repo_url)
            if exp_name:
                return exp_name
        
        # Priority 2: experiment-name.md
        name_file = os.path.join(self.repo_path, "experiment", "experiment-name.md")
        if os.path.exists(name_file):
            try:
                with open(name_file, 'r', encoding='utf-8') as file:
                    content = file.read().strip()
                    # Remove markdown formatting
                    content = re.sub(r'^#+\s*', '', content, flags=re.MULTILINE)
                    content = re.sub(r'[*_`]', '', content)
                    if content and len(content.split()) <= 10:  # Reasonable experiment name length
                        return content.strip()
            except:
                pass
        
        # Priority 3: Extract from README.md title
        readme_file = os.path.join(self.repo_path, "README.md")
        if os.path.exists(readme_file):
            try:
                with open(readme_file, 'r', encoding='utf-8') as file:
                    content = file.read()
                    # Look for the first heading
                    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                    if match:
                        title = match.group(1).strip()
                        # Clean up common prefixes
                        title = re.sub(r'^(experiment|lab|virtual lab):\s*', '', title, flags=re.IGNORECASE)
                        return title
            except:
                pass
        
        # Fallback: Use repo name
        if self.repo_url:
            repo_name = self.repo_url.split('/')[-1].replace('.git', '')
            if repo_name.startswith('exp-'):
                # Remove exp- prefix and institution suffix
                parts = repo_name[4:].split('-')
                if len(parts) > 1:
                    # Remove last part (institution) and join the rest
                    exp_name = ' '.join(parts[:-1]).replace('-', ' ').title()
                    return exp_name
        
        return "Unknown Experiment"
    
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
                    content = content.strip()
                    if content:
                        return content[:500]  # First 500 chars
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
                    for para in paragraphs[1:]:  # Skip first (usually title)
                        if para.strip() and not para.strip().startswith('#'):
                            # Clean up the paragraph
                            clean_para = re.sub(r'^[*-]\s+', '', para.strip(), flags=re.MULTILINE)
                            clean_para = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean_para)  # Remove links
                            if len(clean_para) > 50:  # Substantial content
                                return clean_para[:500]
            except:
                pass
        
        return "No overview available"
    
    def get_output(self):
        """Get repository metadata without structure compliance"""
        if not self.repo_path and self.repo_url:
            success, result = self.clone_repository()
            if not success:
                return {
                    "experiment_name": "Unknown",
                    "experiment_overview": "Could not analyze repository",
                    "enhanced_overview": "Repository analysis failed",
                    "learning_objectives": [],
                    "subject_area": "Unknown",
                    "error": result
                }
        
        # Extract repository metadata
        experiment_name = self._extract_experiment_name()
        experiment_overview = self._get_experiment_overview()
        
        # Use LLM for enhancement if we have meaningful content
        enhanced_overview = experiment_overview
        learning_objectives = []
        subject_area = "Unknown"
        
        if experiment_overview and experiment_overview != "No overview available":
            try:
                context = self.basic_prompt_template.format(
                    repo_url=self.repo_url or "Unknown",
                    experiment_name=experiment_name,
                    experiment_overview=experiment_overview
                )
                self.context = context
                response = super().get_output()
                
                # Try to extract JSON from response
                json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
                if json_match:
                    llm_analysis = json.loads(json_match.group(1))
                    if llm_analysis.get('enhanced_overview'):
                        enhanced_overview = llm_analysis['enhanced_overview']
                    if llm_analysis.get('learning_objectives'):
                        learning_objectives = llm_analysis['learning_objectives']
                    if llm_analysis.get('subject_area'):
                        subject_area = llm_analysis['subject_area']
                        
            except Exception as e:
                print(f"Warning: LLM enhancement failed: {str(e)}")
        
        return {
            "experiment_name": experiment_name,
            "experiment_overview": experiment_overview,
            "enhanced_overview": enhanced_overview,
            "learning_objectives": learning_objectives,
            "subject_area": subject_area,
            "repo_path": self.repo_path,
            "repo_url": self.repo_url
        }