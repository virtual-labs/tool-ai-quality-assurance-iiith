import os
import json
import asyncio
import tempfile
import shutil
import base64
import socket
from playwright.async_api import async_playwright
from BaseAgent import BaseAgent

class PlaywrightTestingAgent(BaseAgent):
    role = "Browser Functionality Tester"
    
    # AI prompt to decide what to test
    test_planning_prompt = """
You are an expert in testing Virtual Labs simulations in real browsers.

SIMULATION ANALYSIS:
- Experiment Name: {experiment_name}
- Interactive Elements: {interactive_elements}
- JavaScript Functions: {js_analysis}
- HTML Content Preview: {html_preview}

Based on this Virtual Labs simulation, create a comprehensive browser test plan.

Return a JSON with test scenarios:
{{
  "basic_tests": [
    {{"name": "page_load", "description": "Check if simulation loads properly"}},
    {{"name": "ui_elements", "description": "Verify all buttons and inputs are visible"}}
  ],
  "interaction_tests": [
    {{"name": "button_clicks", "selectors": ["#start-btn", ".calculate"], "description": "Test button functionality"}},
    {{"name": "input_fields", "selectors": ["input[type='range']", "input[type='number']"], "description": "Test input interactions"}}
  ],
  "calculation_tests": [
    {{"name": "result_verification", "description": "Verify calculation accuracy", "test_values": {{"input1": 5, "input2": 10, "expected": 50}}}}
  ],
  "visual_tests": [
    {{"name": "responsive_design", "description": "Test mobile and desktop views"}},
    {{"name": "graph_display", "description": "Check if graphs/charts render properly"}}
  ]
}}
"""
    
    def __init__(self, repo_path):
        self.repo_path = repo_path
        self.simulation_url = None
        self.test_results = {}
        self.screenshots = {}  # NEW: Store screenshots with base64 encoding
        self.execution_timeline = []  # NEW: Track test execution timeline
        self.httpd = None
        super().__init__(
            self.role,
            basic_prompt=self.test_planning_prompt,
            context=""
        )
    
    def _find_free_port(self):
        """Find a free port for the local server"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port
    
    def _start_local_server(self):
        """Start a local HTTP server for the simulation"""
        import http.server
        import socketserver
        import threading
        import time
        from functools import partial
        
        sim_path = os.path.join(self.repo_path, "experiment", "simulation")
        if not os.path.exists(sim_path):
            return None
        
        try:
            # Find a free port
            port = self._find_free_port()
            
            # Create a custom handler that serves from the simulation directory
            class CustomHandler(http.server.SimpleHTTPRequestHandler):
                def __init__(self, *args, directory=None, **kwargs):
                    self.directory = directory
                    super().__init__(*args, **kwargs)
                
                def translate_path(self, path):
                    # Override to serve from our simulation directory
                    path = super().translate_path(path)
                    # Replace the default serve directory with our simulation directory
                    rel_path = os.path.relpath(path, os.getcwd())
                    return os.path.join(self.directory, rel_path)
                
                def log_message(self, format, *args):
                    # Suppress server logs to reduce noise
                    pass
            
            # Create handler with simulation directory
            handler = partial(CustomHandler, directory=sim_path)
            
            # Create server
            self.httpd = socketserver.TCPServer(("", port), handler)
            
            # Start server in background thread
            server_thread = threading.Thread(target=self.httpd.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            
            self.simulation_url = f"http://localhost:{port}"
            time.sleep(1.5)  # Give server more time to start
            return self.simulation_url
            
        except Exception as e:
            print(f"Failed to start server: {e}")
            return None
    
    def _stop_local_server(self):
        """Stop the local HTTP server"""
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
                self.httpd = None
            except:
                pass
    
    def _get_simulation_context(self):
        """Get simulation context for AI test planning"""
        # Get experiment name
        experiment_name = "Unknown Experiment"
        try:
            name_file = os.path.join(self.repo_path, "experiment", "experiment-name.md")
            if os.path.exists(name_file):
                with open(name_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content and len(content) > 3:
                        experiment_name = content.replace('#', '').strip()
        except:
            pass
        
        # Get HTML preview
        html_content = ""
        html_file = os.path.join(self.repo_path, "experiment", "simulation", "index.html")
        if os.path.exists(html_file):
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()[:1000]  # First 1000 chars
            except:
                pass
        
        # Analyze interactive elements
        interactive_elements = []
        if html_content:
            import re
            inputs = len(re.findall(r'<input', html_content, re.IGNORECASE))
            buttons = len(re.findall(r'<button', html_content, re.IGNORECASE))
            canvas = len(re.findall(r'<canvas', html_content, re.IGNORECASE))
            forms = len(re.findall(r'<form', html_content, re.IGNORECASE))
            
            if inputs > 0:
                interactive_elements.append(f"Inputs ({inputs})")
            if buttons > 0:
                interactive_elements.append(f"Buttons ({buttons})")
            if canvas > 0:
                interactive_elements.append(f"Canvas ({canvas})")
            if forms > 0:
                interactive_elements.append(f"Forms ({forms})")
        
        return {
            "experiment_name": experiment_name,
            "interactive_elements": ", ".join(interactive_elements) if interactive_elements else "None detected",
            "js_analysis": "JavaScript files found" if os.path.exists(os.path.join(self.repo_path, "experiment", "simulation", "js")) else "No JavaScript",
            "html_preview": html_content[:500] if html_content else "No HTML content"
        }
    
    def _get_ai_test_plan(self, context):
        """Get AI-generated test plan"""
        try:
            prompt = self.test_planning_prompt.format(**context)
            self.context = prompt
            response = super().get_output()
            
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except Exception as e:
            print(f"AI test planning failed: {e}")
        
        # Fallback test plan
        return {
            "basic_tests": [
                {"name": "page_load", "description": "Check if simulation loads properly"},
                {"name": "ui_elements", "description": "Verify UI elements are visible"}
            ],
            "interaction_tests": [
                {"name": "button_clicks", "selectors": ["button", "input[type='button']"], "description": "Test button functionality"},
                {"name": "input_fields", "selectors": ["input"], "description": "Test input field interactions"}
            ],
            "visual_tests": [
                {"name": "responsive_design", "description": "Test responsive design"},
                {"name": "graph_display", "description": "Check for graphs and visual elements"}
            ]
        }
    
    async def _capture_screenshot(self, page, test_name, description=""):
        """Capture and store screenshot with base64 encoding"""
        try:
            screenshot_bytes = await page.screenshot(
                full_page=True,
                animations='disabled',  # Disable animations for consistent screenshots
                timeout=5000
            )
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            self.screenshots[test_name] = {
                "data": screenshot_b64,
                "description": description,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            return True
        except Exception as e:
            print(f"Failed to capture screenshot for {test_name}: {e}")
            return False
    
    async def _run_basic_tests(self, page, test_plan):
        """Run basic functionality tests with screenshot capture"""
        results = []
        
        for test in test_plan.get("basic_tests", []):
            start_time = asyncio.get_event_loop().time()
            
            try:
                if test["name"] == "page_load":
                    # Check if page loads without errors
                    response = await page.goto(self.simulation_url, wait_until='domcontentloaded', timeout=15000)
                    title = await page.title()
                    
                    # Capture initial page load screenshot
                    await self._capture_screenshot(page, "initial_page_load", "Initial page load state")
                    
                    # Wait for any dynamic content
                    await page.wait_for_timeout(2000)
                    
                    # Capture after dynamic content loads
                    await self._capture_screenshot(page, "page_fully_loaded", "Page after dynamic content loading")
                    
                    status = "PASS" if response and response.status < 400 and title else "FAIL"
                    results.append({
                        "test": "page_load",
                        "status": status,
                        "details": f"Page title: '{title}', HTTP Status: {response.status if response else 'No response'}",
                        "execution_time": round(asyncio.get_event_loop().time() - start_time, 2)
                    })
                
                elif test["name"] == "ui_elements":
                    # Check if basic UI elements exist
                    buttons = await page.query_selector_all("button")
                    inputs = await page.query_selector_all("input")
                    selects = await page.query_selector_all("select")
                    canvas = await page.query_selector_all("canvas")
                    
                    # Capture UI elements screenshot
                    await self._capture_screenshot(page, "ui_elements_detection", "UI elements identification")
                    
                    total_interactive = len(buttons) + len(inputs) + len(selects) + len(canvas)
                    
                    status = "PASS" if total_interactive > 0 else "FAIL"
                    results.append({
                        "test": "ui_elements",
                        "status": status,
                        "details": f"Found {len(buttons)} buttons, {len(inputs)} inputs, {len(selects)} select elements, {len(canvas)} canvas elements",
                        "execution_time": round(asyncio.get_event_loop().time() - start_time, 2)
                    })
                    
            except Exception as e:
                results.append({
                    "test": test["name"],
                    "status": "ERROR",
                    "details": f"Test execution error: {str(e)}",
                    "execution_time": round(asyncio.get_event_loop().time() - start_time, 2)
                })
        
        return results
    
    async def _run_interaction_tests(self, page, test_plan):
        """Run interaction tests with screenshot capture"""
        results = []
        
        for test in test_plan.get("interaction_tests", []):
            start_time = asyncio.get_event_loop().time()
            
            try:
                if test["name"] == "button_clicks":
                    # Test button clicking
                    selectors = test.get("selectors", ["button"])
                    clicked_count = 0
                    
                    # Capture before interaction
                    await self._capture_screenshot(page, "before_button_interactions", "State before button interactions")
                    
                    for selector in selectors:
                        elements = await page.query_selector_all(selector)
                        for element in elements[:3]:  # Test first 3 elements
                            try:
                                # Check if element is visible and clickable
                                is_visible = await element.is_visible()
                                if is_visible:
                                    await element.click(timeout=3000)
                                    clicked_count += 1
                                    await page.wait_for_timeout(500)  # Small delay between clicks
                            except Exception as click_error:
                                print(f"Click failed for element: {click_error}")
                                pass
                    
                    # Capture after interactions
                    await self._capture_screenshot(page, "after_button_interactions", f"State after clicking {clicked_count} buttons")
                    
                    status = "PASS" if clicked_count > 0 else "FAIL"
                    results.append({
                        "test": "button_clicks",
                        "status": status,
                        "details": f"Successfully clicked {clicked_count} interactive elements",
                        "execution_time": round(asyncio.get_event_loop().time() - start_time, 2)
                    })
                
                elif test["name"] == "input_fields":
                    # Test input field interactions
                    selectors = test.get("selectors", ["input"])
                    filled_count = 0
                    
                    # Capture before input interactions
                    await self._capture_screenshot(page, "before_input_interactions", "State before input field interactions")
                    
                    for selector in selectors:
                        elements = await page.query_selector_all(selector)
                        for element in elements[:3]:  # Test first 3 elements
                            try:
                                input_type = await element.get_attribute("type")
                                is_visible = await element.is_visible()
                                
                                if is_visible:
                                    if input_type in ["text", "number", "email", "password"]:
                                        await element.fill("test123")
                                        filled_count += 1
                                    elif input_type == "range":
                                        await element.fill("50")
                                        filled_count += 1
                                    elif input_type in ["checkbox", "radio"]:
                                        await element.click()
                                        filled_count += 1
                                    else:
                                        await element.click()
                                        filled_count += 1
                                    
                                    await page.wait_for_timeout(300)  # Small delay between interactions
                            except Exception as input_error:
                                print(f"Input interaction failed: {input_error}")
                                pass
                    
                    # Capture after input interactions
                    await self._capture_screenshot(page, "after_input_interactions", f"State after interacting with {filled_count} input fields")
                    
                    status = "PASS" if filled_count > 0 else "FAIL"
                    results.append({
                        "test": "input_fields",
                        "status": status,
                        "details": f"Successfully interacted with {filled_count} input fields",
                        "execution_time": round(asyncio.get_event_loop().time() - start_time, 2)
                    })
                    
            except Exception as e:
                results.append({
                    "test": test["name"],
                    "status": "ERROR",
                    "details": f"Interaction test error: {str(e)}",
                    "execution_time": round(asyncio.get_event_loop().time() - start_time, 2)
                })
        
        return results
    
    async def _run_visual_tests(self, page, test_plan):
        """Run visual and responsive tests with screenshot capture"""
        results = []
        
        for test in test_plan.get("visual_tests", []):
            start_time = asyncio.get_event_loop().time()
            
            try:
                if test["name"] == "responsive_design":
                    # Test mobile view
                    await page.set_viewport_size({"width": 375, "height": 667})  # iPhone size
                    await page.wait_for_timeout(1500)  # Wait for layout changes
                    await self._capture_screenshot(page, "mobile_view", "Mobile viewport (375x667)")
                    
                    # Test tablet view
                    await page.set_viewport_size({"width": 768, "height": 1024})  # Tablet size
                    await page.wait_for_timeout(1000)
                    await self._capture_screenshot(page, "tablet_view", "Tablet viewport (768x1024)")
                    
                    # Test desktop view
                    await page.set_viewport_size({"width": 1920, "height": 1080})  # Desktop size
                    await page.wait_for_timeout(1000)  # Wait for layout changes
                    await self._capture_screenshot(page, "desktop_view", "Desktop viewport (1920x1080)")
                    
                    results.append({
                        "test": "responsive_design",
                        "status": "PASS",
                        "details": "Successfully tested mobile (375x667), tablet (768x1024), and desktop (1920x1080) viewports",
                        "execution_time": round(asyncio.get_event_loop().time() - start_time, 2)
                    })
                
                elif test["name"] == "graph_display":
                    # Check for canvas or SVG elements (graphs)
                    canvas_elements = await page.query_selector_all("canvas")
                    svg_elements = await page.query_selector_all("svg")
                    chart_elements = await page.query_selector_all("[class*='chart'], [id*='chart'], [class*='graph'], [id*='graph']")
                    
                    # Capture visual elements screenshot
                    await self._capture_screenshot(page, "visual_elements", "Visual elements and graphs detection")
                    
                    total_visual = len(canvas_elements) + len(svg_elements) + len(chart_elements)
                    
                    status = "PASS" if total_visual > 0 else "FAIL"
                    results.append({
                        "test": "graph_display",
                        "status": status,
                        "details": f"Found {len(canvas_elements)} canvas, {len(svg_elements)} SVG, {len(chart_elements)} chart elements",
                        "execution_time": round(asyncio.get_event_loop().time() - start_time, 2)
                    })
                    
            except Exception as e:
                results.append({
                    "test": test["name"],
                    "status": "ERROR",
                    "details": f"Visual test error: {str(e)}",
                    "execution_time": round(asyncio.get_event_loop().time() - start_time, 2)
                })
        
        return results
    
    async def _run_browser_tests(self):
        """Run all browser tests using Playwright with comprehensive screenshot capture"""
        if not self.simulation_url:
            return {
                "status": "ERROR",
                "message": "Could not start local server for simulation",
                "test_results": [],
                "screenshots": {}
            }
        
        try:
            async with async_playwright() as p:
                # Launch browser with additional options
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage']  # Better compatibility
                )
                
                # Create page with enhanced settings
                page = await browser.new_page(
                    viewport={'width': 1280, 'height': 720},  # Standard viewport
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                )
                
                # Get test plan from AI
                context = self._get_simulation_context()
                test_plan = self._get_ai_test_plan(context)
                
                # Run all test categories
                basic_results = await self._run_basic_tests(page, test_plan)
                interaction_results = await self._run_interaction_tests(page, test_plan)
                visual_results = await self._run_visual_tests(page, test_plan)
                
                # Take a final comprehensive screenshot
                await self._capture_screenshot(page, "final_state", "Final simulation state after all tests")
                
                await browser.close()
                
                # Combine results
                all_results = basic_results + interaction_results + visual_results
                
                # Calculate metrics
                total_tests = len(all_results)
                passed_tests = len([r for r in all_results if r["status"] == "PASS"])
                failed_tests = len([r for r in all_results if r["status"] == "FAIL"])
                error_tests = len([r for r in all_results if r["status"] == "ERROR"])
                
                browser_score = (passed_tests / total_tests * 10) if total_tests > 0 else 0
                
                # Calculate total execution time
                total_execution_time = sum(r.get("execution_time", 0) for r in all_results)
                
                return {
                    "status": "SUCCESS",
                    "browser_score": round(browser_score, 1),
                    "total_tests": total_tests,
                    "passed_tests": passed_tests,
                    "failed_tests": failed_tests,
                    "error_tests": error_tests,
                    "test_results": all_results,
                    "test_plan_used": test_plan,
                    "simulation_context": context,
                    "screenshots": self.screenshots,  # Include all captured screenshots
                    "execution_metrics": {
                        "total_execution_time": round(total_execution_time, 2),
                        "average_test_time": round(total_execution_time / total_tests, 2) if total_tests > 0 else 0,
                        "screenshots_captured": len(self.screenshots),
                        "browser_engine": "Chromium",
                        "viewport_tested": ["375x667", "768x1024", "1920x1080"]
                    }
                }
                
        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"Browser testing failed: {str(e)}",
                "browser_score": 0,
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "error_tests": 0,
                "test_results": [],
                "screenshots": self.screenshots  # Include any screenshots captured before failure
            }
    
    def get_output(self):
        """Main method to run browser functionality tests"""
        # Check if simulation exists
        sim_path = os.path.join(self.repo_path, "experiment", "simulation", "index.html")
        if not os.path.exists(sim_path):
            return {
                "browser_score": 0,
                "status": "MISSING",
                "message": "No simulation found to test",
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "error_tests": 0,
                "test_results": [],
                "screenshots": {}
            }
        
        # Start local server
        server_url = self._start_local_server()
        if not server_url:
            return {
                "browser_score": 0,
                "status": "ERROR", 
                "message": "Could not start local server",
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "error_tests": 0,
                "test_results": [],
                "screenshots": {}
            }
        
        try:
            # Run async browser tests
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                # If loop is already running, create a new one
                import nest_asyncio
                nest_asyncio.apply()
                results = loop.run_until_complete(self._run_browser_tests())
            else:
                results = loop.run_until_complete(self._run_browser_tests())
            
            return results
            
        except Exception as e:
            return {
                "browser_score": 0,
                "status": "ERROR",
                "message": f"Testing failed: {str(e)}",
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "error_tests": 0,
                "test_results": [],
                "screenshots": self.screenshots  # Include any screenshots captured before failure
            }
        finally:
            # Stop local server
            self._stop_local_server()
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        self._stop_local_server()
