import os
import json
import re
import subprocess
import tempfile
import shutil
from difflib import SequenceMatcher
from BaseAgent import BaseAgent

class ContentEvaluationAgent(BaseAgent):
    role = "Content Quality Evaluator"
    
    # Only for non-template content evaluation
    evaluation_prompt_template = """
You are an educational content evaluator for Virtual Labs.

Evaluate this NON-TEMPLATE content file:
FILE: {file_name}
CONTENT: {content}

This content has been verified as genuine educational content (not template).

EVALUATION CRITERIA (Score 1-10):
1. Educational Value: Teaching effectiveness and learning value
2. Completeness: Thoroughness and coverage
3. Accuracy: Technical correctness
4. Organization: Structure and logical flow
5. Clarity: Language clarity and readability

SCORING:
- Basic genuine content: 4-6
- Good educational content: 7-8
- Excellent comprehensive content: 9-10

Respond in JSON only:
{{
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
    
    def __init__(self, repo_path, template_repo_url="https://github.com/virtual-labs/ph3-exp-template"):
        self.repo_path = repo_path
        self.template_repo_url = template_repo_url
        self.template_cache_dir = None
        self.template_content_cache = {}
        self.template_comparison_enabled = True
        super().__init__(self.role, basic_prompt=self.evaluation_prompt_template, context=None)
        
        # Initialize template repository
        self._initialize_template_repo()
    
    def _initialize_template_repo(self):
        """Initialize and cache template repository"""
        try:
            self.template_cache_dir = tempfile.mkdtemp(prefix="vlabs_template_")
            
            result = subprocess.run([
                'git', 'clone', '--depth', '1', self.template_repo_url, self.template_cache_dir
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                print(f"Warning: Failed to clone template repository: {result.stderr}")
                self.template_comparison_enabled = False
                return
            
            self._cache_template_contents()
            
        except Exception as e:
            print(f"Warning: Template repository initialization failed: {str(e)}")
            self.template_comparison_enabled = False
    
    def _cache_template_contents(self):
        """Cache template file contents for comparison"""
        if not self.template_cache_dir or not os.path.exists(self.template_cache_dir):
            return
        
        template_files = [
            "README.md", "experiment/aim.md", "experiment/theory.md", 
            "experiment/procedure.md", "experiment/references.md",
            "experiment/experiment-name.md", "experiment/contributors.md"
        ]
        
        for file_path in template_files:
            full_path = os.path.join(self.template_cache_dir, file_path)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        self.template_content_cache[file_path] = f.read().strip()
                except:
                    continue
        
        experiment_dir = os.path.join(self.template_cache_dir, "experiment")
        if os.path.exists(experiment_dir):
            for root, dirs, files in os.walk(experiment_dir):
                for file in files:
                    if file.lower().endswith('.md'):
                        relative_path = os.path.relpath(os.path.join(root, file), self.template_cache_dir)
                        if relative_path not in self.template_content_cache:
                            try:
                                with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                                    self.template_content_cache[relative_path] = f.read().strip()
                            except:
                                continue
    
    def _is_template_content(self, file_path, content):
        """Determine if content is template using comparison and patterns"""
        if not content:
            return True, 0.0, "Empty content"
        
        # Method 1: Template comparison (primary method)
        if self.template_comparison_enabled:
            template_result = self._compare_with_template(file_path, content)
            if template_result["comparison_available"]:
                similarity_score = template_result["similarity_score"]
                
                # High similarity threshold for template detection
                if similarity_score > 0.75:
                    return True, similarity_score, f"High similarity to template ({similarity_score:.2f})"
                elif similarity_score > 0.5:
                    # Medium similarity - check other indicators
                    pattern_result = self._pattern_based_template_check(content)
                    if pattern_result:
                        return True, similarity_score, f"Medium similarity + pattern match ({similarity_score:.2f})"
                elif similarity_score < 0.3:
                    # Very low similarity - likely genuine content
                    return False, similarity_score, f"Low similarity to template ({similarity_score:.2f})"
        
        # Method 2: Pattern-based detection (fallback)
        pattern_result = self._pattern_based_template_check(content)
        if pattern_result:
            return True, 0.0, "Pattern-based template detection"
        
        # Method 3: Content analysis for very short files
        if len(content.split()) < 10:
            if self._is_generic_short_content(content):
                return True, 0.0, "Generic short content"
        
        return False, 0.0, "Genuine content detected"
    
    def _compare_with_template(self, file_path, content):
        """Compare file content with template counterpart"""
        if not self.template_comparison_enabled or not content:
            return {"similarity_score": 0, "comparison_available": False}
        
        # Find corresponding template file
        template_content = self.template_content_cache.get(file_path)
        
        if not template_content:
            file_name = os.path.basename(file_path)
            for template_path, template_text in self.template_content_cache.items():
                if os.path.basename(template_path) == file_name:
                    template_content = template_text
                    break
        
        if not template_content:
            return {"similarity_score": 0, "comparison_available": False}
        
        # Calculate similarity metrics
        similarities = self._calculate_similarity_metrics(content, template_content)
        
        return {
            "similarity_score": similarities["overall_similarity"],
            "comparison_available": True,
            "metrics": similarities
        }
    
    def _calculate_similarity_metrics(self, content, template_content):
        """Calculate comprehensive similarity metrics"""
        # 1. Text similarity
        text_similarity = SequenceMatcher(None, content.lower(), template_content.lower()).ratio()
        
        # 2. Line overlap
        content_lines = set(line.strip().lower() for line in content.split('\n') if line.strip())
        template_lines = set(line.strip().lower() for line in template_content.split('\n') if line.strip())
        
        line_overlap = len(content_lines.intersection(template_lines)) / len(template_lines) if template_lines else 0
        
        # 3. Structure similarity
        structure_similarity = self._compare_markdown_structure(content, template_content)
        
        # 4. Placeholder indicators
        placeholder_score = self._count_placeholder_indicators(content, template_content)
        
        # 5. Length ratio
        length_ratio = min(len(content), len(template_content)) / max(len(content), len(template_content), 1)
        
        # Weighted overall similarity
        overall_similarity = (
            text_similarity * 0.3 +
            line_overlap * 0.25 +
            structure_similarity * 0.2 +
            placeholder_score * 0.15 +
            length_ratio * 0.1
        )
        
        return {
            "text_similarity": text_similarity,
            "line_overlap": line_overlap,
            "structure_similarity": structure_similarity,
            "placeholder_score": placeholder_score,
            "length_ratio": length_ratio,
            "overall_similarity": overall_similarity
        }
    
    def _compare_markdown_structure(self, content, template_content):
        """Compare markdown structure"""
        try:
            content_headers = re.findall(r'^#+\s+(.+)$', content, re.MULTILINE)
            template_headers = re.findall(r'^#+\s+(.+)$', template_content, re.MULTILINE)
            
            if not template_headers:
                return 0.5
            
            content_headers_lower = [h.lower().strip() for h in content_headers]
            template_headers_lower = [h.lower().strip() for h in template_headers]
            
            common_headers = len(set(content_headers_lower).intersection(set(template_headers_lower)))
            return min(common_headers / len(template_headers), 1.0)
        except:
            return 0.5
    
    def _count_placeholder_indicators(self, content, template_content):
        """Count placeholder indicators"""
        template_placeholders = re.findall(
            r'\b(?:experiment name|lab name|discipline name|write the|add your|enter your|please fill|replace with)\b', 
            template_content.lower()
        )
        content_placeholders = re.findall(
            r'\b(?:experiment name|lab name|discipline name|write the|add your|enter your|please fill|replace with)\b', 
            content.lower()
        )
        
        if not template_placeholders:
            return 0.0
        
        common_placeholders = len(set(content_placeholders).intersection(set(template_placeholders)))
        return common_placeholders / len(template_placeholders)
    
    def _pattern_based_template_check(self, content):
        """Pattern-based template detection (fallback)"""
        content_lower = content.lower()
        
        # Strong template indicators
        strong_patterns = [
            "write the aim of the experiment here",
            "write the theory required for this experiment",
            "explain the procedure to be followed",
            "add references in apa format here",
            "experiment name",
            "discipline name",
            "lab name"
        ]
        
        # Check for strong patterns
        for pattern in strong_patterns:
            if pattern in content_lower:
                return True
        
        # Check for multiple weak patterns
        weak_patterns = ["add your", "enter your", "please fill", "replace with", "todo", "to-do"]
        weak_count = sum(1 for pattern in weak_patterns if pattern in content_lower)
        
        return weak_count >= 2
    
    def _is_generic_short_content(self, content):
        """Check if short content is generic"""
        content_clean = re.sub(r'[#*_`-]', '', content).strip().lower()
        generic_terms = ["experiment", "lab", "virtual", "simulation", "test", "demo"]
        
        words = content_clean.split()
        if len(words) <= 3:
            return any(term in content_clean for term in generic_terms)
        
        return False
    
    def _is_short_content_file(self, file_path, content):
        """Determine if file should be treated as short content"""
        if not content:
            return True
        
        short_files = ['experiment-name.md', 'contributors.md', 'lab-name.md', 'discipline.md']
        file_name = os.path.basename(file_path).lower()
        
        if any(short_file in file_name for short_file in short_files):
            return True
        
        word_count = len(content.split())
        return word_count < 20
    
    def _read_file_content(self, file_path):
        full_path = os.path.join(self.repo_path, file_path)
        if not os.path.exists(full_path):
            return None
        try:
            with open(full_path, 'r', encoding='utf-8') as file:
                return file.read().strip() or None
        except:
            return None
    
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
                    if isinstance(parsed, dict) and 'scores' in parsed:
                        return parsed
                except:
                    continue
        return None
    
    def _validate_scores(self, json_data):
        if not isinstance(json_data, dict) or 'scores' not in json_data:
            return None
        
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
            "scores": valid_scores,
            "average_score": round(average_score, 1),
            "feedback": json_data.get('feedback', 'Evaluation completed')
        }
    
    def _evaluate_single_file(self, file_path):
        """Evaluate a single content file"""
        content = self._read_file_content(file_path)
        
        if not content:
            return {
                "file": file_path,
                "status": "Error",
                "reason": "File not found or empty",
                "average_score": 0,
                "scores": {},
                "is_template": True,
                "is_short_content": False,
                "template_similarity": 0,
                "feedback": "File could not be read"
            }
        
        # Step 1: Template detection (no LLM needed)
        is_template, similarity_score, detection_reason = self._is_template_content(file_path, content)
        is_short = self._is_short_content_file(file_path, content)
        
        # Step 2: Handle based on template status and content length
        if is_template:
            # Template content - no detailed scoring needed
            return {
                "file": file_path,
                "status": "Evaluated",
                "average_score": 2.0 if is_short else 1.5,
                "scores": {},
                "is_template": True,
                "is_short_content": is_short,
                "template_similarity": similarity_score,
                "feedback": f"Template content detected: {detection_reason}"
            }
        
        elif is_short:
            # Short genuine content - simple scoring
            return {
                "file": file_path,
                "status": "Evaluated",
                "average_score": 6.0,  # Reasonable score for short genuine content
                "scores": {},
                "is_template": False,
                "is_short_content": True,
                "template_similarity": similarity_score,
                "feedback": "Short genuine content - basic scoring applied"
            }
        
        else:
            # Non-template substantial content - full LLM evaluation
            return self._evaluate_with_llm(file_path, content, similarity_score)
    
    def _evaluate_with_llm(self, file_path, content, similarity_score):
        """Evaluate substantial non-template content with LLM"""
        content_preview = content[:2500] + "..." if len(content) > 2500 else content
        
        for attempt in range(2):
            try:
                if attempt == 0:
                    prompt = self.evaluation_prompt_template.format(
                        file_name=file_path,
                        content=content_preview
                    )
                else:
                    prompt = f"Evaluate educational content: {file_path}\n{content_preview[:1500]}\nJSON with scores, average_score, feedback required."
                
                self.context = prompt
                response = super().get_output()
                
                json_data = self._extract_json_from_response(response)
                if json_data:
                    validated_data = self._validate_scores(json_data)
                    if validated_data:
                        return {
                            "file": file_path,
                            "status": "Evaluated",
                            "is_template": False,
                            "is_short_content": False,
                            "template_similarity": similarity_score,
                            **validated_data
                        }
                
                if attempt == 0:
                    continue
                    
            except Exception as e:
                if attempt == 0:
                    continue
        
        # LLM failed - use rule-based scoring for non-template content
        return self._rule_based_scoring(file_path, content, similarity_score)
    
    def _rule_based_scoring(self, file_path, content, similarity_score):
        """Rule-based scoring for non-template content when LLM fails"""
        word_count = len(content.split())
        
        # Base score for genuine content
        if word_count > 500:
            base_score = 7
        elif word_count > 200:
            base_score = 6
        elif word_count > 100:
            base_score = 5
        else:
            base_score = 4
        
        # Adjust for content characteristics
        bonus = 0
        if "#" in content:  # Has structure
            bonus += 1
        if any(marker in content for marker in ["-", "*", "1."]):  # Has lists
            bonus += 1
        if "[" in content and "]" in content:  # Has links
            bonus += 1
        
        final_score = min(base_score + bonus, 9)
        
        scores = {
            "Educational Value": final_score,
            "Completeness": final_score,
            "Accuracy": final_score,
            "Organization": final_score,
            "Clarity": final_score
        }
        
        return {
            "file": file_path,
            "status": "Evaluated",
            "average_score": final_score,
            "scores": scores,
            "is_template": False,
            "is_short_content": False,
            "template_similarity": similarity_score,
            "feedback": "Rule-based scoring for genuine content (LLM unavailable)"
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
                "template_comparison_enabled": self.template_comparison_enabled,
                "status": "No content files found"
            }
        
        file_evaluations = {}
        total_score = 0
        evaluated_count = 0
        template_count = 0
        short_content_count = 0
        high_similarity_count = 0
        
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
                
                if evaluation.get('template_similarity', 0) > 0.7:
                    high_similarity_count += 1
        
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
            "high_similarity_count": high_similarity_count,
            "template_comparison_enabled": self.template_comparison_enabled,
            "status": f"Evaluated {evaluated_count}/{len(content_files)} content files"
        }
    
    def __del__(self):
        """Cleanup template cache directory"""
        if hasattr(self, 'template_cache_dir') and self.template_cache_dir and os.path.exists(self.template_cache_dir):
            try:
                shutil.rmtree(self.template_cache_dir)
            except:
                pass