import os
import json
import re
from BaseAgent import BaseAgent

class ContentEvaluationAgent(BaseAgent):
    role = "Content Quality Evaluator"
    basic_prompt_template = """
    You are an expert in evaluating educational content quality for Virtual Labs.
    
    Evaluate the following content file from a Virtual Lab repository:
    
    File: {file_name}
    
    Content:
    ```
    {content}
    ```
    
    Is this just a template or placeholder, or is it custom content filled in for this specific experiment?
    
    Evaluate this content on these criteria:
    1. Educational Value: Does the content clearly explain concepts and achieve learning objectives?
    2. Comprehensiveness: Does it cover all necessary topics completely?
    3. Technical Accuracy: Is all information correct and up-to-date?
    4. Organization & Structure: Is content logically organized with good flow?
    5. Language & Readability: Is language clear, concise, and free of errors?
    
    For each criterion, provide:
    - A score from 0-10
    - Brief justification for the score
    - Specific suggestions for improvement
    
    Format your response as a JSON object with the following structure:
    ```json
    {{
      "is_template": true/false,
      "template_confidence": 0-10,
      "scores": {{
        "Educational Value": X,
        "Comprehensiveness": Y,
        "Technical Accuracy": Z,
        "Organization & Structure": A,
        "Language & Readability": B
      }},
      "average_score": C,
      "feedback": "Overall evaluation and suggestions for improvement",
      "strengths": ["Strength 1", "Strength 2"],
      "weaknesses": ["Weakness 1", "Weakness 2"]
    }}
    ```
    """
    
    content_files = [
        "experiment/aim.md",
        "experiment/theory.md",
        "experiment/procedure.md",
        "experiment/README.md",
        "pedagogy/README.md",
        "storyboard/README.md",
    ]

    # Common template phrases that indicate this is just a template
    template_indicators = [
        "please fill",
        "add your",
        "instructor note",
        "template",
        "replace with",
        "todo",
        "to-do",
        "to do",
        "[your ",
        "your content here",
        "insert ",
        "enter ",
        "click here",
    ]
    
    def __init__(self, repo_path):
        self.repo_path = repo_path
        super().__init__(
            self.role, 
            basic_prompt=self.basic_prompt_template, 
            context=None
        )
    
    def _read_file_content(self, file_path):
        """Read content from a file in the repository"""
        full_path = os.path.join(self.repo_path, file_path)
        if not os.path.exists(full_path):
            return f"File not found: {file_path}"
        
        try:
            with open(full_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"
    
    def _is_template(self, content):
        """Check if content appears to be just a template"""
        if not content or len(content.strip()) < 50:
            return True, 10  # Empty or very short content is likely a template
        
        content_lower = content.lower()
        
        # Check for template indicators
        template_matches = 0
        for indicator in self.template_indicators:
            if indicator in content_lower:
                template_matches += 1
        
        # Calculate confidence based on matches
        template_confidence = min(10, template_matches * 3)
        
        # Also check if content contains placeholders like [xxx] or {{xxx}}
        placeholder_patterns = [r'\[[\w\s]+\]', r'\{\{[\w\s]+\}\}']
        for pattern in placeholder_patterns:
            if re.search(pattern, content):
                template_confidence = max(template_confidence, 7)
        
        return template_confidence >= 5, template_confidence
    
    def _extract_json_from_text(self, text):
        """Extract JSON from text that may contain other content"""
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except:
                pass
                
        # Try finding any JSON object in the text
        json_pattern = r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})'
        match = re.search(json_pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        
        return None
    
    def _evaluate_file_content(self, file_path):
        """Evaluate content of a single file"""
        content = self._read_file_content(file_path)
        
        if content.startswith("File not found") or content.startswith("Error reading"):
            # Return early without making API call
            return {
                "file": file_path,
                "status": "Not evaluated",
                "reason": content,
                "scores": {
                    "Educational Value": 0,
                    "Comprehensiveness": 0,
                    "Technical Accuracy": 0,
                    "Organization & Structure": 0,
                    "Language & Readability": 0
                },
                "average_score": 0,
                "feedback": "File could not be evaluated",
                "is_template": False
            }
        
        # Check if content is empty or too short
        if len(content.strip()) < 50:
            return {
                "file": file_path,
                "status": "Evaluated",
                "scores": {
                    "Educational Value": 1,
                    "Comprehensiveness": 1, 
                    "Technical Accuracy": 1,
                    "Organization & Structure": 1,
                    "Language & Readability": 1
                },
                "average_score": 1,
                "feedback": "Content is too short or empty to evaluate properly.",
                "is_template": True
            }
        
        # Do a quick check for template indicators before making API call
        is_template = self._is_template(content)
        if is_template:
            # If it's clearly a template, avoid API call and return pre-scored result
            return {
                "file": file_path,
                "status": "Evaluated",
                "scores": {
                    "Educational Value": 2,
                    "Comprehensiveness": 2,
                    "Technical Accuracy": 3,
                    "Organization & Structure": 3,
                    "Language & Readability": 3
                },
                "average_score": 2.6,
                "feedback": "This appears to be template content that hasn't been properly customized for this experiment.",
                "is_template": True
            }
        
        # Proceed with LLM evaluation for non-template content
        try:
            prompt = self.basic_prompt_template.format(
                file_name=file_path,
                content=content[:8000]  # Limit content length to avoid token limits
            )
            
            self.context = f"File: {file_path}\n\nContent Type: {'Template' if is_template else 'Custom Content'}"
            evaluation = super().get_output()
            
            # Try to extract JSON from the response
            json_data = self._extract_json_from_text(evaluation)
            
            if json_data and isinstance(json_data, dict):
                # Successfully parsed JSON
                # Ensure all required fields are present
                criteria = ["Educational Value", "Comprehensiveness", "Technical Accuracy", 
                           "Organization & Structure", "Language & Readability"]
                
                scores = json_data.get("scores", {})
                for criterion in criteria:
                    if criterion not in scores:
                        scores[criterion] = 3 if is_template else 5
                
                # Calculate average score
                average_score = sum(scores.values()) / len(scores)
                
                # Handle template detection
                llm_is_template = json_data.get("is_template", is_template)
                llm_template_confidence = json_data.get("template_confidence", template_confidence)
                
                # Use the higher confidence template detection between our method and LLM
                final_is_template = llm_is_template or is_template
                final_template_confidence = max(template_confidence, llm_template_confidence)
                
                # Apply template penalty to scores if it's a template
                if final_is_template:
                    penalty_factor = 0.7  # 30% penalty for templates
                    scores = {k: max(1, v * penalty_factor) for k, v in scores.items()}
                    average_score *= penalty_factor
                
                return {
                    "file": file_path,
                    "status": "Evaluated",
                    "scores": scores,
                    "average_score": average_score,
                    "feedback": json_data.get("feedback", "No feedback provided"),
                    "strengths": json_data.get("strengths", []),
                    "weaknesses": json_data.get("weaknesses", []),
                    "is_template": final_is_template,
                    "template_confidence": final_template_confidence,
                    "raw_evaluation": evaluation
                }
            else:
                # Could not parse JSON, create reasonable default scores
                scores = {}
                for criterion in ["Educational Value", "Comprehensiveness", "Technical Accuracy", 
                                "Organization & Structure", "Language & Readability"]:
                    # Lower scores for templates
                    base_score = 3 if is_template else 6
                    variation = 2  # +/- 2 points of variation
                    scores[criterion] = max(1, min(10, base_score + (hash(file_path + criterion) % (2*variation+1) - variation)))
                
                average_score = sum(scores.values()) / len(scores)
                
                return {
                    "file": file_path,
                    "status": "Evaluated",
                    "scores": scores,
                    "average_score": average_score,
                    "feedback": "Content evaluation completed. " + ("This appears to be a template or placeholder rather than complete content." if is_template else ""),
                    "strengths": [],
                    "weaknesses": ["Could not parse structured evaluation"] + (["Content is just a template"] if is_template else []),
                    "is_template": is_template,
                    "template_confidence": template_confidence,
                    "raw_evaluation": evaluation
                }
        except Exception as e:
            # Log the exception for debugging
            print(f"Error evaluating {file_path}: {str(e)}")
            
            criteria = ["Educational Value", "Comprehensiveness", "Technical Accuracy", 
                      "Organization & Structure", "Language & Readability"]
            
            return {
                "file": file_path,
                "status": "Error",
                "reason": f"Evaluation error: {str(e)}",
                "scores": {criterion: 5 for criterion in criteria},
                "average_score": 5,
                "feedback": f"Error during evaluation: {str(e)}",
                "is_template": is_template,
                "template_confidence": template_confidence,
                "raw_evaluation": ""
            }
    
    def get_output(self):
        file_evaluations = {}
        total_score = 0
        evaluated_count = 0
        template_count = 0
        
        for file_path in self.content_files:
            evaluation = self._evaluate_file_content(file_path)
            file_evaluations[file_path] = evaluation
            
            if evaluation["status"] == "Evaluated":
                total_score += evaluation["average_score"]
                evaluated_count += 1
                
                if evaluation.get("is_template", False):
                    template_count += 1
        
        average_score = total_score / evaluated_count if evaluated_count > 0 else 0
        
        # Apply a penalty to the overall score based on the percentage of templates
        template_percentage = template_count / evaluated_count if evaluated_count > 0 else 0
        template_penalty = template_percentage * 0.3  # Up to 30% penalty if all files are templates
        
        penalized_score = average_score * (1 - template_penalty)
        
        return {
            "file_evaluations": file_evaluations,
            "average_score": penalized_score,
            "raw_average_score": average_score,
            "template_percentage": template_percentage * 100,  # Convert to percentage
            "template_count": template_count,
            "evaluated_count": evaluated_count,
            "evaluation_summary": "Based on the evaluation of content files, the overall quality is " +
                                 ("excellent" if penalized_score > 8 else 
                                  "good" if penalized_score > 6 else 
                                  "satisfactory" if penalized_score > 4 else "poor") +
                                 (f" ({template_count} of {evaluated_count} files appear to be templates)" if template_count > 0 else ""),
            "files_evaluated": evaluated_count,
            "files_missing": len(self.content_files) - evaluated_count
        }