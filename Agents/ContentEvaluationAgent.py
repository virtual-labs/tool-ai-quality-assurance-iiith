import os
import json
import re
from BaseAgent import BaseAgent

class ContentEvaluationAgent(BaseAgent):
    role = "Content Quality Evaluator"
    
    basic_prompt_template = """
You are an educational content evaluator for Virtual Labs.

Evaluate this content file:
FILE: {file_name}
CONTENT: {content}

TEMPLATE DETECTION:
Template content contains:
- Placeholder text like "write the aim here", "add your content"
- Generic terms like "Experiment Name", "Discipline Name" without context
- Instructions to fill content rather than actual content

EVALUATION CRITERIA (Score 1-10):
1. Educational Value: Teaching effectiveness and learning value
2. Completeness: Thoroughness and coverage
3. Accuracy: Technical correctness
4. Organization: Structure and logical flow
5. Clarity: Language clarity and readability

SCORING:
- Template/placeholder: 1-3
- Basic genuine content: 4-6
- Good educational content: 7-8
- Excellent comprehensive content: 9-10

Respond in JSON only:
{{
  "is_template": boolean,
  "scores": {{
    "Educational Value": number,
    "Completeness": number,
    "Accuracy": number,
    "Organization": number,
    "Clarity": number
  }},
  "average_score": number,
  "feedback": "brief evaluation"
}}
"""
    
    short_content_template = """
Evaluate this short content file:
FILE: {file_name}
CONTENT: {content}

Determine if template or genuine content.
Template indicators: "Experiment Name", "Lab Name", placeholder text
Genuine indicators: Specific names, actual titles

JSON only:
{{
  "is_template": boolean,
  "is_short_content": true,
  "feedback": "brief explanation"
}}
"""
    
    def __init__(self, repo_path):
        self.repo_path = repo_path
        super().__init__(self.role, basic_prompt=self.basic_prompt_template, context=None)
    
    def _read_file_content(self, file_path):
        full_path = os.path.join(self.repo_path, file_path)
        if not os.path.exists(full_path):
            return None
        try:
            with open(full_path, 'r', encoding='utf-8') as file:
                return file.read().strip() or None
        except:
            return None
    
    def _is_short_content_file(self, file_path, content):
        if not content:
            return True
        
        short_files = ['experiment-name.md', 'contributors.md', 'lab-name.md', 'discipline.md']
        file_name = os.path.basename(file_path).lower()
        
        if any(short_file in file_name for short_file in short_files):
            return True
        
        word_count = len(content.split())
        line_count = len(content.split('\n'))
        
        if word_count < 20 and line_count < 5:
            content_clean = re.sub(r'[#*_`-]', '', content).strip()
            if len(content_clean.split()) < 15:
                return True
        
        return False
    
    def _extract_json_from_response(self, text):
        if not text:
            return None
        
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()
        
        patterns = [r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', r'\{.*?\}']
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    parsed = json.loads(match)
                    if isinstance(parsed, dict) and 'is_template' in parsed:
                        return parsed
                except:
                    continue
        return None
    
    def _validate_scores(self, json_data):
        if not isinstance(json_data, dict) or 'is_template' not in json_data:
            return None
        
        if json_data.get('is_short_content', False):
            return {
                "is_template": bool(json_data['is_template']),
                "is_short_content": True,
                "average_score": 5.0 if not json_data['is_template'] else 2.0,
                "scores": {},
                "feedback": json_data.get('feedback', 'Short content evaluation')
            }
        
        scores = json_data.get('scores', {})
        if not isinstance(scores, dict):
            return None
        
        criteria = ["Educational Value", "Completeness", "Accuracy", "Organization", "Clarity"]
        valid_scores = {}
        
        for criterion in criteria:
            if criterion in scores:
                score = scores[criterion]
                if isinstance(score, (int, float)) and 1 <= score <= 10:
                    valid_scores[criterion] = float(score)
        
        if len(valid_scores) < 4:
            return None
        
        if len(valid_scores) < 5:
            avg_existing = sum(valid_scores.values()) / len(valid_scores)
            for criterion in criteria:
                if criterion not in valid_scores:
                    valid_scores[criterion] = round(avg_existing, 1)
        
        average_score = sum(valid_scores.values()) / len(valid_scores)
        
        return {
            "is_template": bool(json_data['is_template']),
            "scores": valid_scores,
            "average_score": round(average_score, 1),
            "is_short_content": False,
            "feedback": json_data.get('feedback', 'Evaluation completed')
        }
    
    def _evaluate_single_file(self, file_path):
        content = self._read_file_content(file_path)
        
        if not content:
            return {
                "file": file_path,
                "status": "Error",
                "reason": "File not found or empty",
                "average_score": 0,
                "scores": {},
                "is_template": True,
                "feedback": "File could not be read"
            }
        
        is_short = self._is_short_content_file(file_path, content)
        content_preview = content[:2500] + "..." if len(content) > 2500 else content
        
        for attempt in range(2):
            try:
                if is_short:
                    prompt = self.short_content_template.format(
                        file_name=file_path, content=content_preview
                    )
                elif attempt == 0:
                    prompt = self.basic_prompt_template.format(
                        file_name=file_path, content=content_preview
                    )
                else:
                    prompt = f"Evaluate: {file_path}\nContent: {content_preview[:1500]}\nJSON format required with is_template, scores, average_score, feedback."
                
                self.context = prompt
                response = super().get_output()
                
                json_data = self._extract_json_from_response(response)
                if json_data:
                    validated_data = self._validate_scores(json_data)
                    if validated_data:
                        return {"file": file_path, "status": "Evaluated", **validated_data}
                
                if attempt == 0 and not is_short:
                    continue
                elif is_short:
                    break
            except Exception as e:
                if attempt == 0 and not is_short:
                    continue
                pass
        
        return self._emergency_fallback(file_path, content, is_short)
    
    def _emergency_fallback(self, file_path, content, is_short_content):
        content_lower = content.lower()
        template_phrases = [
            "write the aim", "add your", "enter your", "experiment name", 
            "discipline name", "lab name", "please fill"
        ]
        
        is_template = any(phrase in content_lower for phrase in template_phrases)
        
        if is_short_content:
            return {
                "file": file_path,
                "status": "Evaluated",
                "average_score": 5.0 if not is_template else 2.0,
                "scores": {},
                "is_template": is_template,
                "is_short_content": True,
                "feedback": "Emergency fallback: Short content evaluation"
            }
        
        word_count = len(content.split())
        base_score = 2 if is_template else (3 if word_count < 20 else (5 if word_count < 100 else 6))
        
        scores = {
            "Educational Value": base_score,
            "Completeness": base_score,
            "Accuracy": base_score + 1,
            "Organization": base_score,
            "Clarity": base_score
        }
        
        return {
            "file": file_path,
            "status": "Evaluated",
            "average_score": base_score,
            "scores": scores,
            "is_template": is_template,
            "is_short_content": False,
            "feedback": "Emergency fallback evaluation"
        }
    
    def _find_content_files(self):
        content_files = []
        
        priority_files = [
            "README.md", "experiment/aim.md", "experiment/theory.md", 
            "experiment/procedure.md", "experiment/references.md",
            "experiment/experiment-name.md", "experiment/contributors.md"
        ]
        
        for file_path in priority_files:
            full_path = os.path.join(self.repo_path, file_path)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                content_files.append(file_path)
        
        experiment_dir = os.path.join(self.repo_path, "experiment")
        if os.path.exists(experiment_dir):
            for root, dirs, files in os.walk(experiment_dir):
                for file in files:
                    if file.lower().endswith('.md'):
                        relative_path = os.path.relpath(os.path.join(root, file), self.repo_path)
                        
                        parts = os.path.normpath(relative_path).split(os.sep)
                        if 'simulation' in parts or 'images' in parts:
                            continue
                        
                        if relative_path not in content_files:
                            try:
                                file_size = os.path.getsize(os.path.join(root, file))
                                if file_size < 1024 * 1024:
                                    content_files.append(relative_path)
                            except:
                                continue
        
        return content_files
    
    def get_output(self):
        content_files = self._find_content_files()
        
        if not content_files:
            return {
                "average_score": 0,
                "file_evaluations": {},
                "total_files": 0,
                "evaluated_count": 0,
                "template_count": 0,
                "template_percentage": 0,
                "short_content_count": 0,
                "status": "No content files found"
            }
        
        file_evaluations = {}
        total_score = 0
        evaluated_count = 0
        template_count = 0
        short_content_count = 0
        
        for file_path in content_files:
            evaluation = self._evaluate_single_file(file_path)
            file_evaluations[file_path] = evaluation
            
            if evaluation['status'] == "Evaluated":
                total_score += evaluation['average_score']
                evaluated_count += 1
                
                if evaluation.get('is_template', False):
                    template_count += 1
                
                if evaluation.get('is_short_content', False):
                    short_content_count += 1
        
        average_score = total_score / evaluated_count if evaluated_count > 0 else 0
        template_percentage = (template_count / evaluated_count * 100) if evaluated_count > 0 else 0
        
        return {
            "average_score": round(average_score, 1),
            "file_evaluations": file_evaluations,
            "total_files": len(content_files),
            "evaluated_count": evaluated_count,
            "template_count": template_count,
            "template_percentage": round(template_percentage, 1),
            "short_content_count": short_content_count,
            "status": f"Evaluated {evaluated_count}/{len(content_files)} content files"
        }