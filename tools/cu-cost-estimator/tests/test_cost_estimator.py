"""
Tests for Azure AI Content Understanding Cost Estimator

These tests are based on the pricing examples from Microsoft documentation:
https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/pricing-explainer

Note: Some values may have minor discrepancies from the documentation due to:
- Rounding differences in calculations
- Updates to pricing rates
- Variations in token estimation methods

For production use, always verify estimates against actual API usage data.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from cu_cost_estimator import (
    CostEstimator,
    ProcessingRequest,
    UsageData,
    SchemaConfig,
    CostBreakdown,
    EstimationMode,
    PRICING_CONFIG
)


@pytest.mark.unit
class TestPricingConfig:
    """Tests for pricing configuration values"""
    
    def test_content_extraction_rates(self):
        """Verify content extraction pricing rates match documentation"""
        # From MS docs: Content extraction: $5.00 per 1,000 pages
        assert PRICING_CONFIG["ce"]["doc_per_1000_pages"] == 5.0
        
        # Audio and video rates
        assert PRICING_CONFIG["ce"]["audio_per_minute"] == 0.006
        assert PRICING_CONFIG["ce"]["video_per_minute"] == 0.0167
    
    def test_contextualization_rates(self):
        """Verify contextualization token rates"""
        # From MS docs: $1.00 per 1M contextualization tokens
        assert PRICING_CONFIG["ctx"]["regular_per_mtok"] == 1.0
        assert PRICING_CONFIG["ctx"]["mini_per_mtok"] == 1.0
    
    def test_contextualization_units(self):
        """Verify contextualization tokens per unit match documentation"""
        # From MS docs:
        # 1 Page = 1,000 contextualization tokens
        # 1 Image = 1,000 contextualization tokens
        # 1 hour audio = 100,000 tokens (1667 per minute)
        # 1 hour video = 1,000,000 tokens (16667 per minute)
        assert PRICING_CONFIG["ctx"]["units"]["doc_page"] == 1000
        assert PRICING_CONFIG["ctx"]["units"]["image"] == 1000
        assert PRICING_CONFIG["ctx"]["units"]["audio_minute"] == 1667
        assert PRICING_CONFIG["ctx"]["units"]["video_minute"] == 16667
    
    def test_model_pricing_gpt4o_mini(self):
        """Verify GPT-4o-mini pricing from documentation"""
        # Find gpt-4o-mini model
        model = None
        for m in PRICING_CONFIG["models"]:
            if m["name"] == "gpt-4o-mini":
                model = m
                break
        
        assert model is not None
        # From MS docs: GPT-4o-mini
        # Input: $0.15 per 1M tokens (global)
        # Output: $0.60 per 1M tokens (global)
        assert model["pricing"]["global_regional"]["input_per_mtok"] == 0.15
        assert model["pricing"]["global_regional"]["output_per_mtok"] == 0.60


@pytest.mark.unit
class TestDocumentationPricingExample:
    """
    Tests based on the invoice field extraction example from MS documentation.
    
    Scenario: Processing 1,000 invoice pages using GPT-4o-mini
    Reference: https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/pricing-explainer
    """
    
    def setup_method(self):
        """Set up test fixtures"""
        self.estimator = CostEstimator()
    
    def test_invoice_example_content_extraction(self):
        """
        Test content extraction cost calculation.
        
        From documentation:
        - Content extraction: 1,000 pages × $5.00 per 1,000 pages = $5.00
        """
        cost = self.estimator.calculate_content_extraction("document", 1000)
        assert cost == pytest.approx(5.00, rel=0.01)
    
    def test_invoice_example_contextualization(self):
        """
        Test contextualization cost calculation.
        
        From documentation:
        - Contextualization: 1,000 pages × 1,000 tokens/page = 1,000,000 tokens
        - Cost: 1,000,000 tokens × $1.00 per 1M tokens = $1.00
        """
        model = self.estimator.get_model_config("gpt-4o-mini")
        tokens, cost = self.estimator.calculate_contextualization("document", 1000, model)
        
        assert tokens == 1_000_000
        assert cost == pytest.approx(1.00, rel=0.01)
    
    def test_invoice_example_with_actual_usage(self):
        """
        Test the complete invoice example using actual usage data from documentation.
        
        From documentation:
        - Input tokens: 1,100 per page × 1,000 pages = 1,100,000 tokens
        - Output tokens: 60 per page × 1,000 pages = 60,000 tokens
        - Contextualization: 1,000 tokens per page × 1,000 pages = 1,000,000 tokens
        
        Expected costs (from documentation, may need adjustment for actual rates):
        - Content extraction: $5.00
        - Contextualization: $1.00
        - Input tokens: $0.44 (at $0.40/M for gpt-4o-mini - note: docs show $0.40)
        - Output tokens: $0.10 (at $1.60/M - note: docs show $1.60)
        
        Note: Documentation uses $0.40/M input and $1.60/M output which differs
        slightly from our config ($0.15/M and $0.60/M for gpt-4o-mini).
        This test validates the calculation logic rather than exact pricing.
        """
        usage = UsageData(
            input_tokens=1_100_000,
            output_tokens=60_000,
            contextualization_tokens=1_000_000,
            document_pages_standard=1000
        )
        
        request = ProcessingRequest(
            file_type="document",
            quantity=1000,
            model_name="gpt-4o-mini",
            deployment_type="global",
            usage_data=usage
        )
        
        breakdown = self.estimator.estimate_from_usage(request, scale_factor=1.0)
        
        # Verify content extraction
        assert breakdown.ce_cost == pytest.approx(5.00, rel=0.01)
        
        # Verify contextualization
        assert breakdown.ctx_cost == pytest.approx(1.00, rel=0.01)
        
        # Verify token counts
        assert breakdown.input_tokens == 1_100_000
        assert breakdown.output_tokens == 60_000
        
        # Verify LLM costs with actual gpt-4o-mini rates
        # Input: 1,100,000 × $0.15/M = $0.165
        # Output: 60,000 × $0.60/M = $0.036
        expected_fe_cost = (1_100_000 / 1_000_000) * 0.15 + (60_000 / 1_000_000) * 0.60
        assert breakdown.fe_cost == pytest.approx(expected_fe_cost, rel=0.01)
        
        # Verify estimation mode
        assert breakdown.estimation_mode == "usage_based"
    
    def test_invoice_example_documentation_rates(self):
        """
        Test using the exact rates mentioned in the documentation example.
        
        Documentation uses these illustrative rates:
        - GPT-4o-mini input: $0.40 per 1M tokens
        - GPT-4o-mini output: $1.60 per 1M tokens
        
        Expected total from docs: $6.54 per 1000 pages
        """
        # Create custom config with documentation rates
        doc_config = PRICING_CONFIG.copy()
        doc_config = {
            **PRICING_CONFIG,
            "models": [
                {
                    "name": "gpt-4o-mini-doc",
                    "class": "mini",
                    "tokens_per_unit": PRICING_CONFIG["models"][1]["tokens_per_unit"],
                    "pricing": {
                        "global_regional": {"input_per_mtok": 0.40, "output_per_mtok": 1.60},
                        "data_zone": {"input_per_mtok": 0.44, "output_per_mtok": 1.76}
                    }
                }
            ]
        }
        
        estimator = CostEstimator(doc_config)
        
        usage = UsageData(
            input_tokens=1_100_000,
            output_tokens=60_000,
            contextualization_tokens=1_000_000,
            document_pages_standard=1000
        )
        
        request = ProcessingRequest(
            file_type="document",
            quantity=1000,
            model_name="gpt-4o-mini-doc",
            deployment_type="global",
            usage_data=usage
        )
        
        breakdown = estimator.estimate_from_usage(request, scale_factor=1.0)
        
        # Calculate expected costs per documentation:
        # Content extraction: $5.00
        # Contextualization: $1.00
        # Input tokens: 1,100,000 × $0.40/M = $0.44
        # Output tokens: 60,000 × $1.60/M = $0.096 ≈ $0.10
        # Total: $5.00 + $1.00 + $0.44 + $0.10 = $6.54
        
        expected_total = 5.00 + 1.00 + 0.44 + 0.096
        assert breakdown.total_cost == pytest.approx(expected_total, rel=0.02)


@pytest.mark.unit
class TestUsageBasedEstimation:
    """Tests for usage-based cost estimation"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.estimator = CostEstimator()
    
    def test_from_api_response(self):
        """Test creating UsageData from API response format"""
        api_usage = {
            "documentPagesMinimal": 0,
            "documentPagesBasic": 0,
            "documentPagesStandard": 2,
            "contextualizationToken": 2000,
            "tokens": {
                "gpt-4.1-input": 10400,
                "gpt-4.1-output": 360
            }
        }
        
        usage = UsageData.from_api_response(api_usage)
        
        assert usage.input_tokens == 10400
        assert usage.output_tokens == 360
        assert usage.contextualization_tokens == 2000
        assert usage.document_pages_standard == 2
    
    def test_scaling_from_test_to_production(self):
        """Test scaling usage data from test batch to production volume"""
        # Test results from 10 pages
        usage = UsageData(
            input_tokens=11000,  # 1100 per page
            output_tokens=600,   # 60 per page
            contextualization_tokens=10000,  # 1000 per page
            document_pages_standard=10
        )
        
        request = ProcessingRequest(
            file_type="document",
            quantity=1000,  # Scale to 1000 pages
            model_name="gpt-4o-mini",
            deployment_type="global",
            usage_data=usage
        )
        
        # Scale factor: 1000 / 10 = 100
        breakdown = self.estimator.estimate_from_usage(request, test_pages=10)
        
        assert breakdown.input_tokens == 1_100_000
        assert breakdown.output_tokens == 60_000
        assert breakdown.estimation_mode == "usage_based"
    
    def test_usage_based_has_high_confidence(self):
        """Verify usage-based estimation reports high confidence"""
        usage = UsageData(
            input_tokens=1000,
            output_tokens=100,
            contextualization_tokens=1000,
            document_pages_standard=1
        )
        
        request = ProcessingRequest(
            file_type="document",
            quantity=1,
            model_name="gpt-4o",
            usage_data=usage
        )
        
        breakdown = self.estimator.estimate_from_usage(request)
        
        assert "High confidence" in breakdown.confidence_note
        assert breakdown.estimation_mode == "usage_based"


