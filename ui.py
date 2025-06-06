import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import json
import time
import re
from main import QAPipeline
from config_loader import load_config

# Load configuration
CONFIG = load_config()

st.set_page_config(
    page_title="Virtual Labs QA",
    page_icon="vlabs.png",
    layout="wide"
)

st.title("Virtual Labs Quality Assurance Pipeline")
st.markdown("This tool evaluates the quality of Virtual Labs repositories based on structure, content, and simulation.")

# Initialize session state variables properly at the top
def initialize_session_state():
    """Initialize all session state variables with proper defaults"""
    defaults = {
        'pipeline': None,  # Will be created when needed
        'evaluation_complete': False,
        'results': None,
        'error_message': None,
        'progress': 0,
        'progress_message': "",
        'branches': [],
        'selected_branch': "main",
        'custom_weights': CONFIG["weights"].copy(),
        'raw_weights': CONFIG["weights"].copy(),
        'repo_url_input': ""  # Add this to persist URL input
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

# Call initialization at the very beginning
initialize_session_state()

# Ensure pipeline is always available
if st.session_state.pipeline is None:
    st.session_state.pipeline = QAPipeline()

# Alternative approach using session state keys for slider values

with st.sidebar:
    st.header("Options")
    model = st.selectbox(
        "Select LLM model",
        CONFIG["general"]["available_models"]
    )
    
    st.markdown("---")
    st.subheader("Evaluation Weights")
    
    # Initialize slider values separately from normalized weights
    if 'slider_structure' not in st.session_state:
        st.session_state.slider_structure = CONFIG["weights"]["structure"]
    if 'slider_content' not in st.session_state:
        st.session_state.slider_content = CONFIG["weights"]["content"]
    if 'slider_simulation' not in st.session_state:
        st.session_state.slider_simulation = CONFIG["weights"]["simulation"]
    
    # Use session state keys for slider values
    structure_weight = st.slider(
        "Structure Weight", 
        min_value=0.0, 
        max_value=1.0, 
        step=0.01,
        help="Weight for repository structure compliance",
        key="slider_structure"
    )
    
    content_weight = st.slider(
        "Content Weight", 
        min_value=0.0, 
        max_value=1.0, 
        step=0.01,
        help="Weight for educational content quality",
        key="slider_content"
    )
    
    simulation_weight = st.slider(
        "Simulation Weight", 
        min_value=0.0, 
        max_value=1.0, 
        step=0.01,
        help="Weight for simulation implementation",
        key="slider_simulation"
    )
    
    # Real-time normalization
    total_weight = structure_weight + content_weight + simulation_weight
    
    if total_weight > 0:
        # Calculate normalized weights
        normalized_weights = {
            "structure": round(structure_weight / total_weight, 2),
            "content": round(content_weight / total_weight, 2),
            "simulation": round(simulation_weight / total_weight, 2)
        }
        
        # Ensure sum equals 1.0
        weight_sum = sum(normalized_weights.values())
        if abs(weight_sum - 1.0) > 0.005:
            diff = 1.0 - weight_sum
            max_key = max(normalized_weights, key=normalized_weights.get)
            normalized_weights[max_key] = round(normalized_weights[max_key] + diff, 2)
        
        # Store normalized weights
        st.session_state.custom_weights = normalized_weights
        
        # Visual feedback
        st.markdown("**Live Weight Distribution:**")
        st.progress(normalized_weights["structure"], text=f"Structure: {normalized_weights['structure']:.2f} ({normalized_weights['structure']*100:.0f}%)")
        st.progress(normalized_weights["content"], text=f"Content: {normalized_weights['content']:.2f} ({normalized_weights['content']*100:.0f}%)")
        st.progress(normalized_weights["simulation"], text=f"Simulation: {normalized_weights['simulation']:.2f} ({normalized_weights['simulation']*100:.0f}%)")
        
        st.success(f"**Total: {sum(normalized_weights.values()):.2f}**")
    else:
        st.error("⚠️ All weights cannot be zero!")
    
    # Reset buttons with proper key handling
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Reset Weights", type="secondary", use_container_width=True):
            # Delete the slider keys to force recreation with default values
            slider_keys = ['slider_structure', 'slider_content', 'slider_simulation']
            for key in slider_keys:
                if key in st.session_state:
                    del st.session_state[key]
            
            # Reset the custom weights
            st.session_state.custom_weights = CONFIG["weights"].copy()
            st.rerun()
    
    with col2:
        if st.button("Reset All", type="secondary", use_container_width=True):
            # Store URL before reset
            current_url = st.session_state.get('repo_url_input', "")
            
            # Clear most session state but preserve form keys
            keys_to_keep = [k for k in st.session_state.keys() if k.startswith('FormSubmitter')]
            
            for key in list(st.session_state.keys()):
                if key not in keys_to_keep:
                    del st.session_state[key]
            
            # Reinitialize essential state (don't set slider values directly)
            st.session_state.custom_weights = CONFIG["weights"].copy()
            st.session_state.repo_url_input = current_url
            st.session_state.evaluation_complete = False
            st.session_state.results = None
            st.session_state.branches = []
            st.session_state.selected_branch = "main"
            st.session_state.pipeline = None
            
            st.rerun()
        
    st.markdown("---")
    st.markdown(f"**VLabs QA Tool v{CONFIG['general']['version']}**")

# Initialize custom weights if not present
if 'custom_weights' not in st.session_state:
    st.session_state.custom_weights = CONFIG["weights"].copy()

# Step 1: Input repository URL
with st.container():
    st.header("Step 1: Repository Information")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Use session state to persist URL input
        repo_url = st.text_input(
            "Enter Git Repository URL", 
            value=st.session_state.repo_url_input,
            placeholder="https://github.com/username/repo",
            key="url_input"
        )
        
        # Update session state when URL changes
        if repo_url != st.session_state.repo_url_input:
            st.session_state.repo_url_input = repo_url
            # Clear branches when URL changes
            st.session_state.branches = []
            st.session_state.selected_branch = "main"
    
    # Initialize branches and selected_branch if not present
    if 'branches' not in st.session_state:
        st.session_state.branches = []
    
    if 'selected_branch' not in st.session_state:
        st.session_state.selected_branch = "main"
    
    # Show branch selection only if branches are fetched
    if st.session_state.branches:
        branch = st.selectbox(
            "Select Branch",
            st.session_state.branches,
            index=st.session_state.branches.index(st.session_state.selected_branch) if st.session_state.selected_branch in st.session_state.branches else 0
        )
        st.session_state.selected_branch = branch
    
    # Button row - Use repo_url for enabling/disabling
    cols = st.columns([1, 1, 2])
    
    with cols[0]:
        fetch_btn = st.button("Fetch Branches", type="secondary", use_container_width=True, 
                            disabled=not repo_url.strip())  # Check if URL is not empty
    
    with cols[1]:
        analyze_btn = st.button("Analyze Repository", type="primary", use_container_width=True, 
                               disabled=not repo_url.strip())  # Check if URL is not empty
    
    # Fetch branches if requested - ensure pipeline exists
    if fetch_btn and repo_url.strip():
        # Always ensure we have a valid pipeline
        if st.session_state.pipeline is None:
            try:
                st.session_state.pipeline = QAPipeline()
            except Exception as e:
                st.error(f"Failed to initialize pipeline: {str(e)}")
                st.stop()
    
        with st.spinner("Fetching branches..."):
            try:
                success, result = st.session_state.pipeline.get_repository_branches(repo_url.strip())
                
                if not success:
                    st.error(f"❌ Branch fetch failed: {result}")
                    st.session_state.branches = []
                else:
                    st.session_state.branches = result
                    st.session_state.selected_branch = result[0] if result else "main"
                    st.success(f"✅ Found {len(result)} branches: {', '.join(result[:3])}{'...' if len(result) > 3 else ''}")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Error fetching branches: {str(e)}")
                st.session_state.branches = []

# Start analysis when button is clicked
if analyze_btn and repo_url.strip():
    # Always create a fresh pipeline with current settings
    try:
        st.session_state.pipeline = QAPipeline(model=model, custom_weights=st.session_state.custom_weights)
    except Exception as e:
        st.error(f"Failed to initialize pipeline: {str(e)}")
        st.stop()
    
    # Reset evaluation state
    st.session_state.evaluation_complete = False
    st.session_state.results = None
    st.session_state.error_message = None
    
    # Initialize progress tracking
    progress_container = st.empty()
    
    with progress_container.container():
        progress_bar = st.progress(0, text="Cloning repository...")
    
    with st.spinner("Cloning repository..."):
        try:
            branch = st.session_state.selected_branch if st.session_state.branches else "main"
            success, message = st.session_state.pipeline.clone_repository(repo_url, branch)
            
            if not success:
                progress_container.empty()
                st.error(f"❌ Clone failed: {message}")
            else:
                # Update progress for evaluation
                with progress_container.container():
                    progress_bar = st.progress(25, text="Evaluating structure...")
                
                with st.spinner("Evaluating quality..."):
                    try:
                        success, message = st.session_state.pipeline.evaluate_repository()
                        
                        # Update progress steps
                        with progress_container.container():
                            progress_bar = st.progress(50, text="Evaluating content...")
                        time.sleep(0.2)
                        
                        with progress_container.container():
                            progress_bar = st.progress(75, text="Evaluating simulation...")
                        time.sleep(0.2)
                        
                        with progress_container.container():
                            progress_bar = st.progress(90, text="Generating report...")
                        time.sleep(0.2)
                        
                        if success:
                            st.session_state.evaluation_complete = True
                            st.session_state.results = st.session_state.pipeline.get_results()
                            
                            # Complete and hide progress
                            with progress_container.container():
                                progress_bar = st.progress(100, text="Complete!")
                            time.sleep(0.5)
                            progress_container.empty()  # Remove progress bar
                            
                            st.success("✅ Evaluation completed successfully!")
                        else:
                            progress_container.empty()
                            st.error(f"❌ Evaluation failed: {message}")
                            
                    except Exception as e:
                        progress_container.empty()
                        st.error(f"❌ Evaluation error: {str(e)}")
                    
        except Exception as e:
            progress_container.empty()
            st.error(f"❌ Clone error: {str(e)}")

# Step 2: Display Results
if st.session_state.evaluation_complete and st.session_state.results:
    results = st.session_state.results
    st.header("Quality Assessment Results")
    
    # Extract experiment name properly
    experiment_name = "Virtual Lab Experiment"
    if 'detailed_results' in results and 'repository' in results['detailed_results']:
        repo_data = results['detailed_results']['repository']
        if 'experiment_name' in repo_data and repo_data['experiment_name']:
            experiment_name = repo_data['experiment_name']
    
    st.subheader(f"Experiment: {experiment_name}")
    
    # Show overall score with coloring
    score_color = "red"
    if results['final_score'] >= 80:
        score_color = "green"
    elif results['final_score'] >= 60:
        score_color = "orange"
    
    st.markdown(f"<h2 style='color:{score_color}'>Score: {results['final_score']:.1f}/100</h2>", unsafe_allow_html=True)
    
    # Tabs for different sections of the report
    tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Content Evaluation", "Simulation Evaluation", "Full Report"])
    
    with tab1:
        col1, col2 = st.columns([2, 3])
        
        with col1:
            # Create a bar chart for category scores
            categories = []
            scores = []
            
            component_scores = results.get('detailed_results', {})
            
            if 'structure' in component_scores:
                categories.append('Structure')
                scores.append(component_scores['structure'].get('compliance_score', 0) * 10)
            
            if 'content' in component_scores:
                categories.append('Content')
                scores.append(component_scores['content'].get('average_score', 0) * 10)
            
            if 'simulation' in component_scores:
                categories.append('Simulation')
                scores.append(component_scores['simulation'].get('overall_score', 0) * 10)
            
            fig, ax = plt.subplots(figsize=(6, 4))
            colors = ['blue', 'green', 'purple']
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
            
            # Structure metrics
            structure_status = component_scores.get('structure', {}).get('structure_status', 'Unknown')
            structure_score = component_scores.get('structure', {}).get('compliance_score', 0) * 10
            
            # Content metrics
            template_count = component_scores.get('content', {}).get('template_count', 0)
            total_evaluated = component_scores.get('content', {}).get('evaluated_count', 0)
            content_score = component_scores.get('content', {}).get('average_score', 0) * 10
            
            # Simulation metrics
            simulation_status = component_scores.get('simulation', {}).get('simulation_status', 'Unknown')
            simulation_score = component_scores.get('simulation', {}).get('overall_score', 0) * 10
            
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
            
            st.markdown("#### Simulation Score")
            cols = st.columns([1, 2])
            cols[0].metric("Simulation", f"{simulation_score:.1f}/100", simulation_status)
            cols[1].markdown(f"""
            Measures quality of the interactive simulation implementation.
            Status: **{simulation_status}**
            """)
    
    with tab2:
        if 'content' in component_scores:
            content_results = component_scores['content']
            
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
                if total_evaluated > 0:
                    fig, ax = plt.subplots(figsize=(5, 5))
                    labels = ['Custom Content', 'Template Content']
                    sizes = [total_evaluated - template_count, template_count]
                    colors = ['#66b3ff', '#ff9999']
                    explode = (0, 0.1)  # explode the 2nd slice (template)
                    
                    # Remove shadow and add legend
                    wedges, texts, autotexts = ax.pie(
                        sizes, 
                        explode=explode, 
                        labels=None,  # Remove direct labels
                        colors=colors, 
                        autopct='%1.1f%%',
                        shadow=False,  # Remove shadow
                        startangle=90
                    )
                    
                    # Add a legend with explanations
                    legend_labels = [
                        'Custom Content: Fully developed educational content',
                        'Template Content: Placeholder or undeveloped content'
                    ]
                    ax.legend(wedges, legend_labels, loc="center left", bbox_to_anchor=(0.9, 0.5))
                    ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
                    ax.set_title('Content Analysis')
                    
                    st.pyplot(fig)
                else:
                    st.warning("No content files were evaluated")
            
            # Individual file evaluations
            st.subheader("File Evaluations")

            # Add explanation text
            st.markdown("""
            **How to interpret scores:**
            - **Educational Value**: How well the content helps students learn
            - **Comprehensiveness**: How completely the topic is covered
            - **Technical Accuracy**: Correctness of information presented
            - **Organization & Structure**: How well the content flows and is organized
            - **Language & Readability**: Grammar, clarity, and ease of reading
            """)

            if 'file_evaluations' in content_results:
                for file_path, evaluation in content_results['file_evaluations'].items():
                    if evaluation['status'] == "Evaluated":
                        with st.expander(f"{file_path} - Score: {evaluation['average_score']:.1f}/10"):
                            if evaluation.get('is_template', False):
                                st.warning("⚠️ This appears to be template content that needs to be customized")
                            
                            # Create score chart for this file
                            criteria = list(evaluation['scores'].keys())
                            scores_list = list(evaluation['scores'].values())
                            
                            # Color-code the bars based on score
                            colors = []
                            for score in scores_list:
                                if score >= 8:
                                    colors.append('green')
                                elif score >= 6:
                                    colors.append('lightgreen')
                                elif score >= 4:
                                    colors.append('orange')
                                else:
                                    colors.append('red')
                            
                            fig, ax = plt.subplots(figsize=(6, 3))
                            bars = ax.barh(criteria, scores_list, color=colors)
                            ax.set_xlim(0, 10)
                            ax.set_title(f"Evaluation: {os.path.basename(file_path)}")
                            
                            # Add value labels
                            for i, score in enumerate(scores_list):
                                ax.text(score + 0.1, i, f"{score}", va='center')
                                
                            # Add a vertical line to mark "good" threshold
                            ax.axvline (x=7, color='gray', linestyle='--', alpha=0.5)
                            ax.text(7.1, -0.5, 'Good threshold', color='gray', alpha=0.7)
                            
                            st.pyplot(fig)
                            
                            st.markdown("**Feedback:**")
                            st.markdown(evaluation.get('feedback', 'No feedback available').split("```json")[0])
                    else:
                        st.warning(f"{file_path}: {evaluation.get('reason', 'Not evaluated')}")
    
    with tab3:
        if 'simulation' in component_scores:
            simulation_results = component_scores['simulation']
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Simulation Quality")
                st.metric("Simulation Score", f"{simulation_score:.1f}/100")
                
                # Display different aspects of the simulation evaluation
                complexity = simulation_results.get('complexity', 0)
                st.progress(complexity/10, text=f"Complexity: {complexity:.1f}/10")
                
                # Display libraries used
                libraries = simulation_results.get('libraries_used', [])
                if libraries:
                    st.write("Libraries detected:")
                    for lib in libraries:
                        st.markdown(f"- {lib}")
                else:
                    st.write("No standard libraries detected")
            
            with col2:
                # Create radar chart for evaluation criteria
                if simulation_status != "Missing":
                    categories = ['Functionality', 'Code Quality', 'UX', 'Educational', 'Technical']
                    
                    # Add tooltips/explanations
                    category_explanations = {
                        'Functionality': 'How well the simulation works as expected',
                        'Code Quality': 'Code organization, readability and maintainability',
                        'UX': 'User experience and interface design quality',
                        'Educational': 'Educational value for students',
                        'Technical': 'Technical implementation quality'
                    }
                    
                    values = [
                        simulation_results.get('functionality_score', 0),
                        simulation_results.get('code_quality_score', 0),
                        simulation_results.get('ux_score', 0),
                        simulation_results.get('educational_value', 0),
                        simulation_results.get('technical_score', 0)
                    ]
                    
                    # Create figure and polar axis
                    fig = plt.figure(figsize=(6, 6))
                    ax = fig.add_subplot(111, polar=True)
                    
                    # Draw one axis per variable and add labels
                    angles = [n / float(len(categories)) * 2 * 3.14159 for n in range(len(categories))]
                    values += values[:1]  # Close the loop
                    angles += angles[:1]  # Close the loop
                    
                    # Draw the chart
                    ax.plot(angles, values, linewidth=2, linestyle='solid', label="Scores")
                    ax.fill(angles, values, alpha=0.25)
                    
                    # Fix axis to go in the right order and start at 12 o'clock
                    ax.set_theta_offset(3.14159 / 2)
                    ax.set_theta_direction(-1)
                    
                    # Draw axis lines for each angle and label
                    ax.set_thetagrids(np.degrees(angles[:-1]), categories)
                    
                    # Set y limits
                    ax.set_ylim(0, 10)
                    
                    # Add values
                    for angle, value in zip(angles[:-1], values[:-1]):
                        ax.text(angle, value + 0.5, f"{value:.1f}", horizontalalignment='center')
                    
                    st.pyplot(fig)
                    
                    # Add explanations below the chart
                    st.markdown("### Score Explanations")
                    for category, explanation in category_explanations.items():
                        st.markdown(f"- **{category}**: {explanation}")
                else:
                    st.error("No simulation found")
            
            st.subheader("Technical Assessment")
            st.markdown(simulation_results.get('technical_assessment', 'No assessment available'))
    
    with tab4:
        # Display report with minimal processing
        report_text = results['report']
        
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
        
    # Export options at the bottom with clear descriptions
    if st.session_state.evaluation_complete and st.session_state.results:
        st.header("Export Options")
        
        # Add descriptions for each export type
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
                # Convert results to JSON (keep weights internal but don't emphasize)
                json_results = {
                    'experiment_name': experiment_name,
                    'final_score': float(results['final_score']),
                    'component_scores': {
                        'structure': float(structure_score),
                        'content': float(content_score),
                        'simulation': float(simulation_score)
                    },
                    'template_percentage': float(template_percentage),
                    'detailed_evaluation': results.get('detailed_results', {}),
                    'report': results['report'],
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
                    data=results['report'],
                    file_name=f"{experiment_name.replace(' ', '_')}_qa_report.md",
                    mime="text/markdown",
                    use_container_width=True,
                    help="Human-readable report with analysis and recommendations"
                )

        with col3:
            st.markdown("**📋 Simple Metrics**")
            if st.button("Export as CSV", use_container_width=True):
                # Create a simple CSV with key metrics (no weights mentioned)
                csv_data = f"Metric,Score\n"
                csv_data += f"Overall Score,{results['final_score']:.1f}\n"
                csv_data += f"Structure Score,{structure_score:.1f}\n"
                csv_data += f"Content Score,{content_score:.1f}\n"
                csv_data += f"Simulation Score,{simulation_score:.1f}\n"
                csv_data += f"Template Percentage,{template_percentage:.1f}\n"
                
                st.download_button(
                    label="📥 Download CSV Report",
                    data=csv_data,
                    file_name=f"{experiment_name.replace(' ', '_')}_qa_metrics.csv",
                    mime="text/csv",
                    use_container_width=True,
                    help="Key metrics in spreadsheet format"
                )