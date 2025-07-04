import os
import tempfile
import subprocess
import json
import re
from BaseAgent import BaseAgent

class ScoreCalculationAgent(BaseAgent):
    role = "Score Calculator and Report Generator"
    
    basic_prompt_template = """
You are a quality assessment report generator for Virtual Labs experiments.

Generate a comprehensive quality assessment report based on the evaluation data provided.

The report should be in markdown format and include:
1. Executive summary with overall score
2. Component analysis for each evaluated area
3. Strengths and areas for improvement
4. Specific recommendations
5. Conclusion

Focus on actionable insights and specific improvements needed.
"""
    
    def __init__(self, evaluation_results, custom_weights=None):
        self.evaluation_results = evaluation_results
        
        # Updated default weights (removed simulation, enhanced browser testing)
        default_weights = {
            "structure": 0.3,
            "content": 0.4,
            "browser_testing": 0.3
        }
        
        if custom_weights:
            # Normalize weights
            total = sum(custom_weights.values())
            self.custom_weights = {k: v/total for k, v in custom_weights.items()}
        else:
            self.custom_weights = default_weights
            
        super().__init__(
            self.role,
            basic_prompt=self.basic_prompt_template,
            context=""
        )

    def get_output(self):
        # Use custom weights
        structure_weight = self.custom_weights["structure"]
        content_weight = self.custom_weights["content"]  
        browser_weight = self.custom_weights["browser_testing"]
        
        # Extract scores - browser testing replaces simulation
        structure_score = self.evaluation_results.get('structure', {}).get('compliance_score', 0)
        content_score = self.evaluation_results.get('content', {}).get('average_score', 0)
        browser_score = self.evaluation_results.get('browser_testing', {}).get('browser_score', 0)

        # Get experiment name from repository results
        experiment_name = "Virtual Lab Experiment"
        if 'repository' in self.evaluation_results:
            repo_data = self.evaluation_results['repository']
            if 'experiment_name' in repo_data and repo_data['experiment_name']:
                experiment_name = repo_data['experiment_name']

        # Calculate final score with updated weights
        final_score = (
            structure_score * structure_weight * 10 +
            content_score * content_weight * 10 +
            browser_score * browser_weight * 10
        )
        
        # Gather data
        structure_data = self.evaluation_results.get('structure', {})
        content_data = self.evaluation_results.get('content', {})
        browser_data = self.evaluation_results.get('browser_testing', {})
        
        # Create comprehensive prompt
        direct_prompt = f"""Write a quality assessment report for the Virtual Lab experiment: {experiment_name}

EVALUATION DATA:
Structure Score: {structure_score}/10 - Status: {structure_data.get('structure_status', 'Unknown')}
Content Score: {content_score}/10 - Files: {content_data.get('evaluated_count', 0)}/{content_data.get('total_files', 0)} - Templates: {content_data.get('template_count', 0)}
Browser Testing Score: {browser_score}/10 - Status: {browser_data.get('status', 'Unknown')} - Tests: {browser_data.get('passed_tests', 0)}/{browser_data.get('total_tests', 0)} passed

Final Score: {final_score:.1f}/100

Write a markdown report starting with:

# Virtual Lab Quality Report: {experiment_name}

## Executive Summary
Brief overview with overall score of {final_score:.1f}/100.

## Component Analysis
### Structure Evaluation: {structure_score * 10:.1f}/100
### Content Evaluation: {content_score * 10:.1f}/100  
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
                # Fallback report with browser testing
                report = f"""# Virtual Lab Quality Report: {experiment_name}

## Executive Summary
Overall Quality Score: {final_score:.1f}/100

## Component Scores
- Structure: {structure_score * 10:.1f}/100
- Content: {content_score * 10:.1f}/100  
- Browser Testing: {browser_score:.1f}/100

## Assessment
This Virtual Lab has been evaluated across structure, content, and browser functionality components.

## Recommendations
Based on the evaluation, improvements are needed in areas scoring below 70/100."""
        
        except Exception as e:
            print(f"Error generating report: {str(e)}")
            # Fallback report
            report = f"""# Virtual Lab Quality Report: {experiment_name}

## Executive Summary
Overall Quality Score: {final_score:.1f}/100

## Component Analysis
- **Structure**: {structure_score * 10:.1f}/100
- **Content**: {content_score * 10:.1f}/100
- **Browser Testing**: {browser_score:.1f}/100

## Status
Report generation encountered an error. Manual review recommended."""

        return {
            'final_score': round(final_score, 1),
            'component_scores': {
                'structure': round(structure_score * 10, 1),
                'content': round(content_score * 10, 1),
                'browser_testing': round(browser_score, 1)
            },
            'weights_used': self.custom_weights,
            'report': report,
            'experiment_name': experiment_name,
            'template_files': template_count,
            'total_content_files': total_evaluated,
            'template_percentage': template_percentage
        }

    def _count_template_files(self):
        """Count template files from content evaluation"""
        content_data = self.evaluation_results.get('content', {})
        template_count = content_data.get('template_count', 0)
        total_evaluated = content_data.get('evaluated_count', 0)
        template_percentage = content_data.get('template_percentage', 0)
        
        return template_count, total_evaluated, template_percentage
