from google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint import MatchNeighbor

from langgraph.managed.is_last_step import RemainingSteps
from langgraph.graph import StateGraph, END, START

from langfuse.decorators import observe, langfuse_context
from langfuse import Langfuse

from typing import TypedDict, Literal, List, Dict, Any
from typing_extensions import TypedDict
from datetime import datetime, timezone
from loguru import logger

from utils import PromptLoader, GCPStorageClient, Database
from services import VectorSearchService, LLMService
from config import config

import pandas as pd
import os
import re

class AgentState(TypedDict):
    supporting_docs: List[Dict[str, Any]]
    remaining_steps: RemainingSteps
    neighbours: int
    ai_response: str
    requirements: str
    project_id: int
    user_id: int


class RFPGraphService:
    def __init__(self):
        self.env = os.environ['ENV']
        self.vector_search = VectorSearchService()
        self.gcp_client = GCPStorageClient()
        self.db = Database.get_instance()
        self.llm_service = LLMService()
        self.prompt_loader = PromptLoader()
        self.graph = self._create_graph()
        
        # Configure the Langfuse client
        self.langfuse_client = Langfuse(
            public_key=config['env'][self.env]['LANGFUSE_PUBLIC_KEY'],
            secret_key=config['env'][self.env]['LANGFUSE_SECRET_KEY'],
            host=config['env'][self.env]['LANGFUSE_HOST'],
        )
        # langfuse_context.configure(
        #     secret_key=config['env'][self.env]['LANGFUSE_SECRET_KEY'],
        #     public_key=config['env'][self.env]['LANGFUSE_PUBLIC_KEY'],
        #     host=config['env'][self.env]['LANGFUSE_HOST'],
        #     enabled=True,
        # )

    def _has_supporting_documents(self, state) -> Literal["retrieve", "direct_answer"]:
        """
        Determine if we need to retrieve supporting documents by checking if
        the user has any indexed files in the project
        
        Args:
            state: Current state containing user_id and project_id
            
        Returns:
            Literal["retrieve", "direct_answer"]: Next step in the workflow
        """
        try:
            # Get files for this user and project
            files = self.db.get_project_files(
                project_id=state["project_id"],
                user_id=state["user_id"]
            )
            
            # Check if there are any indexed files
            has_indexed_files = any(file['is_indexed'] for file in files)

            if has_indexed_files:
                return "retrieve"
            else:
                logger.warning(f"No indexed files found for user {state['user_id']} in project {state['project_id']}. Answering without supporting documents.")
                return "direct_answer"
        
        except Exception as e:
            logger.exception(f"Error checking for supporting documents: {e}")
            return "direct_answer"  # Fallback to direct answer if database query fails

    def _parse_sufficiency_response(self, response: str) -> Dict[str, Any]:
        """
        Parse LLM response for sufficiency evaluation
        
        Args:
            response: Raw response from LLM
            
        Returns:
            Dict containing parsed response components
        """
        # Define regex patterns
        response_pattern = r"Response:\s*(YES|NO)"
        explanation_pattern = r"Explanation:\s*(.+)"
        additional_info_pattern = r"Additional Information Needed \(if NO\):\s*(.+)"
        
        # Extract values
        response_match = re.search(response_pattern, response)
        explanation_match = re.search(explanation_pattern, response)
        additional_info_match = re.search(additional_info_pattern, response)
        
        return {
            "response": response_match.group(1) if response_match else None,
            "explanation": explanation_match.group(1).strip() if explanation_match else None,
            "additional_info_needed": additional_info_match.group(1).strip() if additional_info_match else None
        }

    def _is_sufficient_info(self, state) -> Literal["generate", "retrieve_more"]:
        """
        Check if we have sufficient information to answer using LLM evaluation
        
        Args:
            state: Current state containing messages and supporting docs
            
        Returns:
            Literal["generate", "retrieve_more"]: Next step in workflow
        """
        try:
            # If no supporting docs or max steps reached, go to generate
            if not state["supporting_docs"] or state["remaining_steps"] == 2:
                return "generate"
            
            # Format context with source information
            context_parts = []
            for doc in state["supporting_docs"]:
                context_parts.append(
                    f"Source:  {doc['source']}\n"
                    f"Content:\n"
                    f"{doc['text']}"
                )
            context = "\n\n".join(context_parts)
            question = state["requirements"]
            
            # Get LLM evaluation
            response = self.llm_service.get_sufficiency_completion(
                context=context,
                question=question,
                trace=self.current_trace
            )
            
            # Parse response
            parsed = self._parse_sufficiency_response(response)
            
            # Log evaluation results
            logger.info(f"Sufficiency evaluation: {parsed}")
            
            # Return based on LLM response
            if parsed["response"] == "YES":
                return "generate"
            else:
                logger.warning(f"Insufficient information: {parsed['explanation']}")
                logger.warning(f"Additional info needed: {parsed['additional_info_needed']}")
                return "retrieve_more"
            
        except Exception as e:
            logger.exception(f"Error evaluating information sufficiency: {e}")
            # Fallback to generate on error
            return "generate"

    def _process_match_neighbors(self, match_group: List[MatchNeighbor]) -> List[str]:
        """
        Process match neighbors to get document texts within a window around matching chunks
        
        Args:
            match_group: Group of MatchNeighbor objects from vector search
            
        Returns:
            List[str]: List of document texts within the configured window
        """
        processed_files = set()  # Track which files we've already processed
        documents = []
        
        # Configure the window size - 8
        window_before = 4  # Number of chunks to include before match
        window_after = 3  # Number of chunks to include after match
        
        for neighbor in match_group:
            # Extract file_id, user_id and chunk_number from restricts
            file_id = None
            user_id = None
            chunk_number = None
            for restrict in neighbor.restricts:
                if restrict.name == "file_id":
                    file_id = int(restrict.allow_tokens[0])
                elif restrict.name == "user_id":
                    user_id = int(restrict.allow_tokens[0])
                elif restrict.name == "chunk_number":
                    chunk_number = int(restrict.allow_tokens[0])
            
            # Skip if we've already processed this file or missing required info
            if not all([file_id, user_id, chunk_number]):
                continue
            
            # Calculate window boundaries
            start_chunk = max(1, chunk_number - window_before)  # Ensure we don't go below 1
            end_chunk = chunk_number + window_after
            
            # Get vectors within the window, ordered by chunk number
            vectors = self.db.get_file_vectors_ordered(
                file_id=file_id,
                user_id=user_id,
                start_chunk=start_chunk,
                end_chunk=end_chunk
            )
            
            if vectors:  # Only process if we found vectors
                file_name = self.db.get_file_name(file_id, user_id)
                complete_text = "\n\n".join(vector['text'] for vector in vectors)
                documents.append({
                    "source": file_name,
                    "text": complete_text
                })
                
                processed_files.add(file_id)
        
        return documents

    @observe(as_type="retrieval") 
    def _retrieve_documents(self, state):
        try:
            query = state["requirements"]
            
            # Create a retrieval span
            retrieval_span = self.current_trace.span(
                name="document-retrieval",
                input=query
            )
            
            # Get search results
            results = self.vector_search.search(
                query=query,
                user_id=state["user_id"],
                project_id=state["project_id"],
                limit=state["neighbours"]
            )
            
            # Process each match group and track metadata
            supporting_docs = []
            retrieval_metadata = []
            
            for match in results:
                metadata = {}
                for restrict in match.restricts:
                    metadata[restrict.name] = restrict.allow_tokens[0]
                retrieval_metadata.append(metadata)
                
            documents = self._process_match_neighbors(results)
            supporting_docs.extend(documents)
            
            # Update retrieval span with results
            retrieval_span.end(
                output=supporting_docs,
                metadata={
                    "retrieved_chunks": retrieval_metadata
                }
            )
            
            if not supporting_docs:
                error_msg = f"No relevant documents found for query in project {state['project_id']}"
                logger.warning(error_msg)
                retrieval_span.update(
                    level="WARNING",
                    metadata={"warning": error_msg}
                )
            
            return {"supporting_docs": supporting_docs}
            
        except Exception as e:
            error_msg = f"Error retrieving documents: {str(e)}"
            logger.exception(error_msg)
            if 'retrieval_span' in locals():
                retrieval_span.update(
                    level="ERROR",
                    metadata={"error": error_msg}
                )
            return {"supporting_docs": []}

    @observe(as_type="generation")
    def _generate_answer(self, state):
        try:
            # Format context with source information
            context_parts = []
            for doc in state["supporting_docs"]:
                context_parts.append(
                    f"Source: {doc['source']}\n"
                    f"Content:\n"
                    f"{doc['text']}"
                )
            context = "\n\n".join(context_parts)
            
            # # Create final generation
            # final_generation = self.current_trace.generation(
            #     name="final-response",
            #     model=config['env'][self.env]['GCP_LLM_MODEL_NAME'],
            #     input={
            #         "context": context,
            #         "requirements": state["requirements"]
            #     }
            # )
            
            # Get completion from LLM
            response = self.llm_service.get_rfp_completion(
                context=context,
                new_requirements=state["requirements"],
                trace=self.current_trace
            )
            
            if not response:
                error_msg = "Failed to generate response from LLM"
                logger.error(error_msg)
                # final_generation.update(
                #     level="WARNING",
                #     status_message="Response not received from LLM",
                #     metadata={"error": error_msg}
                # )
                response = "I apologize, but I was unable to generate a response at this time."
            
            # End the generation with the response
            # final_generation.end(
            #     output=response
            # )

            self.current_trace.update(
                level="INFO",
                input=state["requirements"],
                output=response
            )
            
            return {"ai_response": response}
            
        except Exception as e:
            error_msg = f"Error generating answer: {str(e)}"
            logger.exception(error_msg)
            # if 'final_generation' in locals():
                # final_generation.update(
                #     level="ERROR",
                #     metadata={"error": error_msg}
                # )
            return {"ai_response": "I apologize, but I was unable to generate a response at this time."}

    def _increase_neighbours(self, state):
        return {"neighbours": state["neighbours"] + 1}
    
    def _create_graph(self):
        """Create the workflow graph"""
        workflow = StateGraph(AgentState)
        
        workflow.add_node("retrieve", self._retrieve_documents)
        workflow.add_node("generate", self._generate_answer)
        workflow.add_node("increase_neighbours", self._increase_neighbours)

        workflow.add_conditional_edges(
            START,
            self._has_supporting_documents,
            {
                "retrieve": "retrieve",
                "direct_answer": "generate"
            }
        )
        
        workflow.add_conditional_edges(
            "retrieve",
            self._is_sufficient_info,
            {
                "generate": "generate",
                "retrieve_more": "increase_neighbours"
            }
        )
        workflow.add_edge("increase_neighbours", "retrieve")
        workflow.add_edge("generate", END)
        
        return workflow.compile()

    @observe()
    def process_rfp(self, rfp_name: str, bucket: str, gcp_path: str, 
                         project_id: int, project_name: str, user_id: int, username: str):
        """Process RFP using the graph workflow"""
        try:
            # Insert into DB
            rfp_id = self.db.insert_rfp(
                name=rfp_name,
                gcp_path=gcp_path,
                bucket=bucket,
                project_id=project_id,
                user_id=user_id
            )
            # Create a unique session ID for this RFP processing
            rfp_name_stripped = rfp_name.replace(" ", "_")
            project_name_stripped = project_name.replace(" ", "_")
            date_time = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
            session_id = f"{rfp_name_stripped}_{project_name_stripped}_{date_time}"

            # Download and read file
            temp_file_path = self.gcp_client.download_blob_to_temp(bucket, gcp_path)
            
            if temp_file_path.endswith('.csv'):
                df = pd.read_csv(temp_file_path)
                output_extension = 'csv'
            else:
                df = pd.read_excel(temp_file_path)
                output_extension = 'xlsx'
            
            answers = []
            
            # Process each row
            for idx, row in df.iterrows():
                # Create a new trace for each row
                self.current_trace = self.langfuse_client.trace(
                    name=f"RFP Row {idx+1}",
                    session_id=session_id,
                    user_id=username,
                    metadata={
                        "row_number": idx + 1,
                        "project_id": project_id,
                        "project_name": project_name,
                        "file_name": rfp_name,
                        "user_id": user_id
                    }
                )
                
                requirements = ""
                for column in row.index:
                    requirements += f"{column}: \n{row[column]}\n\n"
                
                # Initialize graph state
                state = {
                    "requirements": requirements,
                    "supporting_docs": [],
                    "user_id": user_id,
                    "project_id": project_id,
                    "neighbours": 3,
                    "ai_response": "No response generated"
                }
                
                # Run the graph
                logger.debug(f"Running graph for row {idx+1}")
                final_state = self.graph.invoke(state, {"recursion_limit": int(config['env'][self.env]['RECURSION_LIMIT'])})
                answers.append(final_state["ai_response"])

            
            # Make sure all events are sent to Langfuse
            self.langfuse_client.flush()
            
            # Add answers column and save
            df['AI Response'] = answers
            processed_filename = f"{rfp_name_stripped}_processed.{output_extension}"
            temp_output_path = f"/tmp/{processed_filename}"
            
            if output_extension == 'csv':
                df.to_csv(temp_output_path, index=False)
            else:
                df.to_excel(temp_output_path, index=False)
            
            # Upload to GCP
            processed_gcp_path = self.gcp_client._upload_to_gcp(
                filename=processed_filename,
                bucket=bucket,
                username=username,
                project_name=project_name
            )
            
            # Cleanup
            self.gcp_client.cleanup_temp_file(temp_file_path)
            self.gcp_client.cleanup_temp_file(temp_output_path)
            
            self.db.update_rfp_status(
                rfp_id=rfp_id,
                status='completed',
                processed_file_path=processed_gcp_path
            )

            return {
                "message": "RFP processed successfully",
                "file_info": {
                    "bucket": bucket,
                    "gcp_path": processed_gcp_path
                },
                "processed_file": df.to_dict('records')
            }
        

            
        except Exception as e:
            error_msg = f"Error processing RFP with graph: {str(e)}"
            logger.exception(error_msg)
            self.current_trace.update(
                level="ERROR",
                metadata={"error": error_msg}
            )
            self.db.update_rfp_status(
                rfp_id=rfp_id,
                status='failed'
            )
            raise 