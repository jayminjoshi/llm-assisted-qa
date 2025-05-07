import yaml
from pathlib import Path
from typing import Dict, Any
from loguru import logger

class PromptLoader:
    _instance = None
    _prompts = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PromptLoader, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self._load_prompts()
        self._initialized = True

    def _load_prompts(self):
        """Load prompts from YAML file"""
        try:
            prompt_path = Path(__file__).parent.parent / "config" / "prompts.yaml"
            with open(prompt_path, 'r') as f:
                self._prompts = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading prompts: {e}")
            self._prompts = {}

    def get_prompt(self, key: str) -> Dict[str, str]:
        """
        Get prompt by key
        
        Args:
            key (str): Prompt key (e.g., 'rfp_expert')
            
        Returns:
            Dict[str, str]: Dictionary containing system message and template
        """
        if not self._prompts or key not in self._prompts:
            raise KeyError(f"Prompt not found: {key}")
        return self._prompts[key]

    def format_prompt(self, key: str, **kwargs: Any) -> str:
        """
        Format prompt template with variables
        
        Args:
            key (str): Prompt key
            **kwargs: Variables to format the template with
            
        Returns:
            str: Formatted prompt
        """
        prompt = self.get_prompt(key)
        return f"{prompt['system']}\n\n{prompt['template'].format(**kwargs)}" 