@pytest.mark.unit
class TestSchemaBasedEstimation:
    """Tests for schema-based cost estimation"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.estimator = CostEstimator()
    
    def test_simple_schema(self):
        """Test estimation with simple schema"""
        schema = SchemaConfig(
            num_fields=5,
            field_complexity="simple",
            source_grounding_enabled=False,
            confidence_scores_enabled=False
        )
        
        request = ProcessingRequest(
            file_type="document",
            quantity=100,
            model_name="gpt-4o-mini",
            schema_config=schema
        )
        
        breakdown = self.estimator.estimate_from_schema(request)
        
        assert breakdown.estimation_mode == "schema_based"
        assert "LOW confidence" in breakdown.confidence_note
        assert breakdown.total_cost > 0
    
    def test_complex_schema_with_features(self):
        """Test estimation with complex schema and advanced features"""
        schema = SchemaConfig(
            num_fields=20,
            field_complexity="complex",
            source_grounding_enabled=True,
            confidence_scores_enabled=True,
            extractive_mode=True
        )
        
        simple_schema = SchemaConfig(
            num_fields=5,
            field_complexity="simple"
        )
        
        request_complex = ProcessingRequest(
            file_type="document",
            quantity=100,
            model_name="gpt-4o",
            schema_config=schema
        )
        
        request_simple = ProcessingRequest(
            file_type="document",
            quantity=100,
            model_name="gpt-4o",
            schema_config=simple_schema
        )
        
        breakdown_complex = self.estimator.estimate_from_schema(request_complex)
        breakdown_simple = self.estimator.estimate_from_schema(request_simple)
        
        # Complex schema with features should cost more
        assert breakdown_complex.total_cost > breakdown_simple.total_cost
    
    def test_feature_multipliers(self):
        """Test that feature multipliers increase token estimates"""
        base_schema = SchemaConfig(
            num_fields=10,
            field_complexity="moderate"
        )
        
        grounded_schema = SchemaConfig(
            num_fields=10,
            field_complexity="moderate",
            source_grounding_enabled=True,
            confidence_scores_enabled=True
        )
        
        # Base multiplier should be 1.0
        assert base_schema.get_token_multiplier() == 1.0
        
        # Source grounding + confidence = 2x
        assert grounded_schema.get_token_multiplier() == 2.0
    
    def test_schema_output_token_estimation(self):
        """Test output token estimation based on schema"""
        simple_schema = SchemaConfig(
            num_fields=5,
            field_complexity="simple",
            avg_field_value_length=20
        )
        
        complex_schema = SchemaConfig(
            num_fields=20,
            field_complexity="complex",
            avg_field_value_length=100
        )
        
        simple_output = simple_schema.estimate_output_tokens_per_page()
        complex_output = complex_schema.estimate_output_tokens_per_page()
        
        # Complex schema should have more output tokens
        assert complex_output > simple_output


@pytest.mark.unit
class TestContentExtractionCosts:
    """Tests for content extraction cost calculations"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.estimator = CostEstimator()
    
    def test_document_content_extraction(self):
        """Test document content extraction at $5 per 1000 pages"""
        # 1000 pages = $5
        assert self.estimator.calculate_content_extraction("document", 1000) == pytest.approx(5.0)
        
        # 5000 pages = $25
        assert self.estimator.calculate_content_extraction("document", 5000) == pytest.approx(25.0)
        
        # 100 pages = $0.50
        assert self.estimator.calculate_content_extraction("document", 100) == pytest.approx(0.5)
    
    def test_audio_content_extraction(self):
        """Test audio content extraction at $0.006 per minute"""
        # 60 minutes = $0.36
        cost = self.estimator.calculate_content_extraction("audio", 60)
        assert cost == pytest.approx(0.36, rel=0.01)
        
        # 1 hour = $0.36
        assert self.estimator.calculate_content_extraction("audio", 60) == pytest.approx(0.36)
    
    def test_video_content_extraction(self):
        """Test video content extraction at $0.0167 per minute"""
        # 60 minutes = $1.002
        cost = self.estimator.calculate_content_extraction("video", 60)
        assert cost == pytest.approx(1.002, rel=0.01)
    
    def test_text_content_extraction_free(self):
        """Test that text content extraction is free"""
        assert self.estimator.calculate_content_extraction("text", 10000) == 0.0
    
    def test_image_content_extraction_free(self):
        """Test that image content extraction is free"""
        assert self.estimator.calculate_content_extraction("image", 100) == 0.0


