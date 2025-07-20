# Virtual Labs AI Quality Assurance Tool

A comprehensive tool for automatically evaluating Virtual Labs repositories across structure, content quality, and browser functionality using AI-powered analysis.

## Overview

### What It Does

The tool performs multi-dimensional quality assessment:

- **Structure Compliance**: Validates repository structure against Virtual Labs standards
- **Content Evaluation**: Analyzes educational content quality and detects template placeholders using AI
- **Browser Testing**: Uses Playwright to test simulation functionality across different browsers
- **Automated Reporting**: Generates detailed markdown reports with actionable recommendations

### Architecture

The system uses an agent-based architecture where each component handles a specific evaluation aspect:

```
tool-ai-quality-assurance-iiith/
├── main.py                          # Main pipeline
├── ui.py                            # Streamlit web interface
├── BaseAgent.py                     # Base class for all agents
├── config_loader.py                 # Configuration management
├── config.toml                      # Configuration file
└── Agents/
    ├── RepositoryAgent.py           # Repository metadata analysis
    ├── StructureComplianceAgent.py  # File structure validation
    ├── ContentEvaluationAgent.py    # Content quality assessment
    ├── PlaywrightTestingAgent.py    # Browser functionality testing
    └── ScoreCalculationAgent.py     # Final scoring and reporting
```

## Setup and Installation

This guide provides a step-by-step process to set up the project and all its dependencies correctly.

### 1. System Prerequisites

First, ensure your system has the necessary base software installed.

#### Python
Version 3.10 or newer is required.

```bash
python3 --version
```

#### Node.js & npm
We recommend using nvm (Node Version Manager) to avoid version conflicts.

Install nvm:
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
```

Reload your shell (`source ~/.bashrc`) and install the recommended Node.js version:
```bash
nvm install --lts
nvm use --lts
```

#### Git
Required for cloning the repository.

### 2. Project Installation

Follow these steps to download the project and install its dependencies.

#### Clone the Repository
```bash
git clone https://github.com/virtual-labs/tool-ai-quality-assurance-iiith.git
cd tool-ai-quality-assurance-iiith
```

#### Create and Activate Python Virtual Environment
This isolates the project's Python packages.

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

#### Install Python & Playwright Dependencies
This installs all required Python libraries and the necessary browser binaries for Playwright.

```bash
pip install -r requirements.txt
playwright install
```

#### Install Lighthouse
This tool is used for performance audits and is installed globally via npm.

```bash
npm install -g lighthouse
```

### 3. Configuration

#### Set up Google API Key
The tool requires a Google Gemini API key for its AI evaluation features.

```bash
# Create a .env file with your API key
echo "GOOGLE_API_KEY=your_api_key_here" > .env
```

#### Configure CHROME_PATH for Lighthouse
This step is crucial for running Lighthouse from the command line. It tells Lighthouse where to find the browser that Playwright downloaded.

```bash
# This command adds the path to your shell's startup file
echo -e '\n# Set CHROME_PATH for Lighthouse\nexport CHROME_PATH=$(find ~/.cache/ms-playwright -type f -name "chrome" | head -n 1)' >> ~/.bashrc

# Reload your shell to apply the change
source ~/.bashrc
```

## Usage

Ensure your virtual environment is active before running the tool.

```bash
source venv/bin/activate
```

### Web Interface (Recommended)

Launch the user-friendly Streamlit interface.

```bash
streamlit run ui.py
```

### Command Line

Run the full evaluation pipeline directly from the command line.

```bash
python main.py
```

## Extending the Tool

### Adding New Evaluation Criteria

1. **Create a new agent class** inheriting from BaseAgent:

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

2. **Integrate into the pipeline** (main.py):

```python
# Add to evaluate_repository method
my_agent = MyEvaluationAgent(self.temp_dir)
my_agent.set_llm(self.llm)
my_results = my_agent.get_output()
self.evaluation_results['my_evaluation'] = my_results
```

3. **Update scoring weights** in config.toml and ScoreCalculationAgent.

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