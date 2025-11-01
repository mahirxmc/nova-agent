#!/usr/bin/env python3
"""
Nova Agent - Health Check Script
This script monitors the health of Nova Agent deployment
"""

import requests
import sys
import time
import json
from datetime import datetime

def check_health(url: str, timeout: int = 10) -> dict:
    """Check if Nova Agent is healthy"""
    try:
        response = requests.get(f"{url}/health", timeout=timeout)
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "url": url,
            "status_code": response.status_code,
            "healthy": response.status_code == 200,
            "response_time": response.elapsed.total_seconds(),
            "server": response.headers.get('server', 'unknown')
        }
        
        if response.status_code == 200:
            try:
                data = response.json()
                result.update(data)
            except:
                result["content"] = response.text[:200]
        
        return result
        
    except requests.exceptions.Timeout:
        return {
            "timestamp": datetime.now().isoformat(),
            "url": url,
            "healthy": False,
            "error": "Connection timeout",
            "status_code": None
        }
    except requests.exceptions.ConnectionError:
        return {
            "timestamp": datetime.now().isoformat(),
            "url": url,
            "healthy": False,
            "error": "Connection failed",
            "status_code": None
        }
    except Exception as e:
        return {
            "timestamp": datetime.now().isoformat(),
            "url": url,
            "healthy": False,
            "error": str(e),
            "status_code": None
        }

def main():
    """Main health check function"""
    if len(sys.argv) < 2:
        print("Usage: python health_check.py <url>")
        print("Example: python health_check.py https://nova-agent.northflank.app")
        sys.exit(1)
    
    url = sys.argv[1].rstrip('/')
    
    print(f"🔍 Checking health of: {url}")
    print("=" * 50)
    
    # Perform health check
    result = check_health(url)
    
    # Display results
    if result["healthy"]:
        print("✅ Service is HEALTHY")
        print(f"Status Code: {result['status_code']}")
        print(f"Response Time: {result['response_time']:.2f}s")
        print(f"Server: {result['server']}")
        
        if "content" in result:
            print(f"Response: {result['content']}")
    else:
        print("❌ Service is UNHEALTHY")
        print(f"Status Code: {result['status_code']}")
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    # Save detailed report
    with open(f"health_report_{int(time.time())}.json", "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: health_report_{int(time.time())}.json")
    
    # Exit with appropriate code
    sys.exit(0 if result["healthy"] else 1)

if __name__ == "__main__":
    main()
