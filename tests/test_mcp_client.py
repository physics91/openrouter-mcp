#!/usr/bin/env python3
"""
MCP Client test for Collective Intelligence tools.

This script connects to the running MCP server and tests the 5 collective
intelligence tools through the MCP protocol.
"""

import asyncio
import json
import websockets
import time
from typing import Dict, Any, Optional


class MCPClient:
    """Simple MCP client for testing tools."""
    
    def __init__(self, uri: str = "ws://localhost:8001"):
        self.uri = uri
        self.websocket = None
        self.request_id = 0
    
    async def connect(self):
        """Connect to MCP server."""
        print(f"[CLIENT] Connecting to MCP server at {self.uri}")
        self.websocket = await websockets.connect(self.uri)
        print("[CLIENT] Connected successfully")
    
    async def disconnect(self):
        """Disconnect from MCP server."""
        if self.websocket:
            await self.websocket.close()
            print("[CLIENT] Disconnected")
    
    async def send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send MCP request and get response."""
        if not self.websocket:
            raise RuntimeError("Not connected to server")
        
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        
        print(f"[CLIENT] Sending: {method}")
        await self.websocket.send(json.dumps(request))
        
        response_str = await self.websocket.recv()
        response = json.loads(response_str)
        
        if "error" in response:
            raise Exception(f"MCP Error: {response['error']}")
        
        return response.get("result", {})
    
    async def list_tools(self) -> Dict[str, Any]:
        """List available tools."""
        return await self.send_request("tools/list")
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a specific tool."""
        return await self.send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })


