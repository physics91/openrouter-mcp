"""
Test cases for model benchmarking functionality.

This module tests the benchmark handler that allows comparing multiple AI models
by sending the same prompt and analyzing their responses.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

from src.openrouter_mcp.handlers.benchmark import (
    BenchmarkHandler,
    BenchmarkResult,
    ModelComparison,
    BenchmarkMetrics
)


class TestBenchmarkResult:
    """Test the BenchmarkResult data class."""
    
    def test_benchmark_result_creation(self):
        """Test creating a benchmark result."""
        result = BenchmarkResult(
            model_id="openai/gpt-4",
            prompt="Test prompt",
            response="Test response",
            response_time_ms=150.5,
            tokens_used=25,
            cost=0.0015,
            timestamp=datetime.now(timezone.utc)
        )
        
        assert result.model_id == "openai/gpt-4"
        assert result.prompt == "Test prompt"
        assert result.response == "Test response"
        assert result.response_time_ms == 150.5
        assert result.tokens_used == 25
        assert result.cost == 0.0015
        assert isinstance(result.timestamp, datetime)
    
    def test_benchmark_result_to_dict(self):
        """Test converting benchmark result to dictionary."""
        timestamp = datetime.now(timezone.utc)
        result = BenchmarkResult(
            model_id="anthropic/claude-3-opus",
            prompt="Explain quantum computing",
            response="Quantum computing uses quantum bits...",
            response_time_ms=200.0,
            tokens_used=50,
            cost=0.003,
            timestamp=timestamp,
            error=None
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["model_id"] == "anthropic/claude-3-opus"
        assert result_dict["prompt"] == "Explain quantum computing"
        assert result_dict["response"] == "Quantum computing uses quantum bits..."
        assert result_dict["response_time_ms"] == 200.0
        assert result_dict["tokens_used"] == 50
        assert result_dict["cost"] == 0.003
        assert result_dict["timestamp"] == timestamp.isoformat()
        assert result_dict["error"] is None
    
    def test_benchmark_result_with_error(self):
        """Test benchmark result with error."""
        result = BenchmarkResult(
            model_id="openai/gpt-3.5-turbo",
            prompt="Test prompt",
            response=None,
            response_time_ms=0,
            tokens_used=0,
            cost=0,
            timestamp=datetime.now(timezone.utc),
            error="API rate limit exceeded"
        )
        
        assert result.error == "API rate limit exceeded"
        assert result.response is None
        assert result.tokens_used == 0


class TestBenchmarkMetrics:
    """Test the BenchmarkMetrics class."""
    
    def test_metrics_calculation(self):
        """Test calculating metrics from benchmark results."""
        results = [
            BenchmarkResult(
                model_id="model1",
                prompt="test",
                response="response1",
                response_time_ms=100,
                tokens_used=20,
                cost=0.001,
                timestamp=datetime.now(timezone.utc)
            ),
            BenchmarkResult(
                model_id="model1",
                prompt="test",
                response="response2",
                response_time_ms=150,
                tokens_used=25,
                cost=0.0015,
                timestamp=datetime.now(timezone.utc)
            )
        ]
        
        metrics = BenchmarkMetrics.from_results(results)
        
        assert metrics.avg_response_time_ms == 125.0
        assert metrics.avg_tokens_used == 22.5
        assert metrics.avg_cost == 0.00125
        assert metrics.total_cost == 0.0025
        assert metrics.success_rate == 1.0
        assert metrics.sample_count == 2
    
    def test_metrics_with_errors(self):
        """Test metrics calculation with some errors."""
        results = [
            BenchmarkResult(
                model_id="model1",
                prompt="test",
                response="response1",
                response_time_ms=100,
                tokens_used=20,
                cost=0.001,
                timestamp=datetime.now(timezone.utc)
            ),
            BenchmarkResult(
                model_id="model1",
                prompt="test",
                response=None,
                response_time_ms=0,
                tokens_used=0,
                cost=0,
                timestamp=datetime.now(timezone.utc),
                error="API error"
            )
        ]
        
        metrics = BenchmarkMetrics.from_results(results)
        
        assert metrics.success_rate == 0.5
        assert metrics.sample_count == 2
        # Averages should only include successful results
        assert metrics.avg_response_time_ms == 100.0
        assert metrics.avg_tokens_used == 20.0


class TestModelComparison:
    """Test the ModelComparison class."""
    
    def test_model_comparison_creation(self):
        """Test creating a model comparison."""
        results = {
            "openai/gpt-4": [
                BenchmarkResult(
                    model_id="openai/gpt-4",
                    prompt="test",
                    response="response",
                    response_time_ms=200,
                    tokens_used=30,
                    cost=0.002,
                    timestamp=datetime.now(timezone.utc)
                )
            ],
            "anthropic/claude-3-opus": [
                BenchmarkResult(
                    model_id="anthropic/claude-3-opus",
                    prompt="test",
                    response="response",
                    response_time_ms=150,
                    tokens_used=25,
                    cost=0.0015,
                    timestamp=datetime.now(timezone.utc)
                )
            ]
        }
        
        comparison = ModelComparison(
            prompt="test",
            models=["openai/gpt-4", "anthropic/claude-3-opus"],
            results=results,
            timestamp=datetime.now(timezone.utc)
        )
        
        assert comparison.prompt == "test"
        assert len(comparison.models) == 2
        assert "openai/gpt-4" in comparison.models
        assert len(comparison.results) == 2
    
    def test_model_comparison_rankings(self):
        """Test getting model rankings from comparison."""
        results = {
            "openai/gpt-4": [
                BenchmarkResult(
                    model_id="openai/gpt-4",
                    prompt="test",
                    response="response",
                    response_time_ms=200,
                    tokens_used=30,
                    cost=0.002,
                    timestamp=datetime.now(timezone.utc)
                )
            ],
            "anthropic/claude-3-opus": [
                BenchmarkResult(
                    model_id="anthropic/claude-3-opus",
                    prompt="test",
                    response="response",
                    response_time_ms=150,
                    tokens_used=25,
                    cost=0.0015,
                    timestamp=datetime.now(timezone.utc)
                )
            ]
        }
        
        comparison = ModelComparison(
            prompt="test",
            models=["openai/gpt-4", "anthropic/claude-3-opus"],
            results=results,
            timestamp=datetime.now(timezone.utc)
        )
        
        rankings = comparison.get_rankings()
        
        # Claude should be ranked first (faster and cheaper)
        assert rankings["speed"][0]["model"] == "anthropic/claude-3-opus"
        assert rankings["cost"][0]["model"] == "anthropic/claude-3-opus"
        assert rankings["speed"][0]["metric"] == 150
        assert rankings["cost"][0]["metric"] == 0.0015


class TestBenchmarkHandler:
    """Test the BenchmarkHandler class."""
    
    @pytest.fixture
    def handler(self):
        """Create a benchmark handler instance."""
        # Use a mock API key for testing
        return BenchmarkHandler(api_key="test-api-key")
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock OpenRouter client."""
        client = Mock()
        client.chat_completion = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_benchmark_single_model(self, handler, mock_client):
        """Test benchmarking a single model."""
        # Mock the response
        mock_client.chat_completion.return_value = {
            "choices": [{"message": {"content": "Test response"}}],
            "usage": {"total_tokens": 25}
        }
        
        handler.client = mock_client
        
        result = await handler.benchmark_model(
            model_id="openai/gpt-4",
            prompt="Test prompt",
            temperature=0.7,
            max_tokens=100
        )
        
        assert result.model_id == "openai/gpt-4"
        assert result.prompt == "Test prompt"
        assert result.response == "Test response"
        assert result.tokens_used == 25
        assert result.response_time_ms > 0
        
        mock_client.chat_completion.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_benchmark_multiple_models(self, handler, mock_client):
        """Test benchmarking multiple models."""
        # Mock different responses for different models
        mock_client.chat_completion.side_effect = [
            {
                "choices": [{"message": {"content": "GPT-4 response"}}],
                "usage": {"total_tokens": 30}
            },
            {
                "choices": [{"message": {"content": "Claude response"}}],
                "usage": {"total_tokens": 25}
            }
        ]
        
        handler.client = mock_client
        
        comparison = await handler.benchmark_models(
            models=["openai/gpt-4", "anthropic/claude-3-opus"],
            prompt="Compare these models",
            temperature=0.7,
            max_tokens=100,
            runs_per_model=1
        )
        
        assert comparison.prompt == "Compare these models"
        assert len(comparison.models) == 2
        assert "openai/gpt-4" in comparison.results
        assert "anthropic/claude-3-opus" in comparison.results
        
        gpt4_results = comparison.results["openai/gpt-4"]
        assert len(gpt4_results) == 1
        assert gpt4_results[0].response == "GPT-4 response"
        
        claude_results = comparison.results["anthropic/claude-3-opus"]
        assert len(claude_results) == 1
        assert claude_results[0].response == "Claude response"
    
    @pytest.mark.asyncio
    async def test_benchmark_with_multiple_runs(self, handler, mock_client):
        """Test benchmarking with multiple runs per model."""
        # Mock multiple responses
        mock_client.chat_completion.side_effect = [
            {
                "choices": [{"message": {"content": f"Response {i}"}}],
                "usage": {"total_tokens": 20 + i}
            }
            for i in range(3)
        ]
        
        handler.client = mock_client
        
        comparison = await handler.benchmark_models(
            models=["openai/gpt-4"],
            prompt="Test multiple runs",
            temperature=0.7,
            max_tokens=100,
            runs_per_model=3
        )
        
        assert len(comparison.results["openai/gpt-4"]) == 3
        
        for i, result in enumerate(comparison.results["openai/gpt-4"]):
            assert result.response == f"Response {i}"
            assert result.tokens_used == 20 + i
    
    @pytest.mark.asyncio
    async def test_benchmark_with_error_handling(self, handler, mock_client):
        """Test benchmark with error handling."""
        # Mock an error for one model
        mock_client.chat_completion.side_effect = [
            {
                "choices": [{"message": {"content": "Success"}}],
                "usage": {"total_tokens": 20}
            },
            Exception("API Error"),
        ]
        
        handler.client = mock_client
        
        comparison = await handler.benchmark_models(
            models=["openai/gpt-4", "anthropic/claude-3-opus"],
            prompt="Test error handling",
            temperature=0.7,
            max_tokens=100,
            runs_per_model=1
        )
        
        # GPT-4 should succeed
        assert comparison.results["openai/gpt-4"][0].error is None
        assert comparison.results["openai/gpt-4"][0].response == "Success"
        
        # Claude should have an error
        assert comparison.results["anthropic/claude-3-opus"][0].error is not None
        assert "API Error" in comparison.results["anthropic/claude-3-opus"][0].error
        assert comparison.results["anthropic/claude-3-opus"][0].response is None
    
    @pytest.mark.asyncio
    async def test_save_and_load_comparison(self, handler, tmp_path):
        """Test saving and loading benchmark comparisons."""
        # Create a comparison
        comparison = ModelComparison(
            prompt="Test prompt",
            models=["model1", "model2"],
            results={
                "model1": [
                    BenchmarkResult(
                        model_id="model1",
                        prompt="Test prompt",
                        response="Response 1",
                        response_time_ms=100,
                        tokens_used=20,
                        cost=0.001,
                        timestamp=datetime.now(timezone.utc)
                    )
                ],
                "model2": [
                    BenchmarkResult(
                        model_id="model2",
                        prompt="Test prompt",
                        response="Response 2",
                        response_time_ms=150,
                        tokens_used=25,
                        cost=0.0015,
                        timestamp=datetime.now(timezone.utc)
                    )
                ]
            },
            timestamp=datetime.now(timezone.utc)
        )
        
        # Save comparison
        file_path = tmp_path / "benchmark_test.json"
        handler.save_comparison(comparison, str(file_path))
        
        # Load comparison
        loaded = handler.load_comparison(str(file_path))
        
        assert loaded.prompt == comparison.prompt
        assert loaded.models == comparison.models
        assert len(loaded.results) == len(comparison.results)
        assert loaded.results["model1"][0].response == "Response 1"
        assert loaded.results["model2"][0].response == "Response 2"
    
    def test_format_comparison_report(self, handler):
        """Test formatting comparison report."""
        comparison = ModelComparison(
            prompt="Test prompt",
            models=["openai/gpt-4", "anthropic/claude-3-opus"],
            results={
                "openai/gpt-4": [
                    BenchmarkResult(
                        model_id="openai/gpt-4",
                        prompt="Test prompt",
                        response="GPT-4 response",
                        response_time_ms=200,
                        tokens_used=30,
                        cost=0.002,
                        timestamp=datetime.now(timezone.utc)
                    )
                ],
                "anthropic/claude-3-opus": [
                    BenchmarkResult(
                        model_id="anthropic/claude-3-opus",
                        prompt="Test prompt",
                        response="Claude response",
                        response_time_ms=150,
                        tokens_used=25,
                        cost=0.0015,
                        timestamp=datetime.now(timezone.utc)
                    )
                ]
            },
            timestamp=datetime.now(timezone.utc)
        )
        
        report = handler.format_comparison_report(comparison)
        
        assert "Benchmark Comparison Report" in report
        assert "Test prompt" in report
        assert "openai/gpt-4" in report
        assert "anthropic/claude-3-opus" in report
        assert "Response Time" in report
        assert "Cost" in report
        assert "Rankings" in report


