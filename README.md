# Virtual Labs AI Quality Assurance Tool

A comprehensive tool for automatically evaluating Virtual Labs repositories across structure, content quality, and browser functionality using AI-powered analysis.

## What It Does

The tool performs multi-dimensional quality assessment:

- **Structure Compliance**: Validates repository structure against Virtual Labs standards
- **Content Evaluation**: Analyzes educational content quality and detects template placeholders
- **Browser Testing**: Uses Playwright to test simulation functionality across different browsers
- **Automated Reporting**: Generates detailed markdown reports with actionable recommendations

## Architecture

The system uses an agent-based architecture where each component handles a specific evaluation aspect:

```
tool-ai-quality-assurance-iiith/
├── main.py                 # Main pipeline
├── ui.py                   # Streamlit web interface
├── BaseAgent.py            # Base class for all agents
├── config_loader.py        # Configuration management
├── config.toml             # Configuration file
└── Agents/
    ├── RepositoryAgent.py           # Repository metadata analysis
    ├── StructureComplianceAgent.py  # File structure validation
    ├── ContentEvaluationAgent.py    # Content quality assessment
    ├── PlaywrightTestingAgent.py    # Browser functionality testing
    └── ScoreCalculationAgent.py     # Final scoring and reporting
```

## Setup

### Prerequisites

- Python 3.10+
- Google AI API key (for Gemini)
- Node.js (for Playwright browser automation)

### Installation

1. Clone and setup environment:
```bash
git clone https://github.com/virtual-labs/tool-ai-quality-assurance-iiith.git
cd tool-ai-quality-assurance-iiith
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

3. Configure API access:
```bash
# Create .env file
echo "GOOGLE_API_KEY=your_api_key_here" > .env
```

## Running the Tool

### Activate venv
```bash
source venv/bin/activate
```

### Web Interface (Recommended)
```bash
streamlit run ui.py
```

### Command Line
```bash
python main.py
```

## Extending the Tool

### Adding New Evaluation Criteria

1. Create a new agent class inheriting from `BaseAgent`:
```python
class MyEvaluationAgent(BaseAgent):
    role = "My Specific Evaluator"
    
    def __init__(self, repo_path):
        self.repo_path = repo_path
        super().__init__(self.role, basic_prompt=self.prompt_template)
    
    def get_output(self):
        # Implement your evaluation logic
        return evaluation_results
```

2. Integrate into the pipeline (`main.py`):
```python
# Add to evaluate_repository method
my_agent = MyEvaluationAgent(self.temp_dir)
my_agent.set_llm(self.llm)
my_results = my_agent.get_output()
self.evaluation_results['my_evaluation'] = my_results
```

3. Update scoring weights in `config.toml` and `ScoreCalculationAgent`

### Customizing Evaluation Logic

Agents can be enhanced by:
- Modifying prompt templates for different evaluation criteria
- Adding new similarity metrics for template detection
- Implementing custom file parsing logic
- Extending browser testing scenarios

### UI Customization

The Streamlit interface (ui.py) can be extended with:
- New visualization components
- Additional export formats
- Custom result filtering and analysis
- Real-time evaluation progress tracking