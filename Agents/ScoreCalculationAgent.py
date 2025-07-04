import os
import tempfile
import subprocess
from BaseAgent import BaseAgent

class ScoreCalculationAgent(BaseAgent):
    def __init__(self, evaluation_results, custom_weights=None):
        self.evaluation_results = evaluation_results
        self.custom_weights = custom_weights or {"structure": 0.25, "content": 0.5, "simulation": 0.25}
        
        super().__init__(
            role="Score Calculation Agent",
            basic_prompt="Calculate final scores based on evaluation results",
            context=""
        )
    
    def _count_template_files(self):
        """Count how many content files are templates"""
        if 'content' not in self.evaluation_results:
            return 0, 0, 0
            
        content_results = self.evaluation_results['content']
        file_evaluations = content_results.get('file_evaluations', {})
        
        template_count = 0
        total_evaluated = 0
        
        for _, evaluation in file_evaluations.items():
            if evaluation['status'] == 'Evaluated':
                total_evaluated += 1
                if evaluation.get('is_template', False):
                    template_count += 1
                    
        template_percentage = (template_count / total_evaluated * 100) if total_evaluated > 0 else 0
        
        return template_count, total_evaluated, template_percentage
    
    def get_output(self):
        # Use custom weights instead of config weights
        structure_weight = self.custom_weights["structure"]
        content_weight = self.custom_weights["content"]  
        simulation_weight = self.custom_weights["simulation"]
        browser_weight = self.custom_weights.get("browser_testing", 0.15)
        
        # Extract scores
        structure_score = self.evaluation_results.get('structure', {}).get('compliance_score', 0)
        content_score = self.evaluation_results.get('content', {}).get('average_score', 0)
        simulation_score = self.evaluation_results.get('simulation', {}).get('overall_score', 0)
        browser_score = self.evaluation_results.get('browser_testing', {}).get('browser_score', 0)

        
        # Get experiment name from repository results
        experiment_name = "Virtual Lab Experiment"
        if 'repository' in self.evaluation_results:
            repo_data = self.evaluation_results['repository']
            if 'experiment_name' in repo_data and repo_data['experiment_name']:
                experiment_name = repo_data['experiment_name']
    
        # Calculate final score with custom weights
        final_score = (
            structure_score * structure_weight * 10 +
            content_score * content_weight * 10 +
            simulation_score * simulation_weight * 10 +
            browser_score * browser_weight * 10
        )
        
        # Gather data
        structure_data = self.evaluation_results.get('structure', {})
        content_data = self.evaluation_results.get('content', {})
        simulation_data = self.evaluation_results.get('simulation', {})
        browser_data = self.evaluation_results.get('browser_testing', {})
        
        # UPDATED: Create direct prompt WITH browser testing information
        direct_prompt = f"""Write a quality assessment report for the Virtual Lab experiment: {experiment_name}

EVALUATION DATA:
Structure Score: {structure_score}/10 - Status: {structure_data.get('structure_status', 'Unknown')}
Content Score: {content_score}/10 - Files: {content_data.get('evaluated_count', 0)}/{content_data.get('total_files', 0)} - Templates: {content_data.get('template_count', 0)}
Simulation Score: {simulation_score}/10 - Status: {simulation_data.get('simulation_status', 'Unknown')} - Complexity: {simulation_data.get('complexity', 0)}/10
Browser Testing Score: {browser_score}/10 - Status: {browser_data.get('status', 'Unknown')} - Tests: {browser_data.get('passed_tests', 0)}/{browser_data.get('total_tests', 0)} passed

Final Score: {final_score:.1f}/100

Write a markdown report starting with:

# Virtual Lab Quality Report: {experiment_name}

## Executive Summary
Brief overview with overall score of {final_score:.1f}/100.

## Component Analysis
### Structure Evaluation: {structure_score * 10:.1f}/100
### Content Evaluation: {content_score * 10:.1f}/100  
### Simulation Evaluation: {simulation_score * 10:.1f}/100
### Browser Testing: {browser_score * 10:.1f}/100

## Strengths
- List key positive aspects

## Areas for Improvement  
- List issues that need attention

## Recommendations
1. Specific actionable recommendations
2. Priority improvements needed

## Conclusion
Final assessment and next steps."""

        # Set context directly
        self.context = direct_prompt
        
        # Generate report using LLM
        template_count, total_evaluated, template_percentage = self._count_template_files()
        
        # Get enhanced overview from repository results
        enhanced_overview = ""
        learning_objectives = []
        if 'repository' in self.evaluation_results:
            repo_data = self.evaluation_results['repository']
            enhanced_overview = repo_data.get('enhanced_overview', repo_data.get('experiment_overview', ''))
            learning_objectives = repo_data.get('learning_objectives', [])
        
        
        try:
            self.context = report_prompt
            report_response = super().get_output()
            
            # Clean up the report
            lines = report_response.split('\n')
            clean_lines = []
            found_start = False
            
            for line in lines:
                line_clean = line.strip()
                
                # Skip LLM conversational responses
                if any(unwanted in line_clean.lower() for unwanted in [
                    'okay, i will', 'i will generate', 'here\'s the', 'here is the',
                    'certainly', 'sure,', 'as requested', 'markdown'
                ]):
                    continue
                    
                if line_clean.startswith('# Virtual Lab Quality Report'):
                    found_start = True
                    
                if found_start:
                    clean_lines.append(line)
        
            if clean_lines:
                report = '\n'.join(clean_lines)
            else:
                # UPDATED: Fallback report includes browser testing
                report = f"""# Virtual Lab Quality Report: {experiment_name}

## Executive Summary
Overall Quality Score: {final_score:.1f}/100

## Component Scores
- Structure: {structure_score * 10:.1f}/100
- Content: {content_score * 10:.1f}/100  
- Simulation: {simulation_score * 10:.1f}/100
- Browser Testing: {browser_score * 10:.1f}/100

## Assessment
This Virtual Lab has been evaluated across structure, content, simulation, and browser functionality components.

## Recommendations
Based on the evaluation, improvements are needed in areas scoring below 70/100."""
        
        except Exception as e:
            print(f"Error generating report: {str(e)}")
            report = f"""# Virtual Lab Quality Report: {experiment_name}

## Executive Summary
Overall Quality Score: {final_score:.1f}/100

## Component Scores
- Structure: {structure_score * 10:.1f}/100
- Content: {content_score * 10:.1f}/100  
- Simulation: {simulation_score * 10:.1f}/100

## Assessment
This Virtual Lab has been evaluated across structure, content, and simulation components."""
    
        # UPDATED: Return includes browser testing component
        return {
            "final_score": final_score,
            "component_scores": {
                "structure": structure_score * 10,
                "content": content_score * 10,
                "simulation": simulation_score * 10,
                "browser_testing": browser_score * 10
            },
            "weights_used": self.custom_weights.copy(),
            "report": report,
            "experiment_name": experiment_name
        }
