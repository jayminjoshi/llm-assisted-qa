from google.cloud.pubsub_v1.subscriber.message import Message
from google.cloud import pubsub_v1

from concurrent.futures import TimeoutError
from typing import Callable, List, Dict
from config import config
from loguru import logger

from routers import (
    RFPGraphRouter,
    DocumentRouter,
    CrawlerRouter
)

import asyncio
import json
import os

# Initialize services
rfp_graph_router = RFPGraphRouter()
document_router = DocumentRouter()
crawler_router = CrawlerRouter()

async def handle_message(message: Message) -> None:
    """Route messages to appropriate handlers based on request_type"""
    # Acknowledge the message
    message.ack()
    
    try:
        data = json.loads(message.data.decode('utf-8'))
        request_type = data.get('request_type')
        
        # Map request types to handlers
        handler_mapping = {
            'rfp': rfp_graph_router.process_rfp_with_graph,
            'document_process': document_router.process_document,
            'document_delete': document_router.delete_document,
            'project_delete': document_router.delete_project,
            'crawl': crawler_router.crawl_url
        }
        
        logger.info(f"Routing {request_type} request to appropriate handler")
        handler = handler_mapping[request_type]
        
        # Handle async vs sync handlers
        if asyncio.iscoroutinefunction(handler):
            await handler(data)
        else:
            handler(data)
            
    except Exception as e:
        logger.exception("Error processing message")

def callback(message: Message):
    """Wrapper function to run async handle_message"""
    asyncio.run(handle_message(message))

def main():
    """Main entry point for the application"""
    try:
        # Pub/Sub configuration
        env = os.environ['ENV']
        project_id = config['env'][env]['GCP_PROJECT_ID']
        subscription_id = config['env'][env]['GCP_SUBSCRIPTION_ID']

        subscriber = pubsub_v1.SubscriberClient()
        subscription_path = subscriber.subscription_path(
            project_id,
            subscription_id
        )
        
        streaming_pull_future = subscriber.subscribe(
            subscription_path,
            callback=callback
        )
        
        logger.info(f"Listening for messages on {subscription_path}")
        
        # Wait for messages indefinitely
        try:
            streaming_pull_future.result()
        except TimeoutError:
            streaming_pull_future.cancel()
            streaming_pull_future.result()
                
    except Exception as e:
        logger.exception("Fatal error in main process")
        raise

if __name__ == "__main__":
    main()