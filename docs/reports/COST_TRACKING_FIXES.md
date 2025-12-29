# Cost Tracking Fixes - Summary

## Problem Statement

The collective intelligence system had critical cost tracking issues that made quota limits completely ineffective:

### Issues Identified

1. **Hard-coded token estimates** in `consensus_engine.py` (lines 158-159, 283-285):
   - Used `len(task.content)` as token count (character count, not actual tokens)
   - Set `cost=0.0` for all requests
   - Made QuotaTracker useless - requests never got throttled

2. **Inaccurate cost estimation** in `collective_intelligence.py` (lines 172-176):
   - `_estimate_cost` hard-coded $0.00002 per token for all models
   - Didn't fetch real pricing from OpenRouter API or ModelCache
   - Could cause 10x-100x cost estimation errors

3. **No actual token counting**:
   - Character-based estimation is inaccurate (typically off by 4x)
   - Different models use different tokenizers

## Solution Implemented

### 1. Token Counting Utility (`src/openrouter_mcp/utils/token_counter.py`)

Created a comprehensive token counting system using `tiktoken`:

```python
class TokenCounter:
    """Token counter for accurate cost estimation using tiktoken."""

    def count_tokens(self, text: str, model_id: str) -> int:
        """Count tokens accurately using model-specific encoding."""

    def count_message_tokens(self, messages: List[Dict], model_id: str) -> int:
        """Count tokens in chat messages including formatting overhead."""
```

**Features:**
- Uses tiktoken for accurate token counting
- Model-family aware encoding selection (GPT-4, Claude, Gemini, etc.)
- Handles message formatting overhead correctly
- Encoding cache for performance
- Fallback to character-based estimation if tiktoken fails

### 2. Real Cost Estimation (`src/openrouter_mcp/handlers/collective_intelligence.py`)

Updated `OpenRouterModelProvider` to fetch real model pricing:

```python
async def _get_model_pricing(self, model_id: str) -> Dict[str, float]:
    """Fetch actual pricing from ModelCache with local caching."""

async def _estimate_cost(self, model_id: str, usage: Dict[str, int]) -> float:
    """Calculate cost using real pricing: prompt_tokens * prompt_cost + completion_tokens * completion_cost."""
```

**Features:**
- Fetches pricing from ModelCache (which gets it from OpenRouter API)
- Caches pricing per-model to avoid repeated lookups
- Uses actual prompt/completion token breakdown
- Falls back to conservative defaults if pricing unavailable
- Detailed debug logging for cost calculations

### 3. Consensus Engine Fixes (`src/openrouter_mcp/collective_intelligence/consensus_engine.py`)

Fixed both hardcoded locations:

**Initial quota check (lines 156-175):**
```python
# OLD: tokens=len(task.content) * len(models), cost=0.0
# NEW:
estimated_tokens = count_tokens(task.content, model_id=models[0])
total_estimated_tokens = estimated_tokens * len(models)
estimated_cost = total_estimated_tokens * estimated_cost_per_token
```

**Per-model quota check (lines 293-341):**
```python
# OLD: tokens=len(task.content), cost=0.0
# NEW:
estimated_tokens = count_tokens(task.content, model_id=model_id)
estimated_cost = estimated_tokens * estimated_cost_per_token

# After API response:
actual_token_diff = result.tokens_used - estimated_tokens
actual_cost_diff = result.cost - estimated_cost
# Update quota with actual values
```

**Features:**
- Uses tiktoken for accurate token estimation
- Updates quota tracker with actual costs from API responses
- Properly handles per-model and per-request limits
- Conservative estimation prevents quota overruns

### 4. ProcessingResult Updates

Verified that `ProcessingResult` already contains:
- `tokens_used: int` - Actual tokens from API response
- `cost: float` - Actual cost calculated from real pricing

The `OpenRouterModelProvider.process_task()` now populates these with accurate values.

## Testing

Created comprehensive test suite (`tests/test_cost_tracking.py`):

- **Token Counting Tests**: Verify tiktoken integration works correctly
- **Cost Estimation Tests**: Verify real pricing is fetched and used
- **Consensus Engine Tests**: Verify quota tracking uses real values
- **Integration Tests**: Verify end-to-end flow

**Results:** All 13 tests passing ✓

```bash
$ pytest tests/test_cost_tracking.py -v
============================= 13 passed in 0.84s ==============================
```

## Dependencies

Added `tiktoken>=0.5.0` to `requirements.txt` for accurate token counting.

## Impact

### Before:
- ❌ All requests showed 0 cost
- ❌ Token estimates off by 4x (character count)
- ❌ Quota limits completely ineffective
- ❌ Could not prevent runaway costs

### After:
- ✅ Accurate token counting using tiktoken
- ✅ Real model pricing from OpenRouter API
- ✅ Quota tracker receives accurate values
- ✅ Per-model and per-request limits enforced
- ✅ Prevents runaway costs effectively

## Files Modified

1. `src/openrouter_mcp/utils/token_counter.py` - **NEW**
   - Token counting utility using tiktoken

2. `src/openrouter_mcp/handlers/collective_intelligence.py`
   - Added `_get_model_pricing()` to fetch real pricing
   - Updated `_estimate_cost()` to use prompt/completion breakdown
   - Updated `process_task()` to calculate actual costs

3. `src/openrouter_mcp/collective_intelligence/consensus_engine.py`
   - Fixed initial quota check (line 156-175)
   - Fixed per-model quota check (line 293-341)
   - Added actual cost tracking from API responses

4. `requirements.txt`
   - Added `tiktoken>=0.5.0`

5. `tests/test_cost_tracking.py` - **NEW**
   - Comprehensive test suite

## Usage Example

```python
from openrouter_mcp.utils.token_counter import count_tokens

# Accurate token counting
prompt = "What is the capital of France?"
tokens = count_tokens(prompt, model_id="openai/gpt-4")
# Returns ~7 tokens (not 31 characters!)

# Cost calculation now uses real pricing
usage = {
    "prompt_tokens": 100,
    "completion_tokens": 50
}
# GPT-4: 100 * $0.00003 + 50 * $0.00006 = $0.006
# Claude: 100 * $0.00008 + 50 * $0.00024 = $0.020
```

## Verification

To verify the fixes work:

```bash
# Run tests
pytest tests/test_cost_tracking.py -v

# Check token counting
python -c "from src.openrouter_mcp.utils.token_counter import count_tokens; print(count_tokens('Hello world'))"

# Check consensus engine logging
# Should see lines like:
# "Estimated 15 tokens for request (not 46 characters)"
# "Cost calculation for openai/gpt-4: 100 prompt tokens ($0.003) + 50 completion tokens ($0.003) = $0.006"
# "Updated quota for model1: token_diff=10, cost_diff=$0.000150"
```

## Future Improvements

1. **Model-specific pricing cache refresh**: Currently caches pricing indefinitely per session
2. **Token estimation for images**: Currently doesn't estimate vision tokens
3. **Streaming token tracking**: Need to track costs for streaming responses
4. **Cost alerts**: Add proactive warnings when approaching quota limits

## Security Notes

- Token counting happens client-side, no sensitive data sent to external services
- Pricing data fetched from OpenRouter API (already trusted source)
- Fallback pricing is conservative to prevent under-estimation

## Migration Guide

No breaking changes - existing code continues to work but with accurate cost tracking.

To take advantage of improvements:

1. Install/upgrade: `pip install -r requirements.txt`
2. Restart MCP server
3. Monitor logs for accurate cost tracking messages
4. Adjust quota limits if needed based on accurate costs
