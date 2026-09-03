#!/usr/bin/env python3
"""
Azure AI Content Understanding Cost Estimator and Explainer

This module provides cost estimation and analysis for Azure AI Content Understanding services.
It supports two estimation modes:

1. **Usage-based estimation** (Recommended): Use actual token counts from API responses
   for the most accurate cost calculations. Run test cases first to get the `usage` object.

2. **Schema-based estimation**: Estimate costs based on schema configuration when you
   haven't run test cases yet. This provides rough estimates but is less accurate than
   usage-based calculations.

IMPORTANT: For production cost planning, always validate estimates by running representative
test files through the actual Azure Content Understanding service and using the returned
usage data for calculations.
"""

import json
import argparse
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, asdict, field
from pathlib import Path
from enum import Enum


# Pricing Configuration - based on Azure Content Understanding pricing
# Reference: https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/pricing-explainer
PRICING_CONFIG = {
    "ce": {
        "doc_per_1000_pages": 5.0,
        "audio_per_minute": 0.006,
        "video_per_minute": 0.0167
    },
    "ctx": {
        "regular_per_mtok": 1.0,
        "mini_per_mtok": 1.0,
        "units": {
            "doc_page": 1000,
            "text_page": 1,
            "text_chars": 1,
            "image": 1000,
            "audio_minute": 1667,  # 100,000 tokens per hour = 1667 per minute
            "video_minute": 16667  # 1,000,000 tokens per hour = 16667 per minute
        }
    },
    "models": [
        {
            "name": "gpt-4o",
            "class": "regular",
            "tokens_per_unit": {
                "doc_page": {"in": 2600, "out": 90},
                "text_page": {"in": 2600, "out": 90},
                "image": {"in": 1043, "out": 170},
                "audio_minute": {"in": 604, "out": 19},
                "video_minute": {"in": 10695, "out": 3103}
            },
            "pricing": {
                "global_regional": {"input_per_mtok": 2.50, "output_per_mtok": 10.00},
                "data_zone": {"input_per_mtok": 2.75, "output_per_mtok": 11.00}
            }
        },
        {
            "name": "gpt-4o-mini",
            "class": "mini",
            "tokens_per_unit": {
                "doc_page": {"in": 2600, "out": 90},
                "text_page": {"in": 2600, "out": 90},
                "image": {"in": 3476, "out": 170},
                "audio_minute": {"in": 604, "out": 19},
                "video_minute": {"in": 175575, "out": 3103}
            },
            "pricing": {
                "global_regional": {"input_per_mtok": 0.15, "output_per_mtok": 0.60},
                "data_zone": {"input_per_mtok": 0.165, "output_per_mtok": 0.66}
            }
        },
        {
            "name": "gpt-4.1",
            "class": "regular",
            "tokens_per_unit": {
                "doc_page": {"in": 2600, "out": 90},
                "text_page": {"in": 2600, "out": 90},
                "image": {"in": 1043, "out": 170},
                "audio_minute": {"in": 604, "out": 19},
                "video_minute": {"in": 10695, "out": 3103}
            },
            "pricing": {
                "global_regional": {"input_per_mtok": 2.00, "output_per_mtok": 8.00},
                "data_zone": {"input_per_mtok": 2.20, "output_per_mtok": 8.80}
            }
        },
        {
            "name": "gpt-4.1-mini",
            "class": "mini",
            "tokens_per_unit": {
                "doc_page": {"in": 2600, "out": 90},
                "text_page": {"in": 2600, "out": 90},
                "image": {"in": 3476, "out": 170},
                "audio_minute": {"in": 604, "out": 19},
                "video_minute": {"in": 175575, "out": 3103}
            },
            "pricing": {
                "global_regional": {"input_per_mtok": 0.40, "output_per_mtok": 1.60},
                "data_zone": {"input_per_mtok": 0.44, "output_per_mtok": 1.76}
            }
        },
        {
            "name": "gpt-4.1-nano",
            "class": "mini",
            "tokens_per_unit": {
                "doc_page": {"in": 2600, "out": 90},
                "text_page": {"in": 2600, "out": 90},
                "image": {"in": 3476, "out": 170},
                "audio_minute": {"in": 604, "out": 19},
                "video_minute": {"in": 175575, "out": 3103}
            },
            "pricing": {
                "global_regional": {"input_per_mtok": 0.10, "output_per_mtok": 0.40},
                "data_zone": {"input_per_mtok": 0.11, "output_per_mtok": 0.44}
            }
        }
    ],
    "embeddings": {
        "text-embedding-3-small": {
            "tokens_per_call": 1500,
            "price_per_1k_tokens": 0.000022
        },
        "text-embedding-3-large": {
            "tokens_per_call": 1500,
            "price_per_1k_tokens": 0.000143
        },
        "text-embedding-ada-002 (Version 2)": {
            "tokens_per_call": 1500,
            "price_per_1k_tokens": 0.00011
        }
    },
    "page_from_chars": 3000,
    # Token multipliers for advanced features (from MS docs)
    "feature_multipliers": {
        "source_grounding_confidence": 2.0,  # ~2x token usage
        "extractive_mode": 1.5,               # ~1.5x token usage  
        "training_examples": 2.0,             # ~2x token usage
        "segmentation_categorization": 2.0    # ~2x token usage
    }
}


class EstimationMode(Enum):
    """Estimation mode - either from actual usage data or schema-based estimation"""
    USAGE_BASED = "usage_based"      # Recommended: Use actual token counts from API
    SCHEMA_BASED = "schema_based"    # Estimate from schema configuration


@dataclass
class UsageData:
    """
    Actual usage data from Azure Content Understanding API response.
    
    This is the RECOMMENDED way to estimate costs - by running test cases
    and using the actual usage object returned by the API.
    
    Example API response usage object:
    ```json
    "usage": {
        "documentPagesMinimal": 0,
        "documentPagesBasic": 0,
        "documentPagesStandard": 2,
        "contextualizationToken": 2000,
        "tokens": {
            "gpt-4.1-input": 10400,
            "gpt-4.1-output": 360
        }
    }
    ```
    """
    input_tokens: int
    output_tokens: int
    contextualization_tokens: int = 0
    document_pages_minimal: int = 0
    document_pages_basic: int = 0
    document_pages_standard: int = 0
    audio_minutes: float = 0.0
    video_minutes: float = 0.0
    embedding_tokens: int = 0
    
    @classmethod
    def from_api_response(cls, usage: Dict[str, Any]) -> 'UsageData':
        """
        Create UsageData from Azure Content Understanding API response.
        
        Args:
            usage: The 'usage' object from the API response
            
        Returns:
            UsageData instance populated from the response
        """
        tokens = usage.get("tokens", {})
        
        # Extract input/output tokens (may be prefixed with model name)
        input_tokens = 0
        output_tokens = 0
        for key, value in tokens.items():
            if "input" in key.lower():
                input_tokens += value
            elif "output" in key.lower():
                output_tokens += value
        
        return cls(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            contextualization_tokens=usage.get("contextualizationToken", 0),
            document_pages_minimal=usage.get("documentPagesMinimal", 0),
            document_pages_basic=usage.get("documentPagesBasic", 0),
            document_pages_standard=usage.get("documentPagesStandard", 0),
            audio_minutes=usage.get("audioMinutes", 0.0),
            video_minutes=usage.get("videoMinutes", 0.0),
            embedding_tokens=usage.get("embeddingTokens", 0)
        )


