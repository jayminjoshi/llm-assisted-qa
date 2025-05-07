from services import RFPGraphService
from utils.database import Database
from pydantic import BaseModel
from loguru import logger

import json

class RFPRequest(BaseModel):
    rfp_name: str
    bucket: str
    gcp_path: str
    project_id: int
    project_name: str
    user_id: int
    username: str
    timestamp: str


class RFPGraphRouter:

    def __init__(self):
        self.rfp_graph_service = RFPGraphService()
        self.db = Database.get_instance()

    def process_rfp_with_graph(
        self,
        request: RFPRequest
    ):
        logger.debug(f"Received graph processing request: {request}")
    
        try:
            result = self.rfp_graph_service.process_rfp(
                rfp_name=request['rfp_name'],
                bucket=request['bucket'],
                gcp_path=request['gcp_path'],
                project_id=request['project_id'],
                project_name=request['project_name'],
                user_id=request['user_id'],
                username=request['username']
            )
            
            return json.dumps(result)

        except Exception as e:
            logger.exception("Error processing RFP with graph")
            raise