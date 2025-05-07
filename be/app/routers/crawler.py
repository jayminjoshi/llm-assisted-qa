from pydantic import BaseModel, HttpUrl
from services import CrawlerService
from loguru import logger
from typing import List
import asyncio

class CrawlRequest(BaseModel):
    urls: List[HttpUrl]
    project_id: int
    user_id: int

class CrawlerRouter:
    
    def __init__(self):
        self.crawler_service = CrawlerService()

    async def crawl_url(self, request: dict):
        logger.debug(f"Received request: {request}")
        
        try:
            for url in request['urls']:
                result = await self.crawler_service.process_url(
                    url=str(url),
                    project_id=request['project_id'],
                    user_id=request['user_id'],
                )
            return {"message": "Successfully processed all URLs"}
        
        except Exception as e:
            logger.error(f"Error processing URLs: {str(e)}")
            raise 