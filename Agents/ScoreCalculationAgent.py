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
        """Calculate final scores and generate report"""
        
        # Extract scores from each component
        structure_score = self.evaluation_results.get('structure', {}).get('compliance_score', 0) / 10
        content_score = self.evaluation_results.get('content', {}).get('average_score', 0) / 10
        simulation_score = self.evaluation_results.get('simulation', {}).get('overall_score', 0) / 10
        
        # Calculate weighted final score
        final_score = (
            structure_score * self.custom_weights['structure'] +
            content_score * self.custom_weights['content'] +
            simulation_score * self.custom_weights['simulation']
        ) * 100
        
        # Get experiment name from repository results
        experiment_name = "Virtual Lab Experiment"
        if 'repository' in self.evaluation_results:
            repo_data = self.evaluation_results['repository']
            if 'experiment_name' in repo_data and repo_data['experiment_name']:
                experiment_name = repo_data['experiment_name']
        
        # Generate report using LLM
        template_count, total_evaluated, template_percentage = self._count_template_files()
        
        # Get enhanced overview from repository results
        enhanced_overview = ""
        learning_objectives = []
        if 'repository' in self.evaluation_results:
            repo_data = self.evaluation_results['repository']
            enhanced_overview = repo_data.get('enhanced_overview', repo_data.get('experiment_overview', ''))
            learning_objectives = repo_data.get('learning_objectives', [])
        
        report_prompt = f"""
Generate a comprehensive quality report for this Virtual Lab:

Experiment: {experiment_name}
Overview: {enhanced_overview}
Learning Objectives: {', '.join(learning_objectives) if learning_objectives else 'Not specified'}

SCORES:
- Final Score: {final_score:.1f}/100
- Structure Score: {structure_score * 10:.1f}/100
- Content Score: {content_score * 10:.1f}/100
- Simulation Score: {simulation_score * 10:.1f}/100

ANALYSIS:
- Template Files: {template_count}/{total_evaluated} ({template_percentage:.1f}%)
- Structure Compliance: {self.evaluation_results.get('structure', {}).get('structure_status', 'Unknown')}
- Simulation Status: {self.evaluation_results.get('simulation', {}).get('simulation_status', 'Unknown')}

Generate a professional markdown report with:
1. Executive Summary
2. Component Analysis
3. Key Findings
4. Recommendations for Improvement
5. Conclusion

Start with "# Virtual Lab Quality Report: {experiment_name}"
"""
        
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
                report = f"""# Virtual Lab Quality Report: {experiment_name}

## Executive Summary
Overall Quality Score: {final_score:.1f}/100

## Component Scores
- Structure: {structure_score * 10:.1f}/100
- Content: {content_score * 10:.1f}/100  
- Simulation: {simulation_score * 10:.1f}/100

## Assessment
This Virtual Lab has been evaluated across structure, content, and simulation components.

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
    
        return {
            "final_score": final_score,
            "component_scores": {
                "structure": structure_score * 10,
                "content": content_score * 10,
                "simulation": simulation_score * 10
            },
            "weights_used": self.custom_weights.copy(),
            "report": report,
            "experiment_name": experiment_name
        }