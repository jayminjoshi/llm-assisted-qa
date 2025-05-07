from utils.extractor_factory import ExtractorFactory
from services import VectorSearchService
from utils.database import Database

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from datetime import datetime, timezone
from loguru import logger

import asyncio
import certifi
import ssl
import os


class CrawlerService:
    def __init__(self):
        self.vector_search_service = VectorSearchService()
        self.db = Database.get_instance()
        
        # Configure SSL context
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        
        # Configure browser settings
        self.browser_config = BrowserConfig(
            # chrome_path=os.getenv('CHROME_BIN', None),
            # chromedriver_path=os.getenv('CHROMEDRIVER_PATH', None),
            headless=True,
            verbose=True,
            user_agent_mode="random",  # Helps avoid blocking
            java_script_enabled=True   # For dynamic content
        )

    async def process_url(
        self,
        url: str,
        project_id: int,
        user_id: int,
        cache_mode: bool = True,
        verbose: bool = True
    ) -> bool:
        extractor = ExtractorFactory.get_extractor('website')
        crawler = None
        
        try:
            # Insert into DB
            file_id = self.db.insert_file(
                project_id=project_id,
                user_id=user_id,
                type='website',
                link=url,
                gcp_path=None,
                bucket=None
            )

            logger.debug(f"File ID: {file_id}")

            # Configure run settings
            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.ENABLED if cache_mode else CacheMode.DISABLED,
                markdown_generator=DefaultMarkdownGenerator(
                    options={"ignore_links": True}  # Simplified markdown output
                ),
                page_timeout=60000  # 60 seconds timeout
            )

            # Create crawler instance and crawl with retry logic
            async with AsyncWebCrawler(browser_config=self.browser_config) as crawler:
                max_retries = 3
                result = None
                
                for attempt in range(max_retries):
                    try:
                        result = await crawler.arun(
                            url=url,
                            config=run_config
                        )
                        
                        if result and result.success:
                            break
                        
                        logger.warning(f"Attempt {attempt + 1} failed for URL: {url}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                            
                    except Exception as e:
                        logger.error(f"Attempt {attempt + 1} error for URL {url}: {str(e)}")
                        if attempt == max_retries - 1:
                            raise

                # Verify crawl result
                if not result or not result.success:
                    raise Exception(f"Failed to crawl URL after {max_retries} attempts: {url}")

                if not result.markdown_v2 or not result.markdown_v2.raw_markdown:
                    raise Exception(f"No content extracted from URL: {url}")

                # Process the crawled content
                documents = extractor.extract_documents(
                    file_path=url,
                    project_id=project_id,
                    user_id=user_id,
                    file_id=file_id,
                    raw_markdown=result.markdown_v2.raw_markdown
                )
                
                self.vector_search_service.insert(
                    documents=documents
                )
                
                self.db.update_file_indexing_status(
                    file_id=file_id,
                    is_indexed=True,
                    completed_at=datetime.now(timezone.utc)
                )
                
                return True
        
        except Exception as e:
            error_msg = f"Error processing URL {url}: {str(e)}"
            logger.error(error_msg)
            self.db.update_file_indexing_status(
                file_id=file_id,
                is_indexed=False,
                completed_at=datetime.now(timezone.utc)
            )