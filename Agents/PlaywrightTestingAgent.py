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
        self.screenshots = {}  # Store screenshots with base64 encoding
        self.execution_timeline = []  # Track test execution timeline
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
        import os
        
        sim_path = os.path.join(self.repo_path, "experiment", "simulation")
        if not os.path.exists(sim_path):
            print(f"❌ Simulation directory not found: {sim_path}")
            return None
        
        # Check if index.html exists and is a file (not directory)
        index_file = os.path.join(sim_path, "index.html")
        if not os.path.exists(index_file):
            print(f"❌ index.html not found in {sim_path}")
            # List what files are actually there
            try:
                files = os.listdir(sim_path)
                print(f"📁 Files in simulation directory: {files}")
            except:
                pass
            return None
        
        if not os.path.isfile(index_file):
            print(f"❌ index.html exists but is not a file: {index_file}")
            return None
        
        try:
            # Find a free port
            port = self._find_free_port()
            print(f"🌐 Starting server on port {port}")
            
            # Create a robust handler that forces index.html serving
            class ForceIndexHandler(http.server.SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=sim_path, **kwargs)
                
                def end_headers(self):
                    # Add headers to prevent caching
                    self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                    self.send_header('Pragma', 'no-cache')
                    self.send_header('Expires', '0')
                    super().end_headers()
                
                def do_GET(self):
                    # Force serve index.html for root requests
                    if self.path == '/' or self.path == '' or self.path == '/index.html':
                        try:
                            # Read and serve index.html directly
                            with open(index_file, 'rb') as f:
                                content = f.read()
                            
                            self.send_response(200)
                            self.send_header('Content-type', 'text/html')
                            self.send_header('Content-length', str(len(content)))
                            self.end_headers()
                            self.wfile.write(content)
                            return
                        except Exception as e:
                            print(f"❌ Error serving index.html: {e}")
                            self.send_response(500)
                            self.end_headers()
                            return
                    
                    # For other files, use default handling but from simulation directory
                    try:
                        # Remove leading slash and resolve path
                        file_path = self.path.lstrip('/')
                        full_path = os.path.join(sim_path, file_path)
                        
                        if os.path.exists(full_path) and os.path.isfile(full_path):
                            with open(full_path, 'rb') as f:
                                content = f.read()
                            
                            # Determine content type
                            if file_path.endswith('.css'):
                                content_type = 'text/css'
                            elif file_path.endswith('.js'):
                                content_type = 'application/javascript'
                            elif file_path.endswith(('.png', '.jpg', '.jpeg')):
                                content_type = 'image/*'
                            else:
                                content_type = 'text/plain'
                            
                            self.send_response(200)
                            self.send_header('Content-type', content_type)
                            self.send_header('Content-length', str(len(content)))
                            self.end_headers()
                            self.wfile.write(content)
                            return
                        else:
                            # File not found
                            self.send_response(404)
                            self.send_header('Content-type', 'text/html')
                            self.end_headers()
                            self.wfile.write(b'File not found')
                            return
                            
                    except Exception as e:
                        print(f"❌ Error serving file {self.path}: {e}")
                        self.send_response(500)
                        self.end_headers()
                        return
                
                def log_message(self, format, *args):
                    # Print detailed logs for debugging
                    print(f"🌐 Server request: {format % args}")
            
            # Create server
            self.httpd = socketserver.TCPServer(("", port), ForceIndexHandler)
            print(f"✅ Server created successfully on port {port}")
            
            # Start server in background thread
            server_thread = threading.Thread(target=self.httpd.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            print(f"✅ Server thread started")
            
            self.simulation_url = f"http://localhost:{port}"
            time.sleep(2)  # Give server time to start
            
            # Test the server with detailed error reporting
            print(f"🧪 Testing server at {self.simulation_url}")
            try:
                import urllib.request
                with urllib.request.urlopen(self.simulation_url, timeout=10) as response:
                    content = response.read().decode('utf-8', errors='ignore')
                    status_code = response.getcode()
                    
                    print(f"📊 Server response: Status {status_code}")
                    print(f"📄 Content preview (first 200 chars): {content[:200]}")
                    
                    if status_code == 200:
                        # Check if we got HTML content (not directory listing)
                        if '<html' in content.lower() and 'directory listing for' not in content.lower():
                            print(f"✅ Server successfully serving simulation at {self.simulation_url}")
                            return self.simulation_url
                        else:
                            print(f"❌ Server serving directory listing instead of index.html")
                            print(f"📄 Full content: {content}")
                            return None
                    else:
                        print(f"❌ Server returned status {status_code}")
                        return None
            except Exception as test_error:
                print(f"❌ Server test failed: {test_error}")
                return None
                
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
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
        """Get AI-generated test plan with fallback for quota issues"""
        try:
            prompt = self.test_planning_prompt.format(**context)
            self.context = prompt
            response = super().get_output()
            
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                print("✅ AI test plan generated successfully")
                return json.loads(json_match.group(0))
        except Exception as e:
            print(f"⚠️ AI test planning failed: {e}")
            
            # Check if it's a quota issue
            if "429" in str(e) or "quota" in str(e).lower() or "ResourceExhausted" in str(e):
                print("🔄 Using enhanced fallback test plan due to API quota limits")
                return self._get_enhanced_fallback_test_plan(context)
            else:
                print("🔄 Using basic fallback test plan due to other error")
        
        # Basic fallback test plan
        return self._get_basic_fallback_test_plan()

    def _get_enhanced_fallback_test_plan(self, context):
        """Enhanced fallback test plan when AI is unavailable"""
        interactive_elements = context.get('interactive_elements', '')
        
        # Analyze what elements we found to create smarter tests
        has_buttons = 'buttons' in interactive_elements.lower()
        has_inputs = 'inputs' in interactive_elements.lower()
        has_canvas = 'canvas' in interactive_elements.lower()
        has_forms = 'forms' in interactive_elements.lower()
        
        test_plan = {
            "basic_tests": [
                {"name": "page_load", "description": "Check if simulation loads properly"},
                {"name": "ui_elements", "description": "Verify UI elements are visible"}
            ],
            "interaction_tests": [],
            "visual_tests": [
                {"name": "responsive_design", "description": "Test responsive design"},
                {"name": "graph_display", "description": "Check for graphs and visual elements"}
            ]
        }
        
        # Add interaction tests based on detected elements
        if has_buttons:
            test_plan["interaction_tests"].append({
                "name": "button_clicks", 
                "selectors": ["button", ".btn", "input[type='button']", "input[type='submit']"], 
                "description": "Test button functionality"
            })
        
        if has_inputs:
            test_plan["interaction_tests"].append({
                "name": "input_fields", 
                "selectors": ["input", "select", "textarea"], 
                "description": "Test input field interactions"
            })
        
        if has_canvas:
            test_plan["interaction_tests"].append({
                "name": "canvas_interaction", 
                "selectors": ["canvas"], 
                "description": "Test canvas element interactions"
            })
        
        if has_forms:
            test_plan["interaction_tests"].append({
                "name": "form_interaction", 
                "selectors": ["form"], 
                "description": "Test form functionality"
            })
        
        print(f"📋 Enhanced fallback test plan created: {len(test_plan['basic_tests'])} basic, {len(test_plan['interaction_tests'])} interaction, {len(test_plan['visual_tests'])} visual tests")
        return test_plan

    def _get_basic_fallback_test_plan(self):
        """Basic fallback when AI and enhanced logic both fail"""
        return {
            "basic_tests": [
                {"name": "page_load", "description": "Check if simulation loads properly"},
                {"name": "ui_elements", "description": "Verify UI elements are visible"}
            ],
            "interaction_tests": [
                {"name": "button_clicks", "selectors": ["button", "input[type='button']", ".btn"], "description": "Test button functionality"},
                {"name": "input_fields", "selectors": ["input", "select", "textarea"], "description": "Test input field interactions"}
            ],
            "visual_tests": [
                {"name": "responsive_design", "description": "Test responsive design"},
                {"name": "graph_display", "description": "Check for graphs and visual elements"}
            ]
        }

    
    async def _capture_screenshot(self, page, test_name, description=""):
        """Enhanced screenshot capture with better content detection"""
        try:
            # Wait a bit before screenshot to ensure content is rendered
            await page.wait_for_timeout(1000)
            
            # Check if page has visible content before screenshot
            has_visible_content = await page.evaluate("""() => {
                const body = document.body;
                if (!body) return false;
                
                // Check if body has visible dimensions
                const hasSize = body.offsetHeight > 50 && body.offsetWidth > 50;
                
                // Check for visible elements
                const visibleElements = document.querySelectorAll('*');
                let hasVisibleElement = false;
                for (let elem of visibleElements) {
                    const style = window.getComputedStyle(elem);
                    if (style.display !== 'none' && style.visibility !== 'hidden' && elem.offsetHeight > 0) {
                        hasVisibleElement = true;
                        break;
                    }
                }
                
                return hasSize && hasVisibleElement;
            }""")
            
            if not has_visible_content:
                print(f"⚠️ Warning: No visible content detected for screenshot {test_name}")
                # Wait a bit more and try again
                await page.wait_for_timeout(2000)
            
            # Take screenshot with better options
            screenshot_bytes = await page.screenshot(
                full_page=True,
                animations='disabled',
                timeout=10000,  # Increased timeout
                clip=None,  # Full page
                omit_background=False  # Include background
            )
            
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            # Get page info for debugging
            page_info = await page.evaluate("""() => {
                return {
                    url: window.location.href,
                    title: document.title,
                    bodyHTML: document.body ? document.body.innerHTML.length : 0,
                    bodyText: document.body ? document.body.innerText.length : 0,
                    hasVisibleContent: document.body && document.body.offsetHeight > 0
                };
            }""")
            
            self.screenshots[test_name] = {
                "data": screenshot_b64,
                "description": f"{description} | Page: {page_info['title']} | Content: {page_info['bodyHTML']} chars",
                "timestamp": asyncio.get_event_loop().time(),
                "page_info": page_info
            }
            
            print(f"📸 Screenshot captured: {test_name} - {page_info}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to capture screenshot for {test_name}: {e}")
            return False

    
    async def _run_basic_tests(self, page, test_plan):
        """Run basic functionality tests with JavaScript dependency detection"""
        results = []
        
        for test in test_plan.get("basic_tests", []):
            start_time = asyncio.get_event_loop().time()
            
            try:
                if test["name"] == "page_load":
                    print("🚀 Starting enhanced page load with dependency checking...")
                    
                    # Navigate and wait for network to be completely idle
                    response = await page.goto(
                        self.simulation_url, 
                        wait_until='networkidle',  # Wait for ALL network requests
                        timeout=30000
                    )
                    
                    print("✅ Initial navigation complete")
                    
                    # Debug missing resources
                    await self._debug_missing_resources(page)
                    
                    # ENHANCED: Wait for common Virtual Labs JavaScript patterns
                    js_loaded = False
                    for attempt in range(8):  # 8 attempts with different strategies
                        print(f"🔄 JavaScript detection attempt {attempt + 1}/8")
                        
                        await page.wait_for_timeout(3000)
                        
                        # Strategy 1: Wait for jQuery (very common in Virtual Labs)
                        try:
                            await page.wait_for_function("window.jQuery || window.$", timeout=5000)
                            print("✅ jQuery detected!")
                            js_loaded = True
                            break
                        except:
                            pass
                        
                        # Strategy 2: Wait for any global simulation objects
                        try:
                            await page.wait_for_function(
                                """() => {
                                    // Common Virtual Labs global variables
                                    return window.simulation || window.lab || window.experiment || 
                                        window.vlabs || window.app || window.main ||
                                        document.querySelector('canvas') ||
                                        document.querySelector('.simulation-area') ||
                                        document.querySelector('#simulation');
                                }""", 
                                timeout=5000
                            )
                            print("✅ Simulation objects detected!")
                            js_loaded = True
                            break
                        except:
                            pass
                        
                        # Strategy 3: Wait for DOM mutations (elements being added)
                        try:
                            initial_dom_size = await page.evaluate("document.querySelectorAll('*').length")
                            await page.wait_for_timeout(2000)
                            new_dom_size = await page.evaluate("document.querySelectorAll('*').length")
                            
                            if new_dom_size > initial_dom_size:
                                print(f"✅ DOM growing: {initial_dom_size} -> {new_dom_size} elements")
                                # Continue waiting a bit more for DOM to stabilize
                                await page.wait_for_timeout(3000)
                            
                        except:
                            pass
                    
                    # FORCE LOAD: Try to manually load common Virtual Labs JavaScript
                    if not js_loaded:
                        print("🔧 Attempting to force-load common JavaScript files...")
                        
                        common_js_files = [
                            '/js/main.js', '/js/script.js', '/js/simulation.js', '/js/app.js',
                            '/javascript/main.js', '/scripts/main.js'
                        ]
                        
                        for js_file in common_js_files:
                            try:
                                # Try to inject the script
                                await page.evaluate(f"""
                                    new Promise((resolve) => {{
                                        const script = document.createElement('script');
                                        script.src = '{js_file}';
                                        script.onload = () => resolve(true);
                                        script.onerror = () => resolve(false);
                                        document.head.appendChild(script);
                                        setTimeout(() => resolve(false), 3000);
                                    }})
                                """)
                                
                                # Wait for script to execute
                                await page.wait_for_timeout(2000)
                                
                                # Check if this created interactive elements
                                elements_check = await page.evaluate(
                                    "document.querySelectorAll('button, input, canvas, [onclick]').length"
                                )
                                
                                if elements_check > 0:
                                    print(f"✅ Success! {js_file} created {elements_check} interactive elements")
                                    break
                                    
                            except Exception as e:
                                print(f"⚠️ Failed to load {js_file}: {e}")
                    
                    # Final comprehensive check
                    await page.wait_for_timeout(3000)
                    
                    title = await page.title()
                    content_length = await page.evaluate("document.body ? document.body.innerHTML.length : 0")
                    visible_text = await page.evaluate("document.body ? document.body.innerText.trim().length : 0")
                    
                    await self._capture_screenshot(page, "initial_page_load", f"Enhanced load: {content_length} chars")
                    await page.wait_for_timeout(2000)
                    await self._capture_screenshot(page, "page_fully_loaded", f"Final enhanced state: {content_length} chars")
                    
                    has_content = content_length > 500 or visible_text > 100
                    status = "PASS" if response and response.status < 400 and title and has_content else "FAIL"
                    
                    results.append({
                        "test": "page_load",
                        "status": status,
                        "details": f"Title: '{title}', Status: {response.status if response else 'No response'}, Content: {content_length} chars, JS Loaded: {js_loaded}",
                        "execution_time": round(asyncio.get_event_loop().time() - start_time, 2)
                    })
                
                elif test["name"] == "ui_elements":
                    print("🔍 Starting ULTIMATE element detection...")
                    
                    # Wait for any remaining JavaScript
                    await page.wait_for_timeout(5000)
                    
                    # ULTIMATE element detection - try EVERYTHING
                    element_counts = await page.evaluate("""() => {
                        // Force re-scan the entire DOM
                        const allElements = document.querySelectorAll('*');
                        
                        let interactive = {
                            buttons: document.querySelectorAll('button, .btn, .button, [role="button"], input[type="button"], input[type="submit"]').length,
                            inputs: document.querySelectorAll('input, select, textarea, [contenteditable="true"]').length,
                            clickables: document.querySelectorAll('[onclick], .clickable, .click, [data-click]').length,
                            canvas: document.querySelectorAll('canvas').length,
                            svg: document.querySelectorAll('svg').length,
                            links: document.querySelectorAll('a[href]').length,
                            forms: document.querySelectorAll('form').length,
                            
                            // Advanced detection
                            hasTabIndex: document.querySelectorAll('[tabindex]').length,
                            hasAriaLabel: document.querySelectorAll('[aria-label]').length,
                            hasDataAttributes: document.querySelectorAll('[data-action], [data-target], [data-toggle]').length,
                            
                            // Check for hidden/dynamic elements
                            hiddenElements: document.querySelectorAll('[style*="display:none"], [style*="visibility:hidden"], .hidden, .d-none').length,
                            
                            totalElements: allElements.length,
                            bodyHTML: document.body ? document.body.innerHTML.length : 0
                        };
                        
                        interactive.anyInteractive = interactive.buttons + interactive.inputs + 
                                                interactive.clickables + interactive.canvas + 
                                                interactive.svg + interactive.links;
                        
                        return interactive;
                    }""")
                    
                    await self._capture_screenshot(page, "ui_elements_detection", f"ULTIMATE detection: {element_counts}")
                    
                    total_interactive = element_counts['anyInteractive']
                    status = "PASS" if total_interactive > 0 else "FAIL"
                    
                    details = f"ULTIMATE detection - Found: {element_counts['anyInteractive']} total interactive ({element_counts['buttons']}btn/{element_counts['inputs']}inp/{element_counts['clickables']}click/{element_counts['canvas']}canvas/{element_counts['links']}links), Hidden: {element_counts['hiddenElements']}, Total DOM: {element_counts['totalElements']}"
                    
                    results.append({
                        "test": "ui_elements",
                        "status": status,
                        "details": details,
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
            
    async def _debug_missing_resources(self, page):
        """Debug what resources are missing that might contain interactive elements"""
        try:
            # Check for JavaScript files that should be loading
            js_info = await page.evaluate("""() => {
                const scripts = Array.from(document.querySelectorAll('script'));
                const links = Array.from(document.querySelectorAll('link[rel="stylesheet"]'));
                const errors = [];
                
                // Check for common Virtual Labs JavaScript patterns
                const commonJS = [
                    'js/main.js', 'js/script.js', 'js/simulation.js', 'js/app.js',
                    'javascript/main.js', 'javascript/script.js',
                    'assets/js/', 'scripts/', 'lib/', 'libs/'
                ];
                
                // Check for external CDN dependencies
                const externalResources = scripts.filter(s => 
                    s.src && (s.src.includes('cdn') || s.src.includes('http'))
                );
                
                return {
                    totalScripts: scripts.length,
                    scriptSources: scripts.map(s => s.src).filter(Boolean),
                    stylesheets: links.map(l => l.href).filter(Boolean),
                    externalResources: externalResources.map(s => s.src),
                    hasJQuery: !!window.jQuery,
                    hasBootstrap: !!window.bootstrap,
                    documentReady: document.readyState,
                    errorMessages: window.console ? 'Check browser console' : 'No console access'
                };
            }""")
            
            print(f"🔍 Resource debug info: {js_info}")
            return js_info
            
        except Exception as e:
            print(f"❌ Debug failed: {e}")
            return {}



    async def _debug_blank_page(self, page, test_name):
        """Debug method to understand why page is blank"""
        try:
            debug_info = await page.evaluate("""() => {
                const body = document.body;
                const html = document.documentElement;
                
                return {
                    hasBody: !!body,
                    bodyHTML: body ? body.innerHTML.substring(0, 500) : 'NO BODY',
                    bodyText: body ? body.innerText.substring(0, 200) : 'NO TEXT',
                    bodyStyle: body ? window.getComputedStyle(body).display : 'NO STYLE',
                    htmlContent: html ? html.innerHTML.substring(0, 300) : 'NO HTML',
                    scripts: document.querySelectorAll('script').length,
                    links: document.querySelectorAll('link').length,
                    readyState: document.readyState,
                    bodyDimensions: body ? `${body.offsetWidth}x${body.offsetHeight}` : 'NO DIMENSIONS'
                };
            }""")
            
            print(f"🔍 Debug info for {test_name}: {debug_info}")
            
            # Take screenshot anyway for debugging
            await self._capture_screenshot(page, f"debug_{test_name}", f"Debug capture: {debug_info}")
            
        except Exception as e:
            print(f"❌ Debug failed: {e}")

    
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