class TestAdvancedBenchmarkMetrics:
    """Test enhanced benchmark metrics functionality."""
    
    def test_detailed_cost_calculation(self):
        """Test detailed token-based cost calculation."""
        # Test with detailed token usage breakdown
        result = BenchmarkResult(
            model_id="openai/gpt-4",
            prompt="Test prompt",
            response="Test response",
            response_time_ms=150.0,
            tokens_used=100,
            cost=0.006,  # Expected: 50 prompt tokens * 0.03/1k + 50 completion tokens * 0.06/1k
            timestamp=datetime.now(timezone.utc),
            prompt_tokens=50,
            completion_tokens=50,
            input_cost_per_1k_tokens=0.03,
            output_cost_per_1k_tokens=0.06
        )
        
        # This test will fail initially - we need to add these fields
        assert hasattr(result, 'prompt_tokens')
        assert hasattr(result, 'completion_tokens')
        assert hasattr(result, 'input_cost_per_1k_tokens')
        assert hasattr(result, 'output_cost_per_1k_tokens')
        assert result.prompt_tokens == 50
        assert result.completion_tokens == 50
    
    def test_response_quality_scoring(self):
        """Test response quality assessment."""
        result = BenchmarkResult(
            model_id="openai/gpt-4",
            prompt="Explain quantum computing",
            response="Quantum computing uses quantum bits or qubits...",
            response_time_ms=200.0,
            tokens_used=75,
            cost=0.0045,
            timestamp=datetime.now(timezone.utc),
            quality_score=0.85,  # Score based on completeness, accuracy, relevance
            response_length=150,
            contains_code_example=False,
            language_coherence_score=0.9
        )
        
        # These will fail initially - we need to add quality assessment
        assert hasattr(result, 'quality_score')
        assert hasattr(result, 'response_length')
        assert hasattr(result, 'contains_code_example')
        assert hasattr(result, 'language_coherence_score')
        assert result.quality_score == 0.85
        assert result.response_length == 150
        assert result.language_coherence_score == 0.9
    
    def test_throughput_measurement(self):
        """Test throughput calculation (tokens per second)."""
        result = BenchmarkResult(
            model_id="anthropic/claude-3-opus",
            prompt="Generate a story",
            response="Once upon a time...",
            response_time_ms=2000.0,  # 2 seconds
            tokens_used=200,
            cost=0.01,
            timestamp=datetime.now(timezone.utc),
            throughput_tokens_per_second=100.0  # 200 tokens / 2 seconds
        )
        
        # This will fail initially - we need throughput calculation
        assert hasattr(result, 'throughput_tokens_per_second')
        assert result.throughput_tokens_per_second == 100.0
    
    def test_enhanced_metrics_calculation(self):
        """Test enhanced metrics with new fields."""
        results = [
            BenchmarkResult(
                model_id="model1",
                prompt="test",
                response="response1",
                response_time_ms=1000,
                tokens_used=100,
                cost=0.005,
                timestamp=datetime.now(timezone.utc),
                prompt_tokens=40,
                completion_tokens=60,
                quality_score=0.8,
                throughput_tokens_per_second=100.0
            ),
            BenchmarkResult(
                model_id="model1",
                prompt="test",
                response="response2",
                response_time_ms=1500,
                tokens_used=150,
                cost=0.0075,
                timestamp=datetime.now(timezone.utc),
                prompt_tokens=50,
                completion_tokens=100,
                quality_score=0.9,
                throughput_tokens_per_second=100.0
            )
        ]
        
        metrics = BenchmarkMetrics.from_results(results)
        
        # Test enhanced metrics - these will fail initially
        assert hasattr(metrics, 'avg_quality_score')
        assert hasattr(metrics, 'avg_throughput')
        assert hasattr(metrics, 'avg_prompt_tokens')
        assert hasattr(metrics, 'avg_completion_tokens')
        assert hasattr(metrics, 'cost_per_quality_point')
        
        assert abs(metrics.avg_quality_score - 0.85) < 0.0001
        assert metrics.avg_throughput == 100.0
        assert metrics.avg_prompt_tokens == 45.0
        assert metrics.avg_completion_tokens == 80.0
        # Cost per quality point = avg_cost / avg_quality_score
        assert abs(metrics.cost_per_quality_point - (0.00625 / 0.85)) < 0.0001


