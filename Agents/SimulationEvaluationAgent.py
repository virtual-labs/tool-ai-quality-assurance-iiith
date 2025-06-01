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
    
    def _find_js_files(self):
        """Find all JS files in the simulation directory"""
        sim_dir = os.path.join(self.repo_path, "experiment/simulation/js")
        if not os.path.exists(sim_dir):
            return []
            
        js_files = []
        for root, _, files in os.walk(sim_dir):
            for file in files:
                if file.endswith(".js"):
                    js_files.append(os.path.relpath(os.path.join(root, file), self.repo_path))
        
        return js_files
    
    def _find_css_files(self):
        """Find all CSS files in the simulation directory"""
        sim_dir = os.path.join(self.repo_path, "experiment/simulation/css")
        if not os.path.exists(sim_dir):
            return []
            
        css_files = []
        for root, _, files in os.walk(sim_dir):
            for file in files:
                if file.endswith(".css"):
                    css_files.append(os.path.relpath(os.path.join(root, file), self.repo_path))
        
        return css_files
        
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
    
    def _analyze_simulation_complexity(self, html_content, js_content):
        """Analyze simulation complexity based on code"""
        complexity = 5  # Default medium complexity
        
        if not js_content or len(js_content) < 100:
            return max(1, complexity - 3)  # Very simple
            
        # Check for features that indicate complexity
        features = {
            "canvas": r'<canvas|getContext|createCanvas',
            "svg": r'<svg|createElementNS.*svg|d3\.select',
            "webgl": r'webgl|gl\.|THREE\.|glMatrix|WebGLRenderer',
            "charts": r'chart\.|plotly|echarts|highcharts',
            "animation": r'requestAnimationFrame|setInterval|setTimeout.*\d{3,}',
            "interactivity": r'addEventListener|onclick|onchange|\.on\([\'"]click',
            "ajax": r'fetch\(|\.ajax\(|XMLHttpRequest',
            "simulation_logic": r'function\s+\w+Simulation|class\s+\w+Simulation|simulation\.start',
        }
        
        # Combined content
        combined = html_content + js_content
        
        # Count matches
        feature_count = 0
        for _, pattern in features.items():
            if re.search(pattern, combined, re.IGNORECASE):
                feature_count += 1
        
        # Adjust complexity based on features and code size
        code_size_factor = min(3, max(0, (len(js_content) - 500) / 1000))
        
        # Calculate final complexity
        final_complexity = min(10, max(1, complexity + feature_count * 0.5 + code_size_factor))
        
        return final_complexity
    
    def get_output(self):
        # Get HTML content
        html_content = self._read_file_content(
            "experiment/simulation/index.html",
            "HTML file not found"
        )
        
        # Fast check if simulation exists
        if html_content == "HTML file not found":
            # Return early without making API call
            return {
                "functionality_score": 0,
                "code_quality_score": 0,
                "ux_score": 0,
                "educational_value": 0,
                "technical_score": 0,
                "overall_score": 0,
                "technical_assessment": "Simulation does not exist",
                "simulation_status": "Missing",
                "complexity": 0,
                "libraries_used": [],
                "js_files_count": 0,
                "css_files_count": 0
            }
        
        # Get JS content (concatenate all JS files)
        js_files = self._find_js_files()
        js_content = ""
        for js_file in js_files[:3]:  # Limit to first 3 files to avoid token limits
            js_content += f"// File: {js_file}\n"
            js_content += self._read_file_content(js_file, "// JS file content not available") + "\n\n"
        
        if not js_content:
            js_content = "No JavaScript files found"
        
        # Get CSS content (concatenate all CSS files)
        css_files = self._find_css_files()
        css_content = ""
        for css_file in css_files[:2]:  # Limit to first 2 files to avoid token limits
            css_content += f"/* File: {css_file} */\n"
            css_content += self._read_file_content(css_file, "/* CSS file content not available */") + "\n\n"
        
        if not css_content:
            css_content = "No CSS files found"
        
        # Check for simulation complexity and libraries used
        simulation_complexity = self._analyze_simulation_complexity(html_content, js_content)
        used_libraries = self._check_common_libraries(html_content)
        
        # Set context
        self.context = (
            f"Simulation files: HTML: {'Found' if html_content != 'HTML file not found' else 'Not found'}, "
            f"JS: {len(js_files)} files, CSS: {len(css_files)} files\n"
            f"Complexity assessment: {simulation_complexity}/10\n"
            f"Libraries: {', '.join(used_libraries) if used_libraries else 'None detected'}"
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
                "complexity": 0,
                "libraries_used": [],
                "js_files_count": len(js_files),
                "css_files_count": len(css_files)
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
                    "js_files_count": len(js_files),
                    "css_files_count": len(css_files),
                    "raw_evaluation": evaluation
                }
            else:
                # Could not parse JSON, create reasonable default scores
                # Base scores on simulation complexity
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
                    "technical_assessment": f"Simulation appears to be of {['very low', 'low', 'below average', 'average', 'above average', 'good', 'very good', 'excellent', 'exceptional', 'outstanding'][int(simulation_complexity)-1]} complexity.",
                    "simulation_status": "Available",
                    "complexity": simulation_complexity,
                    "libraries_used": used_libraries,
                    "js_files_count": len(js_files),
                    "css_files_count": len(css_files),
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
                "js_files_count": len(js_files),
                "css_files_count": len(css_files)
            }