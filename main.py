#!/usr/bin/env python3
"""
Nova Agent - Professional Browser Automation Platform
Built for Northflank deployment with Playwright + Groq API + Gradio
"""

import asyncio
import base64
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import uuid

import gradio as gr
import requests
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BrowserAction(BaseModel):
    """Represents a browser action with metadata"""
    id: str
    type: str  # click, type, scroll, navigate, etc.
    selector: Optional[str] = None
    text: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    timestamp: datetime
    success: bool = True
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None

class SessionState(BaseModel):
    """Manages browser session state"""
    session_id: str
    page: Optional[Page] = None
    browser: Optional[Browser] = None
    context: Optional[BrowserContext] = None
    actions: List[BrowserAction] = []
    current_url: str = ""
    is_active: bool = False
    created_at: datetime = datetime.now()

class GroqVisionClient:
    """Client for Groq API with Llama 4 Maverick Vision"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.groq.com/openai/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def analyze_screenshot(self, image_data: bytes, prompt: str = "") -> Dict[str, Any]:
        """Analyze screenshot using Groq Vision API"""
        try:
            # Convert image to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            payload = {
                "model": "llama-4-maverick",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt or "Analyze this webpage screenshot and identify clickable elements, forms, navigation elements, and overall layout. Describe what you see and suggest appropriate actions."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 1000,
                "temperature": 0.1
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "analysis": result["choices"][0]["message"]["content"],
                    "usage": result.get("usage", {})
                }
            else:
                logger.error(f"Groq API error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"API Error: {response.status_code}",
                    "analysis": ""
                }
                
        except Exception as e:
            logger.error(f"Error analyzing screenshot: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis": ""
            }

class NovaAgent:
    """Main Nova Agent class - Browser Automation Engine"""
    
    def __init__(self):
        self.sessions: Dict[str, SessionState] = {}
        self.groq_client: Optional[GroqVisionClient] = None
        self.default_prompt = "Analyze the webpage and help me interact with it. Identify clickable elements, forms, and navigation options."
    
    def set_groq_api_key(self, api_key: str):
        """Set Groq API key"""
        self.groq_client = GroqVisionClient(api_key)
    
    async def create_session(self) -> str:
        """Create new browser session"""
        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--single-process',
                    '--disable-gpu'
                ]
            )
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            session_id = str(uuid.uuid4())
            session = SessionState(session_id=session_id, page=page, browser=browser, context=context)
            self.sessions[session_id] = session
            
            logger.info(f"Created new session: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise
    
    async def navigate(self, session_id: str, url: str) -> Tuple[bool, str, str]:
        """Navigate to URL"""
        try:
            session = self.sessions.get(session_id)
            if not session or not session.page:
                return False, "Invalid session", ""
            
            await session.page.goto(url)
            session.current_url = session.page.url
            
            # Take screenshot
            screenshot = await session.page.screenshot()
            screenshot_path = f"/tmp/screenshot_{session_id}.png"
            with open(screenshot_path, 'wb') as f:
                f.write(screenshot)
            
            # Log action
            action = BrowserAction(
                id=str(uuid.uuid4()),
                type="navigate",
                timestamp=datetime.now(),
                screenshot_path=screenshot_path
            )
            session.actions.append(action)
            
            logger.info(f"Navigated to: {url}")
            return True, f"Successfully navigated to {url}", screenshot_path
            
        except Exception as e:
            logger.error(f"Navigation error: {e}")
            return False, f"Navigation failed: {str(e)}", ""
    
    async def analyze_with_ai(self, session_id: str, custom_prompt: str = "") -> Tuple[bool, str, str]:
        """Analyze current page with AI"""
        try:
            session = self.sessions.get(session_id)
            if not session or not session.page:
                return False, "Invalid session", ""
            
            if not self.groq_client:
                return False, "Groq API key not configured", ""
            
            # Take screenshot
            screenshot = await session.page.screenshot()
            
            # Analyze with AI
            prompt = custom_prompt or self.default_prompt
            result = self.groq_client.analyze_screenshot(screenshot, prompt)
            
            if result["success"]:
                analysis = result["analysis"]
                logger.info("AI analysis completed successfully")
                return True, analysis, f"Analysis completed for {session.current_url}"
            else:
                return False, result["error"], "AI analysis failed"
                
        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            return False, f"AI analysis failed: {str(e)}", ""
    
    async def click_element(self, session_id: str, selector: str) -> Tuple[bool, str, str]:
        """Click element by selector"""
        try:
            session = self.sessions.get(session_id)
            if not session or not session.page:
                return False, "Invalid session", ""
            
            # Wait for element and click
            await session.page.wait_for_selector(selector, timeout=10000)
            await session.page.click(selector)
            
            # Take screenshot after click
            screenshot = await session.page.screenshot()
            screenshot_path = f"/tmp/screenshot_{session_id}.png"
            with open(screenshot_path, 'wb') as f:
                f.write(screenshot)
            
            # Log action
            action = BrowserAction(
                id=str(uuid.uuid4()),
                type="click",
                selector=selector,
                timestamp=datetime.now(),
                screenshot_path=screenshot_path
            )
            session.actions.append(action)
            
            logger.info(f"Clicked element: {selector}")
            return True, f"Successfully clicked: {selector}", screenshot_path
            
        except Exception as e:
            logger.error(f"Click error: {e}")
            return False, f"Failed to click {selector}: {str(e)}", ""
    
    async def type_text(self, session_id: str, selector: str, text: str) -> Tuple[bool, str, str]:
        """Type text into element"""
        try:
            session = self.sessions.get(session_id)
            if not session or not session.page:
                return False, "Invalid session", ""
            
            # Clear field and type
            await session.page.wait_for_selector(selector, timeout=10000)
            await session.page.fill(selector, text)
            
            # Take screenshot
            screenshot = await session.page.screenshot()
            screenshot_path = f"/tmp/screenshot_{session_id}.png"
            with open(screenshot_path, 'wb') as f:
                f.write(screenshot)
            
            # Log action
            action = BrowserAction(
                id=str(uuid.uuid4()),
                type="type",
                selector=selector,
                text=text,
                timestamp=datetime.now(),
                screenshot_path=screenshot_path
            )
            session.actions.append(action)
            
            logger.info(f"Typed text into: {selector}")
            return True, f"Successfully typed: {text} into {selector}", screenshot_path
            
        except Exception as e:
            logger.error(f"Type error: {e}")
            return False, f"Failed to type into {selector}: {str(e)}", ""
    
    async def scroll_page(self, session_id: str, direction: str = "down") -> Tuple[bool, str, str]:
        """Scroll page"""
        try:
            session = self.sessions.get(session_id)
            if not session or not session.page:
                return False, "Invalid session", ""
            
            if direction == "down":
                await session.page.keyboard.press("PageDown")
            elif direction == "up":
                await session.page.keyboard.press("PageUp")
            elif direction == "top":
                await session.page.keyboard.press("Home")
            elif direction == "bottom":
                await session.page.keyboard.press("End")
            
            # Take screenshot
            screenshot = await session.page.screenshot()
            screenshot_path = f"/tmp/screenshot_{session_id}.png"
            with open(screenshot_path, 'wb') as f:
                f.write(screenshot)
            
            # Log action
            action = BrowserAction(
                id=str(uuid.uuid4()),
                type="scroll",
                text=direction,
                timestamp=datetime.now(),
                screenshot_path=screenshot_path
            )
            session.actions.append(action)
            
            logger.info(f"Scrolled {direction}")
            return True, f"Successfully scrolled {direction}", screenshot_path
            
        except Exception as e:
            logger.error(f"Scroll error: {e}")
            return False, f"Failed to scroll {direction}: {str(e)}", ""
    
    async def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get session information"""
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        return {
            "session_id": session.session_id,
            "current_url": session.current_url,
            "is_active": session.is_active,
            "actions_count": len(session.actions),
            "created_at": session.created_at.isoformat(),
            "last_action": session.actions[-1].timestamp.isoformat() if session.actions else None
        }
    
    async def cleanup_session(self, session_id: str):
        """Clean up session"""
        try:
            session = self.sessions.get(session_id)
            if session:
                if session.page:
                    await session.page.close()
                if session.browser:
                    await session.browser.close()
                del self.sessions[session_id]
                logger.info(f"Cleaned up session: {session_id}")
        except Exception as e:
            logger.error(f"Error cleaning up session: {e}")