@pytest.mark.unit
class TestContextualizationCosts:
    """Tests for contextualization cost calculations"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.estimator = CostEstimator()
        self.model = self.estimator.get_model_config("gpt-4o")
    
    def test_document_contextualization(self):
        """Test 1000 tokens per page at $1 per 1M tokens"""
        # 1000 pages × 1000 tokens = 1M tokens = $1.00
        tokens, cost = self.estimator.calculate_contextualization("document", 1000, self.model)
        assert tokens == 1_000_000
        assert cost == pytest.approx(1.0, rel=0.01)
    
    def test_image_contextualization(self):
        """Test 1000 tokens per image"""
        # 500 images × 1000 tokens = 500K tokens = $0.50
        tokens, cost = self.estimator.calculate_contextualization("image", 500, self.model)
        assert tokens == 500_000
        assert cost == pytest.approx(0.5, rel=0.01)
    
    def test_audio_contextualization(self):
        """Test 100,000 tokens per hour (1667 per minute)"""
        # 60 minutes × 1667 tokens = 100,020 tokens ≈ $0.10
        tokens, cost = self.estimator.calculate_contextualization("audio", 60, self.model)
        assert tokens == pytest.approx(100_000, rel=0.01)
        assert cost == pytest.approx(0.10, rel=0.01)
    
    def test_video_contextualization(self):
        """Test 1,000,000 tokens per hour (16667 per minute)"""
        # 60 minutes × 16667 tokens = 1,000,020 tokens ≈ $1.00
        tokens, cost = self.estimator.calculate_contextualization("video", 60, self.model)
        assert tokens == pytest.approx(1_000_000, rel=0.01)
        assert cost == pytest.approx(1.0, rel=0.01)


@pytest.mark.unit
class TestModelComparison:
    """Tests comparing different model costs"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.estimator = CostEstimator()
    
    def test_mini_model_cheaper_than_regular(self):
        """Verify mini models are significantly cheaper"""
        request_regular = ProcessingRequest(
            file_type="document",
            quantity=1000,
            model_name="gpt-4o",
            deployment_type="global"
        )
        
        request_mini = ProcessingRequest(
            file_type="document",
            quantity=1000,
            model_name="gpt-4o-mini",
            deployment_type="global"
        )
        
        breakdown_regular = self.estimator.estimate_cost(request_regular)
        breakdown_mini = self.estimator.estimate_cost(request_mini)
        
        # Mini should be significantly cheaper for LLM costs
        assert breakdown_mini.fe_cost < breakdown_regular.fe_cost
        
        # From docs: "up to 80% savings" with mini models
        # FE cost ratio should show significant savings
        if breakdown_regular.fe_cost > 0:
            savings = (breakdown_regular.fe_cost - breakdown_mini.fe_cost) / breakdown_regular.fe_cost
            assert savings > 0.5  # At least 50% savings
    
    def test_data_zone_more_expensive(self):
        """Verify Data Zone deployment is ~10% more expensive"""
        request_global = ProcessingRequest(
            file_type="document",
            quantity=1000,
            model_name="gpt-4o",
            deployment_type="global"
        )
        
        request_data_zone = ProcessingRequest(
            file_type="document",
            quantity=1000,
            model_name="gpt-4o",
            deployment_type="data_zone"
        )
        
        breakdown_global = self.estimator.estimate_cost(request_global)
        breakdown_data_zone = self.estimator.estimate_cost(request_data_zone)
        
        # Data zone should be more expensive
        assert breakdown_data_zone.fe_cost > breakdown_global.fe_cost
        
        # Should be approximately 10% more
        if breakdown_global.fe_cost > 0:
            markup = (breakdown_data_zone.fe_cost - breakdown_global.fe_cost) / breakdown_global.fe_cost
            assert markup == pytest.approx(0.10, abs=0.02)


