import os
import shutil
import tempfile
import re
import subprocess
from git import Repo, GitCommandError
from langchain_google_genai import ChatGoogleGenerativeAI
from Agents.PlaywrightTestingAgent import PlaywrightTestingAgent
from Agents.StructureComplianceAgent import StructureComplianceAgent
from Agents.ContentEvaluationAgent import ContentEvaluationAgent
from Agents.ScoreCalculationAgent import ScoreCalculationAgent
from Agents.RepositoryAgent import RepositoryAgent
from config_loader import load_config

# Load the configuration
CONFIG = load_config()

class QAPipeline:
    def __init__(self, model="gemini-1.5-flash", custom_weights=None):
        self.model = model
        self.llm = ChatGoogleGenerativeAI(
            model=self.model,
            temperature=0.1,
            # google_api_key=CONFIG["general"]["api_key"]
        )
        self.temp_dir = None
        self.repo_url = None
        self.evaluation_results = {}
        self.final_score = 0
        self.report = ""
        
        # Use custom weights if provided, otherwise use config defaults
        if custom_weights:
            # Updated weights structure - removed simulation, enhanced browser_testing
            total_weight = custom_weights.get("structure", 0.3) + custom_weights.get("content", 0.4) + custom_weights.get("browser_testing", 0.3)
            self.weights = {
                "structure": custom_weights.get("structure", 0.3) / total_weight,
                "content": custom_weights.get("content", 0.4) / total_weight,
                "browser_testing": custom_weights.get("browser_testing", 0.3) / total_weight
            }
        else:
            # Default weights - removed simulation
            self.weights = {
                "structure": 0.3,
                "content": 0.4,
                "browser_testing": 0.3
            }

    def get_repository_branches(self, repo_url):
        """Get available branches from the repository"""
        try:
            # Use git ls-remote to get branches without cloning
            result = subprocess.run([
                'git', 'ls-remote', '--heads', repo_url
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return False, f"Failed to fetch branches: {result.stderr}"
            
            # Parse branch names from output
            branches = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    # Extract branch name from "hash refs/heads/branch-name"
                    parts = line.split('\t')
                    if len(parts) == 2 and 'refs/heads/' in parts[1]:
                        branch_name = parts[1].replace('refs/heads/', '')
                        branches.append(branch_name)
            
            if not branches:
                return False, "No branches found"
            
            # Sort branches with main/master first
            priority_branches = ['main', 'master']
            sorted_branches = []
            
            for priority in priority_branches:
                if priority in branches:
                    sorted_branches.append(priority)
                    branches.remove(priority)
            
            sorted_branches.extend(sorted(branches))
            
            return True, sorted_branches
            
        except subprocess.TimeoutExpired:
            return False, "Timeout while fetching branches"
        except Exception as e:
            return False, f"Error fetching branches: {str(e)}"

    def clone_repository(self, repo_url, branch="main"):
        """Clone the repository to a temporary directory"""
        try:
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
            
            self.temp_dir = tempfile.mkdtemp()
            self.repo_url = repo_url
            
            # Clone with specific branch
            Repo.clone_from(repo_url, self.temp_dir, branch=branch, depth=1)
            
            return True, f"Repository cloned successfully to {self.temp_dir}"
        except GitCommandError as e:
            error_msg = str(e)
            if "does not exist" in error_msg or "not found" in error_msg:
                return False, f"Branch '{branch}' not found in repository"
            else:
                return False, f"Git error: {error_msg}"
        except Exception as e:
            return False, f"Failed to clone repository: {str(e)}"

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

        # Step 4: Browser functionality testing (replaces simulation evaluation)
        try:
            playwright_agent = PlaywrightTestingAgent(self.temp_dir)
            playwright_agent.set_llm(self.llm)
            playwright_results = playwright_agent.get_output()
            self.evaluation_results['browser_testing'] = playwright_results
        except Exception as e:
            print(f"Warning: Browser testing failed: {str(e)}")
            self.evaluation_results['browser_testing'] = {
                "browser_score": 0,
                "status": "ERROR",
                "message": f"Browser testing failed: {str(e)}",
                "overall_score": 0,
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "error_tests": 0,
                "test_results": [],
                "screenshots": {}
            }

        # Step 5: Generate final report with updated weights
        try:
            score_agent = ScoreCalculationAgent(self.evaluation_results, self.weights)
            score_agent.set_llm(self.llm)
            score_results = score_agent.get_output()
            
            self.final_score = score_results['final_score']
            self.report = score_results['report']
            self.evaluation_results.update(score_results)
        except Exception as e:
            print(f"Warning: Score calculation failed: {str(e)}")
            # Provide fallback scoring
            structure_score = self.evaluation_results.get('structure', {}).get('compliance_score', 0) * 10
            content_score = self.evaluation_results.get('content', {}).get('average_score', 0) * 10
            browser_score = self.evaluation_results.get('browser_testing', {}).get('browser_score', 0) * 10
            
            self.final_score = (structure_score * 0.3 + content_score * 0.4 + browser_score * 0.3)
            self.report = f"# Evaluation Report\n\nOverall Score: {self.final_score:.1f}/100"
            
            self.evaluation_results.update({
                'final_score': self.final_score,
                'component_scores': {
                    'structure': structure_score,
                    'content': content_score,
                    'browser_testing': browser_score
                },
                'report': self.report
            })

        return True, "Evaluation completed successfully."

    def get_results(self):
        """Get the evaluation results"""
        if 'repository' not in self.evaluation_results:
            self.evaluation_results['repository'] = {
                "experiment_name": "Unknown Experiment",
                "experiment_overview": "No overview available",
                "enhanced_overview": "Repository analysis not completed",
                "learning_objectives": [],
                "subject_area": "Unknown"
            }

        # Ensure all required fields exist
        if 'final_score' not in self.evaluation_results:
            self.evaluation_results['final_score'] = self.final_score

        if 'report' not in self.evaluation_results:
            self.evaluation_results['report'] = self.report

        self.evaluation_results['detailed_results'] = {
            'repository': self.evaluation_results.get('repository', {}),
            'structure': self.evaluation_results.get('structure', {}),
            'content': self.evaluation_results.get('content', {}),
            'browser_testing': self.evaluation_results.get('browser_testing', {})
        }
        
        return self.evaluation_results

    def cleanup(self):
        """Clean up temporary files"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def __del__(self):
        self.cleanup()

if __name__ == "__main__":
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
            print(f"Experiment: {results.get('repository', {}).get('experiment_name', 'Unknown')}")
            print(f"Final Score: {results.get('final_score', 0):.1f}/100")
            
            if 'component_scores' in results:
                component_scores = results['component_scores']
                print(f"Structure: {component_scores.get('structure', 0):.1f}/100")
                print(f"Content: {component_scores.get('content', 0):.1f}/100")
                print(f"Browser Testing: {component_scores.get('browser_testing', 0):.1f}/100")
