"""
OpenRouter API Client Wrapper
Provides OpenAI-compatible interface for accessing various AI models through OpenRouter.
"""
import os
import json
import asyncio
from typing import Optional, List, Dict, Any, AsyncGenerator, Union
from dotenv import load_dotenv

load_dotenv()

# OpenRouter uses OpenAI-compatible API
try:
    from openai import AsyncOpenAI
except ImportError:
    raise ImportError("Please install openai: pip install openai")


class OpenRouterClient:
    """
    A wrapper client for OpenRouter API that provides streaming chat completions
    and tool/function calling support with auto-updating free models and fallbacks.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model or os.getenv("OPENROUTER_MODEL", "openrouter/free")
        
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found. Set it in .env or pass it directly.")
        
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            default_headers={
                "HTTP-Referer": "http://localhost:3000",  # Required by OpenRouter
                "X-Title": "Smarty V2"  # Optional, shows in OpenRouter dashboard
            }
        )
        
        # 1. Fetch and update the list of free models dynamically
        self._fetch_and_update_free_models()
        
        # 2. Startup validation check:
        # If the requested model is a free model but is no longer listed as active on OpenRouter,
        # proactively auto-update it to the best available free model.
        if self.model.endswith(":free") and self.model not in self.free_models:
            new_model = self._get_fallback_model(self.model)
            print(f"[OpenRouter] Proactively auto-updating model from '{self.model}' to '{new_model}' (failed model is not active on OpenRouter)")
            self.model = new_model
        
        print(f"[OpenRouter] Initialized with model: {self.model}")

    def _fetch_and_update_free_models(self) -> List[str]:
        """Fetch the list of current free models from OpenRouter API dynamically."""
        import urllib.request
        import json
        
        json_path = os.path.join(os.path.dirname(__file__), "free_models.json")
        
        # Default fallback list in case network request fails
        fallback_list = [
            "z-ai/glm-4.5-air:free",
            "google/gemma-4-26b-a4b-it:free",
            "google/gemma-4-31b-it:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "deepseek/deepseek-v4-flash:free",
            "qwen/qwen3-coder:free",
            "meta-llama/llama-3.2-3b-instruct:free",
            "openrouter/free"
        ]
        
        # Load existing cached models if available
        existing_list = []
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    existing_list = json.load(f)
            except Exception:
                pass
                
        self.free_models = existing_list or fallback_list
        
        try:
            print("[OpenRouter] Fetching current free models list dynamically...")
            url = "https://openrouter.ai/api/v1/models"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "Smarty V2"
                }
            )
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode())
                models = data.get("data", [])
                fetched_free = []
                for m in models:
                    model_id = m.get("id", "")
                    pricing = m.get("pricing", {})
                    prompt_price = float(pricing.get("prompt", 0))
                    completion_price = float(pricing.get("completion", 0))
                    if model_id.endswith(":free") or (prompt_price == 0 and completion_price == 0):
                        fetched_free.append(model_id)
                
                if fetched_free:
                    self.free_models = fetched_free
                    # Save to json file
                    try:
                        with open(json_path, "w", encoding="utf-8") as f:
                            json.dump(fetched_free, f)
                        print(f"[OpenRouter] Successfully updated free_models.json with {len(fetched_free)} models.")
                    except Exception as e:
                        print(f"[OpenRouter] Failed to write free_models.json: {e}")
        except Exception as e:
            print(f"[OpenRouter] Could not fetch live models list, using cached list. Error: {e}")
            
        return self.free_models

    def _get_fallback_model(self, failed_models: Union[str, List[str]]) -> str:
        """Find the best fallback model from the active free models list."""
        if isinstance(failed_models, str):
            failed_list = [failed_models]
        else:
            failed_list = failed_models
            
        # Preferred models ranked by tool compatibility and quality
        preferred_ranking = [
            "openrouter/free",
            "google/gemma-4-31b-it:free",
            "google/gemma-4-26b-a4b-it:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "nvidia/nemotron-3.5-super-vl:free",
            "nvidia/nemotron-3.5-lightning:free",
            "deepseek/deepseek-v4-flash:free",
            "qwen/qwen3-coder:free",
            "meta-llama/llama-3.2-3b-instruct:free",
            "nousresearch/hermes-3-llama-3.1-405b:free"
        ]
        
        # Filter out all previously failed models
        candidates = [m for m in self.free_models if m not in failed_list]
        
        # Try to find the highest ranked preferred model in the candidates
        for pref in preferred_ranking:
            if pref in candidates:
                return pref
                
        # If none of our preferred models are available, return the first available candidate
        if candidates:
            return candidates[0]
            
        return "openrouter/free"
    
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.6,
        max_tokens: int = 4096,
        stream: bool = False
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """
        Send a chat completion request to OpenRouter.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            system_instruction: Optional system prompt to prepend
            tools: Optional list of tool definitions in OpenAI format
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response
            stream: Whether to stream the response
            
        Returns:
            Response dict with 'content', 'tool_calls', and 'usage'
        """
        # Prepare messages with system instruction
        all_messages = []
        if system_instruction:
            all_messages.append({"role": "system", "content": system_instruction})
        all_messages.extend(messages)
        
        # Prepare request kwargs
        kwargs = {
            "model": self.model,
            "messages": all_messages,
            "temperature": temperature,
            "top_p": 0.7,
            "max_tokens": max_tokens,
            "stream": stream,
            "timeout": 15.0
        }
        
        # Add tools if provided
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        import re
        max_attempts = 8
        last_error = None
        failed_models = []
        ignored_providers = []
        
        for attempt in range(max_attempts):
            try:
                # Add ignored providers to request body
                if ignored_providers:
                    kwargs["extra_body"] = {
                        "provider": {
                            "ignore": list(set(ignored_providers))
                        }
                    }
                else:
                    kwargs.pop("extra_body", None)

                if stream:
                    return self._stream_chat(**kwargs)
                else:
                    response = await self.client.chat.completions.create(**kwargs)
                    return self._parse_response(response)
            except Exception as e:
                last_error = e
                error_str = str(e)
                error_lower = error_str.lower()
                
                is_recoverable = False
                if hasattr(e, "status_code") and e.status_code in (400, 404, 408, 429, 500, 502, 503, 504):
                    is_recoverable = True
                elif any(phrase in error_lower for phrase in [
                    "404", "400", "429", "500", "503", "not found", "no endpoints",
                    "rate limit", "rate-limit", "quota", "exhausted", "provider returned error",
                    "unsupported", "multimodal", "image_url", "image input", "temporarily rate-limited",
                    "upstream", "rate_limit", "bad request"
                ]):
                    is_recoverable = True
                
                if is_recoverable and (self.model.endswith(":free") or self.model == "openrouter/free"):
                    # Detect if a specific provider rate limited us
                    if "429" in error_str or "rate limit" in error_lower or "rate-limit" in error_lower or "temporarily rate-limited" in error_lower:
                        match_prov = re.search(r"'provider_name':\s*'([^']+)'", error_str)
                        if match_prov:
                            prov = match_prov.group(1)
                            ignored_providers.append(prov)
                            print(f"[OpenRouter] Provider '{prov}' rate limited us. Adding to ignore list.")
                        elif "venice" in error_lower:
                            ignored_providers.append("Venice")
                            print(f"[OpenRouter] Venice rate limited us. Adding to ignore list.")
                        
                        # Determine sleep time (exponential or from header)
                        sleep_time = 2.0
                        try:
                            match_secs = re.search(r"'retry_after_seconds':\s*([0-9.]+)", error_str)
                            if match_secs:
                                sleep_time = float(match_secs.group(1))
                            else:
                                match_secs_raw = re.search(r"retry_after_seconds_raw':\s*([0-9.]+)", error_str)
                                if match_secs_raw:
                                    sleep_time = float(match_secs_raw.group(1))
                        except Exception:
                            pass
                        # Clamp sleep time between 1 and 5 seconds to prevent freezing
                        sleep_time = max(1.0, min(sleep_time, 5.0))
                        print(f"[OpenRouter] Rate limited (429). Sleeping for {sleep_time:.2f} seconds before retrying...")
                        await asyncio.sleep(sleep_time)

                    failed_model = self.model
                    match = re.search(r'([\w\-]+/[\w\-]+:free)', error_str)
                    if match:
                        failed_model = match.group(1)
                    
                    failed_models.append(failed_model)
                    failed_models.append(self.model)
                    
                    new_model = self._get_fallback_model(failed_models)
                    if new_model == self.model and failed_model == self.model:
                        print(f"[OpenRouter] Request failed on '{self.model}' with no further fallbacks.")
                        break
                    
                    print(f"[OpenRouter] Attempt {attempt + 1} failed for '{self.model}'. Error: {error_str[:150]}. Auto-switching to fallback: '{new_model}'")
                    self.model = new_model
                    kwargs["model"] = new_model
                    ignored_providers = []  # Reset ignored providers for the new model
                else:
                    print(f"[OpenRouter] Non-recoverable error or not a free model: {e}")
                    raise e
        
        if last_error:
            raise last_error
    
    async def _stream_chat(self, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream chat completion responses."""
        stream = await self.client.chat.completions.create(**kwargs)
        
        full_content = ""
        tool_calls = []
        current_tool_call = None
        
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            
            if delta:
                # Handle content streaming
                text_chunk = delta.content or ""
                
                # Reasoning models may put content in non-standard fields
                if not text_chunk:
                    try:
                        delta_dict = delta.model_dump()
                        text_chunk = delta_dict.get("reasoning", "") or ""
                    except Exception:
                        pass
                
                if text_chunk:
                    full_content += text_chunk
                    yield {"type": "content", "content": text_chunk}
                
                # Handle tool calls streaming
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        if tc.index is not None:
                            # New or continuing tool call
                            while len(tool_calls) <= tc.index:
                                tool_calls.append({
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""}
                                })
                            
                            if tc.id:
                                tool_calls[tc.index]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    tool_calls[tc.index]["function"]["name"] = tc.function.name
                                if tc.function.arguments:
                                    tool_calls[tc.index]["function"]["arguments"] += tc.function.arguments
            
            # Check for finish reason
            if chunk.choices and chunk.choices[0].finish_reason:
                if tool_calls:
                    # Parse tool call arguments
                    for tc in tool_calls:
                        try:
                            args = tc["function"]["arguments"]
                            if isinstance(args, str):
                                tc["function"]["arguments"] = json.loads(args)
                        except (json.JSONDecodeError, TypeError):
                            pass
                    yield {"type": "tool_calls", "tool_calls": tool_calls}
                
                yield {"type": "done", "content": full_content, "tool_calls": tool_calls}
    
    def _parse_response(self, response) -> Dict[str, Any]:
        """Parse a non-streaming response. Handles reasoning models too."""
        choice = response.choices[0] if response.choices else None
        
        result = {
            "content": "",
            "tool_calls": [],
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0
            }
        }
        
        if choice:
            content = choice.message.content or ""
            
            if not content:
                try:
                    msg_dict = choice.message.model_dump()
                    reasoning = msg_dict.get("reasoning")
                    if reasoning and isinstance(reasoning, str):
                        content = reasoning.strip()
                    
                    if not content:
                        details = msg_dict.get("reasoning_details", [])
                        if details and isinstance(details, list):
                            parts = []
                            for d in details:
                                if isinstance(d, dict) and d.get("content"):
                                    parts.append(d["content"])
                            if parts:
                                content = "\n".join(parts).strip()
                except Exception:
                    pass
            
            result["content"] = content
            
            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    raw_args = tc.function.arguments
                    if isinstance(raw_args, str):
                        try:
                            parsed_args = json.loads(raw_args)
                        except (json.JSONDecodeError, TypeError):
                            parsed_args = raw_args
                    else:
                        parsed_args = raw_args
                    
                    tool_call = {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": parsed_args
                        }
                    }
                    result["tool_calls"].append(tool_call)
        
        return result
    
    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.6,
        max_tokens: int = 4096
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream a chat completion response.
        
        Yields dicts with:
        - {"type": "content", "content": "..."}  for text chunks
        - {"type": "tool_calls", "tool_calls": [...]}  for tool calls
        - {"type": "done", "content": "...", "tool_calls": [...]}  when complete
        """
        all_messages = []
        if system_instruction:
            all_messages.append({"role": "system", "content": system_instruction})
        all_messages.extend(messages)
        
        kwargs = {
            "model": self.model,
            "messages": all_messages,
            "temperature": temperature,
            "top_p": 0.7,
            "max_tokens": max_tokens,
            "stream": True,
            "timeout": 15.0
        }
        
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        import re
        max_attempts = 8
        last_error = None
        failed_models = []
        ignored_providers = []
        
        for attempt in range(max_attempts):
            try:
                # Add ignored providers to request body
                if ignored_providers:
                    kwargs["extra_body"] = {
                        "provider": {
                            "ignore": list(set(ignored_providers))
                        }
                    }
                else:
                    kwargs.pop("extra_body", None)

                async for chunk in self._stream_chat(**kwargs):
                    yield chunk
                return
            except Exception as e:
                last_error = e
                error_str = str(e)
                error_lower = error_str.lower()
                
                is_recoverable = False
                if hasattr(e, "status_code") and e.status_code in (400, 404, 408, 429, 500, 502, 503, 504):
                    is_recoverable = True
                elif any(phrase in error_lower for phrase in [
                    "404", "400", "429", "500", "503", "not found", "no endpoints",
                    "rate limit", "rate-limit", "quota", "exhausted", "provider returned error",
                    "unsupported", "multimodal", "image_url", "image input", "temporarily rate-limited",
                    "upstream", "rate_limit", "bad request"
                ]):
                    is_recoverable = True
                
                if is_recoverable and (self.model.endswith(":free") or self.model == "openrouter/free"):
                    # Detect if a specific provider rate limited us
                    if "429" in error_str or "rate limit" in error_lower or "rate-limit" in error_lower or "temporarily rate-limited" in error_lower:
                        match_prov = re.search(r"'provider_name':\s*'([^']+)'", error_str)
                        if match_prov:
                            prov = match_prov.group(1)
                            ignored_providers.append(prov)
                            print(f"[OpenRouter] Provider '{prov}' rate limited us. Adding to ignore list.")
                        elif "venice" in error_lower:
                            ignored_providers.append("Venice")
                            print(f"[OpenRouter] Venice rate limited us. Adding to ignore list.")
                        
                        # Determine sleep time (exponential or from header)
                        sleep_time = 2.0
                        try:
                            match_secs = re.search(r"'retry_after_seconds':\s*([0-9.]+)", error_str)
                            if match_secs:
                                sleep_time = float(match_secs.group(1))
                            else:
                                match_secs_raw = re.search(r"retry_after_seconds_raw':\s*([0-9.]+)", error_str)
                                if match_secs_raw:
                                    sleep_time = float(match_secs_raw.group(1))
                        except Exception:
                            pass
                        # Clamp sleep time between 1 and 5 seconds to prevent freezing
                        sleep_time = max(1.0, min(sleep_time, 5.0))
                        print(f"[OpenRouter] Rate limited (429). Sleeping for {sleep_time:.2f} seconds before retrying...")
                        await asyncio.sleep(sleep_time)

                    failed_model = self.model
                    match = re.search(r'([\w\-]+/[\w\-]+:free)', error_str)
                    if match:
                        failed_model = match.group(1)
                    
                    failed_models.append(failed_model)
                    failed_models.append(self.model)
                    
                    new_model = self._get_fallback_model(failed_models)
                    if new_model == self.model and failed_model == self.model:
                        break
                    
                    print(f"[OpenRouter] Stream attempt {attempt + 1} failed for '{self.model}'. Error: {error_str[:150]}. Auto-switching to fallback: '{new_model}'")
                    self.model = new_model
                    kwargs["model"] = new_model
                    ignored_providers = []  # Reset ignored providers for the new model
                else:
                    raise e
                    
        if last_error:
            raise last_error


def convert_gemini_tools_to_openai(gemini_tools: List[Dict]) -> List[Dict]:
    """
    Convert Gemini-style tool definitions to OpenAI format.
    
    Gemini format:
    {
        "name": "tool_name",
        "description": "...",
        "parameters": {
            "type": "OBJECT",
            "properties": {...},
            "required": [...]
        }
    }
    
    OpenAI format:
    {
        "type": "function",
        "function": {
            "name": "tool_name",
            "description": "...",
            "parameters": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
    }
    """
    openai_tools = []
    
    for tool in gemini_tools:
        # Skip google_search and other special tools
        if isinstance(tool, dict) and "function_declarations" in tool:
            for func in tool["function_declarations"]:
                openai_tool = _convert_single_function(func)
                if openai_tool:
                    openai_tools.append(openai_tool)
        elif isinstance(tool, dict) and "name" in tool:
            openai_tool = _convert_single_function(tool)
            if openai_tool:
                openai_tools.append(openai_tool)
    
    return openai_tools


def _convert_single_function(func: Dict) -> Optional[Dict]:
    """Convert a single Gemini function to OpenAI format."""
    if not func.get("name"):
        return None
    
    # Convert parameters
    params = func.get("parameters", {})
    openai_params = {
        "type": "object",
        "properties": {},
        "required": params.get("required", [])
    }
    
    # Convert properties
    for prop_name, prop_def in params.get("properties", {}).items():
        openai_params["properties"][prop_name] = {
            "type": prop_def.get("type", "string").lower(),
            "description": prop_def.get("description", "")
        }
    
    return {
        "type": "function",
        "function": {
            "name": func["name"],
            "description": func.get("description", ""),
            "parameters": openai_params
        }
    }


# Singleton instance for convenience
_client: Optional[OpenRouterClient] = None


def get_client() -> OpenRouterClient:
    """Get or create the singleton OpenRouter client."""
    global _client
    if _client is None:
        _client = OpenRouterClient()
    return _client


async def test_client():
    """Test the OpenRouter client."""
    client = OpenRouterClient()
    
    # Simple test
    response = await client.chat(
        messages=[{"role": "user", "content": "Say hello in one word."}],
        temperature=0.5,
        max_tokens=50
    )
    
    print(f"Response: {response['content']}")
    print(f"Usage: {response['usage']}")


if __name__ == "__main__":
    asyncio.run(test_client())
