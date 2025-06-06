import os
import toml

def load_config():
    """Load and return configuration from toml file"""
    config_path = os.path.join(os.path.dirname(__file__), "config.toml")
    try:
        config = toml.load(config_path)
        return config
    except Exception as e:
        print(f"Warning: Could not load config file: {str(e)}")
        # Define minimal default configuration
        return {
            "general": {"default_model": "gemini-2.0-flash", "temp_cleanup": True},
            "llm": {"temperature": 0.2, "max_tokens": 100000},
            "weights": {"structure": 0.25, "content": 0.5, "simulation": 0.25},
            "thresholds": {
                "structure_minimum": 3.0,
                "template_penalty": 0.3,
                "good_score": 8.0,
                "satisfactory_score": 5.0,
                "minimum_content_length": 50
            }
        }