@dataclass 
class SchemaConfig:
    """
    Schema configuration for schema-based cost estimation.
    
    WARNING: Schema-based estimation provides ROUGH estimates only.
    For accurate cost calculations, run test cases through the actual
    Azure Content Understanding service and use the returned usage data.
    
    Attributes:
        num_fields: Number of fields in your extraction schema
        field_complexity: Average complexity of fields ('simple', 'moderate', 'complex')
        source_grounding_enabled: Whether source grounding is enabled
        confidence_scores_enabled: Whether confidence scores are enabled
        extractive_mode: Whether extractive mode is used
        training_examples_count: Number of training examples (0 if not using knowledge base)
        use_segmentation: Whether segmentation is used
        use_categorization: Whether categorization is used
        avg_field_value_length: Estimated average length of extracted field values (chars)
    """
    num_fields: int = 5
    field_complexity: str = "moderate"  # simple, moderate, complex
    source_grounding_enabled: bool = False
    confidence_scores_enabled: bool = False
    extractive_mode: bool = False
    training_examples_count: int = 0
    use_segmentation: bool = False
    use_categorization: bool = False
    avg_field_value_length: int = 50  # characters per field value
    
    def estimate_output_tokens_per_page(self) -> int:
        """
        Estimate output tokens per page based on schema configuration.
        
        This is a ROUGH estimate. Actual token usage varies significantly
        based on document content and structure.
        """
        # Base output tokens (rough estimate)
        complexity_multipliers = {
            "simple": 0.7,
            "moderate": 1.0,
            "complex": 1.5
        }
        multiplier = complexity_multipliers.get(self.field_complexity, 1.0)
        
        # Estimate ~4 tokens per character in field values
        # Plus overhead for JSON structure, field names, etc.
        tokens_per_field = (self.avg_field_value_length / 4) + 10  # ~10 tokens overhead per field
        base_output = int(self.num_fields * tokens_per_field * multiplier)
        
        # Apply feature multipliers
        if self.source_grounding_enabled or self.confidence_scores_enabled:
            base_output = int(base_output * 1.5)  # Grounding/confidence adds ~50% more output
        
        if self.extractive_mode:
            base_output = int(base_output * 1.3)  # Extractive mode adds source text
            
        return max(base_output, 30)  # Minimum reasonable output
    
    def get_token_multiplier(self) -> float:
        """Get combined token multiplier based on enabled features"""
        multiplier = 1.0
        
        if self.source_grounding_enabled and self.confidence_scores_enabled:
            multiplier *= 2.0
        elif self.source_grounding_enabled or self.confidence_scores_enabled:
            multiplier *= 1.5
            
        if self.extractive_mode:
            multiplier *= 1.5
            
        if self.training_examples_count > 0:
            multiplier *= 2.0
            
        if self.use_segmentation or self.use_categorization:
            multiplier *= 2.0
            
        return multiplier


@dataclass
class CostBreakdown:
    """Represents a detailed cost breakdown"""
    ce_cost: float  # Content Extraction
    fe_cost: float  # Field Extraction (LLM)
    ctx_cost: float  # Contextualization
    embeddings_cost: float  # Embeddings
    total_cost: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    units: float
    estimation_mode: str = "schema_based"  # or "usage_based"
    confidence_note: str = ""


@dataclass
class ProcessingRequest:
    """Represents a document processing request"""
    file_type: str  # document, text, image, audio, video
    quantity: float  # pages, characters, images, or minutes
    model_name: str = "gpt-4o"
    deployment_type: str = "global"  # global, regional, data_zone, ptu
    field_extraction_enabled: bool = True
    embeddings_enabled: bool = False
    embeddings_model: str = "text-embedding-3-small"
    # New fields for estimation mode
    usage_data: Optional[UsageData] = None  # For usage-based estimation
    schema_config: Optional[SchemaConfig] = None  # For schema-based estimation