class TestAdvancedBenchmarkHandler:
    """Test enhanced benchmark handler functionality."""
    
    @pytest.fixture
    def enhanced_handler(self):
        """Create an enhanced benchmark handler."""
        from src.openrouter_mcp.handlers.benchmark import EnhancedBenchmarkHandler
        return EnhancedBenchmarkHandler(api_key="test-api-key")
    
    @pytest.mark.asyncio
    async def test_quality_assessment(self, enhanced_handler):
        """Test response quality assessment."""
        # This will fail initially - we need to implement quality assessment
        response_text = "Quantum computing is a revolutionary technology that uses quantum bits..."
        quality_score = enhanced_handler.assess_response_quality(
            prompt="Explain quantum computing",
            response=response_text
        )
        
        assert 0 <= quality_score <= 1
        assert quality_score > 0.5  # Should be decent quality
    
    @pytest.mark.asyncio
    async def test_detailed_cost_calculation_from_api(self, enhanced_handler):
        """Test detailed cost calculation from actual API response."""
        mock_response = {
            "choices": [{"message": {"content": "Test response"}}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 15,
                "total_tokens": 25
            },
            "model": "openai/gpt-4"
        }
        
        # This will fail initially - we need enhanced cost calculation
        cost_details = enhanced_handler.calculate_detailed_cost(
            api_response=mock_response,
            model_pricing={
                "prompt": 0.03,  # per 1k tokens
                "completion": 0.06  # per 1k tokens
            }
        )
        
        assert "input_cost" in cost_details
        assert "output_cost" in cost_details
        assert "total_cost" in cost_details
        assert cost_details["input_cost"] == 10 * 0.03 / 1000
        assert cost_details["output_cost"] == 15 * 0.06 / 1000
    
    @pytest.mark.asyncio
    async def test_parallel_benchmarking(self, enhanced_handler):
        """Test parallel model benchmarking for better performance."""
        # This will fail initially - we need parallel execution
        models = ["openai/gpt-4", "anthropic/claude-3-opus", "google/gemini-pro"]
        
        with patch.object(enhanced_handler, 'benchmark_model') as mock_benchmark:
            mock_benchmark.return_value = BenchmarkResult(
                model_id="test",
                prompt="test",
                response="test",
                response_time_ms=100,
                tokens_used=20,
                cost=0.001,
                timestamp=datetime.now(timezone.utc)
            )
            
            comparison = await enhanced_handler.benchmark_models_parallel(
                models=models,
                prompt="Test parallel execution",
                max_concurrent=3
            )
            
            # Should have been called for all models
            assert mock_benchmark.call_count == len(models)
            assert len(comparison.models) == len(models)