@pytest.mark.unit
class TestBatchAnalysis:
    """Tests for batch processing analysis"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.estimator = CostEstimator()
    
    def test_batch_analysis_averages(self):
        """Test that batch analysis correctly calculates averages"""
        results = [
            {
                "file_name": "doc1.pdf",
                "file_type": "document",
                "pages": 10,
                "actual_input_tokens": 26000,  # 2600 per page
                "actual_output_tokens": 900,    # 90 per page
                "model_name": "gpt-4o",
                "deployment_type": "global"
            },
            {
                "file_name": "doc2.pdf",
                "file_type": "document",
                "pages": 20,
                "actual_input_tokens": 52000,  # 2600 per page
                "actual_output_tokens": 1800,   # 90 per page
                "model_name": "gpt-4o",
                "deployment_type": "global"
            }
        ]
        
        analysis = self.estimator.analyze_batch_results(results)
        
        assert analysis["summary"]["total_documents"] == 2
        assert analysis["summary"]["total_pages"] == 30
        assert analysis["averages"]["pages_per_document"] == 15.0
    
    def test_empty_batch_returns_error(self):
        """Test that empty batch returns error"""
        analysis = self.estimator.analyze_batch_results([])
        assert "error" in analysis


@pytest.mark.unit
class TestAutoEstimationModeSelection:
    """Tests for automatic estimation mode selection"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.estimator = CostEstimator()
    
    def test_selects_usage_based_when_usage_provided(self):
        """Test that usage data triggers usage-based estimation"""
        usage = UsageData(input_tokens=1000, output_tokens=100, contextualization_tokens=500)
        request = ProcessingRequest(
            file_type="document",
            quantity=1,
            model_name="gpt-4o",
            usage_data=usage
        )
        
        breakdown = self.estimator.estimate_cost(request)
        assert breakdown.estimation_mode == "usage_based"
    
    def test_selects_schema_based_when_schema_provided(self):
        """Test that schema config triggers schema-based estimation"""
        schema = SchemaConfig(num_fields=10)
        request = ProcessingRequest(
            file_type="document",
            quantity=1,
            model_name="gpt-4o",
            schema_config=schema
        )
        
        breakdown = self.estimator.estimate_cost(request)
        assert breakdown.estimation_mode == "schema_based"
    
    def test_selects_default_when_neither_provided(self):
        """Test that default estimation is used when no usage or schema"""
        request = ProcessingRequest(
            file_type="document",
            quantity=1,
            model_name="gpt-4o"
        )
        
        breakdown = self.estimator.estimate_cost(request)
        assert breakdown.estimation_mode == "default"


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and error handling"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.estimator = CostEstimator()
    
    def test_invalid_model_raises_error(self):
        """Test that invalid model name raises ValueError"""
        request = ProcessingRequest(
            file_type="document",
            quantity=100,
            model_name="invalid-model"
        )
        
        with pytest.raises(ValueError, match="not found"):
            self.estimator.estimate_cost(request)
    
    def test_zero_quantity(self):
        """Test handling of zero quantity"""
        request = ProcessingRequest(
            file_type="document",
            quantity=0,
            model_name="gpt-4o"
        )
        
        breakdown = self.estimator.estimate_cost(request)
        assert breakdown.total_cost == 0.0
    
    def test_ptu_deployment_no_token_cost(self):
        """Test that PTU deployment has no per-token costs"""
        request = ProcessingRequest(
            file_type="document",
            quantity=1000,
            model_name="gpt-4o",
            deployment_type="ptu"
        )
        
        breakdown = self.estimator.estimate_cost(request)
        # PTU should only have content extraction costs (no LLM token costs)
        assert breakdown.fe_cost == 0.0


@pytest.mark.unit
class TestTextConversion:
    """Tests for text-to-page conversion"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.estimator = CostEstimator()
    
    def test_text_to_pages_conversion(self):
        """Test that 3000 characters = 1 page"""
        # Default is 3000 chars per page
        assert self.estimator.convert_text_to_pages(3000) == 1.0
        assert self.estimator.convert_text_to_pages(6000) == 2.0
        assert self.estimator.convert_text_to_pages(1500) == 0.5
    
    def test_text_processing_free_ce(self):
        """Test that text processing has free content extraction"""
        request = ProcessingRequest(
            file_type="text",
            quantity=30000,  # 10 pages worth
            model_name="gpt-4o"
        )
        
        breakdown = self.estimator.estimate_cost(request)
        assert breakdown.ce_cost == 0.0  # Text CE is free


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
