# Model Benchmarking Guide

Learn how to use the OpenRouter MCP Server's powerful benchmarking system to compare and analyze AI model performance.

## Table of Contents
- [Overview](#overview)
- [Key Features](#key-features)
- [Using MCP Tools](#using-mcp-tools)
- [Python API Usage](#python-api-usage)
- [Performance Metrics](#performance-metrics)
- [Report Formats](#report-formats)
- [Advanced Features](#advanced-features)
- [Optimization Tips](#optimization-tips)

## Overview

The OpenRouter MCP Server benchmarking system provides:

- 🏃‍♂️ **Multi-Model Performance Comparison**: Send identical prompts to multiple models for fair comparison
- 📊 **Detailed Metric Collection**: Response time, token usage, costs, quality scores
- 📈 **Intelligent Ranking**: Model ranking based on speed, cost, and quality
- 📋 **Multiple Report Formats**: Export results as Markdown, CSV, or JSON
- 🎯 **Category-Based Comparison**: Find the best models for chat, code, reasoning, etc.

## Key Features

### 1. Basic Benchmarking
```python
# Compare performance across multiple models
models = [
    "openai/gpt-4",
    "anthropic/claude-3-opus",
    "google/gemini-pro-1.5",
    "meta-llama/llama-3.1-8b-instruct"
]

results = await benchmark_models(
    models=models,
    prompt="Explain how to get started with machine learning in Python.",
    runs=3,
    delay_seconds=1.0
)
```

### 2. Category-Based Comparison
```python
# Compare top models by category
comparison = await compare_model_categories(
    categories=["chat", "code", "reasoning"],
    top_n=2,
    metric="overall"
)
```

### 3. Advanced Performance Analysis
```python
# Weight-based model comparison
analysis = await compare_model_performance(
    models=["openai/gpt-4", "anthropic/claude-3-opus"],
    weights={
        "speed": 0.2,
        "cost": 0.3,
        "quality": 0.4,
        "throughput": 0.1
    }
)
```

## Using MCP Tools

You can use these tools in Claude Desktop or other MCP clients:

### benchmark_models
Benchmark multiple models simultaneously.

**Parameters:**
- `models` (List[str]): List of model IDs to benchmark
- `prompt` (str): Test prompt (default: "Hello! Please introduce yourself briefly.")
- `runs` (int): Number of runs per model (default: 3)
- `delay_seconds` (float): Delay between API calls (default: 1.0)
- `save_results` (bool): Whether to save results to file (default: True)

**Example:**
```
Use benchmark_models to compare the performance of gpt-4 and claude-3-opus
```

### get_benchmark_history
Retrieve recent benchmark history.

**Parameters:**
- `limit` (int): Maximum number of results to return (default: 10)
- `days_back` (int): Number of days to look back (default: 30)
- `model_filter` (Optional[str]): Filter for specific models

**Example:**
```
Show me the last 10 benchmark results
```

### compare_model_categories
Compare top-performing models by category.

**Parameters:**
- `categories` (Optional[List[str]]): List of categories to compare
- `top_n` (int): Number of top models to select per category (default: 3)
- `metric` (str): Comparison metric (default: "overall")

**Example:**
```
Compare the best models in chat, code, and reasoning categories
```

### export_benchmark_report
Export benchmark results in various formats.

**Parameters:**
- `benchmark_file` (str): Benchmark result file to export
- `format` (str): Output format ("markdown", "csv", "json")
- `output_file` (Optional[str]): Output filename (default: auto-generated)

**Example:**
```
Export benchmark_20240112_143000.json as markdown format
```

### compare_model_performance
Perform advanced weight-based model performance comparison.

**Parameters:**
- `models` (List[str]): List of model IDs to compare
- `weights` (Optional[Dict[str, float]]): Weights for each metric
- `include_cost_analysis` (bool): Whether to include detailed cost analysis

**Example:**
```
Compare gpt-4 and claude-3-opus with weights: speed 20%, cost 30%, quality 50%
```

## Python API Usage

### Basic Usage

```python
import os
import asyncio
from src.openrouter_mcp.handlers.mcp_benchmark import get_benchmark_handler

async def run_benchmark():
    # Set API key
    os.environ["OPENROUTER_API_KEY"] = "your-api-key"
    
    # Get benchmark handler
    handler = await get_benchmark_handler()
    
    # Run model benchmarking
    results = await handler.benchmark_models(
        model_ids=["openai/gpt-3.5-turbo", "anthropic/claude-3-haiku"],
        prompt="Explain how to print Hello World in Python.",
        runs=2,
        delay_between_requests=0.5
    )
    
    print(f"Benchmark complete: {len(results)} models")
    for model_id, result in results.items():
        if result.success:
            print(f"- {model_id}: {result.metrics.avg_response_time_ms:.2f}ms, "
                  f"${result.metrics.avg_cost:.6f}")
        else:
            print(f"- {model_id}: Failed ({result.error_message})")

# Run
asyncio.run(run_benchmark())
```

### Advanced Usage

```python
async def advanced_benchmark():
    handler = await get_benchmark_handler()
    
    # 1. Select models by category
    cache = handler.model_cache
    models = await cache.get_models()
    
    # Select top 3 chat models
    chat_models = cache.filter_models_by_metadata(category="chat")
    top_chat_models = sorted(
        chat_models, 
        key=lambda x: x.get('quality_score', 0), 
        reverse=True
    )[:3]
    
    model_ids = [model['id'] for model in top_chat_models]
    
    # 2. Run benchmark
    results = await handler.benchmark_models(
        model_ids=model_ids,
        prompt="Explain a step-by-step approach to solving complex problems.",
        runs=3
    )
    
    # 3. Save results
    filename = f"advanced_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    await handler.save_results(results, filename)
    
    # 4. Export report
    from src.openrouter_mcp.handlers.mcp_benchmark import BenchmarkReportExporter
    
    exporter = BenchmarkReportExporter()
    await exporter.export_markdown(
        results, 
        f"reports/{filename.replace('.json', '_report.md')}"
    )
    
    print(f"Advanced benchmark complete: {filename}")

asyncio.run(advanced_benchmark())
```

## Performance Metrics

### Basic Metrics
- **Response Time**: Average, minimum, maximum response time (milliseconds)
- **Token Usage**: Prompt, completion, and total tokens
- **Cost**: Average, minimum, maximum cost (USD)
- **Success Rate**: Percentage of successful requests

### Advanced Metrics
- **Quality Score**: Combined evaluation of completeness, relevance, and language consistency (0-10)
- **Throughput**: Tokens processed per second (tokens/second)
- **Cost Efficiency**: Cost per quality point
- **Response Length**: Length of generated text
- **Code Inclusion**: Whether response includes code examples

### Score Calculation
- **Speed Score**: Normalized score based on response time (0-1)
- **Cost Score**: Normalized score based on cost efficiency (0-1)
- **Quality Score**: Normalized score based on response quality (0-1)
- **Throughput Score**: Normalized score based on throughput (0-1)

## Report Formats

### 1. Markdown Report
Summarizes results in a readable format.

```markdown
# Benchmark Comparison Report

**Execution Time**: 2024-01-12T14:30:00Z
**Prompt**: "Write a Python machine learning getting started guide."
**Test Models**: gpt-4, claude-3-opus, gemini-pro

## Performance Metrics

| Model | Avg Response Time | Avg Cost | Quality Score | Success Rate |
|------|---------------|-----------|-----------|--------|
| gpt-4 | 2.34s | $0.001230 | 9.2 | 100% |
| claude-3-opus | 1.89s | $0.000980 | 9.1 | 100% |
| gemini-pro | 1.23s | $0.000456 | 8.7 | 100% |

## Overall Ranking

1. **gpt-4**: Overall Score 8.9
2. **claude-3-opus**: Overall Score 8.7
3. **gemini-pro**: Overall Score 8.1
```

### 2. CSV Report
Ideal format for spreadsheet analysis.

```csv
model_id,avg_response_time_ms,avg_cost,quality_score,success_rate,throughput
gpt-4,2340,0.001230,9.2,1.0,98.5
claude-3-opus,1890,0.000980,9.1,1.0,112.3
gemini-pro,1230,0.000456,8.7,1.0,145.2
```

### 3. JSON Report
Ideal format for programmatic processing.

```json
{
  "timestamp": "2024-01-12T14:30:00Z",
  "config": {
    "models": ["gpt-4", "claude-3-opus", "gemini-pro"],
    "prompt": "Write a Python machine learning getting started guide.",
    "runs": 3
  },
  "results": {
    "gpt-4": {
      "success": true,
      "metrics": {
        "avg_response_time_ms": 2340,
        "avg_cost": 0.001230,
        "quality_score": 9.2
      }
    }
  },
  "ranking": [
    {
      "rank": 1,
      "model_id": "gpt-4",
      "overall_score": 8.9
    }
  ]
}
```

## Advanced Features

### 1. Weight-Based Comparison
Compare models based on different priorities:

```python
# Speed-focused comparison
speed_focused = {
    "speed": 0.6,
    "cost": 0.2,
    "quality": 0.2
}

# Quality-focused comparison
quality_focused = {
    "speed": 0.1,
    "cost": 0.2,
    "quality": 0.7
}

# Balanced comparison
balanced = {
    "speed": 0.25,
    "cost": 0.25,
    "quality": 0.25,
    "throughput": 0.25
}
```

### 2. Category-Specific Prompts
Use optimized prompts for each category:

- **Chat**: Conversational questions
- **Code**: Programming problems and solutions
- **Reasoning**: Logic-based problems
- **Multimodal**: Image analysis questions
- **Image**: Image generation questions

### 3. Performance Analysis
- **Cost Efficiency Analysis**: Find cost-optimized models for quality
- **Performance Distribution Analysis**: Statistical distribution of response time, quality, throughput
- **Recommendation System**: Optimal model recommendations by use case

## Optimization Tips

### 1. API Call Optimization
```python
# Set appropriate delay time (prevent rate limiting)
delay_seconds = 1.0  # Suitable for most cases

# Limit concurrent execution for parallel processing
max_concurrent = 3  # Too high risks rate limiting

# Set timeout
timeout = 60.0  # Time to wait for long responses
```

### 2. Memory Management
```python
# Batch processing for large benchmarks
batch_size = 5
for i in range(0, len(models), batch_size):
    batch = models[i:i+batch_size]
    results = await benchmark_models(batch, prompt)
    # Save intermediate results
    await save_batch_results(results, i)
```

### 3. Result Caching
```python
# Caching for result reuse
cache_key = f"{model_id}_{hash(prompt)}_{runs}"
if cache_key in benchmark_cache:
    return benchmark_cache[cache_key]

result = await benchmark_model(model_id, prompt)
benchmark_cache[cache_key] = result
return result
```

### 4. Error Handling
```python
# Robust error handling
try:
    result = await benchmark_model(model_id, prompt)
except asyncio.TimeoutError:
    logger.warning(f"Timeout for {model_id}")
    result = create_timeout_result(model_id)
except Exception as e:
    logger.error(f"Error benchmarking {model_id}: {e}")
    result = create_error_result(model_id, str(e))
```

## Use Case Examples

### 1. Finding the Best Performing Model
```python
# Find the best performing model from all models
all_models = await cache.get_models()
model_ids = [m['id'] for m in all_models[:10]]  # Top 10

results = await benchmark_models(
    models=model_ids,
    prompt="Solve a complex data analysis problem.",
    runs=3
)

# Sort by overall score
best_model = max(results.items(), 
                key=lambda x: x[1].metrics.overall_score if x[1].success else 0)
print(f"Best performing model: {best_model[0]}")
```

### 2. Finding Cost-Efficient Models
```python
# Find models with good performance-to-cost ratio
cost_efficient = await compare_model_performance(
    models=budget_models,
    weights={"cost": 0.5, "quality": 0.4, "speed": 0.1}
)

print("Cost efficiency ranking:")
for rank in cost_efficient["ranking"]:
    print(f"{rank['rank']}. {rank['model_id']}: {rank['overall_score']:.2f}")
```

### 3. Finding Category Specialist Models
```python
# Compare specialist models in each category
specialist_comparison = await compare_model_categories(
    categories=["chat", "code", "reasoning", "multimodal"],
    top_n=2,
    metric="quality"
)

for category, models in specialist_comparison["results"].items():
    print(f"\n{category.upper()} Specialists:")
    for model in models:
        print(f"  - {model['model_id']}: {model['metrics']['quality_score']:.1f}")
```

### 4. Regular Performance Monitoring
```python
# Track regular performance of key models
async def monitor_model_performance():
    key_models = ["openai/gpt-4", "anthropic/claude-3-opus", "google/gemini-pro"]
    
    results = await benchmark_models(
        models=key_models,
        prompt="Explain the current state and future prospects of AI technology.",
        runs=2
    )
    
    # Save as time-series data for trend analysis
    timestamp = datetime.now().isoformat()
    performance_log = {
        "timestamp": timestamp,
        "results": {
            model_id: {
                "response_time": result.metrics.avg_response_time_ms,
                "cost": result.metrics.avg_cost,
                "quality": result.metrics.quality_score
            }
            for model_id, result in results.items()
            if result.success
        }
    }
    
    # Save log
    with open(f"performance_log_{datetime.now().strftime('%Y%m')}.json", "a") as f:
        f.write(json.dumps(performance_log) + "\n")

# Scheduling (e.g., run daily)
import schedule
schedule.every().day.at("09:00").do(lambda: asyncio.run(monitor_model_performance()))
```

Use this guide to fully leverage the powerful benchmarking features of the OpenRouter MCP Server!

## Related Documentation

- [Installation Guide](INSTALLATION.md) - Set up the OpenRouter MCP Server
- [API Reference](API.md) - Complete API documentation
- [Model Metadata Guide](METADATA_GUIDE.md) - Understanding model categorization
- [Troubleshooting](TROUBLESHOOTING.md) - Common benchmarking issues
- [Architecture Overview](ARCHITECTURE.md) - System design details

For a complete documentation overview, see the [Documentation Index](INDEX.md).

---

**Last Updated**: 2025-01-12
**Version**: 1.4.0