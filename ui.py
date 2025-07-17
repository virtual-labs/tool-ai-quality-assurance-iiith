import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import json
import time
import base64
from main import QAPipeline
from config_loader import load_config

CONFIG = load_config()

st.set_page_config(
    page_title="Virtual Labs QA",
    page_icon="vlabs.png",
    layout="wide"
)

st.title("Virtual Labs Quality Assurance Pipeline")
st.markdown("Evaluate Virtual Labs repositories for structure, content, and browser functionality.")

def initialize_session_state():
    defaults = {
        'pipeline': None,
        'evaluation_complete': False,
        'results': None,
        'branches': [],
        'selected_branch': "main",
        'custom_weights': CONFIG["weights"].copy(),
        'repo_url_input': ""
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

initialize_session_state()

if st.session_state.pipeline is None:
    st.session_state.pipeline = QAPipeline()

# Sidebar
with st.sidebar:
    st.header("Options")
    model = st.selectbox("Select LLM model", CONFIG["general"]["available_models"])
    
    st.markdown("---")
    st.subheader("Evaluation Weights")
    
    if 'weight_reset_trigger' not in st.session_state:
        st.session_state.weight_reset_trigger = 0
    
    reset_suffix = f"_v{st.session_state.weight_reset_trigger}"
    
    structure_weight = st.slider(
        "Structure Weight", 0.0, 1.0, CONFIG["weights"]["structure"], 0.01,
        help="Weight for repository structure compliance",
        key=f"slider_structure{reset_suffix}"
    )
    
    content_weight = st.slider(
        "Content Weight", 0.0, 1.0, CONFIG["weights"]["content"], 0.01,
        help="Weight for educational content quality",
        key=f"slider_content{reset_suffix}"
    )
    
    browser_weight = st.slider(
        "Browser Testing Weight", 0.0, 1.0, CONFIG["weights"]["browser_testing"], 0.01,
        help="Weight for browser functionality testing",
        key=f"slider_browser{reset_suffix}"
    )
    
    total_weight = structure_weight + content_weight + browser_weight
    
    if total_weight > 0:
        normalized_weights = {
            "structure": round(structure_weight / total_weight, 2),
            "content": round(content_weight / total_weight, 2),
            "browser_testing": round(browser_weight / total_weight, 2)
        }
        
        weight_sum = sum(normalized_weights.values())
        if abs(weight_sum - 1.0) > 0.005:
            diff = 1.0 - weight_sum
            max_key = max(normalized_weights, key=normalized_weights.get)
            normalized_weights[max_key] = round(normalized_weights[max_key] + diff, 2)
        
        st.session_state.custom_weights = normalized_weights
        
        st.markdown("**Live Weight Distribution:**")
        st.progress(normalized_weights["structure"], text=f"Structure: {normalized_weights['structure']:.2f}")
        st.progress(normalized_weights["content"], text=f"Content: {normalized_weights['content']:.2f}")
        st.progress(normalized_weights["browser_testing"], text=f"Browser Testing: {normalized_weights['browser_testing']:.2f}")
    else:
        st.error("All weights cannot be zero!")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Reset Weights", type="secondary", use_container_width=True):
            st.session_state.weight_reset_trigger += 1
            st.session_state.custom_weights = CONFIG["weights"].copy()
            st.rerun()
    
    with col2:
        if st.button("Reset All", type="secondary", use_container_width=True):
            current_url = st.session_state.get('repo_url_input', "")
            keys_to_keep = [k for k in st.session_state.keys() if k.startswith('FormSubmitter')]
            
            for key in list(st.session_state.keys()):
                if key not in keys_to_keep:
                    del st.session_state[key]
            
            initialize_session_state()
            st.session_state.repo_url_input = current_url
            st.rerun()

# Main content
st.header("Step 1: Repository Information")

col1, col2 = st.columns([3, 1])

with col1:
    repo_url = st.text_input(
        "Enter Git Repository URL", 
        value=st.session_state.get('repo_url_input', ''),
        placeholder="https://github.com/username/repo",
        key="url_input"
    )
    
    if repo_url != st.session_state.get('repo_url_input', ''):
        st.session_state.repo_url_input = repo_url
        st.session_state.branches = []
        st.session_state.selected_branch = "main"
        st.session_state.evaluation_complete = False
        st.session_state.results = None

if st.session_state.branches:
    branch = st.selectbox(
        "Select Branch",
        st.session_state.branches,
        index=st.session_state.branches.index(st.session_state.selected_branch) if st.session_state.selected_branch in st.session_state.branches else 0
    )
    st.session_state.selected_branch = branch

# Button logic
if not st.session_state.branches and repo_url.strip():
    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        fetch_btn = st.button("Fetch Branches", type="primary")
    analyze_btn = False
elif st.session_state.branches and repo_url.strip():
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.button("Refresh", type="secondary"):
            st.session_state.branches = []
            st.rerun()
    
    with col2:
        analyze_btn = st.button("Analyze Repository", type="primary")
    
    fetch_btn = False
else:
    fetch_btn = False
    analyze_btn = False
    if not repo_url.strip():
        st.info("Please enter a repository URL to get started")

# Handle fetch branches
if 'fetch_btn' in locals() and fetch_btn and repo_url.strip():
    if st.session_state.pipeline is None:
        st.session_state.pipeline = QAPipeline()

    with st.spinner("Fetching branches..."):
        try:
            success, result = st.session_state.pipeline.get_repository_branches(repo_url.strip())
            
            if not success:
                st.error(f"Failed to fetch branches: {result}")
            else:
                st.session_state.branches = result
                st.session_state.selected_branch = result[0] if result else "main"
                st.rerun()
        except Exception as e:
            st.error(f"Error fetching branches: {str(e)}")

# Handle analyze repository
if 'analyze_btn' in locals() and analyze_btn and repo_url.strip():
    try:
        st.session_state.pipeline = QAPipeline(model=model, custom_weights=st.session_state.custom_weights)
    except Exception as e:
        st.error(f"Failed to initialize pipeline: {str(e)}")
        st.stop()
    
    st.session_state.evaluation_complete = False
    st.session_state.results = None
    
    progress_container = st.empty()
    
    with progress_container.container():
        progress_bar = st.progress(0, text="Cloning repository...")
    
    with st.spinner("Cloning repository..."):
        try:
            branch = st.session_state.selected_branch if st.session_state.branches else "main"
            success, message = st.session_state.pipeline.clone_repository(repo_url, branch)
            
            if not success:
                progress_container.empty()
                st.error(f"Clone failed: {message}")
            else:
                with progress_container.container():
                    progress_bar = st.progress(25, text="Evaluating structure...")
                
                with st.spinner("Evaluating quality..."):
                    try:
                        success, message = st.session_state.pipeline.evaluate_repository()
                        
                        with progress_container.container():
                            progress_bar = st.progress(75, text="Generating report...")
                        
                        if success:
                            st.session_state.evaluation_complete = True
                            st.session_state.results = st.session_state.pipeline.get_results()
                            
                            with progress_container.container():
                                progress_bar = st.progress(100, text="Complete!")
                            time.sleep(0.5)
                            progress_container.empty()
                            
                            st.success("Evaluation completed successfully!")
                        else:
                            progress_container.empty()
                            st.error(f"Evaluation failed: {message}")
                            
                    except Exception as e:
                        progress_container.empty()
                        st.error(f"Evaluation error: {str(e)}")
                        
        except Exception as e:
            progress_container.empty()
            st.error(f"Clone error: {str(e)}")

# Display Results
if st.session_state.evaluation_complete and st.session_state.results:
    results = st.session_state.results
    
    st.header("Quality Assessment Results")
    
    experiment_name = "Virtual Lab Experiment"
    if 'detailed_results' in results and 'repository' in results['detailed_results']:
        repo_data = results['detailed_results']['repository']
        if 'experiment_name' in repo_data and repo_data['experiment_name']:
            experiment_name = repo_data['experiment_name']
    elif 'repository' in results:
        repo_data = results['repository']
        if 'experiment_name' in repo_data and repo_data['experiment_name']:
            experiment_name = repo_data['experiment_name']
    
    st.subheader(f"Experiment: {experiment_name}")
    
    final_score = results.get('final_score', 0)
    score_color = "red" if final_score < 60 else ("orange" if final_score < 80 else "green")
    st.markdown(f"<h2 style='color:{score_color}'>Score: {final_score:.1f}/100</h2>", unsafe_allow_html=True)
    
    # Extract component scores
    component_scores = results.get('component_scores', {})
    structure_score = component_scores.get('structure', 0)
    content_score = component_scores.get('content', 0)
    browser_score = component_scores.get('browser_testing', 0)
    
    # Display individual component scores
    st.markdown("#### Component Scores")
    cols = st.columns(3)
    
    with cols[0]:
        st.metric("Structure", f"{structure_score:.1f}/100")
    with cols[1]:
        st.metric("Content", f"{content_score:.1f}/100")
    with cols[2]:
        st.metric("Browser Testing", f"{browser_score:.1f}/100")

    # Tabs for detailed results
    tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Content Evaluation", "Browser Testing", "Full Report"])
    
    with tab1:
        col1, col2 = st.columns([2, 3])
        
        with col1:
            # Bar chart for category scores
            categories = ['Structure', 'Content', 'Browser Testing']
            scores = [structure_score, content_score, browser_score]
            
            fig, ax = plt.subplots(figsize=(6, 4))
            colors = ['blue', 'green', 'orange']
            bars = ax.bar(categories, scores, color=colors)
            ax.set_ylim(0, 100)
            ax.set_ylabel('Score')
            ax.set_title('Scores by Category')
            
            # Add value labels on top of bars
            for bar, score in zip(bars, scores):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                      f"{score:.1f}", ha='center')
            
            st.pyplot(fig)
        
        with col2:
            # Summary metrics
            st.subheader("Key Metrics Explained")
            
            # Get detailed results
            detailed_results = results.get('detailed_results', {})
            structure_data = detailed_results.get('structure', {})
            content_data = detailed_results.get('content', {})
            browser_data = detailed_results.get('browser_testing', {})
            
            # Structure metrics
            structure_status = structure_data.get('structure_status', 'Unknown')
            
            # Content metrics
            template_count = content_data.get('template_count', 0)
            total_evaluated = content_data.get('evaluated_count', 0)
            
            # Browser testing metrics
            browser_status = browser_data.get('status', 'Unknown')
            browser_passed = browser_data.get('passed_tests', 0)
            browser_total = browser_data.get('total_tests', 0)
            
            # Display metrics with explanations
            st.markdown("#### Structure Score")
            cols = st.columns([1, 2])
            cols[0].metric("Structure", f"{structure_score:.1f}/100", structure_status)
            cols[1].markdown(f"""
            Measures how well the repository follows the required Virtual Labs structure.
            Status: **{structure_status}**
            """)
            
            st.markdown("#### Content Score")
            cols = st.columns([1, 2])
            cols[0].metric("Content", f"{content_score:.1f}/100", f"{template_count}/{total_evaluated} templates" if total_evaluated > 0 else "No files")
            cols[1].markdown(f"""
            Measures quality of educational content across all markdown files.
            {template_count} of {total_evaluated} files contain template content.
            """)
            
            st.markdown("#### Browser Testing Score")
            cols = st.columns([1, 2])
            cols[0].metric("Browser Testing", f"{browser_score:.1f}/100", browser_status)
            if browser_status == "SUCCESS":
                cols[1].markdown(f"✅ Browser tests completed. {browser_passed}/{browser_total} tests passed.")
            elif browser_status == "MISSING":
                cols[1].markdown("⚠️ No simulation found for browser testing.")
            else:
                cols[1].markdown(f"❌ Browser testing failed: {browser_data.get('message', 'Unknown error')}")
    
    with tab2:
        # Content evaluation details
        detailed_results = results.get('detailed_results', {})
        if 'content' in detailed_results:
            content_results = detailed_results['content']
            
            # Template detection summary
            template_percentage = content_results.get('template_percentage', 0)
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Content Quality")
                st.metric("Content Score", f"{content_score:.1f}/100")
                st.metric("Template Content", f"{template_percentage:.1f}%")
                
                # Add explanation text
                st.markdown("""
                **What this means:**
                - Higher content score indicates better educational quality
                - Template content refers to placeholder or unfilled content
                - A high template percentage negatively impacts the overall score
                """)
            
            with col2:
                # Create pie chart showing template vs. custom content
                template_count = content_results.get('template_count', 0)
                custom_count = content_results.get('evaluated_count', 0) - template_count
                
                if template_count + custom_count > 0:
                    fig, ax = plt.subplots(figsize=(6, 4))
                    sizes = [custom_count, template_count]
                    labels = ['Custom Content', 'Template Content']
                    colors = ['lightgreen', 'lightcoral']
                    
                    ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
                    ax.set_title('Content Distribution')
                    st.pyplot(fig)
            
            # File-by-file breakdown
            st.subheader("File Evaluation Details")
            
            file_evaluations = content_results.get('file_evaluations', {})
            if file_evaluations:
                for file_path, evaluation in file_evaluations.items():
                    status = evaluation.get('status', 'Unknown')
                    if status == 'Evaluated':
                        is_template = evaluation.get('is_template', False)
                        avg_score = evaluation.get('average_score', 0)
                        
                        status_icon = "🟡" if is_template else "🟢"
                        content_type = "Template" if is_template else "Custom"
                        
                        st.markdown(f"{status_icon} **{file_path}**: {content_type} content (Score: {avg_score:.1f}/10)")
                    else:
                        st.warning(f"{file_path}: {evaluation.get('reason', 'Not evaluated')}")
    

    with tab3:
        # Browser testing details
        detailed_results = results.get('detailed_results', {})
        if 'browser_testing' in detailed_results:
            browser_data = detailed_results['browser_testing']
            
            st.subheader("🎭 Browser Testing & Performance Analysis")
            
            # Debug information
            st.text(f"Debug: Browser data keys: {list(browser_data.keys())}")
            st.text(f"Debug: Browser score: {browser_data.get('browser_score', 'Not found')}")
            st.text(f"Debug: Overall score: {browser_data.get('overall_score', 'Not found')}")
            
            # Combined metrics in a single row
            metric_cols = st.columns(5)
            with metric_cols[0]:
                combined_score = browser_data.get('browser_score', browser_data.get('overall_score', 0))
                st.metric("Combined Score", f"{combined_score * 10:.1f}/100")
            with metric_cols[1]:
                st.metric("Playwright Tests", f"{browser_data.get('passed_tests', 0)}/{browser_data.get('total_tests', 0)}")
            with metric_cols[2]:
                # Get performance metrics
                perf_metrics = browser_data.get('performance_metrics', {})
                desktop_perf = perf_metrics.get('desktop_performance', 0)
                st.metric("Desktop Performance", f"{desktop_perf*100:.0f}/100")
            with metric_cols[3]:
                mobile_perf = perf_metrics.get('mobile_performance', 0)
                st.metric("Mobile Performance", f"{mobile_perf*100:.0f}/100")
            with metric_cols[4]:
                st.metric("Status", browser_data.get('status', 'Unknown'))
            
            # Create sub-tabs for Playwright and Lighthouse
            playwright_tab, lighthouse_tab, combined_tab = st.tabs(["🎭 Playwright Results", "🚀 Lighthouse Performance", "📊 Combined Analysis"])
            
            with playwright_tab:
                st.subheader("Functional Testing Results")
                
                # Test results
                test_results = browser_data.get('test_results', [])
                if test_results:
                    st.markdown("#### Test Execution Results")
                    for test in test_results:
                        status_icon = "✅" if test.get('status') == 'PASS' else "❌" if test.get('status') == 'FAIL' else "⚠️"
                        st.markdown(f"{status_icon} **{test.get('test', 'Unknown')}**: {test.get('details', 'No details')}")
                        if test.get('execution_time'):
                            st.text(f"   ⏱️ Execution time: {test['execution_time']}s")
                else:
                    st.warning("No test results available")
                    st.text(f"Debug: Browser data contains: {list(browser_data.keys())}")
                
                # Screenshots section - Enhanced display
                screenshots = browser_data.get('screenshots', {})
                if screenshots:
                    st.subheader("📸 Screenshots Captured")
                    st.markdown(f"**{len(screenshots)} screenshots** were captured during testing:")
                    
                    # Create columns for better layout
                    if len(screenshots) <= 3:
                        cols = st.columns(len(screenshots))
                    else:
                        cols = st.columns(3)
                    
                    screenshot_items = list(screenshots.items())
                    for i, (screenshot_name, screenshot_info) in enumerate(screenshot_items):
                        col_index = i % len(cols)
                        
                        with cols[col_index]:
                            display_name = screenshot_name.replace('_', ' ').title()
                            st.markdown(f"**{display_name}**")
                            
                            try:
                                # Handle different screenshot data formats
                                screenshot_data = None
                                
                                if isinstance(screenshot_info, dict):
                                    if 'data' in screenshot_info:
                                        screenshot_data = screenshot_info['data']
                                    elif 'screenshot' in screenshot_info:
                                        screenshot_data = screenshot_info['screenshot']
                                elif isinstance(screenshot_info, str):
                                    screenshot_data = screenshot_info
                                
                                if screenshot_data:
                                    try:
                                        # Try to decode base64 data
                                        if isinstance(screenshot_data, str):
                                            screenshot_bytes = base64.b64decode(screenshot_data)
                                            st.image(screenshot_bytes, caption=display_name, use_container_width=True)
                                        else:
                                            st.info(f"Screenshot data format not supported: {type(screenshot_data)}")
                                    except Exception as decode_error:
                                        st.error(f"Could not decode screenshot {display_name}: {str(decode_error)}")
                                        # Debug info
                                        st.text(f"Data type: {type(screenshot_data)}")
                                        st.text(f"Data preview: {str(screenshot_data)[:100]}...")
                                else:
                                    st.warning(f"No screenshot data found for {display_name}")
                                    # Debug the screenshot_info structure
                                    st.text(f"Available keys: {list(screenshot_info.keys()) if isinstance(screenshot_info, dict) else 'Not a dict'}")
                                    
                            except Exception as e:
                                st.error(f"Error displaying screenshot {display_name}: {str(e)}")
                                # Show debug info
                                st.text(f"Screenshot info type: {type(screenshot_info)}")
                                st.text(f"Screenshot info: {str(screenshot_info)[:200]}...")
                else:
                    st.info("No screenshots were captured during this test run")
                    
                    # Debug information
                    st.text("Debug info:")
                    st.text(f"Browser data keys: {list(browser_data.keys())}")
                    st.text(f"Screenshots type: {type(browser_data.get('screenshots', {}))}")
                    
                    # Check if screenshots are in playwright_results
                    playwright_results = browser_data.get('playwright_results', {})
                    if playwright_results and 'screenshots' in playwright_results:
                        st.text(f"Screenshots in playwright_results: {len(playwright_results['screenshots'])}")
            
            with lighthouse_tab:
                st.subheader("Performance & Quality Analysis")
                
                lighthouse_results = browser_data.get('lighthouse_results', {})
                if lighthouse_results and not lighthouse_results.get('error'):
                    
                    # Performance scores comparison
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### 🖥️ Desktop Performance")
                        desktop_data = lighthouse_results.get('desktop', {})
                        desktop_scores = desktop_data.get('scores', {})
                        
                        # Create score display
                        for category, score in desktop_scores.items():
                            if score is not None:
                                score_color = "🟢" if score >= 0.9 else "🟡" if score >= 0.5 else "🔴"
                                st.markdown(f"{score_color} **{category.title()}**: {score*100:.0f}/100")
                    
                    with col2:
                        st.markdown("#### 📱 Mobile Performance")
                        mobile_data = lighthouse_results.get('mobile', {})
                        mobile_scores = mobile_data.get('scores', {})
                        
                        for category, score in mobile_scores.items():
                            if score is not None:
                                score_color = "🟢" if score >= 0.9 else "🟡" if score >= 0.5 else "🔴"
                                st.markdown(f"{score_color} **{category.title()}**: {score*100:.0f}/100")
                    
                    # Performance metrics table
                    st.subheader("⚡ Key Performance Metrics")
                    
                    metrics_data = []
                    desktop_metrics = desktop_data.get('metrics', {})
                    mobile_metrics = mobile_data.get('metrics', {})
                    
                    metric_names = ['first-contentful-paint', 'largest-contentful-paint', 'speed-index', 'cumulative-layout-shift']
                    
                    for metric in metric_names:
                        metrics_data.append({
                            'Metric': metric.replace('-', ' ').title(),
                            'Desktop': desktop_metrics.get(metric, 'N/A'),
                            'Mobile': mobile_metrics.get(metric, 'N/A')
                        })
                    
                    df_metrics = pd.DataFrame(metrics_data)
                    st.dataframe(df_metrics, use_container_width=True)
                    
                    # Performance opportunities
                    st.subheader("🎯 Performance Opportunities")
                    desktop_opportunities = desktop_data.get('opportunities', [])
                    if desktop_opportunities:
                        for opp in desktop_opportunities[:5]:  # Show top 5
                            potential_savings = opp.get('potential_savings', 0)
                            if potential_savings > 0:
                                st.markdown(f"• **{opp['title']}**: Could save ~{potential_savings}ms")
                            else:
                                st.markdown(f"• **{opp['title']}**: {opp.get('description', '')}")
                    else:
                        st.info("No major performance opportunities identified")
                    
                    # Lighthouse score visualization
                    st.subheader("📊 Lighthouse Score Breakdown")
                    
                    # Create bar chart comparing desktop vs mobile scores
                    categories = ['Performance', 'Accessibility', 'Best Practices', 'SEO']
                    desktop_vals = [desktop_scores.get(cat.lower().replace(' ', '-'), 0)*100 for cat in categories]
                    mobile_vals = [mobile_scores.get(cat.lower().replace(' ', '-'), 0)*100 for cat in categories]
                    
                    fig, ax = plt.subplots(figsize=(10, 6))
                    x = np.arange(len(categories))
                    width = 0.35
                    
                    bars1 = ax.bar(x - width/2, desktop_vals, width, label='Desktop', color='steelblue')
                    bars2 = ax.bar(x + width/2, mobile_vals, width, label='Mobile', color='lightcoral')
                    
                    ax.set_xlabel('Categories')
                    ax.set_ylabel('Score')
                    ax.set_title('Lighthouse Scores: Desktop vs Mobile')
                    ax.set_xticks(x)
                    ax.set_xticklabels(categories)
                    ax.legend()
                    ax.set_ylim(0, 100)
                    
                    # Add value labels on bars
                    for bars in [bars1, bars2]:
                        for bar in bars:
                            height = bar.get_height()
                            ax.annotate(f'{height:.0f}',
                                    xy=(bar.get_x() + bar.get_width() / 2, height),
                                    xytext=(0, 3),
                                    textcoords="offset points",
                                    ha='center', va='bottom')
                    
                    st.pyplot(fig)
                    
                else:
                    st.warning("Lighthouse performance analysis not available")
                    if lighthouse_results.get('error'):
                        st.error(f"Error: {lighthouse_results['error']}")
            
            with combined_tab:
                st.subheader("📊 Comprehensive Analysis")
                
                # Combined score breakdown
                st.markdown("#### Score Components")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Functional Testing (60%)**")
                    playwright_score = browser_data.get('playwright_results', {}).get('browser_score', browser_data.get('browser_score', 0))
                    st.progress(playwright_score/10, text=f"Playwright: {playwright_score:.1f}/10")
                
                with col2:
                    st.markdown("**Performance Testing (40%)**")
                    perf_metrics = browser_data.get('performance_metrics', {})
                    avg_perf = (perf_metrics.get('desktop_performance', 0) + perf_metrics.get('mobile_performance', 0)) / 2
                    st.progress(avg_perf, text=f"Lighthouse: {avg_perf*10:.1f}/10")
                
                # Recommendations section
                st.subheader("🎯 Recommendations")
                
                recommendations = []
                
                # Playwright-based recommendations
                if playwright_score < 7:
                    recommendations.append("🎭 **Functional Issues**: Review and fix failing Playwright tests")
                
                # Lighthouse-based recommendations
                lighthouse_results = browser_data.get('lighthouse_results', {})
                if lighthouse_results and not lighthouse_results.get('error'):
                    desktop_perf = lighthouse_results.get('desktop', {}).get('scores', {}).get('performance', 0)
                    mobile_perf = lighthouse_results.get('mobile', {}).get('scores', {}).get('performance', 0)
                    
                    if desktop_perf < 0.5:
                        recommendations.append("🖥️ **Desktop Performance**: Optimize for desktop users")
                    if mobile_perf < 0.5:
                        recommendations.append("📱 **Mobile Performance**: Optimize for mobile users")
                    
                    # Add specific opportunities
                    desktop_opportunities = lighthouse_results.get('desktop', {}).get('opportunities', [])
                    for opp in desktop_opportunities[:3]:
                        if opp.get('potential_savings', 0) > 500:  # > 500ms savings
                            recommendations.append(f"⚡ **{opp['title']}**: High impact optimization")
                
                if recommendations:
                    for rec in recommendations:
                        st.markdown(f"• {rec}")
                else:
                    st.success("✅ No major issues found. Great job!")
        
        else:
            st.warning("Browser testing data not available")
            # Show debug info
            st.text(f"Available keys in detailed_results: {list(detailed_results.keys())}")


    
    with tab4:
        # Display report
        report_text = results.get('report', 'No report available')
        
        # Only do essential cleanup
        if not report_text.strip().startswith('#'):
            # Find the actual report start
            lines = report_text.split('\n')
            report_lines = []
            found_header = False
            
            for line in lines:
                if line.strip().startswith('# Virtual Lab Quality Report'):
                    found_header = True
                if found_header:
                    report_lines.append(line)
            
            if report_lines:
                report_text = '\n'.join(report_lines)
        
        st.markdown(report_text)
        
    # Export options at the bottom
    if st.session_state.evaluation_complete and st.session_state.results:
        st.header("Export Options")
        
        st.markdown("""
        **Export Formats:**
        - **JSON**: Complete evaluation data including all scores, metrics, and technical details
        - **Markdown**: Human-readable report with analysis and recommendations  
        - **CSV**: Simple metrics table for spreadsheet analysis
        """)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**📊 Complete Data**")
            if st.button("Export as JSON", use_container_width=True):
                json_results = {
                    'experiment_name': experiment_name,
                    'final_score': float(final_score),
                    'component_scores': {
                        'structure': float(structure_score),
                        'content': float(content_score),
                        'browser_testing': float(browser_score)
                    },
                    'template_percentage': float(results.get('template_percentage', 0)),
                    'detailed_evaluation': results.get('detailed_results', {}),
                    'report': results.get('report', ''),
                    'evaluation_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                
                st.download_button(
                    label="📥 Download JSON Report",
                    data=json.dumps(json_results, indent=2),
                    file_name=f"{experiment_name.replace(' ', '_')}_qa_report.json",
                    mime="application/json",
                    use_container_width=True,
                    help="Complete evaluation data with all metrics and details"
                )

        with col2:
            st.markdown("**📝 Formatted Report**")
            if st.button("Export as Markdown", use_container_width=True):
                st.download_button(
                    label="📥 Download Markdown Report", 
                    data=results.get('report', ''),
                    file_name=f"{experiment_name.replace(' ', '_')}_qa_report.md",
                    mime="text/markdown",
                    use_container_width=True,
                    help="Human-readable report with analysis and recommendations"
                )

        with col3:
            st.markdown("**📋 Simple Metrics**")
            if st.button("Export as CSV", use_container_width=True):
                csv_data = f"Metric,Score\n"
                csv_data += f"Overall Score,{final_score:.1f}\n"
                csv_data += f"Structure Score,{structure_score:.1f}\n"
                csv_data += f"Content Score,{content_score:.1f}\n"
                csv_data += f"Browser Testing Score,{browser_score:.1f}\n"
                csv_data += f"Template Percentage,{results.get('template_percentage', 0):.1f}\n"
                
                st.download_button(
                    label="📥 Download CSV Report",
                    data=csv_data,
                    file_name=f"{experiment_name.replace(' ', '_')}_qa_metrics.csv",
                    mime="text/csv",
                    use_container_width=True,
                    help="Key metrics in spreadsheet format"
                )