# Initialize Nova Agent
nova = NovaAgent()

# Gradio UI Functions
async def start_session():
    """Start new browser session"""
    session_id = await nova.create_session()
    return session_id, "Session created successfully!"

async def handle_navigate(session_id: str, url: str):
    """Handle navigation"""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    success, message, screenshot_path = await nova.navigate(session_id, url)
    return message, screenshot_path if success else None

async def handle_ai_analysis(session_id: str, custom_prompt: str):
    """Handle AI analysis"""
    success, analysis, message = await nova.analyze_with_ai(session_id, custom_prompt)
    return analysis, message

async def handle_click(session_id: str, selector: str):
    """Handle click action"""
    success, message, screenshot_path = await nova.click_element(session_id, selector)
    return message, screenshot_path if success else None

async def handle_type(session_id: str, selector: str, text: str):
    """Handle text input"""
    success, message, screenshot_path = await nova.type_text(session_id, selector, text)
    return message, screenshot_path if success else None

async def handle_scroll(session_id: str, direction: str):
    """Handle scroll action"""
    success, message, screenshot_path = await nova.scroll_page(session_id, direction)
    return message, screenshot_path if success else None

def set_api_key(api_key: str):
    """Set Groq API key"""
    nova.set_groq_api_key(api_key)
    return "API key configured successfully!"