async def test_collective_intelligence_tools():
    """Test all 5 collective intelligence tools through MCP."""
    client = MCPClient()
    
    try:
        await client.connect()
        
        # List available tools
        print("\n[TEST] Listing available tools...")
        tools_result = await client.list_tools()
        tools = tools_result.get("tools", [])
        
        collective_tools = [
            "collective_chat_completion",
            "ensemble_reasoning", 
            "adaptive_model_selection",
            "cross_model_validation",
            "collaborative_problem_solving"
        ]
        
        available_collective_tools = [
            tool["name"] for tool in tools 
            if tool["name"] in collective_tools
        ]
        
        print(f"[SUCCESS] Found {len(available_collective_tools)} collective intelligence tools:")
        for tool_name in available_collective_tools:
            print(f"  - {tool_name}")
        
        # Test 1: Collective Chat Completion
        if "collective_chat_completion" in available_collective_tools:
            print("\n[TEST] Testing Collective Chat Completion...")
            try:
                start_time = time.time()
                result = await client.call_tool("collective_chat_completion", {
                    "prompt": "What are the main benefits of renewable energy?",
                    "strategy": "majority_vote",
                    "min_models": 2,
                    "max_models": 3,
                    "temperature": 0.7
                })
                end_time = time.time()
                
                print(f"[SUCCESS] Collective Chat completed in {end_time - start_time:.2f}s")
                if "content" in result:
                    content = result["content"]
                    if isinstance(content, list) and len(content) > 0:
                        response_data = content[0].get("text", "")
                        if response_data:
                            # Try to parse JSON response
                            try:
                                parsed = json.loads(response_data)
                                print(f"[INFO] Consensus: {parsed.get('consensus_response', 'N/A')[:100]}...")
                                print(f"[INFO] Agreement: {parsed.get('agreement_level', 'N/A')}")
                                print(f"[INFO] Models: {len(parsed.get('participating_models', []))}")
                            except json.JSONDecodeError:
                                print(f"[INFO] Response: {response_data[:200]}...")
                        
            except Exception as e:
                print(f"[ERROR] Collective Chat failed: {str(e)}")
        
        # Test 2: Ensemble Reasoning
        if "ensemble_reasoning" in available_collective_tools:
            print("\n[TEST] Testing Ensemble Reasoning...")
            try:
                start_time = time.time()
                result = await client.call_tool("ensemble_reasoning", {
                    "problem": "Analyze the impact of remote work on productivity",
                    "task_type": "analysis",
                    "decompose": True,
                    "temperature": 0.7
                })
                end_time = time.time()
                
                print(f"[SUCCESS] Ensemble Reasoning completed in {end_time - start_time:.2f}s")
                if "content" in result:
                    content = result["content"]
                    if isinstance(content, list) and len(content) > 0:
                        response_data = content[0].get("text", "")
                        if response_data:
                            try:
                                parsed = json.loads(response_data)
                                print(f"[INFO] Final Result: {parsed.get('final_result', 'N/A')[:100]}...")
                                print(f"[INFO] Subtasks: {len(parsed.get('subtask_results', []))}")
                            except json.JSONDecodeError:
                                print(f"[INFO] Response: {response_data[:200]}...")
                        
            except Exception as e:
                print(f"[ERROR] Ensemble Reasoning failed: {str(e)}")
        
        # Test 3: Adaptive Model Selection
        if "adaptive_model_selection" in available_collective_tools:
            print("\n[TEST] Testing Adaptive Model Selection...")
            try:
                start_time = time.time()
                result = await client.call_tool("adaptive_model_selection", {
                    "query": "Write a Python function for binary search",
                    "task_type": "code_generation",
                    "performance_requirements": {"accuracy": 0.9, "speed": 0.8}
                })
                end_time = time.time()
                
                print(f"[SUCCESS] Adaptive Model Selection completed in {end_time - start_time:.2f}s")
                if "content" in result:
                    content = result["content"]
                    if isinstance(content, list) and len(content) > 0:
                        response_data = content[0].get("text", "")
                        if response_data:
                            try:
                                parsed = json.loads(response_data)
                                print(f"[INFO] Selected Model: {parsed.get('selected_model', 'N/A')}")
                                print(f"[INFO] Confidence: {parsed.get('confidence', 'N/A')}")
                            except json.JSONDecodeError:
                                print(f"[INFO] Response: {response_data[:200]}...")
                        
            except Exception as e:
                print(f"[ERROR] Adaptive Model Selection failed: {str(e)}")
        
        # Test 4: Cross-Model Validation
        if "cross_model_validation" in available_collective_tools:
            print("\n[TEST] Testing Cross-Model Validation...")
            try:
                start_time = time.time()
                result = await client.call_tool("cross_model_validation", {
                    "content": "Python is a programming language known for simplicity",
                    "validation_criteria": ["factual_accuracy", "technical_correctness"],
                    "threshold": 0.7
                })
                end_time = time.time()
                
                print(f"[SUCCESS] Cross-Model Validation completed in {end_time - start_time:.2f}s")
                if "content" in result:
                    content = result["content"]
                    if isinstance(content, list) and len(content) > 0:
                        response_data = content[0].get("text", "")
                        if response_data:
                            try:
                                parsed = json.loads(response_data)
                                print(f"[INFO] Validation Result: {parsed.get('validation_result', 'N/A')}")
                                print(f"[INFO] Score: {parsed.get('validation_score', 'N/A')}")
                            except json.JSONDecodeError:
                                print(f"[INFO] Response: {response_data[:200]}...")
                        
            except Exception as e:
                print(f"[ERROR] Cross-Model Validation failed: {str(e)}")
        
        # Test 5: Collaborative Problem Solving
        if "collaborative_problem_solving" in available_collective_tools:
            print("\n[TEST] Testing Collaborative Problem Solving...")
            try:
                start_time = time.time()
                result = await client.call_tool("collaborative_problem_solving", {
                    "problem": "Design a simple recycling program for an office",
                    "requirements": {"budget": "low", "participation": "voluntary"},
                    "max_iterations": 2
                })
                end_time = time.time()
                
                print(f"[SUCCESS] Collaborative Problem Solving completed in {end_time - start_time:.2f}s")
                if "content" in result:
                    content = result["content"]
                    if isinstance(content, list) and len(content) > 0:
                        response_data = content[0].get("text", "")
                        if response_data:
                            try:
                                parsed = json.loads(response_data)
                                print(f"[INFO] Final Solution: {parsed.get('final_solution', 'N/A')[:100]}...")
                                print(f"[INFO] Strategy: {parsed.get('strategy_used', 'N/A')}")
                            except json.JSONDecodeError:
                                print(f"[INFO] Response: {response_data[:200]}...")
                        
            except Exception as e:
                print(f"[ERROR] Collaborative Problem Solving failed: {str(e)}")
        
        print(f"\n[SUCCESS] All available tools tested: {len(available_collective_tools)}/5")
        
    except Exception as e:
        print(f"[ERROR] Test failed: {str(e)}")
    
    finally:
        await client.disconnect()


async def main():
    """Main test function."""
    print("[AI] Collective Intelligence MCP Client Test")
    print("=" * 50)
    
    try:
        await test_collective_intelligence_tools()
    except Exception as e:
        print(f"[ERROR] Main test failed: {str(e)}")
    
    print("\n[SUCCESS] MCP Client test completed!")


if __name__ == "__main__":
    asyncio.run(main())