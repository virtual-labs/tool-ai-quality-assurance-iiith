import os
import json
import re
from BaseAgent import BaseAgent

class SimulationEvaluationAgent(BaseAgent):
    role = "Simulation Quality Evaluator"
    basic_prompt_template = """
    You are an expert in evaluating web-based educational simulations.
    
    Evaluate the following simulation code from a Virtual Lab repository:
    
    HTML:
    ```html
    {html_content}
    ```
    
    JavaScript:
    ```javascript
    {js_content}
    ```
    
    CSS:
    ```css
    {css_content}
    ```
    
    Evaluate this simulation on these criteria:
    1. Functionality: Does it appear to work properly? Are there any obvious bugs?
    2. Code Quality: Is the code well-organized, readable, and properly commented?
    3. User Experience: Is the simulation interactive and easy to use?
    4. Educational Value: Does it effectively demonstrate the concept being taught?
    5. Technical Implementation: Is it implemented using appropriate web technologies?
    
    For each criterion, provide:
    - A score from 0-10
    - Brief justification for the score
    - Specific suggestions for improvement
    
    Format your response as a JSON object with the following structure:
    ```json
    {{
      "scores": {{
        "Functionality": X,
        "Code Quality": Y,
        "User Experience": Z,
        "Educational Value": A,
        "Technical Implementation": B
      }},
      "overall_score": C,
      "technical_assessment": "Overall evaluation of the code",
      "improvement_suggestions": ["Suggestion 1", "Suggestion 2"]
    }}
    ```
    """
    
    def __init__(self, repo_path):
        self.repo_path = repo_path
        super().__init__(
            self.role, 
            basic_prompt=self.basic_prompt_template, 
            context=None
        )
    
    def _read_file_content(self, file_path, default=""):
        """Read content from a file in the repository"""
        full_path = os.path.join(self.repo_path, file_path)
        if not os.path.exists(full_path):
            return default
        
        try:
            with open(full_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            return default
    
    def _find_all_simulation_files(self):
        """Find ALL files in the simulation directory and subdirectories"""
        sim_dir = os.path.join(self.repo_path, "experiment/simulation")
        if not os.path.exists(sim_dir):
            return {
                "html_files": [],
                "js_files": [],
                "css_files": [],
                "image_files": [],
                "json_files": [],
                "other_files": []
            }
        
        files = {
            "html_files": [],
            "js_files": [],
            "css_files": [],
            "image_files": [],
            "json_files": [],
            "other_files": []
        }
        
        # Common file extensions
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.bmp']
        
        for root, dirs, file_list in os.walk(sim_dir):
            for file in file_list:
                file_path = os.path.relpath(os.path.join(root, file), self.repo_path)
                file_lower = file.lower()
                
                # Skip very large files and system files
                try:
                    full_file_path = os.path.join(root, file)
                    if os.path.getsize(full_file_path) > 5 * 1024 * 1024:  # Skip files larger than 5MB
                        continue
                    if file.startswith('.') or file.startswith('~'):  # Skip hidden/temp files
                        continue
                except:
                    continue
                
                if file_lower.endswith(('.html', '.htm')):
                    files["html_files"].append(file_path)
                elif file_lower.endswith('.js'):
                    files["js_files"].append(file_path)
                elif file_lower.endswith('.css'):
                    files["css_files"].append(file_path)
                elif file_lower.endswith('.json'):
                    files["json_files"].append(file_path)
                elif any(file_lower.endswith(ext) for ext in image_extensions):
                    files["image_files"].append(file_path)
                else:
                    files["other_files"].append(file_path)
        
        return files
    
    def _check_common_libraries(self, html_content):
        """Check if simulation uses common libraries"""
        libraries = {
            "jQuery": r'jquery(\.min)?\.js|\/jquery\/|cdn.*jquery',
            "Bootstrap": r'bootstrap(\.min)?\.js|\/bootstrap\/|bootstrap\.css',
            "D3.js": r'd3(\.min)?\.js|\/d3\/|d3\.v\d',
            "Three.js": r'three(\.min)?\.js|\/three\/|three\.',
            "p5.js": r'p5(\.min)?\.js|\/p5\/|processing',
            "Chart.js": r'chart(\.min)?\.js|\/chart\/|chart\.js',
            "MathJax": r'mathjax|\/mathjax\/',
            "React": r'react(\.min)?\.js|\/react\/|react-dom',
            "Vue": r'vue(\.min)?\.js|\/vue\/|vue@',
        }
        
        if not html_content:
            return []
            
        found_libraries = []
        for library, pattern in libraries.items():
            if re.search(pattern, html_content, re.IGNORECASE):
                found_libraries.append(library)
                
        return found_libraries
    
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
    
    def _analyze_simulation_complexity(self, html_content, js_content, all_files):
        """Analyze simulation complexity based on content and ALL file structure"""
        complexity_score = 1  # Base score
        
        if html_content and html_content != "HTML file not found":
            # Check HTML complexity
            if len(html_content) > 1000:
                complexity_score += 1
            if 'canvas' in html_content.lower():
                complexity_score += 2
            if 'svg' in html_content.lower():
                complexity_score += 1
            if re.search(r'class\s*=', html_content):
                complexity_score += 1
            if 'webgl' in html_content.lower():
                complexity_score += 2
        
        if js_content and js_content != "No JavaScript files found":
            # Check JS complexity
            js_length = len(js_content)
            if js_length > 500:
                complexity_score += 1
            if js_length > 2000:
                complexity_score += 1
            if js_length > 5000:
                complexity_score += 1
                
            # Check for complex JS features
            if re.search(r'function\s+\w+', js_content):
                complexity_score += 1
            if re.search(r'class\s+\w+', js_content):
                complexity_score += 1
            if 'addEventListener' in js_content:
                complexity_score += 1
            if re.search(r'setInterval|setTimeout', js_content):
                complexity_score += 1
            if re.search(r'fetch|XMLHttpRequest|ajax', js_content, re.IGNORECASE):
                complexity_score += 1
        
        # Factor in ALL files found in simulation directory
        total_files = sum(len(files) for files in all_files.values())
        if total_files > 5:
            complexity_score += 1
        if total_files > 10:
            complexity_score += 1
        if total_files > 20:
            complexity_score += 1
        
        # Factor in file diversity
        file_types = sum(1 for files in all_files.values() if files)
        complexity_score += min(3, file_types - 1)  # Bonus for having multiple file types, capped at 3
        
        # Bonus for having JSON configuration files
        if all_files["json_files"]:
            complexity_score += 1
        
        # Bonus for having multiple HTML files (multi-page simulation)
        if len(all_files["html_files"]) > 1:
            complexity_score += 1
        
        return min(10, complexity_score)  # Cap at 10

    def get_output(self):
        """Evaluate simulation quality by checking ALL files in simulation folder"""
        
        # Find all files in simulation directory and subdirectories
        all_files = self._find_all_simulation_files()
        
        # Get main HTML content
        html_content = self._read_file_content(
            "experiment/simulation/index.html",
            "HTML file not found"
        )
        
        # If no index.html, try to find any HTML file
        if html_content == "HTML file not found" and all_files["html_files"]:
            html_content = self._read_file_content(all_files["html_files"][0], "HTML file not found")
        
        # Get JS content (concatenate all JS files, but limit for API)
        js_files = all_files["js_files"]
        js_content = ""
        
        for js_file in js_files[:5]:  # Limit to first 5 JS files to avoid token limits
            js_content += f"// File: {js_file}\n"
            content = self._read_file_content(js_file, "// JS file content not available")
            js_content += content[:2000] + "\n\n"  # Limit each file to 2000 chars
        
        if not js_content:
            js_content = "No JavaScript files found"
        
        # Get CSS content (concatenate all CSS files)
        css_files = all_files["css_files"]
        css_content = ""
        
        for css_file in css_files[:3]:  # Limit to first 3 CSS files
            css_content += f"/* File: {css_file} */\n"
            content = self._read_file_content(css_file, "/* CSS file content not available */")
            css_content += content[:1500] + "\n\n"  # Limit each file to 1500 chars
        
        if not css_content:
            css_content = "No CSS files found"
        
        # Check for simulation complexity and libraries used
        simulation_complexity = self._analyze_simulation_complexity(html_content, js_content, all_files)
        used_libraries = self._check_common_libraries(html_content)
        
        # Enhanced context with ALL file information
        file_summary = []
        for file_type, files in all_files.items():
            if files:
                file_summary.append(f"{file_type}: {len(files)} files")
        
        self.context = (
            f"Simulation files found: {', '.join(file_summary)}\n"
            f"Total files: {sum(len(files) for files in all_files.values())}\n"
            f"Complexity assessment: {simulation_complexity}/10\n"
            f"Libraries: {', '.join(used_libraries) if used_libraries else 'None detected'}\n"
            f"File structure: {dict(all_files)}"
        )
        
        # Check if simulation exists
        if html_content == "HTML file not found" or len(js_files) == 0:
            return {
                "functionality_score": 0,
                "code_quality_score": 0,
                "ux_score": 0,
                "educational_value": 0,
                "technical_score": 0,
                "overall_score": 0,
                "technical_assessment": "Simulation does not exist or is incomplete",
                "simulation_status": "Missing",
                "complexity": simulation_complexity,
                "libraries_used": used_libraries,
                "all_files": all_files,
                "file_count": sum(len(files) for files in all_files.values())
            }
        
        # Evaluate simulation
        try:
            prompt = self.basic_prompt_template.format(
                html_content=html_content[:3000],  # Limit content length
                js_content=js_content[:3000],
                css_content=css_content[:2000]
            )
            
            evaluation = super().get_output()
            
            # Try to extract JSON from the response
            json_data = self._extract_json_from_text(evaluation)
            
            if json_data and isinstance(json_data, dict):
                # Successfully parsed JSON from LLM response
                scores = json_data.get("scores", {})
                
                # Ensure all criteria are present
                criteria = ["Functionality", "Code Quality", "User Experience", 
                          "Educational Value", "Technical Implementation"]
                
                for criterion in criteria:
                    if criterion not in scores:
                        # Assign score based on complexity for missing criteria
                        if criterion == "Functionality":
                            scores[criterion] = min(8, simulation_complexity)
                        elif criterion == "Code Quality":
                            scores[criterion] = min(7, simulation_complexity * 0.8)
                        else:
                            scores[criterion] = min(7, simulation_complexity * 0.9)
                
                # Get individual scores
                functionality_score = scores.get("Functionality", 0)
                code_quality_score = scores.get("Code Quality", 0)
                ux_score = scores.get("User Experience", 0)
                educational_value = scores.get("Educational Value", 0)
                technical_score = scores.get("Technical Implementation", 0)
                
                # Calculate overall score
                overall_score = json_data.get("overall_score", 
                                            sum(scores.values()) / len(scores) if scores else 0)
                
                return {
                    "functionality_score": functionality_score,
                    "code_quality_score": code_quality_score,
                    "ux_score": ux_score,
                    "educational_value": educational_value,
                    "technical_score": technical_score,
                    "overall_score": overall_score,
                    "technical_assessment": json_data.get("technical_assessment", "No assessment provided"),
                    "improvement_suggestions": json_data.get("improvement_suggestions", []),
                    "simulation_status": "Available",
                    "complexity": simulation_complexity,
                    "libraries_used": used_libraries,
                    "all_files": all_files,
                    "file_count": sum(len(files) for files in all_files.values()),
                    "raw_evaluation": evaluation
                }
            else:
                # Could not parse JSON, create reasonable default scores
                # Base scores on simulation complexity and file diversity
                functionality_score = min(8, simulation_complexity)
                code_quality_score = min(7, simulation_complexity * 0.8)
                ux_score = min(7, simulation_complexity * 0.9)
                educational_value = min(8, simulation_complexity * 0.9)
                technical_score = min(7, simulation_complexity * 0.8)
                
                overall_score = (functionality_score + code_quality_score + ux_score + 
                               educational_value + technical_score) / 5
                
                return {
                    "functionality_score": functionality_score,
                    "code_quality_score": code_quality_score,
                    "ux_score": ux_score,
                    "educational_value": educational_value,
                    "technical_score": technical_score,
                    "overall_score": overall_score,
                    "technical_assessment": f"Simulation appears to be of {['very low', 'low', 'below average', 'average', 'above average', 'good', 'very good', 'excellent', 'exceptional', 'outstanding'][int(simulation_complexity)-1]} complexity with {sum(len(files) for files in all_files.values())} total files.",
                    "simulation_status": "Available",
                    "complexity": simulation_complexity,
                    "libraries_used": used_libraries,
                    "all_files": all_files,
                    "file_count": sum(len(files) for files in all_files.values()),
                    "raw_evaluation": evaluation
                }
                
        except Exception as e:
            # Log the exception for debugging
            print(f"Error evaluating simulation: {str(e)}")
            
            return {
                "functionality_score": 0,
                "code_quality_score": 0,
                "ux_score": 0,
                "educational_value": 0,
                "technical_score": 0,
                "overall_score": 0,
                "technical_assessment": f"Error evaluating simulation: {str(e)}",
                "simulation_status": "Error",
                "complexity": simulation_complexity,
                "libraries_used": used_libraries,
                "all_files": all_files,
                "file_count": sum(len(files) for files in all_files.values())
            }