class CostEstimator:
    """
    Main cost estimator class for Azure AI Content Understanding.
    
    Supports two estimation modes:
    
    1. **Usage-based** (Recommended): Provide actual token counts from API responses
       for accurate cost calculations. Get this data by running test cases first.
       
    2. **Schema-based**: Estimate costs from schema configuration. This is useful
       for initial planning but is less accurate than usage-based calculations.
    
    Example (usage-based - recommended):
        ```python
        # After running a test through the API, use the usage object:
        usage = UsageData(
            input_tokens=10400,
            output_tokens=360,
            contextualization_tokens=2000,
            document_pages_standard=2
        )
        request = ProcessingRequest(
            file_type="document",
            quantity=1000,  # Scale up from test results
            model_name="gpt-4.1",
            usage_data=usage
        )
        breakdown = estimator.estimate_from_usage(request, scale_factor=500)  # 2 pages -> 1000
        ```
    
    Example (schema-based - rough estimate):
        ```python
        schema = SchemaConfig(
            num_fields=10,
            field_complexity="moderate",
            source_grounding_enabled=True
        )
        request = ProcessingRequest(
            file_type="document",
            quantity=1000,
            model_name="gpt-4o-mini",
            schema_config=schema
        )
        breakdown = estimator.estimate_from_schema(request)
        ```
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or PRICING_CONFIG
    
    def get_model_config(self, model_name: str) -> Optional[Dict]:
        """Get model configuration by name"""
        for model in self.config["models"]:
            if model["name"] == model_name:
                return model
        return None
    
    def get_unit_key(self, file_type: str) -> str:
        """Convert file type to unit key"""
        mapping = {
            "document": "doc_page",
            "text": "text_page",
            "image": "image",
            "audio": "audio_minute",
            "video": "video_minute"
        }
        return mapping.get(file_type, "doc_page")
    
    def convert_text_to_pages(self, characters: float) -> float:
        """Convert text characters to pages"""
        return characters / self.config["page_from_chars"]
    
    def get_units_for_calculation(self, file_type: str, quantity: float) -> float:
        """Get units for calculation (convert text chars to pages if needed)"""
        if file_type == "text":
            return self.convert_text_to_pages(quantity)
        return quantity
    
    def calculate_content_extraction(self, file_type: str, units: float) -> float:
        """Calculate content extraction cost"""
        if file_type == "document":
            return (units / 1000) * self.config["ce"]["doc_per_1000_pages"]
        elif file_type == "audio":
            return units * self.config["ce"]["audio_per_minute"]
        elif file_type == "video":
            return units * self.config["ce"]["video_per_minute"]
        # text is free, image doesn't have CE
        return 0.0
    
    def calculate_field_extraction(
        self, 
        file_type: str, 
        units: float, 
        model: Dict,
        deployment_type: str
    ) -> Tuple[int, int, float]:
        """Calculate field extraction tokens and cost
        
        Returns: (input_tokens, output_tokens, cost)
        """
        unit_key = self.get_unit_key(file_type)
        tokens_per_unit = model["tokens_per_unit"].get(unit_key)
        
        if not tokens_per_unit:
            return 0, 0, 0.0
        
        input_tokens = int(units * tokens_per_unit["in"])
        output_tokens = int(units * tokens_per_unit["out"])
        
        # Calculate cost based on deployment type (PTU deployments don't have per-token costs)
        cost = 0.0
        if deployment_type != "ptu":
            pricing_tier = self.get_pricing_tier(deployment_type)
            input_cost = (input_tokens / 1_000_000) * model["pricing"][pricing_tier]["input_per_mtok"]
            output_cost = (output_tokens / 1_000_000) * model["pricing"][pricing_tier]["output_per_mtok"]
            cost = input_cost + output_cost
        
        return input_tokens, output_tokens, cost
    
    def calculate_field_extraction_from_usage(
        self,
        usage: UsageData,
        scale_factor: float,
        model: Dict,
        deployment_type: str
    ) -> Tuple[int, int, float]:
        """Calculate field extraction cost from actual usage data
        
        Args:
            usage: Actual usage data from API
            scale_factor: Multiplier to scale from test to production volume
            model: Model configuration
            deployment_type: Deployment type
            
        Returns: (input_tokens, output_tokens, cost)
        """
        input_tokens = int(usage.input_tokens * scale_factor)
        output_tokens = int(usage.output_tokens * scale_factor)
        
        cost = 0.0
        if deployment_type != "ptu":
            pricing_tier = self.get_pricing_tier(deployment_type)
            input_cost = (input_tokens / 1_000_000) * model["pricing"][pricing_tier]["input_per_mtok"]
            output_cost = (output_tokens / 1_000_000) * model["pricing"][pricing_tier]["output_per_mtok"]
            cost = input_cost + output_cost
        
        return input_tokens, output_tokens, cost
    
    def calculate_embeddings(
        self,
        units: float,
        model: Dict,
        file_type: str,
        embeddings_model: str,
        deployment_type: str
    ) -> Tuple[int, float]:
        """Calculate embeddings tokens and cost
        
        Returns: (total_tokens, cost)
        """
        embedding_config = self.config["embeddings"].get(embeddings_model)
        if not embedding_config:
            return 0, 0.0
        
        unit_key = self.get_unit_key(file_type)
        tokens_per_unit = model["tokens_per_unit"].get(unit_key)
        
        if not tokens_per_unit:
            return 0, 0.0
        
        total_tokens = int(units * tokens_per_unit["in"])
        
        cost = 0.0
        if deployment_type != "ptu":
            cost = (total_tokens / 1000) * embedding_config["price_per_1k_tokens"]
        
        return total_tokens, cost
    
    def calculate_contextualization(self, file_type: str, units: float, model: Dict, original_quantity: float = None) -> Tuple[int, float]:
        """Calculate contextualization tokens and cost
        
        Args:
            file_type: Type of file being processed
            units: Effective units (pages for most types)
            model: Model configuration dictionary
            original_quantity: Original quantity before conversion (for text type)
        
        Returns: (tokens, cost)
        """
        # For text type, use original character count for CTX calculation
        if file_type == "text" and original_quantity is not None:
            tokens_per_unit = self.config["ctx"]["units"]["text_chars"]
            tokens = int(original_quantity * tokens_per_unit)
        else:
            # Get CTX tokens per unit
            unit_key_mapping = {
                "document": "doc_page",
                "image": "image",
                "audio": "audio_minute",
                "video": "video_minute"
            }
            
            unit_key = unit_key_mapping.get(file_type, "doc_page")
            tokens_per_unit = self.config["ctx"]["units"][unit_key]
            tokens = int(units * tokens_per_unit)
        
        # Use model class to determine rate
        rate_per_mtok = (
            self.config["ctx"]["mini_per_mtok"] 
            if model["class"] == "mini" 
            else self.config["ctx"]["regular_per_mtok"]
        )
        
        cost = (tokens / 1_000_000) * rate_per_mtok
        
        return tokens, cost
    
    def calculate_contextualization_from_usage(
        self,
        usage: UsageData,
        scale_factor: float,
        model: Dict
    ) -> Tuple[int, float]:
        """Calculate contextualization from actual usage data
        
        Args:
            usage: Actual usage data
            scale_factor: Multiplier to scale from test to production
            model: Model configuration
            
        Returns: (tokens, cost)
        """
        tokens = int(usage.contextualization_tokens * scale_factor)
        
        rate_per_mtok = (
            self.config["ctx"]["mini_per_mtok"]
            if model["class"] == "mini"
            else self.config["ctx"]["regular_per_mtok"]
        )
        
        cost = (tokens / 1_000_000) * rate_per_mtok
        
        return tokens, cost
    
    def get_pricing_tier(self, deployment_type: str) -> str:
        """Get pricing tier from deployment type
        
        Args:
            deployment_type: Deployment type (global, regional, data_zone, ptu)
            
        Returns:
            Pricing tier string for config lookup
        """
        return "data_zone" if deployment_type == "data_zone" else "global_regional"
    
    def estimate_from_usage(
        self,
        request: ProcessingRequest,
        scale_factor: float = 1.0,
        test_pages: Optional[int] = None
    ) -> CostBreakdown:
        """
        Estimate cost using actual usage data from API response.
        
        This is the RECOMMENDED method for accurate cost estimation.
        Run test cases through the Azure Content Understanding API first,
        then use the returned usage object to calculate scaled costs.
        
        Args:
            request: Processing request with usage_data populated
            scale_factor: Multiplier to scale from test volume to production
                         (e.g., if you tested 10 pages and want estimate for 1000,
                         use scale_factor=100)
            test_pages: Number of pages in your test (alternative to scale_factor)
            
        Returns:
            CostBreakdown with accurate cost information
        """
        if not request.usage_data:
            raise ValueError("usage_data is required for usage-based estimation")
        
        usage = request.usage_data
        model = self.get_model_config(request.model_name)
        if not model:
            raise ValueError(f"Model {request.model_name} not found")
        
        # Calculate scale factor if test_pages provided
        if test_pages and test_pages > 0:
            scale_factor = request.quantity / test_pages
        
        # Content Extraction - from usage data
        total_pages = (
            usage.document_pages_minimal +
            usage.document_pages_basic + 
            usage.document_pages_standard
        )
        if total_pages > 0:
            ce_cost = (total_pages * scale_factor / 1000) * self.config["ce"]["doc_per_1000_pages"]
        elif usage.audio_minutes > 0:
            ce_cost = usage.audio_minutes * scale_factor * self.config["ce"]["audio_per_minute"]
        elif usage.video_minutes > 0:
            ce_cost = usage.video_minutes * scale_factor * self.config["ce"]["video_per_minute"]
        else:
            ce_cost = self.calculate_content_extraction(request.file_type, request.quantity)
        
        # Field Extraction (LLM tokens)
        input_tokens, output_tokens, fe_cost = self.calculate_field_extraction_from_usage(
            usage, scale_factor, model, request.deployment_type
        )
        
        # Contextualization
        ctx_tokens, ctx_cost = self.calculate_contextualization_from_usage(
            usage, scale_factor, model
        )
        
        # Embeddings
        embeddings_cost = 0.0
        if usage.embedding_tokens > 0:
            embedding_config = self.config["embeddings"].get(request.embeddings_model)
            if embedding_config:
                scaled_embedding_tokens = usage.embedding_tokens * scale_factor
                embeddings_cost = (scaled_embedding_tokens / 1000) * embedding_config["price_per_1k_tokens"]
        
        total_cost = ce_cost + fe_cost + ctx_cost + embeddings_cost
        total_tokens = input_tokens + output_tokens + ctx_tokens
        
        return CostBreakdown(
            ce_cost=ce_cost,
            fe_cost=fe_cost,
            ctx_cost=ctx_cost,
            embeddings_cost=embeddings_cost,
            total_cost=total_cost,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            units=request.quantity,
            estimation_mode="usage_based",
            confidence_note="High confidence - based on actual API usage data"
        )
    
    def estimate_from_schema(self, request: ProcessingRequest) -> CostBreakdown:
        """
        Estimate cost based on schema configuration.
        
        WARNING: This provides ROUGH estimates only. Token usage varies significantly
        based on actual document content, structure, and complexity.
        
        For accurate cost planning, always validate by running representative test
        files through the Azure Content Understanding service and using the returned
        usage data with estimate_from_usage().
        
        Args:
            request: Processing request with schema_config populated
            
        Returns:
            CostBreakdown with estimated costs (includes confidence warning)
        """
        schema = request.schema_config or SchemaConfig()
        model = self.get_model_config(request.model_name)
        if not model:
            raise ValueError(f"Model {request.model_name} not found")
        
        units = self.get_units_for_calculation(request.file_type, request.quantity)
        
        # Content Extraction
        ce_cost = self.calculate_content_extraction(request.file_type, units)
        
        # Field Extraction with schema-based estimation
        unit_key = self.get_unit_key(request.file_type)
        tokens_per_unit = model["tokens_per_unit"].get(unit_key)
        
        if tokens_per_unit and request.field_extraction_enabled:
            # Base input tokens from model config
            base_input = tokens_per_unit["in"]
            # Estimate output tokens from schema
            estimated_output = schema.estimate_output_tokens_per_page()
            
            # Apply feature multipliers
            multiplier = schema.get_token_multiplier()
            
            input_tokens = int(units * base_input * multiplier)
            output_tokens = int(units * estimated_output * multiplier)
            
            pricing_tier = self.get_pricing_tier(request.deployment_type)
            if request.deployment_type != "ptu":
                input_cost = (input_tokens / 1_000_000) * model["pricing"][pricing_tier]["input_per_mtok"]
                output_cost = (output_tokens / 1_000_000) * model["pricing"][pricing_tier]["output_per_mtok"]
                fe_cost = input_cost + output_cost
            else:
                fe_cost = 0.0
        else:
            input_tokens, output_tokens, fe_cost = 0, 0, 0.0
        
        # Contextualization
        ctx_tokens, ctx_cost = self.calculate_contextualization(
            request.file_type, units, model,
            original_quantity=request.quantity if request.file_type == "text" else None
        )
        
        # Embeddings
        embeddings_cost = 0.0
        if request.embeddings_enabled or schema.training_examples_count > 0:
            _, embeddings_cost = self.calculate_embeddings(
                units, model, request.file_type, request.embeddings_model, request.deployment_type
            )
        
        total_cost = ce_cost + fe_cost + ctx_cost + embeddings_cost
        total_tokens = input_tokens + output_tokens + ctx_tokens
        
        return CostBreakdown(
            ce_cost=ce_cost,
            fe_cost=fe_cost,
            ctx_cost=ctx_cost,
            embeddings_cost=embeddings_cost,
            total_cost=total_cost,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            units=units,
            estimation_mode="schema_based",
            confidence_note=(
                "LOW confidence - schema-based estimate. Actual costs may vary significantly. "
                "For accurate estimates, run test cases through Azure Content Understanding "
                "and use the returned usage data."
            )
        )
    
    def estimate_cost(self, request: ProcessingRequest) -> CostBreakdown:
        """
        Estimate cost for a processing request.
        
        Automatically chooses the best estimation method based on available data:
        - If usage_data is provided: Uses accurate usage-based estimation
        - If schema_config is provided: Uses schema-based estimation (less accurate)
        - Otherwise: Uses default token estimates (least accurate)
        
        Args:
            request: Processing request with all parameters
            
        Returns:
            CostBreakdown with detailed cost information
        """
        # Prefer usage-based if available
        if request.usage_data:
            return self.estimate_from_usage(request)
        
        # Fall back to schema-based if schema provided
        if request.schema_config:
            return self.estimate_from_schema(request)
        
        # Default: use original estimation method
        model = self.get_model_config(request.model_name)
        if not model:
            raise ValueError(f"Model {request.model_name} not found")
        
        # Calculate units
        units = self.get_units_for_calculation(request.file_type, request.quantity)
        
        # Content Extraction
        ce_cost = self.calculate_content_extraction(request.file_type, units)
        
        # Field Extraction
        fe_input_tokens, fe_output_tokens, fe_cost = 0, 0, 0.0
        if request.field_extraction_enabled:
            fe_input_tokens, fe_output_tokens, fe_cost = self.calculate_field_extraction(
                request.file_type, units, model, request.deployment_type
            )
        
        # Embeddings
        embeddings_tokens, embeddings_cost = 0, 0.0
        if request.embeddings_enabled:
            embeddings_tokens, embeddings_cost = self.calculate_embeddings(
                units, model, request.file_type, request.embeddings_model, request.deployment_type
            )
        
        # Contextualization - pass original quantity for text type
        ctx_tokens, ctx_cost = self.calculate_contextualization(
            request.file_type, units, model, 
            original_quantity=request.quantity if request.file_type == "text" else None
        )
        
        # Total
        total_cost = ce_cost + fe_cost + embeddings_cost + ctx_cost
        total_tokens = fe_input_tokens + fe_output_tokens + embeddings_tokens + ctx_tokens
        
        return CostBreakdown(
            ce_cost=ce_cost,
            fe_cost=fe_cost,
            ctx_cost=ctx_cost,
            embeddings_cost=embeddings_cost,
            total_cost=total_cost,
            input_tokens=fe_input_tokens,
            output_tokens=fe_output_tokens,
            total_tokens=total_tokens,
            units=units,
            estimation_mode="default",
            confidence_note=(
                "MODERATE confidence - using default token estimates. "
                "For more accurate estimates, provide schema_config or "
                "usage_data from actual API calls."
            )
        )
    
    def explain_cost_drivers(self, request: ProcessingRequest, breakdown: CostBreakdown) -> str:
        """Generate natural language explanation of cost drivers
        
        Args:
            request: The processing request parameters
            breakdown: The cost breakdown results
            
        Returns:
            Natural language explanation string
        """
        model = self.get_model_config(request.model_name)
        unit_type = {
            "document": "pages",
            "text": "characters (converted to pages)",
            "image": "images",
            "audio": "minutes",
            "video": "minutes"
        }.get(request.file_type, "units")
        
        explanation = []
        explanation.append(f"Cost Analysis for {request.quantity:,.0f} {unit_type} using {request.model_name}")
        explanation.append("=" * 70)
        explanation.append("")
        
        # Estimation mode warning
        if breakdown.estimation_mode == "schema_based":
            explanation.append("⚠️  ESTIMATION MODE: Schema-based (rough estimate)")
            explanation.append("    " + breakdown.confidence_note)
            explanation.append("")
        elif breakdown.estimation_mode == "usage_based":
            explanation.append("✅ ESTIMATION MODE: Usage-based (high accuracy)")
            explanation.append("    Based on actual API usage data from test runs")
            explanation.append("")
        else:
            explanation.append("ℹ️  ESTIMATION MODE: Default estimates")
            explanation.append("    " + breakdown.confidence_note)
            explanation.append("")
        
        # Overall summary
        explanation.append(f"Total Estimated Cost: ${breakdown.total_cost:.4f}")
        explanation.append(f"Effective Units: {breakdown.units:.2f}")
        explanation.append(f"Total Tokens: {breakdown.total_tokens:,}")
        explanation.append("")
        
        # Component breakdown
        explanation.append("Cost Breakdown by Component:")
        explanation.append("-" * 70)
        
        # Content Extraction
        if breakdown.ce_cost > 0:
            percentage = (breakdown.ce_cost / breakdown.total_cost) * 100 if breakdown.total_cost > 0 else 0
            explanation.append(f"1. Content Extraction: ${breakdown.ce_cost:.4f} ({percentage:.1f}%)")
            explanation.append(f"   - Extracts raw content from {request.file_type} files")
            if request.file_type == "document":
                explanation.append(f"   - Charged at ${self.config['ce']['doc_per_1000_pages']:.2f} per 1,000 pages")
            elif request.file_type == "audio":
                explanation.append(f"   - Charged at ${self.config['ce']['audio_per_minute']:.4f} per minute")
            elif request.file_type == "video":
                explanation.append(f"   - Charged at ${self.config['ce']['video_per_minute']:.4f} per minute")
            explanation.append("")
        
        # Field Extraction
        if breakdown.fe_cost > 0:
            percentage = (breakdown.fe_cost / breakdown.total_cost) * 100 if breakdown.total_cost > 0 else 0
            explanation.append(f"2. Field Extraction (AI Processing): ${breakdown.fe_cost:.4f} ({percentage:.1f}%)")
            explanation.append(f"   - Uses {request.model_name} ({model['class']} model)")
            explanation.append(f"   - Input tokens: {breakdown.input_tokens:,}")
            explanation.append(f"   - Output tokens: {breakdown.output_tokens:,}")
            
            pricing_tier = self.get_pricing_tier(request.deployment_type)
            input_rate = model["pricing"][pricing_tier]["input_per_mtok"]
            output_rate = model["pricing"][pricing_tier]["output_per_mtok"]
            explanation.append(f"   - Rates: ${input_rate:.2f}/M input, ${output_rate:.2f}/M output tokens")
            explanation.append(f"   - Deployment: {request.deployment_type}")
            explanation.append("")
        
        # Embeddings
        if breakdown.embeddings_cost > 0:
            percentage = (breakdown.embeddings_cost / breakdown.total_cost) * 100 if breakdown.total_cost > 0 else 0
            explanation.append(f"3. Embeddings: ${breakdown.embeddings_cost:.4f} ({percentage:.1f}%)")
            explanation.append(f"   - Model: {request.embeddings_model}")
            embedding_config = self.config["embeddings"][request.embeddings_model]
            explanation.append(f"   - Rate: ${embedding_config['price_per_1k_tokens']:.6f} per 1K tokens")
            explanation.append("")
        
        # Contextualization
        if breakdown.ctx_cost > 0:
            percentage = (breakdown.ctx_cost / breakdown.total_cost) * 100 if breakdown.total_cost > 0 else 0
            rate = self.config["ctx"]["mini_per_mtok"] if model["class"] == "mini" else self.config["ctx"]["regular_per_mtok"]
            ctx_tokens = int((breakdown.ctx_cost / rate) * 1_000_000)
            explanation.append(f"4. Contextualization: ${breakdown.ctx_cost:.4f} ({percentage:.1f}%)")
            explanation.append(f"   - Maintains document context and relationships")
            explanation.append(f"   - Tokens: {ctx_tokens:,}")
            explanation.append(f"   - Rate: ${rate:.2f} per million tokens")
            explanation.append("")
        
        # Recommendations for better estimates
        if breakdown.estimation_mode != "usage_based":
            explanation.append("Recommendations for Better Estimates:")
            explanation.append("-" * 70)
            explanation.append("To get more accurate cost estimates:")
            explanation.append("1. Run a small test batch (5-10 documents) through the API")
            explanation.append("2. Check the 'usage' object in the API response")
            explanation.append("3. Use the usage data with estimate_from_usage() method")
            explanation.append("")
            explanation.append("Example usage object from API:")
            explanation.append('  "usage": {')
            explanation.append('    "contextualizationToken": 2000,')
            explanation.append('    "tokens": {')
            explanation.append('      "gpt-4.1-input": 10400,')
            explanation.append('      "gpt-4.1-output": 360')
            explanation.append('    }')
            explanation.append('  }')
            explanation.append("")
        
        # Key cost drivers
        explanation.append("Key Cost Drivers:")
        explanation.append("-" * 70)
        
        drivers = []
        if breakdown.fe_cost > breakdown.total_cost * 0.3:
            drivers.append(f"• AI Model Selection: {request.model_name} is a {model['class']} model")
            drivers.append(f"  Consider using a 'mini' model for lower costs if appropriate")
        
        if request.deployment_type == "data_zone":
            drivers.append(f"• Deployment Type: Data Zone pricing is ~10% higher than Global/Regional")
        
        if request.embeddings_enabled:
            drivers.append(f"• Embeddings: Adding vector embeddings increases cost")
        
        drivers.append(f"• Volume: Processing {breakdown.units:.0f} effective units")
        
        if request.file_type == "video":
            drivers.append(f"• File Type: Video files have high token consumption")
        
        explanation.extend(drivers)
        explanation.append("")
        
        # Optimization tips
        explanation.append("Cost Optimization Tips:")
        explanation.append("-" * 70)
        if model["class"] == "regular":
            explanation.append("• Consider using a 'mini' model (e.g., gpt-4o-mini) for 85-95% cost savings")
        if request.deployment_type == "data_zone":
            explanation.append("• Use Global or Regional deployment if data residency is not required")
        if request.embeddings_enabled:
            explanation.append("• Disable embeddings if vector search is not needed")
        explanation.append("• Process documents in batches to amortize fixed costs")
        explanation.append("• Use text file type when possible (free content extraction)")
        explanation.append("• Disable source grounding and confidence scores if not needed (~2x savings)")
        
        return "\n".join(explanation)
    
    def analyze_batch_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze a batch of processing results to calculate average costs per page
        
        Args:
            results: List of processing results, each containing:
                - file_name: str
                - file_type: str
                - pages: int (number of pages processed)
                - actual_input_tokens: int
                - actual_output_tokens: int
                - model_name: str
                - deployment_type: str
        
        Returns:
            Dictionary with analysis results
        """
        if not results:
            return {"error": "No results provided"}
        
        total_pages = sum(r.get("pages", 0) for r in results)
        total_input_tokens = sum(r.get("actual_input_tokens", 0) for r in results)
        total_output_tokens = sum(r.get("actual_output_tokens", 0) for r in results)
        total_docs = len(results)
        
        # Calculate actual costs based on the model and tokens used
        total_cost = 0.0
        for result in results:
            model = self.get_model_config(result.get("model_name", "gpt-4o"))
            if not model:
                continue
            
            deployment_type = result.get("deployment_type", "global")
            pricing_tier = self.get_pricing_tier(deployment_type)
            
            input_cost = (result.get("actual_input_tokens", 0) / 1_000_000) * model["pricing"][pricing_tier]["input_per_mtok"]
            output_cost = (result.get("actual_output_tokens", 0) / 1_000_000) * model["pricing"][pricing_tier]["output_per_mtok"]
            total_cost += input_cost + output_cost
            
            # Add CE cost
            file_type = result.get("file_type", "document")
            pages = result.get("pages", 0)
            if file_type == "document":
                total_cost += (pages / 1000) * self.config["ce"]["doc_per_1000_pages"]
        
        # Calculate averages
        avg_cost_per_page = total_cost / total_pages if total_pages > 0 else 0
        avg_input_tokens_per_page = total_input_tokens / total_pages if total_pages > 0 else 0
        avg_output_tokens_per_page = total_output_tokens / total_pages if total_pages > 0 else 0
        avg_total_tokens_per_page = (total_input_tokens + total_output_tokens) / total_pages if total_pages > 0 else 0
        
        analysis = {
            "summary": {
                "total_documents": total_docs,
                "total_pages": total_pages,
                "total_cost": total_cost,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_tokens": total_input_tokens + total_output_tokens
            },
            "averages": {
                "cost_per_page": avg_cost_per_page,
                "cost_per_document": total_cost / total_docs if total_docs > 0 else 0,
                "input_tokens_per_page": avg_input_tokens_per_page,
                "output_tokens_per_page": avg_output_tokens_per_page,
                "total_tokens_per_page": avg_total_tokens_per_page,
                "pages_per_document": total_pages / total_docs if total_docs > 0 else 0
            },
            "per_document_breakdown": []
        }
        
        # Add per-document details
        for result in results:
            pages = result.get("pages", 0)
            input_tokens = result.get("actual_input_tokens", 0)
            output_tokens = result.get("actual_output_tokens", 0)
            
            model = self.get_model_config(result.get("model_name", "gpt-4o"))
            deployment_type = result.get("deployment_type", "global")
            
            doc_cost = 0.0
            if model:
                pricing_tier = self.get_pricing_tier(deployment_type)
                doc_cost = (input_tokens / 1_000_000) * model["pricing"][pricing_tier]["input_per_mtok"]
                doc_cost += (output_tokens / 1_000_000) * model["pricing"][pricing_tier]["output_per_mtok"]
                
                # Add CE cost
                file_type = result.get("file_type", "document")
                if file_type == "document":
                    doc_cost += (pages / 1000) * self.config["ce"]["doc_per_1000_pages"]
            
            analysis["per_document_breakdown"].append({
                "file_name": result.get("file_name", "unknown"),
                "pages": pages,
                "cost": doc_cost,
                "cost_per_page": doc_cost / pages if pages > 0 else 0,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "tokens_per_page": (input_tokens + output_tokens) / pages if pages > 0 else 0
            })
        
        return analysis
    
    def explain_batch_analysis(self, analysis: Dict[str, Any]) -> str:
        """Generate natural language explanation of batch analysis results
        
        Args:
            analysis: Dictionary containing batch analysis results
            
        Returns:
            Natural language explanation string
        """
        if "error" in analysis:
            return f"Error: {analysis['error']}"
        
        summary = analysis["summary"]
        averages = analysis["averages"]
        
        explanation = []
        explanation.append("Batch Processing Analysis")
        explanation.append("=" * 70)
        explanation.append("")
        
        # Summary
        explanation.append("Overall Summary:")
        explanation.append(f"  • Processed {summary['total_documents']} documents")
        explanation.append(f"  • Total pages: {summary['total_pages']:,}")
        explanation.append(f"  • Total cost: ${summary['total_cost']:.2f}")
        explanation.append(f"  • Total tokens: {summary['total_tokens']:,}")
        explanation.append("")
        
        # Averages
        explanation.append("Average Costs:")
        explanation.append(f"  • Cost per page: ${averages['cost_per_page']:.4f}")
        explanation.append(f"  • Cost per document: ${averages['cost_per_document']:.2f}")
        explanation.append(f"  • Pages per document: {averages['pages_per_document']:.1f}")
        explanation.append("")
        
        explanation.append("Average Token Usage:")
        explanation.append(f"  • Input tokens per page: {averages['input_tokens_per_page']:.0f}")
        explanation.append(f"  • Output tokens per page: {averages['output_tokens_per_page']:.0f}")
        explanation.append(f"  • Total tokens per page: {averages['total_tokens_per_page']:.0f}")
        explanation.append("")
        
        # Cost drivers analysis
        explanation.append("Cost Driver Analysis:")
        explanation.append("-" * 70)
        
        # Find most/least expensive documents
        if analysis["per_document_breakdown"]:
            breakdown = analysis["per_document_breakdown"]
            most_expensive = max(breakdown, key=lambda x: x["cost_per_page"])
            least_expensive = min(breakdown, key=lambda x: x["cost_per_page"])
            
            explanation.append(f"Most expensive per page: {most_expensive['file_name']}")
            explanation.append(f"  • ${most_expensive['cost_per_page']:.4f}/page")
            explanation.append(f"  • {most_expensive['tokens_per_page']:.0f} tokens/page")
            explanation.append("")
            
            explanation.append(f"Least expensive per page: {least_expensive['file_name']}")
            explanation.append(f"  • ${least_expensive['cost_per_page']:.4f}/page")
            explanation.append(f"  • {least_expensive['tokens_per_page']:.0f} tokens/page")
            explanation.append("")
            
            # Variance analysis
            cost_variance = max(d["cost_per_page"] for d in breakdown) - min(d["cost_per_page"] for d in breakdown)
            explanation.append(f"Cost variance: ${cost_variance:.4f} per page")
            explanation.append("This variance is typically driven by:")
            explanation.append("  • Document complexity (tables, images, formatting)")
            explanation.append("  • Content density (text vs whitespace)")
            explanation.append("  • Schema complexity (number of fields extracted)")
            explanation.append("")
        
        # Projections
        explanation.append("Cost Projections:")
        explanation.append("-" * 70)
        for scale in [1000, 10000, 100000, 1000000]:
            projected_cost = averages['cost_per_page'] * scale
            explanation.append(f"  • {scale:,} pages: ${projected_cost:,.2f}")
        
        return "\n".join(explanation)


