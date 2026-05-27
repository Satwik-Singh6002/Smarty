"""
Web Agent using OpenRouter API
Provides basic web automation capabilities with AI guidance.

Note: Full Computer Use functionality requires Gemini's specific model.
This version provides simplified web navigation with screenshot feedback.
"""
import os
import asyncio
import inspect
import base64
from dotenv import load_dotenv
from playwright.async_api import async_playwright

from openrouter_client import OpenRouterClient

load_dotenv()

# Configuration
SCREEN_WIDTH = 1440
SCREEN_HEIGHT = 900


class WebAgent:
    """
    Web agent that uses OpenRouter for AI-guided browser automation.
    Provides navigation, clicking, and typing capabilities.
    """
    
    def __init__(self):
        self.client = OpenRouterClient()
        self.browser = None
        self.context = None
        self.page = None
        
        self.system_instruction = """You are a web browser automation assistant.
You help users navigate websites and perform tasks.

You can use the following actions:
- navigate: Go to a URL
- click: Click at coordinates (x, y) OR click an element by its ID (element_id)
- type: Type text at current focus OR type in a specific element by its ID (element_id)
- scroll: Scroll up or down
- wait: Wait for page to load
- done: Task is complete

When analyzing the page, use the list of interactive elements (and their IDs) to decide the next action. Prefer clicking/typing by element_id for accuracy!

Respond in JSON format:
{
    "observation": "What you see on the page or what elements are present",
    "action": "navigate|click|type|scroll|wait|done",
    "params": {
        "url": "...",  // for navigate
        "element_id": 12, // for click or type (preferred if available)
        "x": 500, "y": 300,  // for click (0-1000 range, fallback if no element_id)
        "text": "...",  // for type
        "press_enter": true, // for type (optional, to submit)
        "direction": "up|down"  // for scroll
    },
    "reasoning": "Why you chose this action"
}
"""

    def is_vision_model(self, model_name: str) -> bool:
        name_lower = model_name.lower()
        return any(x in name_lower for x in ["vision", "vl", "gemini", "gpt-4", "claude", "pixtral", "gemma-3-vl"])

    def denormalize_x(self, x: int, width: int) -> int:
        return int((x / 1000) * width)

    def denormalize_y(self, y: int, height: int) -> int:
        return int((y / 1000) * height)

    async def _safe_callback(self, callback, *args):
        """Safely call a callback, whether it's sync or async."""
        if callback is None:
            return
        result = callback(*args)
        if inspect.isawaitable(result):
            await result

    async def _draw_badges_and_get_elements(self):
        """Draws numbered badges on interactive elements and returns their descriptors."""
        js_draw = """
        () => {
            document.querySelectorAll('.smarty-badge').forEach(e => e.remove());
            
            let style = document.getElementById('smarty-badge-style');
            if (!style) {
                style = document.createElement('style');
                style.id = 'smarty-badge-style';
                style.innerHTML = `
                    .smarty-badge {
                        position: absolute;
                        background-color: rgba(255, 60, 60, 0.9) !important;
                        color: white !important;
                        font-size: 11px !important;
                        font-family: monospace !important;
                        font-weight: bold !important;
                        padding: 1px 4px !important;
                        border-radius: 3px !important;
                        border: 1px solid white !important;
                        z-index: 2147483647 !important;
                        pointer-events: none !important;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.3) !important;
                    }
                `;
                document.head.appendChild(style);
            }
            
            const elements = [];
            const interactiveSelectors = 'a, button, input, textarea, select, [role="button"], [role="link"], [contenteditable]';
            const allElements = document.querySelectorAll(interactiveSelectors);
            
            let idCounter = 1;
            allElements.forEach(el => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                if (rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden' && rect.top >= 0 && rect.left >= 0) {
                    const badge = document.createElement('div');
                    badge.className = 'smarty-badge';
                    badge.style.left = `${window.scrollX + rect.left}px`;
                    badge.style.top = `${window.scrollY + rect.top}px`;
                    badge.innerText = idCounter;
                    document.body.appendChild(badge);
                    
                    el.setAttribute('data-smarty-id', idCounter);
                    
                    let text = '';
                    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                        text = el.placeholder || el.value || el.name || '';
                    } else {
                        text = el.innerText || el.textContent || '';
                    }
                    text = text.trim().substring(0, 100);
                    
                    elements.push({
                        id: idCounter,
                        tagName: el.tagName.toLowerCase(),
                        type: el.type || '',
                        text: text,
                        ariaLabel: el.getAttribute('aria-label') || '',
                        role: el.getAttribute('role') || '',
                        x: Math.round(rect.left + rect.width / 2),
                        y: Math.round(rect.top + rect.height / 2)
                    });
                    idCounter++;
                }
            });
            return elements;
        }
        """
        try:
            return await self.page.evaluate(js_draw)
        except Exception as e:
            print(f"[WebAgent] Error drawing badges/getting elements: {e}")
            return []

    async def _remove_badges(self):
        """Cleans up the interactive element badges from the page."""
        js_remove = """
        () => {
            document.querySelectorAll('.smarty-badge').forEach(e => e.remove());
        }
        """
        try:
            await self.page.evaluate(js_remove)
        except Exception as e:
            print(f"[WebAgent] Error removing badges: {e}")

    async def run_task(self, prompt, update_callback=None):
        """
        Runs the agent with the given prompt.
        update_callback: async function(screenshot_b64: str, logs: str)
        Returns the final response from the agent.
        """
        print(f"[WebAgent] Started. Goal: {prompt}")
        final_response = "Agent finished without a final summary."

        async with async_playwright() as p:
            # Launch browser
            self.browser = await p.chromium.launch(headless=True)
            self.context = await self.browser.new_context(
                viewport={"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            self.page = await self.context.new_page()
            
            # Start at Google
            await self.page.goto("https://www.google.com")
            await asyncio.sleep(2) # Give it a second to settle

            # Draw badges and extract interactive elements
            elements = await self._draw_badges_and_get_elements()
            
            # Capture initial screenshot (with badges overlayed)
            initial_screenshot = await self.page.screenshot(type="png")
            
            # Clean up page
            await self._remove_badges()
            
            encoded_image = base64.b64encode(initial_screenshot).decode('utf-8')
            
            if update_callback:
                await self._safe_callback(update_callback, encoded_image, "Web Agent Initialized")

            # Form elements text description
            elements_desc = []
            for el in elements:
                desc = f"ID [{el['id']}]: <{el['tagName']}>"
                if el['type']:
                    desc += f" (type: {el['type']})"
                if el['text']:
                    desc += f" text: '{el['text']}'"
                if el['ariaLabel']:
                    desc += f" aria-label: '{el['ariaLabel']}'"
                if el['role']:
                    desc += f" role: '{el['role']}'"
                elements_desc.append(desc)
            elements_text = "\n".join(elements_desc)

            is_vision = self.is_vision_model(self.client.model)
            text_prompt = f"Task: {prompt}\n\nInteractive elements on the page:\n{elements_text}\n\nI'm showing you a representation of the current page. Guide me through completing this task step by step."

            # Build conversation
            if is_vision:
                content_payload = [
                    {"type": "text", "text": text_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{encoded_image}"
                        }
                    }
                ]
            else:
                content_payload = text_prompt

            messages = [
                {
                    "role": "user",
                    "content": content_payload
                }
            ]

            MAX_TURNS = 15
            
            for turn in range(MAX_TURNS):
                print(f"\n--- Turn {turn + 1} ---")
                
                try:
                    # Get AI guidance
                    response = await self.client.chat(
                        messages=messages,
                        system_instruction=self.system_instruction,
                        temperature=0.3,
                        max_tokens=1024
                    )
                    
                    content = response.get("content", "")
                    print(f"[WebAgent] AI Response: {content[:200]}...")
                    
                    # Parse JSON response
                    import json
                    import re
                    
                    # Try to extract JSON from response
                    json_match = re.search(r'\{[\s\S]*\}', content)
                    if json_match:
                        try:
                            action_data = json.loads(json_match.group())
                        except json.JSONDecodeError:
                            print("[WebAgent] Failed to parse JSON, asking for clarification")
                            messages.append({"role": "assistant", "content": content})
                            messages.append({"role": "user", "content": "Please respond in valid JSON format."})
                            continue
                    else:
                        # No JSON found, check if done
                        if "done" in content.lower() or "complete" in content.lower():
                            final_response = content
                            break
                        messages.append({"role": "assistant", "content": content})
                        messages.append({"role": "user", "content": "Please respond in JSON format with an action."})
                        continue
                    
                    action = action_data.get("action", "")
                    params = action_data.get("params", {})
                    observation = action_data.get("observation", "")
                    
                    print(f"[WebAgent] Action: {action}, Params: {params}")
                    
                    if action == "done":
                        final_response = observation
                        if update_callback:
                            await self._safe_callback(update_callback, None, f"Task Complete: {observation}")
                        break
                    
                    # Execute action
                    await self._execute_action(action, params)
                    
                    # Wait for page to settle
                    await asyncio.sleep(2.0)
                    
                    # Draw new badges and extract elements
                    elements = await self._draw_badges_and_get_elements()
                    
                    # Capture new screenshot
                    screenshot_bytes = await self.page.screenshot(type="png")
                    await self._remove_badges()
                    
                    current_url = self.page.url
                    encoded_screenshot = base64.b64encode(screenshot_bytes).decode('utf-8')
                    
                    if update_callback:
                        await self._safe_callback(update_callback, encoded_screenshot, f"Executed: {action}")
                    
                    # Form new elements text description
                    elements_desc = []
                    for el in elements:
                        desc = f"ID [{el['id']}]: <{el['tagName']}>"
                        if el['type']:
                            desc += f" (type: {el['type']})"
                        if el['text']:
                            desc += f" text: '{el['text']}'"
                        if el['ariaLabel']:
                            desc += f" aria-label: '{el['ariaLabel']}'"
                        if el['role']:
                            desc += f" role: '{el['role']}'"
                        elements_desc.append(desc)
                    elements_text = "\n".join(elements_desc)
                    
                    # Remove older screenshots to save token limits
                    for msg in messages:
                        if isinstance(msg.get("content"), list):
                            new_content = []
                            for item in msg["content"]:
                                if isinstance(item, dict) and item.get("type") == "image_url":
                                    new_content.append({"type": "text", "text": "[Previous Screenshot Removed]"})
                                else:
                                    new_content.append(item)
                            msg["content"] = new_content

                    is_vision = self.is_vision_model(self.client.model)
                    text_prompt = f"Action executed. Current URL: {current_url}\n\nInteractive elements on the page:\n{elements_text}\n\nWhat's the next step?"
                    
                    if is_vision:
                        turn_payload = [
                            {"type": "text", "text": text_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{encoded_screenshot}"
                                }
                            }
                        ]
                    else:
                        turn_payload = text_prompt

                    # Add to conversation
                    messages.append({"role": "assistant", "content": content})
                    messages.append({
                        "role": "user",
                        "content": turn_payload
                    })
                    
                except Exception as e:
                    print(f"[WebAgent] Error: {e}")
                    if update_callback:
                        await self._safe_callback(update_callback, None, f"Error: {e}")
                    break

            await self.browser.close()
            print("[WebAgent] Browser closed.")
            return final_response

    async def _execute_action(self, action: str, params: dict):
        """Execute a browser action."""
        try:
            if action == "navigate":
                url = params.get("url", "")
                if url:
                    if not url.startswith("http"):
                        url = "https://" + url
                    await self.page.goto(url)
            
            elif action == "click":
                element_id = params.get("element_id")
                if element_id is not None:
                    try:
                        element = await self.page.query_selector(f'[data-smarty-id="{element_id}"]')
                        if element:
                            # Use click() directly on element for DOM click accuracy
                            await element.click()
                            print(f"[WebAgent] Clicked element ID {element_id} successfully.")
                            return
                    except Exception as click_err:
                        print(f"[WebAgent] ID click failed, trying coordinate fallback: {click_err}")
                
                # Fallback to coordinates
                x = self.denormalize_x(params.get("x", 500), SCREEN_WIDTH)
                y = self.denormalize_y(params.get("y", 500), SCREEN_HEIGHT)
                await self.page.mouse.click(x, y)
            
            elif action == "type":
                element_id = params.get("element_id")
                text = params.get("text", "")
                press_enter = params.get("press_enter", False)
                
                if element_id is not None:
                    try:
                        element = await self.page.query_selector(f'[data-smarty-id="{element_id}"]')
                        if element:
                            await element.focus()
                            # Use fill() to enter text reliably, or type()
                            await element.fill("")
                            await element.type(text)
                            if press_enter:
                                await self.page.keyboard.press("Enter")
                            print(f"[WebAgent] Typed in element ID {element_id} successfully.")
                            return
                    except Exception as type_err:
                        print(f"[WebAgent] ID type failed, trying keyboard fallback: {type_err}")
                
                # Fallback to typing at current focus
                await self.page.keyboard.type(text)
                if press_enter:
                    await self.page.keyboard.press("Enter")
            
            elif action == "scroll":
                direction = params.get("direction", "down")
                amount = 500
                if direction == "up":
                    amount = -500
                await self.page.mouse.wheel(0, amount)
            
            elif action == "wait":
                await asyncio.sleep(2)
            
            elif action == "go_back":
                await self.page.go_back()
            
            else:
                print(f"[WebAgent] Unknown action: {action}")
                
        except Exception as e:
            print(f"[WebAgent] Action error: {e}")


if __name__ == "__main__":
    async def main():
        agent = WebAgent()
        result = await agent.run_task(
            "Go to google.com and search for 'Python programming'",
            update_callback=lambda img, log: print(f"[Update] {log}")
        )
        print(f"Result: {result}")
    
    asyncio.run(main())