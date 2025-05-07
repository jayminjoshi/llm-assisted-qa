from typing import Dict, Type
from .base_extractor import BaseExtractor
from .ppt_extractor import PPTExtractor
from .excel_extractor import ExcelExtractor
from .pdf_extractor import PDFExtractor
from .website_extractor import WebsiteExtractor

class ExtractorFactory:
    _extractors: Dict[str, Type[BaseExtractor]] = {
        'pptx': PPTExtractor,
        'ppt': PPTExtractor,
        'xlsx': ExcelExtractor,
        'xls': ExcelExtractor,
        'csv': ExcelExtractor,
        'pdf': PDFExtractor,
        'website': WebsiteExtractor,
        # Add more extractors here
        # 'docx': DocxExtractor,
    }

    @classmethod
    def get_extractor(cls, file_type: str) -> BaseExtractor:
        extractor_class = cls._extractors.get(file_type.lower())
        if not extractor_class:
            raise ValueError(f"No extractor found for file type: {file_type}")
        return extractor_class() 