def extract_usage_from_cu_output(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Extract usage data from Azure Content Understanding analyzer output JSON.
    
    Supports the standard CU analyzer output format:
    {
      "usage": {
        "documentPagesStandard": <pages>,
        "contextualizationTokens": <tokens>,
        "tokens": {
          "<model>-input": <count>,
          "<model>-output": <count>,
          ...
        }
      },
      ...
    }
    
    Args:
        filepath: Path to CU analyzer output JSON file
        
    Returns:
        Dict with extracted usage data compatible with CostEstimator, or None if not found
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
        ValueError: If usage object is malformed
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract usage object
    if 'usage' not in data:
        raise ValueError(f"No 'usage' object found in {filepath}. Invalid CU analyzer output format.")
    
    usage = data['usage']
    
    # Validate required fields
    if 'tokens' not in usage or not isinstance(usage['tokens'], dict):
        raise ValueError(f"Usage object missing 'tokens' dict in {filepath}")
    
    # Extract model tokens
    tokens_dict = usage['tokens']
    
    # Find input/output tokens (handle various naming conventions)
    input_tokens = 0
    output_tokens = 0
    
    for key, value in tokens_dict.items():
        if isinstance(value, int):
            # Single token count (flat format) - shouldn't happen but handle it
            continue
        # Multi-token format (nested) - shouldn't happen based on observed data
        
    # Try to find input and output tokens with model names
    for model_key in tokens_dict:
        if 'input' in model_key.lower():
            input_tokens += tokens_dict[model_key]
        elif 'output' in model_key.lower():
            output_tokens += tokens_dict[model_key]
        # Other token types (embeddings, etc.) are handled separately if needed
    
    # If we couldn't find explicit input/output keys, assume the tokens are for the main model
    if input_tokens == 0 and output_tokens == 0:
        # Count all tokens except known embeddings
        for model_key, value in tokens_dict.items():
            if 'embedding' not in model_key.lower():
                # Assume first token is input, others are output (shouldn't happen with standard format)
                if input_tokens == 0:
                    input_tokens = value
                else:
                    output_tokens = value
    
    context_tokens = usage.get('contextualizationTokens', 0)
    pages = usage.get('documentPagesStandard', 0)
    
    return {
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'contextualization_tokens': context_tokens,
        'document_pages': pages,
        'source_file': filepath
    }


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="Azure AI Content Understanding Cost Estimator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Estimate cost for 1000 document pages (default estimation)
  python -m tools.cost_estimator estimate --file-type document --quantity 1000 --model gpt-4o
  
  # Estimate with schema configuration (rough estimate)
  python -m tools.cost_estimator estimate --file-type document --quantity 1000 \\
      --model gpt-4o-mini --schema-fields 10 --schema-complexity moderate
  
  # Estimate from actual usage data (most accurate)
  python -m tools.cost_estimator estimate-usage --input-tokens 1100000 --output-tokens 60000 \\
      --ctx-tokens 1000000 --pages 1000 --model gpt-4o-mini
  
  # Analyze batch processing results
  python -m tools.cost_estimator analyze --results-file batch_results.json
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Estimate command
    estimate_parser = subparsers.add_parser("estimate", help="Estimate cost before processing")
    estimate_parser.add_argument("--file-type", required=True, 
                                choices=["document", "text", "image", "audio", "video"],
                                help="Type of file to process")
    estimate_parser.add_argument("--quantity", type=float, required=True,
                                help="Quantity (pages, characters, images, or minutes)")
    estimate_parser.add_argument("--model", default="gpt-4o",
                                help="Model name (default: gpt-4o)")
    estimate_parser.add_argument("--deployment", default="global",
                                choices=["global", "regional", "data_zone", "ptu"],
                                help="Deployment type (default: global)")
    estimate_parser.add_argument("--no-field-extraction", action="store_true",
                                help="Disable field extraction")
    estimate_parser.add_argument("--embeddings", action="store_true",
                                help="Enable embeddings")
    estimate_parser.add_argument("--embeddings-model", default="text-embedding-3-small",
                                help="Embeddings model (default: text-embedding-3-small)")
    # Schema-based estimation options
    estimate_parser.add_argument("--schema-fields", type=int, default=0,
                                help="Number of fields in schema (enables schema-based estimation)")
    estimate_parser.add_argument("--schema-complexity", default="moderate",
                                choices=["simple", "moderate", "complex"],
                                help="Schema complexity level")
    estimate_parser.add_argument("--source-grounding", action="store_true",
                                help="Enable source grounding")
    estimate_parser.add_argument("--confidence-scores", action="store_true",
                                help="Enable confidence scores")
    estimate_parser.add_argument("--json", action="store_true",
                                help="Output as JSON")
    
    # Estimate from usage command (recommended)
    usage_parser = subparsers.add_parser("estimate-usage", 
                                          help="Estimate from actual API usage data (recommended)")
    usage_parser_source = usage_parser.add_mutually_exclusive_group(required=True)
    usage_parser_source.add_argument("--cu-output", type=str,
                                    help="Path to CU analyzer output JSON file (automatically extracts usage)")
    usage_parser_source.add_argument("--input-tokens", type=int,
                                    help="Input tokens from API usage")
    usage_parser.add_argument("--output-tokens", type=int,
                             help="Output tokens from API usage (required if --input-tokens used)")
    usage_parser.add_argument("--ctx-tokens", type=int, default=0,
                             help="Contextualization tokens from API usage")
    usage_parser.add_argument("--pages", type=int, default=0,
                             help="Number of document pages")
    usage_parser.add_argument("--model", default="gpt-4o",
                             help="Model name (default: gpt-4o)")
    usage_parser.add_argument("--deployment", default="global",
                             choices=["global", "regional", "data_zone", "ptu"],
                             help="Deployment type (default: global)")
    usage_parser.add_argument("--scale-to", type=int, default=0,
                             help="Scale estimate to this many pages (0 = use provided pages)")
    usage_parser.add_argument("--json", action="store_true",
                             help="Output as JSON")
    
    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze batch processing results")
    analyze_parser.add_argument("--results-file", required=True,
                               help="JSON file with batch processing results")
    analyze_parser.add_argument("--json", action="store_true",
                               help="Output as JSON instead of human-readable text")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    estimator = CostEstimator()
    
    if args.command == "estimate":
        # Create schema config if schema fields specified
        schema_config = None
        if args.schema_fields > 0:
            schema_config = SchemaConfig(
                num_fields=args.schema_fields,
                field_complexity=args.schema_complexity,
                source_grounding_enabled=args.source_grounding,
                confidence_scores_enabled=args.confidence_scores
            )
        
        # Create request
        request = ProcessingRequest(
            file_type=args.file_type,
            quantity=args.quantity,
            model_name=args.model,
            deployment_type=args.deployment,
            field_extraction_enabled=not args.no_field_extraction,
            embeddings_enabled=args.embeddings,
            embeddings_model=args.embeddings_model,
            schema_config=schema_config
        )
        
        # Calculate cost
        breakdown = estimator.estimate_cost(request)
        
        if args.json:
            output = {
                "request": {
                    "file_type": request.file_type,
                    "quantity": request.quantity,
                    "model_name": request.model_name,
                    "deployment_type": request.deployment_type,
                    "field_extraction_enabled": request.field_extraction_enabled,
                    "embeddings_enabled": request.embeddings_enabled,
                    "embeddings_model": request.embeddings_model
                },
                "breakdown": asdict(breakdown)
            }
            print(json.dumps(output, indent=2))
        else:
            explanation = estimator.explain_cost_drivers(request, breakdown)
            print(explanation)
    
    elif args.command == "estimate-usage":
        # Extract usage data from file or command-line arguments
        if hasattr(args, 'cu_output') and args.cu_output:
            # Load from CU analyzer output file
            try:
                usage_dict = extract_usage_from_cu_output(args.cu_output)
                usage = UsageData(
                    input_tokens=usage_dict['input_tokens'],
                    output_tokens=usage_dict['output_tokens'],
                    contextualization_tokens=usage_dict['contextualization_tokens'],
                    document_pages_standard=usage_dict['document_pages']
                )
                pages = usage_dict['document_pages']
                print(f"Extracted usage from: {args.cu_output}")
                print(f"  Pages: {pages}, Input tokens: {usage.input_tokens}, Output tokens: {usage.output_tokens}\n")
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
                print(f"Error reading CU output file: {e}", file=__import__('sys').stderr)
                return
        else:
            # Use command-line arguments
            if not args.input_tokens or not args.output_tokens:
                print("Error: Either --cu-output or both --input-tokens and --output-tokens are required", 
                      file=__import__('sys').stderr)
                return
            
            usage = UsageData(
                input_tokens=args.input_tokens,
                output_tokens=args.output_tokens,
                contextualization_tokens=args.ctx_tokens,
                document_pages_standard=args.pages
            )
            pages = args.pages
        
        # Determine scale
        target_pages = args.scale_to if args.scale_to > 0 else pages
        scale_factor = target_pages / pages if pages > 0 else 1.0
        
        request = ProcessingRequest(
            file_type="document",
            quantity=target_pages,
            model_name=args.model,
            deployment_type=args.deployment,
            usage_data=usage
        )
        
        breakdown = estimator.estimate_from_usage(request, scale_factor=scale_factor)
        
        if args.json:
            output = {
                "usage_data": asdict(usage),
                "scale_factor": scale_factor,
                "target_pages": target_pages,
                "breakdown": asdict(breakdown)
            }
            print(json.dumps(output, indent=2))
        else:
            explanation = estimator.explain_cost_drivers(request, breakdown)
            print(explanation)
    
    elif args.command == "analyze":
        # Load results file
        results_path = Path(args.results_file)
        if not results_path.exists():
            print(f"Error: Results file not found: {args.results_file}")
            return
        
        with open(results_path, 'r') as f:
            results = json.load(f)
        
        # Analyze
        analysis = estimator.analyze_batch_results(results)
        
        if args.json:
            print(json.dumps(analysis, indent=2))
        else:
            explanation = estimator.explain_batch_analysis(analysis)
            print(explanation)


if __name__ == "__main__":
    main()
