from google.api_core.exceptions import TooManyRequests

from vertexai.preview.generative_models import GenerativeModel
from vertexai.preview.tokenization import get_tokenizer_for_model
from vertexai import init

from loguru import logger
from time import sleep

from utils.prompt_loader import PromptLoader
from config import config

import os

class LLMService:
    MAX_RETRIES = 3
    RETRY_DELAY = 20  # seconds

    def __init__(self, project: str = None, location: str = None):
        
        # Initialize Vertex AI
        init(project=project, location=location)

        self.env = os.environ['ENV']
        
        # Initialize the model and prompt loader
        self.model_name = config['env'][self.env]['GCP_LLM_MODEL_NAME']
        self.model = GenerativeModel(self.model_name)
        self.prompt_loader = PromptLoader()

        # Track approximate run cost
        self.run_cost = 0

    def _handle_llm_request(self, prompt: str, temperature: float = 0.0, generation=None) -> str | None:
        """
        Handle LLM request with retries for rate limiting
        
        Args:
            prompt (str): The formatted prompt to send
            temperature (float): Temperature setting for generation
            generation (Generation): Langfuse generation object
            
        Returns:
            str | None: Generated response or None on failure
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": temperature,
                        "top_p": 1,
                        "top_k": 1,
                        "max_output_tokens": 2048,
                    }
                )
                return response.text

            except TooManyRequests as e:
                if attempt < self.MAX_RETRIES - 1:
                    error_msg = f"Rate limit hit, attempt {attempt + 1}/{self.MAX_RETRIES}. Waiting {self.RETRY_DELAY} seconds..."
                    logger.warning(error_msg)
                    sleep(self.RETRY_DELAY)
                else:
                    error_msg = f"Rate limit exceeded after {self.MAX_RETRIES} attempts"
                    logger.error(error_msg)
                    if generation:
                        generation.update(
                            level="ERROR",
                            metadata={
                                "error": str(e),
                                "final_attempt": self.MAX_RETRIES
                            }
                        )
                    return None

            except Exception as e:
                error_msg = f"Error generating completion: {str(e)}"
                logger.exception(error_msg)
                if generation:
                    generation.update(
                        level="ERROR",
                        metadata={"error": error_msg}
                    )
                return None

    def _calculate_token_cost(self, token_count: int, is_input: bool) -> float:
        """
        Calculate cost based on token count and whether it's input or output
        
        Args:
            token_count (int): Number of tokens
            is_input (bool): True if calculating input cost, False for output
            
        Returns:
            float: Calculated cost in dollars
        """

        # (Ref : https://ai.google.dev/pricing#1_5flash)
        
        if token_count <= 128000:  # Standard tier
            rate = 0.000000075 if is_input else 0.0000003
        else:  # Longer prompts 
            rate = 0.00000015 if is_input else 0.0000006
        
        return round(token_count * rate, 6)

    def get_rfp_completion(self, context: str, new_requirements: str, temperature: float = 0.0, trace=None) -> str | None:
        """
        Get a completion from Gemini using Vertex AI
        
        Args:
            context (str): Historical RFPs context
            new_requirements (str): New requirement to analyze
            temperature (float): Controls randomness (0.0 to 1.0)
        
        Returns:
            str: The generated response
        """
        try:
            # Format prompt using loader
            prompt = self.prompt_loader.format_prompt(
                key="rfp_expert",
                historical_rfps=context,
                requirement=new_requirements
            )
            
            logger.info(f"Sending prompt to LLM: \n\n{prompt}")
            
            # Get token count and calculate cost
            tokenizer = get_tokenizer_for_model(self.model_name)
            input_tokens = tokenizer.count_tokens(prompt)
            input_cost = self._calculate_token_cost(input_tokens.total_tokens, is_input=True)
            
            logger.info(f"Token count: {input_tokens.total_tokens}")
            logger.info(f"INPUT COST FOR THIS REQUEST: {input_cost}")

            # Create a generation if trace is provided
            generation = None
            if trace:
                generation = trace.generation(
                    name="rfp-completion",
                    model=self.model_name,
                    input=prompt,
                    metadata={
                        "temperature": temperature,
                    },
                    usage_details={
                        "input_tokens": input_tokens.total_tokens,
                        "total": input_tokens.total_tokens
                    },
                    cost_details={
                        "input": input_cost,
                        "total": input_cost
                    }
                )
            
            # Get response with retry handling
            response_text = self._handle_llm_request(prompt, temperature, generation)
            
            if response_text:
                # Calculate response tokens and cost
                output_tokens = tokenizer.count_tokens(response_text)
                output_cost = self._calculate_token_cost(output_tokens.total_tokens, is_input=False)
                total_cost = input_cost + output_cost
                total_tokens = input_tokens.total_tokens + output_tokens.total_tokens

                if generation:
                    generation.end(
                        output=response_text,
                        usage_details={
                            "input_tokens": input_tokens.total_tokens,
                            "output_tokens": output_tokens.total_tokens,
                            "total": total_tokens
                        },
                        cost_details={
                            "input": input_cost,
                            "output": output_cost,
                            "total": total_cost
                        }
                    )
                return response_text
            return None
            
        except Exception as e:
            logger.exception(f"Error in get_rfp_completion: {e}")
            return None
    
    def get_sufficiency_completion(self, context: str, question: str, temperature: float = 0.7, trace=None) -> str | None:
        """
        Get a completion from Gemini-1.5 using Vertex AI
        
        Args:
            context (str): Supporting documents
            question (str): Question to answer
            temperature (float): Controls randomness (0.0 to 1.0)
        
        Returns:
            str: The generated response
        """
        try:
            # Format prompt using loader
            prompt = self.prompt_loader.format_prompt(
                key="sufficiency_evaluator",
                context=context,
                question=question
            )

            # Get token count and calculate cost
            tokenizer = get_tokenizer_for_model(self.model_name)
            input_tokens = tokenizer.count_tokens(prompt)
            input_cost = self._calculate_token_cost(input_tokens.total_tokens, is_input=True)
            
            logger.info(f"Token count: {input_tokens.total_tokens}")
            logger.info(f"INPUT COST FOR THIS REQUEST: {input_cost}")

            # Create a generation if trace is provided
            generation = None
            if trace:
                generation = trace.generation(
                    name="sufficiency-evaluation",
                    model=self.model_name,
                    input=prompt,
                    metadata={
                        "temperature": temperature,
                    },
                    usage_details={
                        "input_tokens": input_tokens.total_tokens,
                        "total": input_tokens.total_tokens
                    },
                    cost_details={
                        "input": input_cost,
                        "total": input_cost
                    }
                )
            
            # Get response with retry handling
            response_text = self._handle_llm_request(prompt, temperature, generation)
            
            if response_text:
                # Calculate response tokens and cost
                output_tokens = tokenizer.count_tokens(response_text)
                output_cost = self._calculate_token_cost(output_tokens.total_tokens, is_input=False)
                total_cost = input_cost + output_cost
                total_tokens = input_tokens.total_tokens + output_tokens.total_tokens

                if generation:
                    generation.end(
                        output=response_text,
                        usage_details={
                            "input_tokens": input_tokens.total_tokens,
                            "output_tokens": output_tokens.total_tokens,
                            "total": total_tokens
                        },
                        cost_details={
                            "input": input_cost,
                            "output": output_cost,
                            "total": total_cost
                        }
                    )
                return response_text
            return None
            
        except Exception as e:
            logger.exception(f"Error in get_sufficiency_completion: {e}")
            return None