def create_gradio_interface():
    """Create the main Gradio interface"""
    
    # Custom CSS for professional look
    css = """
    .gradio-container {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    .title {
        text-align: center;
        color: #2c3e50;
        font-weight: 700;
        font-size: 2.5em;
        margin-bottom: 30px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .subtitle {
        text-align: center;
        color: #7f8c8d;
        font-size: 1.1em;
        margin-bottom: 40px;
    }
    .section-header {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #667eea;
        margin: 20px 0;
        font-weight: 600;
        color: #2c3e50;
    }
    .status-indicator {
        padding: 10px;
        border-radius: 6px;
        margin: 10px 0;
        font-weight: 500;
    }
    .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    .info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
    """
    
    with gr.Blocks(css=css, title="Nova Agent - Browser Automation Platform") as demo:
        
        # Legal Disclaimers Section
        gr.HTML("""
        <div class="title">🚀 Nova Agent</div>
        <div class="subtitle">Professional Browser Automation with AI Vision • Built for Back4app</div>
        
        <div class="legal-disclaimer" style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 8px; margin: 20px 0; color: #856404;">
            <h4 style="margin-top: 0; color: #856404;">⚖️ Legal Notice & Usage Guidelines</h4>
            <p style="margin-bottom: 10px; font-size: 0.9em;">
                <strong>For personal automation and educational purposes only.</strong> By using Nova Agent, you agree to:
            </p>
            <ul style="font-size: 0.85em; margin: 10px 0; padding-left: 20px;">
                <li>Respect all website Terms of Service and robots.txt files</li>
                <li>Only access publicly available content</li>
                <li>Not engage in prohibited activities (spam, data theft, etc.)</li>
                <li>Comply with applicable laws and regulations</li>
                <li>Use reasonable delays between actions (2-5 seconds)</li>
            </ul>
            <p style="font-size: 0.8em; margin: 10px 0 0 0; font-style: italic;">
                Users are solely responsible for ensuring their usage complies with website policies and local laws.
            </p>
        </div>
        """)
        
        # Compliance Checklist Section
        gr.HTML("""
        <div class="section-header">✅ Compliance Checklist</div>
        <div style="background: #e8f5e8; border: 1px solid #c3e6cb; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <p style="margin: 0 0 10px 0; font-size: 0.9em; color: #155724;"><strong>Before using Nova Agent, ensure:</strong></p>
            <div style="display: flex; flex-wrap: wrap; gap: 20px; font-size: 0.85em; color: #155724;">
                <div style="flex: 1; min-width: 200px;">
                    <h5 style="margin: 0 0 8px 0; color: #155724;">📋 Legal Requirements</h5>
                    <ul style="margin: 0; padding-left: 20px;">
                        <li>✅ Read target website's Terms of Service</li>
                        <li>✅ Check robots.txt compliance</li>
                        <li>✅ Verify legal use in your jurisdiction</li>
                    </ul>
                </div>
                <div style="flex: 1; min-width: 200px;">
                    <h5 style="margin: 0 0 8px 0; color: #155724;">🔒 Security Best Practices</h5>
                    <ul style="margin: 0; padding-left: 20px;">
                        <li>✅ Use delays between actions (2-5s)</li>
                        <li>✅ Don't bypass authentication systems</li>
                        <li>✅ Respect rate limits and CAPTCHA</li>
                    </ul>
                </div>
            </div>
        </div>
        """)
        
        # Settings Section
        with gr.Row():
            with gr.Column(scale=1):
                gr.HTML('<div class="section-header">⚙️ Configuration</div>')
                
                api_key_input = gr.Textbox(
                    label="Groq API Key",
                    placeholder="Enter your Groq API key",
                    type="password",
                    info="Get free API key from console.groq.com"
                )
                
                api_key_btn = gr.Button("🔑 Set API Key", variant="primary")
                api_key_status = gr.HTML("")
                
                session_btn = gr.Button("🚀 Start New Session", variant="secondary")
                session_id_output = gr.Textbox(label="Session ID", info="Keep this session ID for all actions")
                session_status = gr.HTML("")
        
        # Main Action Section
        with gr.Row():
            with gr.Column(scale=2):
                gr.HTML('<div class="section-header">🌐 Browser Control</div>')
                
                # Navigation
                with gr.Row():
                    url_input = gr.Textbox(
                        label="Navigate to URL",
                        placeholder="Enter website URL (e.g., google.com)"
                    )
                    nav_btn = gr.Button("Navigate", variant="primary")
                
                nav_status = gr.HTML("")
                
                # Screenshot Display
                screenshot_display = gr.Image(
                    label="Current Page Screenshot",
                    height=400
                )
                
                # AI Analysis
                gr.HTML('<div class="section-header">🤖 AI Vision Analysis</div>')
                
                ai_prompt = gr.Textbox(
                    label="Custom Analysis Prompt",
                    placeholder="Describe what you want to analyze or do on this page..."
                )
                
                ai_btn = gr.Button("🔍 Analyze with AI", variant="secondary")
                ai_output = gr.Textbox(
                    label="AI Analysis Results",
                    lines=8,
                    info="AI-powered analysis of current page state"
                )
                ai_status = gr.HTML("")
        
            with gr.Column(scale=1):
                gr.HTML('<div class="section-header">⚡ Quick Actions</div>')
                
                # Manual Actions
                click_selector = gr.Textbox(
                    label="Click Element",
                    placeholder="CSS selector (e.g., #button, .link)"
                )
                click_btn = gr.Button("👆 Click", variant="secondary")
                
                type_selector = gr.Textbox(
                    label="Type Text",
                    placeholder="CSS selector for input field"
                )
                type_text = gr.Textbox(
                    label="Text to Type",
                    placeholder="Enter text to input"
                )
                type_btn = gr.Button("⌨️ Type", variant="secondary")
                
                scroll_direction = gr.Dropdown(
                    ["up", "down", "top", "bottom"],
                    label="Scroll Direction",
                    value="down"
                )
                scroll_btn = gr.Button("📜 Scroll", variant="secondary")
                
                action_status = gr.HTML("")
        
        # Event Handlers
        api_key_btn.click(
            fn=set_api_key,
            inputs=[api_key_input],
            outputs=[api_key_status]
        ).then(
            lambda: 'success',
            outputs=[api_key_status]
        ).then(
            lambda: 'success',
            api_key_status,
            api_key_status
        )
        
        session_btn.click(
            fn=start_session,
            outputs=[session_id_output, session_status]
        )
        
        nav_btn.click(
            fn=handle_navigate,
            inputs=[session_id_output, url_input],
            outputs=[nav_status, screenshot_display]
        )
        
        ai_btn.click(
            fn=handle_ai_analysis,
            inputs=[session_id_output, ai_prompt],
            outputs=[ai_output, ai_status]
        )
        
        click_btn.click(
            fn=handle_click,
            inputs=[session_id_output, click_selector],
            outputs=[action_status, screenshot_display]
        )
        
        type_btn.click(
            fn=handle_type,
            inputs=[session_id_output, type_selector, type_text],
            outputs=[action_status, screenshot_display]
        )
        
        scroll_btn.click(
            fn=handle_scroll,
            inputs=[session_id_output, scroll_direction],
            outputs=[action_status, screenshot_display]
        )
    
    return demo

if __name__ == "__main__":
    # Create and launch the interface
    interface = create_gradio_interface()
    
    # Launch Gradio interface on specified port
    interface.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", 7860)),
        share=False,
        show_error=True,
        quiet=False,
        enable_queue=True,
        max_threads=10
    )