class TestNewBenchmarkTools:
    """Test new MCP benchmark tools."""
    
    @pytest.mark.asyncio
    async def test_export_benchmark_report_tool(self):
        """Test exporting benchmark reports to different formats."""
        from src.openrouter_mcp.handlers.benchmark import (
            BenchmarkReportExporter, BenchmarkHandler, ModelComparison, BenchmarkResult
        )
        from datetime import datetime, timezone
        import os
        
        # Create a mock comparison
        results = {
            "openai/gpt-4": [
                BenchmarkResult(
                    model_id="openai/gpt-4",
                    prompt="Test prompt",
                    response="Test response",
                    response_time_ms=200,
                    tokens_used=30,
                    cost=0.002,
                    timestamp=datetime.now(timezone.utc)
                )
            ]
        }
        
        comparison = ModelComparison(
            prompt="Test prompt",
            models=["openai/gpt-4"],
            results=results,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Test the exporter directly
        handler = BenchmarkHandler(api_key="test-key")  # Use test key
        exporter = BenchmarkReportExporter(handler)
        
        # Test CSV export
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "test_report.csv")
            result_path = exporter.export_to_csv(comparison, csv_path)
            assert os.path.exists(result_path)
            assert result_path == csv_path
            
            # Test markdown export  
            md_path = os.path.join(temp_dir, "test_report.md")
            result_path = exporter.export_to_markdown(comparison, md_path)
            assert os.path.exists(result_path)
            assert result_path == md_path
            
            # Test JSON export
            json_path = os.path.join(temp_dir, "test_report.json")
            result_path = exporter.export_to_json(comparison, json_path)
            assert os.path.exists(result_path)
            assert result_path == json_path
    
    @pytest.mark.asyncio
    async def test_compare_model_performance_tool(self):
        """Test advanced model performance comparison."""
        from src.openrouter_mcp.handlers.benchmark import (
            ModelPerformanceAnalyzer, BenchmarkHandler, BenchmarkMetrics
        )
        
        # Test the analyzer directly
        handler = BenchmarkHandler(api_key="test-key")
        analyzer = ModelPerformanceAnalyzer(handler)
        
        # Create mock metrics
        mock_metrics = {
            "openai/gpt-4": BenchmarkMetrics(
                avg_response_time_ms=200,
                avg_tokens_used=30,
                avg_cost=0.002,
                total_cost=0.002,
                success_rate=1.0,
                sample_count=1,
                avg_quality_score=0.8,
                avg_throughput=150
            ),
            "anthropic/claude-3-opus": BenchmarkMetrics(
                avg_response_time_ms=150,
                avg_tokens_used=25,
                avg_cost=0.0015,
                total_cost=0.0015,
                success_rate=1.0,
                sample_count=1,
                avg_quality_score=0.9,
                avg_throughput=167
            )
        }
        
        weighting = {
            "speed": 0.25,
            "cost": 0.25,
            "quality": 0.4,
            "throughput": 0.1
        }
        
        result = analyzer.compare_models_weighted(mock_metrics, weighting)
        
        assert "overall_ranking" in result
        assert "detailed_scores" in result
        assert len(result["overall_ranking"]) == 2
        assert all(metric in result["detailed_scores"] for metric in ["speed", "cost", "quality", "throughput"])


