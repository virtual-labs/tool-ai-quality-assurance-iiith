# Tool: AI Quality Assurance – IIITH

This repository contains the AI Quality Assurance tool developed by the Virtual Labs team at IIITH.

## Getting Started

Follow these steps to set up and run the application locally.

### 1. Clone the Repository

```bash
git clone https://github.com/virtual-labs/tool-ai-quality-assurance-iiith.git
cd tool-ai-quality-assurance-iiith
```

### 2. Create and Activate a Virtual Environment

It is recommended to use a virtual environment to manage dependencies.

```bash
python -m venv venv
```

#### On Windows:

```bash
venv\Scripts\activate
```

#### On macOS/Linux:

```bash
source venv/bin/activate
```

### 3. Install the Required Packages

Install the necessary dependencies from the `requirements.txt` file.

```bash
pip install -r requirements.txt
```

### 4. Configure the Environment Variables

Create a `.env` file if it doesn't already exist:

```bash
touch .env
```

Open `.env` and add the following:

```env
GOOGLE_API_KEY=Your_Google_API_Key_Here
```

Replace `Your_Google_API_Key_Here` with your actual Google API Key.

### 5. Run the Application

Start the Streamlit UI:

```bash
streamlit run ui.py
```
