import os
import shutil
import tempfile
import re
import subprocess
from git import Repo, GitCommandError
from langchain_google_genai import ChatGoogleGenerativeAI
from Agents.StructureComplianceAgent import StructureComplianceAgent
from Agents.ContentEvaluationAgent import ContentEvaluationAgent
from Agents.SimulationEvaluationAgent import SimulationEvaluationAgent
from Agents.ScoreCalculationAgent import ScoreCalculationAgent
from Agents.RepositoryAgent import RepositoryAgent
from config_loader import load_config

# Load the configuration
CONFIG = load_config()

class QAPipeline:
    def __init__(self, model="gemini-1.5-flash", custom_weights=None):
        self.model = model
        self.custom_weights = custom_weights or CONFIG["weights"]
        self.temp_dir = None
        self.repo_url = None
        self.evaluation_results = {}
        
        # Initialize LLM
        try:
            self.llm = ChatGoogleGenerativeAI(
                model=self.model,
                temperature=0.1,
                max_tokens=None,
                timeout=None,
                max_retries=2,
            )
        except Exception as e:
            raise Exception(f"Failed to initialize LLM: {str(e)}")
    
    def get_repository_branches(self, repo_url):
        """Get available branches from the repository"""
        try:
            result = subprocess.run([
                'git', 'ls-remote', '--heads', repo_url
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return False, f"Failed to fetch branches: {result.stderr}"
            
            branches = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    branch_name = line.split('\t')[1].replace('refs/heads/', '')
                    branches.append(branch_name)
            
            return True, branches if branches else ["main"]
        except subprocess.TimeoutExpired:
            return False, "Timeout while fetching branches"
        except Exception as e:
            return False, f"Error fetching branches: {str(e)}"
    
    def clone_repository(self, repo_url, branch="main"):
        """Clone the repository to a temporary directory"""
        self.repo_url = repo_url
        self.temp_dir = tempfile.mkdtemp()
        
        try:
            # Clone with specific branch
            Repo.clone_from(repo_url, self.temp_dir, branch=branch)
            return True, f"Repository cloned successfully to {self.temp_dir}"
        except GitCommandError as e:
            if "does not exist" in str(e) and branch != "main":
                # Try with main branch if specified branch doesn't exist
                try:
                    shutil.rmtree(self.temp_dir)
                    self.temp_dir = tempfile.mkdtemp()
                    Repo.clone_from(repo_url, self.temp_dir, branch="main")
                    return True, f"Repository cloned successfully to {self.temp_dir} (using main branch)"
                except GitCommandError as e2:
                    return False, f"Failed to clone repository: {str(e2)}"
            return False, f"Failed to clone repository: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error during cloning: {str(e)}"
    
    def evaluate_repository(self):
        """Run the complete evaluation pipeline"""
        if not self.temp_dir or not os.path.exists(self.temp_dir):
            return False, "Repository not cloned yet."
        
        # Step 1: Repository metadata analysis
        try:
            repo_agent = RepositoryAgent(repo_path=self.temp_dir, repo_url=self.repo_url)
            repo_agent.set_llm(self.llm)
            repo_results = repo_agent.get_output()
            self.evaluation_results['repository'] = repo_results
        except Exception as e:
            print(f"Warning: Repository analysis failed: {str(e)}")
            # Provide default repository results
            self.evaluation_results['repository'] = {
                "experiment_name": "Unknown Experiment",
                "experiment_overview": "Repository analysis failed",
                "enhanced_overview": "Could not analyze repository metadata",
                "learning_objectives": [],
                "subject_area": "Unknown"
            }
    
        # Step 2: Structure compliance evaluation
        try:
            structure_agent = StructureComplianceAgent(self.temp_dir)
            structure_agent.set_llm(self.llm)
            structure_results = structure_agent.get_output()
            self.evaluation_results['structure'] = structure_results
            
            # Check if structure meets minimum requirements
            if structure_results['compliance_score'] < CONFIG["thresholds"]["structure_minimum"]:
                return False, "Repository structure does not meet minimum requirements."
                
        except Exception as e:
            return False, f"Structure evaluation failed: {str(e)}"
    
        # Step 3: Content evaluation
        try:
            content_agent = ContentEvaluationAgent(self.temp_dir)
            content_agent.set_llm(self.llm)
            content_results = content_agent.get_output()
            self.evaluation_results['content'] = content_results
        except Exception as e:
            return False, f"Content evaluation failed: {str(e)}"
    
        # Step 4: Simulation evaluation
        try:
            simulation_agent = SimulationEvaluationAgent(self.temp_dir)
            simulation_agent.set_llm(self.llm)
            simulation_results = simulation_agent.get_output()
            self.evaluation_results['simulation'] = simulation_results
        except Exception as e:
            return False, f"Simulation evaluation failed: {str(e)}"
    
        # Step 5: Score calculation and report generation
        try:
            score_agent = ScoreCalculationAgent(self.evaluation_results, self.custom_weights)
            score_agent.set_llm(self.llm)
            final_results = score_agent.get_output()
            self.evaluation_results.update(final_results)
        except Exception as e:
            return False, f"Score calculation failed: {str(e)}"
        
        return True, "Evaluation completed successfully."
    
    def get_results(self):
        """Get the evaluation results"""
        # Ensure we have repository metadata for the UI
        if 'repository' not in self.evaluation_results:
            self.evaluation_results['repository'] = {
                "experiment_name": "Unknown Experiment",
                "experiment_overview": "No overview available",
                "enhanced_overview": "Repository analysis not completed",
                "learning_objectives": [],
                "subject_area": "Unknown"
            }
        
        # Add detailed results for backward compatibility
        self.evaluation_results['detailed_results'] = {
            'repository': self.evaluation_results.get('repository', {}),
            'structure': self.evaluation_results.get('structure', {}),
            'content': self.evaluation_results.get('content', {}),
            'simulation': self.evaluation_results.get('simulation', {})
        }
        
        return self.evaluation_results
    
    def cleanup(self):
        """Clean up temporary files"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def __del__(self):
        self.cleanup()

if __name__ == "__main__":
    # Example usage
    pipeline = QAPipeline()
    repo_url = input("Enter Git repository URL: ")
    
    print(f"Cloning repository: {repo_url}")
    success, message = pipeline.clone_repository(repo_url)
    
    if not success:
        print(f"Error: {message}")
    else:
        print(message)
        print("Evaluating repository...")
        success, message = pipeline.evaluate_repository()
        
        if not success:
            print(f"Evaluation failed: {message}")
        else:
            results = pipeline.get_results()
            print(f"\nEvaluation Results:")
            print(f"Experiment: {results.get('experiment_name', 'Unknown')}")
            print(f"Final Score: {results.get('final_score', 0):.1f}/100")
            
            if 'component_scores' in results:
                component_scores = results['component_scores']
                print(f"Structure: {component_scores.get('structure', 0):.1f}/100")
                print(f"Content: {component_scores.get('content', 0):.1f}/100")
                print(f"Simulation: {component_scores.get('simulation', 0):.1f}/100")
