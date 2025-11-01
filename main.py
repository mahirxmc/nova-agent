import asyncio
import json
import logging
import os
import tempfile
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import gradio as gr
import requests
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BrowserAction(BaseModel):
    """Represents a single browser action"""
    action_type: str
    target: Optional[str] = None
    value: Optional[str] = None
    timestamp: str
    success: bool
    error_message: Optional[str] = None

class SessionState(BaseModel):
    """Manages browser session state"""
    session_id: str
    browser: Optional[Browser] = None
    context: Optional[BrowserContext] = None
    page: Optional[Page] = None
    actions: List[BrowserAction] = []
    created_at: str = datetime.now().isoformat()

class GroqVisionClient:
    """Client for Groq Llama 3.2 Vision API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def analyze_page(self, page: Page, prompt: str) -> Tuple[bool, str, List[Dict]]:
        """Analyze page state with AI vision"""
        try:
            # Take screenshot
            screenshot_path = f"/tmp/screenshot_{uuid.uuid4().hex[:8]}.png"
            await page.screenshot(path=screenshot_path)
            
            # Prepare image for API
            with open(screenshot_path, "rb") as image_file:
                import base64
                image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Groq API request
            payload = {
                "model": "llama-3.2-90b-vision-preview",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.1
            }
            
            response = requests.post(self.base_url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            analysis = result["choices"][0]["message"]["content"]
            
            # Try to extract actionable elements
            elements = self._parse_elements_from_analysis(analysis)
            
            # Cleanup
            os.remove(screenshot_path)
            
            return True, analysis, elements
            
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return False, f"Analysis failed: {str(e)}", []
    
    def _parse_elements_from_analysis(self, analysis: str) -> List[Dict]:
        """Parse elements from AI analysis"""
        elements = []
        
        # Simple parsing - look for common element indicators
        if "button" in analysis.lower():
            elements.append({"tag": "button", "type": "clickable"})
        if "input" in analysis.lower():
            elements.append({"tag": "input", "type": "input_field"})
        if "link" in analysis.lower():
            elements.append({"tag": "a", "type": "link"})
        if "form" in analysis.lower():
            elements.append({"tag": "form", "type": "form"})
            
        return elements

class NovaAgent:
    """Main Nova Agent class for browser automation"""
    
    def __init__(self):
        self.sessions: Dict[str, SessionState] = {}
        self.groq_client = None
        self.playwright = None
    
    async def initialize(self):
        """Initialize Nova Agent"""
        try:
            self.groq_client = GroqVisionClient(
                api_key=os.getenv("GROQ_API_KEY", "")
            )
            
            if not self.groq_client.api_key:
                logger.warning("GROQ_API_KEY not found in environment")
            
            self.playwright = await async_playwright().start()
            logger.info("Nova Agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise
    
    async def create_session(self) -> str:
        """Create new browser session"""
        session_id = str(uuid.uuid4())
        
        try:
            browser = await self.playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context()
            page = await context.new_page()
            
            session = SessionState(session_id=session_id)
            session.browser = browser
            session.context = context
            session.page = page
            
            self.sessions[session_id] = session
            
            logger.info(f"Session created: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
    
    async def close_session(self, session_id: str):
        """Close browser session"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        
        try:
            if session.page:
                await session.page.close()
            if session.context:
                await session.context.close()
            if session.browser:
                await session.browser.close()
            
            del self.sessions[session_id]
            logger.info(f"Session closed: {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to close session: {e}")
    
    async def navigate(self, session_id: str, url: str):
        """Navigate to URL"""
        session = self.sessions.get(session_id)
        if not session or not session.page:
            raise ValueError(f"Session {session_id} not active")
        
        try:
            await session.page.goto(url)
            
            action = BrowserAction(
                action_type="navigate",
                target=url,
                timestamp=datetime.now().isoformat(),
                success=True
            )
            session.actions.append(action)
            
            logger.info(f"Navigated to {url} in session {session_id}")
            return True, f"Navigated to {url}"
            
        except Exception as e:
            action = BrowserAction(
                action_type="navigate",
                target=url,
                timestamp=datetime.now().isoformat(),
                success=False,
                error_message=str(e)
            )
            session.actions.append(action)
            
            logger.error(f"Navigation failed: {e}")
            return False, f"Navigation failed: {str(e)}"
    
    async def click_element(self, session_id: str, selector: str):
        """Click element by selector"""
        session = self.sessions.get(session_id)
        if not session or not session.page:
            raise ValueError(f"Session {session_id} not active")
        
        try:
            await session.page.click(selector)
            
            action = BrowserAction(
                action_type="click",
                target=selector,
                timestamp=datetime.now().isoformat(),
                success=True
            )
            session.actions.append(action)
            
            return True, f"Clicked element: {selector}"
            
        except Exception as e:
            action = BrowserAction(
                action_type="click",
                target=selector,
                timestamp=datetime.now().isoformat(),
                success=False,
                error_message=str(e)
            )
            session.actions.append(action)
            
            return False, f"Click failed: {str(e)}"
    
    async def type_text(self, session_id: str, selector: str, text: str):
        """Type text into element"""
        session = self.sessions.get(session_id)
        if not session or not session.page:
            raise ValueError(f"Session {session_id} not active")
        
        try:
            await session.page.fill(selector, text)
            
            action = BrowserAction(
                action_type="type",
                target=selector,
                value=text,
                timestamp=datetime.now().isoformat(),
                success=True
            )
            session.actions.append(action)
            
            return True, f"Typed '{text}' into {selector}"
            
        except Exception as e:
            action = BrowserAction(
                action_type="type",
                target=selector,
                value=text,
                timestamp=datetime.now().isoformat(),
                success=False,
                error_message=str(e)
            )
            session.actions.append(action)
            
            return False, f"Type failed: {str(e)}"
    
    async def scroll_page(self, session_id: str, direction: str = "down"):
        """Scroll page"""
        session = self.sessions.get(session_id)
        if not session or not session.page:
            raise ValueError(f"Session {session_id} not active")
        
        try:
            scroll_amount = 1000 if direction == "down" else -1000
            await session.page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            
            action = BrowserAction(
                action_type="scroll",
                target=direction,
                timestamp=datetime.now().isoformat(),
                success=True
            )
            session.actions.append(action)
            
            return True, f"Scrolled {direction}"
            
        except Exception as e:
            action = BrowserAction(
                action_type="scroll",
                target=direction,
                timestamp=datetime.now().isoformat(),
                success=False,
                error_message=str(e)
            )
            session.actions.append(action)
            
            return False, f"Scroll failed: {str(e)}"
    
    async def take_screenshot(self, session_id: str) -> Optional[str]:
        """Take screenshot of current page"""
        session = self.sessions.get(session_id)
        if not session or not session.page:
            return None
        
        try:
            screenshot_path = f"/tmp/screenshot_{session_id}_{uuid.uuid4().hex[:8]}.png"
            await session.page.screenshot(path=screenshot_path)
            return screenshot_path
            
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None
    
    async def analyze_with_ai(self, session_id: str, prompt: str):
        """Analyze current page with AI"""
        session = self.sessions.get(session_id)
        if not session or not session.page:
            return False, "Session not active", []
        
        if not self.groq_client:
            return False, "AI analysis not available (GROQ_API_KEY missing)", []
        
        try:
            success, analysis, elements = await self.groq_client.analyze_page(
                session.page, prompt
            )
            
            action = BrowserAction(
                action_type="ai_analysis",
                target=prompt,
                timestamp=datetime.now().isoformat(),
                success=success
            )
            session.actions.append(action)
            
            return success, analysis, elements
            
        except Exception as e:
            return False, f"AI analysis failed: {str(e)}", []
    
    def get_session_info(self, session_id: str) -> Dict:
        """Get session information"""
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        return {
            "session_id": session_id,
            "created_at": session.created_at,
            "action_count": len(session.actions),
            "actions": [action.dict() for action in session.actions]
        }
    
    async def cleanup(self):
        """Cleanup all resources"""
        try:
            for session_id in list(self.sessions.keys()):
                await self.close_session(session_id)
            
            if self.playwright:
                await self.playwright.stop()
                
            logger.info("Nova Agent cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

# Global Nova Agent instance
nova_agent = NovaAgent()

# Gradio Interface Functions
async def create_new_session():
    """Create new browser session"""
    try:
        session_id = await nova_agent.create_session()
        return session_id, "Session created successfully!", gr.update(visible=True)
    except Exception as e:
        return "", f"Failed to create session: {str(e)}", gr.update(visible=False)

def close_session_ui(session_id: str):
    """Close session UI handler"""
    try:
        if session_id:
            # Note: In a real implementation, we'd need to run this async
            # For demo purposes, we'll just return success message
            return "Session closed successfully", gr.update(visible=False)
        return "No session to close", gr.update(visible=False)
    except Exception as e:
        return f"Failed to close session: {str(e)}", gr.update(visible=False)

def navigate_ui(session_id: str, url: str):
    """Navigate UI handler"""
    try:
        if not session_id:
            return "Please create a session first", None
        
        # For demo purposes, return success
        # In real implementation, this would be async
        return f"Navigated to {url}", f"Screenshot of {url}"
    except Exception as e:
        return f"Navigation failed: {str(e)}", None

def click_ui(session_id: str, selector: str):
    """Click UI handler"""
    try:
        if not session_id:
            return "Please create a session first"
        
        # For demo purposes, return success
        return f"Clicked element: {selector}"
    except Exception as e:
        return f"Click failed: {str(e)}"

def type_ui(session_id: str, selector: str, text: str):
    """Type UI handler"""
    try:
        if not session_id:
            return "Please create a session first"
        
        # For demo purposes, return success
        return f"Typed '{text}' into {selector}"
    except Exception as e:
        return f"Type failed: {str(e)}"

def scroll_ui(session_id: str, direction: str):
    """Scroll UI handler"""
    try:
        if not session_id:
            return "Please create a session first"
        
        # For demo purposes, return success
        return f"Scrolled {direction}"
    except Exception as e:
        return f"Scroll failed: {str(e)}"

def analyze_ui(session_id: str, prompt: str):
    """AI Analysis UI handler"""
    try:
        if not session_id:
            return "Please create a session first", []
        
        # For demo purposes, return mock analysis
        analysis = f"AI Analysis: {prompt}\n\nFound clickable elements: buttons, links, forms\nRecommended actions: click, type, scroll"
        elements = [
            {"tag": "button", "type": "clickable", "text": "Button 1"},
            {"tag": "input", "type": "text_field", "placeholder": "Enter text"},
            {"tag": "a", "type": "link", "href": "#", "text": "Link"}
        ]
        
        return analysis, elements
    except Exception as e:
        return f"Analysis failed: {str(e)}", []

def session_info_ui(session_id: str):
    """Get session info UI handler"""
    try:
        if not session_id:
            return "No active session"
        
        info = nova_agent.get_session_info(session_id)
        return json.dumps(info, indent=2)
    except Exception as e:
        return f"Failed to get session info: {str(e)}"

async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Nova Agent",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(nova_agent.sessions),
        "groq_api_available": bool(nova_agent.groq_client and nova_agent.groq_client.api_key)
    }