class TestBenchmarkIntegration:
    """Integration tests for enhanced benchmark system."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_enhanced_benchmarking(self):
        """Test complete enhanced benchmarking workflow."""
        from src.openrouter_mcp.handlers.benchmark import (
            EnhancedBenchmarkHandler, BenchmarkResult, ModelComparison,
            BenchmarkReportExporter, ModelPerformanceAnalyzer
        )
        from unittest.mock import AsyncMock, Mock, patch
        from datetime import datetime, timezone
        import tempfile
        import os
        
        # Create enhanced handler
        handler = EnhancedBenchmarkHandler(api_key="test-key")
        
        # Mock client response
        mock_response = {
            "choices": [{"message": {"content": "Test response for quantum computing analysis"}}],
            "usage": {
                "prompt_tokens": 15,
                "completion_tokens": 35,
                "total_tokens": 50
            }
        }
        
        handler.client.chat_completion = AsyncMock(return_value=mock_response)
        handler.model_cache.get_model_info = AsyncMock(return_value={
            "pricing": {"prompt": 0.03, "completion": 0.06}
        })
        
        # Test enhanced single model benchmark
        result = await handler.benchmark_model(
            model_id="openai/gpt-4",
            prompt="Explain quantum computing",
            temperature=0.7,
            max_tokens=100
        )
        
        # Verify enhanced metrics were calculated
        assert result.model_id == "openai/gpt-4"
        assert result.prompt_tokens == 15
        assert result.completion_tokens == 35
        assert result.quality_score is not None
        assert result.quality_score > 0
        assert result.throughput_tokens_per_second is not None
        assert result.response_length == len("Test response for quantum computing analysis")
        
        # Test cost calculation
        expected_cost = (15 * 0.03 + 35 * 0.06) / 1_000_000
        assert abs(result.cost - expected_cost) < 0.0001
        
        # Create comparison for testing export and analysis
        comparison = ModelComparison(
            prompt="Explain quantum computing",
            models=["openai/gpt-4", "anthropic/claude-3-opus"],
            results={
                "openai/gpt-4": [result],
                "anthropic/claude-3-opus": [result]  # Using same result for simplicity
            },
            timestamp=datetime.now(timezone.utc)
        )
        
        # Test export functionality
        exporter = BenchmarkReportExporter(handler)
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test all export formats
            csv_path = exporter.export_to_csv(comparison, os.path.join(temp_dir, "test.csv"))
            assert os.path.exists(csv_path)
            
            md_path = exporter.export_to_markdown(comparison, os.path.join(temp_dir, "test.md"))
            assert os.path.exists(md_path)
            
            json_path = exporter.export_to_json(comparison, os.path.join(temp_dir, "test.json"))
            assert os.path.exists(json_path)
        
        # Test performance analysis
        analyzer = ModelPerformanceAnalyzer(handler)
        metrics = comparison.get_metrics()
        
        analysis_result = analyzer.compare_models_weighted(
            metrics,
            {"speed": 0.3, "cost": 0.3, "quality": 0.4}
        )
        
        assert "overall_ranking" in analysis_result
        assert "detailed_scores" in analysis_result
        assert len(analysis_result["overall_ranking"]) == 2
    
    def test_quality_analyzer_comprehensive(self):
        """Test comprehensive quality analysis."""
        from src.openrouter_mcp.handlers.benchmark import ResponseQualityAnalyzer
        
        analyzer = ResponseQualityAnalyzer()
        
        # Test high-quality response
        high_quality_response = """
        Quantum computing is a revolutionary technology that leverages quantum mechanics principles.
        Unlike classical computers that use bits (0 or 1), quantum computers use quantum bits or qubits.
        These qubits can exist in superposition, allowing them to be both 0 and 1 simultaneously.
        This property enables quantum computers to process vast amounts of information in parallel.
        """
        
        analysis = analyzer.analyze_response("Explain quantum computing", high_quality_response.strip())
        
        assert analysis["quality_score"] > 0.7
        assert analysis["response_length"] > 200
        assert analysis["contains_code_example"] is False
        assert analysis["language_coherence_score"] > 0.6
        assert analysis["completeness_score"] > 0.7
        assert analysis["relevance_score"] > 0.8
        
        # Test code-containing response
        code_response = """
        Here's how to implement a simple quantum circuit:
        
        ```python
        from qiskit import QuantumCircuit, execute, Aer
        
        def create_bell_state():
            qc = QuantumCircuit(2, 2)
            qc.h(0)  # Hadamard gate
            qc.cx(0, 1)  # CNOT gate
            return qc
        ```
        
        This creates a Bell state, demonstrating quantum entanglement.
        """
        
        code_analysis = analyzer.analyze_response("Show me quantum code", code_response.strip())
        
        assert code_analysis["contains_code_example"] is True
        assert code_analysis["quality_score"] > 0.6


class TestBenchmarkMCPTool:
    """Test the MCP tool integration for benchmarking."""
    
    @pytest.mark.asyncio
    async def test_benchmark_models_tool_registration(self):
        """Test that benchmark_models_tool is properly registered."""
        from src.openrouter_mcp.handlers.benchmark import benchmark_models_tool
        
        # Check that the tool is registered (it will be a FunctionTool object)
        assert benchmark_models_tool is not None
        assert hasattr(benchmark_models_tool, 'name')
        assert benchmark_models_tool.name == 'benchmark_models_tool'
    
    @pytest.mark.asyncio
    async def test_get_benchmark_history_tool_registration(self):
        """Test that get_benchmark_history_tool is properly registered."""
        from src.openrouter_mcp.handlers.benchmark import get_benchmark_history_tool
        
        # Check that the tool is registered  
        assert get_benchmark_history_tool is not None
        assert hasattr(get_benchmark_history_tool, 'name')
        assert get_benchmark_history_tool.name == 'get_benchmark_history_tool'
    
    @pytest.mark.asyncio
    async def test_compare_model_categories_tool_registration(self):
        """Test that compare_model_categories_tool is properly registered."""
        from src.openrouter_mcp.handlers.benchmark import compare_model_categories_tool
        
        # Check that the tool is registered
        assert compare_model_categories_tool is not None
        assert hasattr(compare_model_categories_tool, 'name')
        assert compare_model_categories_tool.name == 'compare_model_categories_tool'