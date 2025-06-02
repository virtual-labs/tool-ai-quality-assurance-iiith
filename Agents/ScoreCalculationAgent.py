import os
import json
import re
from BaseAgent import BaseAgent

class ScoreCalculationAgent(BaseAgent):
    role = "Quality Score Calculator"
    basic_prompt_template = """
    You are an expert in evaluating Virtual Labs quality and providing detailed feedback.

    Based on the detailed evaluation results below, create a comprehensive quality report for this Virtual Lab repository:

    Experiment Name: {experiment_name}

    STRUCTURE EVALUATION:
    Structure Compliance Score: {structure_score}/10
    Structure Status: {structure_status}
    Missing Files: {missing_files}
    Missing Directories: {missing_dirs}

    CONTENT EVALUATION:
    Content Quality Score: {content_score}/10
    Files Evaluated: {files_evaluated}/{total_files}
    Template Files Detected: {template_files} ({template_percentage}%)

    SIMULATION EVALUATION:
    Simulation Quality Score: {simulation_score}/10
    Simulation Status: {simulation_status}
    Complexity: {complexity}/10
    Libraries Used: {libraries}

    IMPORTANT FORMATTING INSTRUCTIONS:
    - Start directly with the report content without any acknowledgments
    - Do NOT include any backticks (```) in your response
    - Do NOT include any code blocks or JSON blocks
    - Use Markdown formatting for headings, lists and emphasis
    - Use plain text for all content

    Create a comprehensive quality report in Markdown format with the following sections:

    # Virtual Lab Quality Report: {experiment_name}

    ## Executive Summary
    [Brief overview of quality assessment with overall score (0-100)]

    ## Strengths
    [List key strengths as bullet points]

    ## Areas for Improvement
    [List aspects that need attention as bullet points]

    ## Detailed Assessment

    ### 1. Structure Evaluation
    [Provide details about structure compliance, missing components, recommendations]

    ### 2. Content Evaluation
    [Provide details about content quality, templates vs. custom content, specific feedback]

    ### 3. Simulation Evaluation
    [Provide details about simulation quality, functionality, improvement suggestions]

    ## Recommendations
    [Provide specific, actionable recommendations as numbered list]

    ## Conclusion
    [Provide final assessment and next steps]

    Use formatting features like headings, bullet points, and bold text to make the report clear and professional.
    """
    
    def __init__(self, evaluation_results):
        self.evaluation_results = evaluation_results
        super().__init__(
            self.role, 
            basic_prompt=self.basic_prompt_template, 
            context=None
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
        # Calculate weighted final score
        structure_weight = 0.25
        content_weight = 0.5
        simulation_weight = 0.25
        
        # Extract scores
        structure_score = self.evaluation_results.get('structure', {}).get('compliance_score', 0)
        content_score = self.evaluation_results.get('content', {}).get('average_score', 0)
        simulation_score = self.evaluation_results.get('simulation', {}).get('overall_score', 0)
        
        # Extract experiment name
        experiment_name = "Unknown Experiment"
        if 'repository' in self.evaluation_results:
            experiment_name = self.evaluation_results['repository'].get('experiment_name', "Unknown Experiment")
        
        # Get template statistics
        template_count, total_evaluated, template_percentage = self._count_template_files()
        
        # Get structure compliance details
        structure_data = self.evaluation_results.get('structure', {})
        structure_status = structure_data.get('structure_status', 'Unknown')
        missing_files = ", ".join(structure_data.get('missing_files', [])[:5])
        if len(structure_data.get('missing_files', [])) > 5:
            missing_files += " and others"
        missing_dirs = ", ".join(structure_data.get('missing_directories', [])[:3])
        if len(structure_data.get('missing_directories', [])) > 3:
            missing_dirs += " and others"
            
        # Get simulation details
        simulation_data = self.evaluation_results.get('simulation', {})
        simulation_status = simulation_data.get('simulation_status', 'Unknown')
        complexity = simulation_data.get('complexity', 0)
        libraries = ", ".join(simulation_data.get('libraries_used', []))
        if not libraries:
            libraries = "None detected"
        
        # Calculate final score (scale to 0-100)
        final_score = (
            structure_score * structure_weight +
            content_score * content_weight +
            simulation_score * simulation_weight
        ) * 10  # Scale to 0-100
        
        # Prepare context
        self.context = (
            f"Final Evaluation: {experiment_name}\n"
            f"Structure: {structure_score}/10 ({structure_status})\n"
            f"Content: {content_score}/10 ({template_count}/{total_evaluated} templates)\n"
            f"Simulation: {simulation_score}/10 ({simulation_status}, Complexity: {complexity}/10)\n"
            f"Overall Score: {final_score:.1f}/100"
        )
        
        # Generate report using LLM
        prompt = self.basic_prompt_template.format(
            experiment_name=experiment_name,
            structure_score=structure_score,
            structure_status=structure_status,
            missing_files=missing_files if missing_files else "None",
            missing_dirs=missing_dirs if missing_dirs else "None",
            content_score=content_score,
            files_evaluated=total_evaluated,
            total_files=total_evaluated + self.evaluation_results.get('content', {}).get('files_missing', 0),
            template_files=template_count,
            template_percentage=f"{template_percentage:.1f}",
            simulation_score=simulation_score,
            simulation_status=simulation_status,
            complexity=complexity,
            libraries=libraries
        )
        
        try:
            report = super().get_output()
            
            # Clean up the report by removing prompt acknowledgments and triple backticks
            report_lines = report.split('\n')
            cleaned_lines = []
            skip_line = False
            skip_json = False
            
            for line in report_lines:
                # Skip acknowledgment lines
                if "I will generate" in line or "Here's the" in line or "Okay," in line:
                    continue
                    
                # Skip markdown code blocks and their content
                if "```" in line:
                    skip_json = not skip_json
                    continue
                    
                # Include the line if we're not skipping
                if not skip_json:
                    cleaned_lines.append(line)
                    
            # Rejoin cleaned lines
            report = '\n'.join(cleaned_lines)
        except Exception as e:
            # Fallback report if LLM fails
            report = f"""
# Virtual Lab Quality Report: {experiment_name}

## Executive Summary

This report evaluates the quality of the Virtual Lab experiment "{experiment_name}". The overall quality score is **{final_score:.1f}/100**.

## Strengths
- [Automated evaluation complete]

## Areas for Improvement
- {missing_files if missing_files else "No missing files"}
- {missing_dirs if missing_dirs else "No missing directories"}
- {f"{template_count} of {total_evaluated} content files appear to be templates" if template_count > 0 else ""}

## Detailed Assessment

### 1. Structure Evaluation
Structure score: {structure_score}/10 ({structure_status})

### 2. Content Evaluation
Content score: {content_score}/10 ({template_count}/{total_evaluated} files are templates)

### 3. Simulation Evaluation
Simulation score: {simulation_score}/10 ({simulation_status}, Complexity: {complexity}/10)

## Recommendations
1. Complete missing files and directories
2. Replace template content with actual content
3. Improve simulation implementation

## Conclusion
This report was generated automatically. The quality assessment tool encountered an error generating the detailed report.
"""
        
        return {
            "final_score": final_score,
            "component_scores": {
                "structure": structure_score * 10,  # Scale to 0-100
                "content": content_score * 10,      # Scale to 0-100
                "simulation": simulation_score * 10  # Scale to 0-100
            },
            "report": report,
            "experiment_name": experiment_name,
            "template_percentage": template_percentage
        }