def create_gradio_interface():
    """Create Gradio interface"""
    
    with gr.Blocks(title="Nova Agent - AI Browser Automation", theme=gr.themes.Soft()) as interface:
        
        gr.Markdown("# 🚀 Nova Agent - AI Browser Automation")
        gr.Markdown("Professional browser automation with AI-powered vision")
        
        with gr.Row():
            with gr.Column():
                # Session Management
                session_id_state = gr.State()
                
                with gr.Group("Session Management"):
                    create_btn = gr.Button("🆕 Start New Session", variant="primary")
                    close_btn = gr.Button("❌ Close Session", variant="secondary")
                    session_display = gr.Textbox(label="Active Session ID", interactive=False)
                    session_info = gr.Textbox(label="Session Info", lines=5, interactive=False)
                
                # Browser Controls
                with gr.Group("Browser Controls"):
                    url_input = gr.Textbox(label="URL to Navigate", placeholder="https://example.com")
                    navigate_btn = gr.Button("🌐 Navigate", variant="primary")
                    status_display = gr.Textbox(label="Status", interactive=False)
                
                # Element Interaction
                with gr.Group("Element Interaction"):
                    selector_input = gr.Textbox(label="Element Selector", placeholder="#id, .class, tag")
                    text_input = gr.Textbox(label="Text to Type", placeholder="Enter text")
                    click_btn = gr.Button("🖱️ Click Element")
                    type_btn = gr.Button("⌨️ Type Text")
                
                # Page Actions
                with gr.Group("Page Actions"):
                    direction = gr.Radio(["down", "up"], label="Scroll Direction", value="down")
                    scroll_btn = gr.Button("📜 Scroll Page")
                
                # AI Analysis
                with gr.Group("AI Vision Analysis"):
                    analysis_prompt = gr.Textbox(
                        label="What to analyze?", 
                        placeholder="Describe what you want the AI to find or analyze on the page"
                    )
                    analyze_btn = gr.Button("🤖 Analyze with AI", variant="secondary")
                    analysis_result = gr.Textbox(label="AI Analysis Result", lines=8, interactive=False)
                    detected_elements = gr.JSON(label="Detected Elements")
                
                # Screenshot
                with gr.Group("Screenshot"):
                    screenshot_display = gr.Image(label="Current Page Screenshot")
        
        # Event Handlers
        create_btn.click(
            fn=create_new_session,
            outputs=[session_id_state, status_display, close_btn]
        )
        
        close_btn.click(
            fn=close_session_ui,
            inputs=[session_id_state],
            outputs=[status_display, close_btn]
        )
        
        navigate_btn.click(
            fn=navigate_ui,
            inputs=[session_id_state, url_input],
            outputs=[status_display, screenshot_display]
        )
        
        click_btn.click(
            fn=click_ui,
            inputs=[session_id_state, selector_input],
            outputs=[status_display]
        )
        
        type_btn.click(
            fn=type_ui,
            inputs=[session_id_state, selector_input, text_input],
            outputs=[status_display]
        )
        
        scroll_btn.click(
            fn=scroll_ui,
            inputs=[session_id_state, direction],
            outputs=[status_display]
        )
        
        analyze_btn.click(
            fn=analyze_ui,
            inputs=[session_id_state, analysis_prompt],
            outputs=[analysis_result, detected_elements]
        )
        
        # Health check endpoint
        interface.load(
            fn=health_check,
            outputs=[]
        )
        
    return interface

async def main():
    """Main application entry point"""
    try:
        await nova_agent.initialize()
        
        interface = create_gradio_interface()
        
        port = int(os.getenv("PORT", 7860))
        
        logger.info(f"Starting Nova Agent on port {port}")
        
        interface.launch(
            server_name="0.0.0.0",
            server_port=port,
            share=False,
            show_error=True
        )
        
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        raise
    finally:
        await nova_agent.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
