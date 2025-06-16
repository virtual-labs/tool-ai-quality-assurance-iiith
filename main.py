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
    def __init__(self, model=None, custom_weights=None):
        if model is None:
            model = CONFIG["general"]["default_model"]
            
        self.llm = ChatGoogleGenerativeAI(
            model=model,
            temperature=CONFIG["llm"]["temperature"],
            max_tokens=CONFIG["llm"]["max_tokens"]
        )
        self.temp_dir = None
        self.repo_url = None
        self.evaluation_results = {}
        self.final_score = 0
        self.report = ""
        
        # Use custom weights if provided, otherwise use config defaults
        if custom_weights is None:
            self.weights = CONFIG["weights"].copy()
        else:
            self.weights = custom_weights.copy()
    
    def update_weights(self, new_weights):
        """Update evaluation weights"""
        if new_weights is not None:
            self.weights = new_weights.copy()
        else:
            self.weights = CONFIG["weights"].copy()
    
    def get_weights(self):
        """Get current weights"""
        return self.weights.copy()
    
    def get_repository_branches(self, repo_url):
        """Get all remote branches of a GitHub repository using git ls-remote"""
        try:
            result = subprocess.run(
                ["git", "ls-remote", "--heads", repo_url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
                timeout=30  # Add timeout to prevent hanging
            )
            output = result.stdout
            
            # Extract branch names from lines like: <hash>\trefs/heads/<branch>
            branches = re.findall(r'refs/heads/(.+)', output)
            
            if branches:
                # Sort branches - put main and master first if they exist
                main_branches = [b for b in branches if b in ['main', 'master']]
                other_branches = [b for b in branches if b not in ['main', 'master']]
                sorted_branches = main_branches + sorted(other_branches)
                return True, sorted_branches
            else:
                return True, ["main", "master"]  # Fallback if no branches found
                
        except subprocess.CalledProcessError as e:
            return False, f"Failed to fetch branches: {e.stderr.strip()}"
        except subprocess.TimeoutExpired:
            return False, "Timeout while fetching branches"
        except Exception as e:
            return False, f"Error fetching branches: {str(e)}"
        
    def clone_repository(self, repo_url, branch="main"):
        """Clone the repository to a temporary directory"""
        self.repo_url = repo_url
        self.temp_dir = tempfile.mkdtemp()
        
        try:
            # Clone the repository
            repo = Repo.clone_from(repo_url, self.temp_dir)
            
            # Try to checkout the specified branch
            try:
                repo.git.checkout(branch)
            except GitCommandError as e:
                # If branch doesn't exist, try master as fallback
                if branch != "master":
                    try:
                        repo.git.checkout("master")
                    except GitCommandError:
                        pass
            
            return True, f"Repository cloned successfully to {self.temp_dir}, branch: {branch}"
        except Exception as e:
            return False, f"Failed to clone repository: {str(e)}"
    
    def evaluate_repository(self):
        """Run the complete evaluation pipeline"""
        if not self.temp_dir or not os.path.exists(self.temp_dir):
            return False, "Repository not cloned yet."
        
        # Step 1: Repository analysis first
        try:
            repo_agent = RepositoryAgent(repo_path=self.temp_dir, repo_url=self.repo_url)
            repo_agent.skip_enhancement = True
            repo_agent.set_llm(self.llm)
            repo_results = repo_agent.get_output()
            self.evaluation_results['repository'] = repo_results
        except Exception as e:
            print(f"Warning: Repository analysis failed: {str(e)}")
    
        # Step 2: Structure evaluation
        structure_agent = StructureComplianceAgent(self.temp_dir)
        structure_agent.skip_enhancement = True
        structure_agent.set_llm(self.llm)
        structure_results = structure_agent.get_output()
        self.evaluation_results['structure'] = structure_results
    
        if structure_results['compliance_score'] < CONFIG["thresholds"]["structure_minimum"]:
            return False, "Repository structure does not meet minimum requirements."
    
        # Step 3: Content evaluation
        content_agent = ContentEvaluationAgent(self.temp_dir)
        content_agent.set_llm(self.llm)
        content_results = content_agent.get_output()
        self.evaluation_results['content'] = content_results
    
        # Step 4: Simulation evaluation
        simulation_agent = SimulationEvaluationAgent(self.temp_dir)
        simulation_agent.skip_enhancement = True
        simulation_agent.set_llm(self.llm)
        simulation_results = simulation_agent.get_output()
        self.evaluation_results['simulation'] = simulation_results
    
        # Step 5: Generate final report with custom weights
        score_agent = ScoreCalculationAgent(self.evaluation_results, self.weights)
        score_agent.set_llm(self.llm)
        score_results = score_agent.get_output()
        
        self.final_score = score_results['final_score']
        self.report = score_results['report']
        
        return True, "Evaluation completed successfully."
        
    def get_score(self):
        """Return the final score"""
        return self.final_score
        
    def clean_report(self, report_text):
        """Clean up report text by removing unwanted markdown artifacts and acknowledgments"""
        # Remove code blocks
        report_text = re.sub(r'```[a-z]*\n', '', report_text)
        report_text = report_text.replace("```", "")
        
        # Remove acknowledgment lines
        lines = report_text.split('\n')
        # filtered_lines = []
        
        # for line in lines:
        #     # Skip lines that look like acknowledgments
        #     if any(phrase in line.lower() for phrase in [
        #         "i will", "okay,", "sure,", "here's", "here is", "as requested"
        #     ]) and len(line) < 100:  # Usually acknowledgments are short
        #         continue
        #     filtered_lines.append(line)
        
        # return '\n'.join(filtered_lines)
        return '\n'.join(lines)
    
    def get_report(self):
        """Return the cleaned detailed evaluation report"""
        return self.clean_report(self.report)
    
    def get_results(self):
        """Return all evaluation results"""
        return {
            'final_score': self.final_score,
            'report': self.report,
            'detailed_results': self.evaluation_results
        }
        
    def cleanup(self):
        """Clean up temporary resources"""
        if self.temp_dir and os.path.exists(self.temp_dir) and CONFIG["general"]["temp_cleanup"]:
            try:
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None
            except Exception as e:
                print(f"Warning: Could not clean up temporary directory: {str(e)}")

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
            print(f"\nEvaluation Score: {results['final_score']:.1f}/100\n")
            print("Report:")
            print(results['report'])
            
            # Save report to file
            with open("qa_report.md", "w") as f:
                f.write(results['report'])
            print("\nReport saved to qa_report.md")
            
    # Clean up
    pipeline.cleanup()
