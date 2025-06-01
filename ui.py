import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os
import json
import time
from main import QAPipeline
import numpy as np

st.set_page_config(
    page_title="Virtual Labs QA",
    page_icon="🔍",
    layout="wide"
)

st.title("Virtual Labs Quality Assurance Pipeline")
st.markdown("This tool evaluates the quality of Virtual Labs repositories based on structure, content, and simulation.")

# Initialize session state variables
if 'pipeline' not in st.session_state:
    st.session_state.pipeline = QAPipeline()
if 'evaluation_complete' not in st.session_state:
    st.session_state.evaluation_complete = False
if 'results' not in st.session_state:
    st.session_state.results = None
if 'error_message' not in st.session_state:
    st.session_state.error_message = None
if 'progress' not in st.session_state:
    st.session_state.progress = 0
if 'progress_message' not in st.session_state:
    st.session_state.progress_message = ""

# Side panel with options
with st.sidebar:
    st.header("Options")
    model = st.selectbox(
        "Select LLM model",
        ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-2.5-flash-preview-05-20"]
    )
    
    if st.button("Reset Evaluation", type="secondary"):
        st.session_state.pipeline.cleanup()
        st.session_state.evaluation_complete = False
        st.session_state.results = None
        st.session_state.error_message = None
        st.session_state.progress = 0
        st.session_state.progress_message = ""
        st.session_state.pipeline = QAPipeline(model=model)
        st.rerun()
        
    st.markdown("---")
    st.markdown("**VLabs QA Tool v1.0**")

# Step 1: Input repository URL
with st.container():
    st.header("Step 1: Repository Information")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        repo_url = st.text_input("Enter Git Repository URL", 
                            placeholder="https://github.com/username/repo")
    
    with col2:
        analyze_btn = st.button("Analyze Repository", type="primary", use_container_width=True)
    
    if analyze_btn and repo_url:
        st.session_state.progress = 0
        st.session_state.progress_message = "Cloning repository..."
        progress_bar = st.progress(st.session_state.progress)
        
        with st.spinner("Cloning repository..."):
            success, message = st.session_state.pipeline.clone_repository(repo_url)
            
            if not success:
                st.session_state.error_message = message
                st.error(message)
            else:
                st.session_state.progress = 25
                st.session_state.progress_message = "Evaluating structure..."
                progress_bar.progress(st.session_state.progress, text=st.session_state.progress_message)
                
                with st.spinner("Evaluating quality..."):
                    try:
                        # Step-by-step progress updates
                        success, message = st.session_state.pipeline.evaluate_repository()
                        
                        # Update progress at each major step
                        st.session_state.progress = 50
                        st.session_state.progress_message = "Evaluating content..."
                        progress_bar.progress(st.session_state.progress, text=st.session_state.progress_message)
                        time.sleep(0.5)
                        
                        st.session_state.progress = 75
                        st.session_state.progress_message = "Evaluating simulation..."
                        progress_bar.progress(st.session_state.progress, text=st.session_state.progress_message)
                        time.sleep(0.5)
                        
                        st.session_state.progress = 90
                        st.session_state.progress_message = "Generating final report..."
                        progress_bar.progress(st.session_state.progress, text=st.session_state.progress_message)
                        time.sleep(0.5)
                        
                        if not success:
                            st.session_state.error_message = message
                            st.error(message)
                        else:
                            st.session_state.evaluation_complete = True
                            st.session_state.results = st.session_state.pipeline.get_results()
                            
                            st.session_state.progress = 100
                            st.session_state.progress_message = "Evaluation complete!"
                            progress_bar.progress(st.session_state.progress, text=st.session_state.progress_message)
                            
                            st.success("Evaluation completed successfully!")
                    except Exception as e:
                        st.error(f"Evaluation failed: {str(e)}")

# Step 2: Display Results
if st.session_state.evaluation_complete and st.session_state.results:
    results = st.session_state.results
    
    st.header("Quality Assessment Results")
    
    # Extract experiment name if available
    experiment_name = "Unknown Experiment"
    if 'experiment_name' in results:
        experiment_name = results['experiment_name']
    
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
                                st.warning("This appears to be template content that needs to be customized")
                            
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
                            ax.axvline(x=7, color='gray', linestyle='--', alpha=0.5)
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
        # Full report in Markdown
        st.markdown(results['report'])
        
    # Export options at the bottom
    st.header("Export Options")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Export as JSON", use_container_width=True):
            # Convert results to JSON
            json_results = {
                'experiment_name': experiment_name,
                'final_score': float(results['final_score']),
                'component_scores': {
                    'structure': float(structure_score),
                    'content': float(content_score),
                    'simulation': float(simulation_score)
                },
                'report': results['report']
            }
            
            st.download_button(
                label="Download JSON Report",
                data=json.dumps(json_results, indent=2),
                file_name=f"{experiment_name.replace(' ', '_')}_qa_report.json",
                mime="application/json",
                use_container_width=True
            )
    
    with col2:
        if st.button("Export as Markdown", use_container_width=True):
            st.download_button(
                label="Download Markdown Report",
                data=results['report'],
                file_name=f"{experiment_name.replace(' ', '_')}_qa_report.md",
                mime="text/markdown",
                use_container_width=True
            )
    
    with col3:
        if st.button("Export as CSV", use_container_width=True):
            # Create a simple CSV with key metrics
            csv_data = f"Metric,Score\n"
            csv_data += f"Overall Score,{results['final_score']:.1f}\n"
            csv_data += f"Structure Score,{structure_score:.1f}\n"
            csv_data += f"Content Score,{content_score:.1f}\n"
            csv_data += f"Simulation Score,{simulation_score:.1f}\n"
            csv_data += f"Template Percentage,{template_percentage:.1f}\n"
            
            st.download_button(
                label="Download CSV Report",
                data=csv_data,
                file_name=f"{experiment_name.replace(' ', '_')}_qa_metrics.csv",
                mime="text/csv",
                use_container_width=True
            )