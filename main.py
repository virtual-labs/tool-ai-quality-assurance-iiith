import os
import json
import tempfile
import subprocess
from BaseAgent import BaseAgent
from Agents.RepositoryAgent import RepositoryAgent
from Agents.StructureComplianceAgent import StructureComplianceAgent
from Agents.ContentEvaluationAgent import ContentEvaluationAgent
from Agents.SimulationEvaluationAgent import SimulationEvaluationAgent
from Agents.ScoreCalculationAgent import ScoreCalculationAgent
from langchain_google_genai import ChatGoogleGenerativeAI
import dotenv

# Load environment variables
dotenv.load_dotenv()

class QAPipeline:
    def __init__(self, model="gemini-2.0-flash"):
        self.llm = ChatGoogleGenerativeAI(
            model=model,
            temperature=0.2,
            max_tokens=100000
        )
        self.temp_dir = None
        self.repo_url = None
        self.evaluation_results = {}
        self.final_score = 0
        self.report = ""
        
    def clone_repository(self, repo_url):
        """Clone the repository to a temporary directory"""
        self.repo_url = repo_url
        self.temp_dir = tempfile.mkdtemp()
        
        try:
            subprocess.check_call(['git', 'clone', repo_url, self.temp_dir], 
                                 stderr=subprocess.STDOUT)
            return True, f"Repository cloned successfully to {self.temp_dir}"
        except subprocess.CalledProcessError as e:
            return False, f"Failed to clone repository: {str(e)}"
    
    def evaluate_repository(self):
        """Run the complete evaluation pipeline"""
        if not self.temp_dir or not os.path.exists(self.temp_dir):
            return False, "Repository not cloned yet."
            
        # Step 1: Validate repository structure (skip enhancement for faster processing)
        structure_agent = StructureComplianceAgent(self.temp_dir)
        structure_agent.skip_enhancement = True  # Skip enhancement to reduce API calls
        structure_agent.set_llm(self.llm)
        structure_results = structure_agent.get_output()
        self.evaluation_results['structure'] = structure_results
        
        if structure_results['compliance_score'] < 3:  # Threshold check
            return False, "Repository structure does not meet minimum requirements."
        
        # Step 2: Extract experiment name if available
        experiment_name = "Unknown Experiment"
        if os.path.exists(os.path.join(self.temp_dir, "experiment/experiment-name.md")):
            try:
                with open(os.path.join(self.temp_dir, "experiment/experiment-name.md"), 'r') as f:
                    experiment_name = f.read().strip()
            except:
                pass
        self.evaluation_results['experiment_name'] = experiment_name
        
        # Step 3: Evaluate content (keep enhancement for better analysis)
        content_agent = ContentEvaluationAgent(self.temp_dir)
        content_agent.set_llm(self.llm)
        content_agent.set_prompt_enhancer_llm(self.llm)
        content_results = content_agent.get_output()
        self.evaluation_results['content'] = content_results
        
        # Step 4: Evaluate simulation (skip enhancement for faster processing)
        simulation_agent = SimulationEvaluationAgent(self.temp_dir)
        simulation_agent.skip_enhancement = True  # Skip enhancement to reduce API calls
        simulation_agent.set_llm(self.llm)
        simulation_results = simulation_agent.get_output()
        self.evaluation_results['simulation'] = simulation_results
        
        # Step 5: Calculate final score and generate report (keep enhancement for better results)
        score_agent = ScoreCalculationAgent(self.evaluation_results)
        score_agent.set_llm(self.llm)
        score_agent.set_prompt_enhancer_llm(self.llm)
        score_results = score_agent.get_output()
        
        self.final_score = score_results['final_score']
        self.report = score_results['report']
        
        return True, "Evaluation completed successfully."
        
    def get_score(self):
        """Return the final score"""
        return self.final_score
        
    def get_report(self):
        """Return the detailed evaluation report"""
        return self.report
        
    def get_results(self):
        """Return all evaluation results"""
        return {
            'final_score': self.final_score,
            'report': self.report,
            'detailed_results': self.evaluation_results
        }
        
    def cleanup(self):
        """Remove temporary directory"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            subprocess.run(['rm', '-rf', self.temp_dir])
            self.temp_dir = None

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
