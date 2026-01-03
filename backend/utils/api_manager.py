"""
API Manager for rate limiting and cost tracking
"""
from typing import Dict, Any
from collections import deque
from datetime import datetime, timedelta
import threading
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class APIManager:
    """Manages API rate limiting and cost tracking"""
    
    def __init__(self):
        self.request_times = deque()
        self.cost_accumulator = 0.0
        self.lock = threading.Lock()
        
        # Rate limits (per minute)
        self.max_requests_per_minute = 50
        self.max_cost_per_hour = 10.0  # USD
        
        # Cost tracking
        self.hourly_costs = deque()
        
    def can_make_request(self) -> bool:
        """Check if request can be made without exceeding limits"""
        with self.lock:
            now = datetime.now()
            
            # Clean old request times (older than 1 minute)
            while self.request_times and self.request_times[0] < now - timedelta(minutes=1):
                self.request_times.popleft()
            
            # Check rate limit
            if len(self.request_times) >= self.max_requests_per_minute:
                logger.warning("Rate limit reached, please wait...")
                return False
            
            # Clean old hourly costs (older than 1 hour)
            while self.hourly_costs and self.hourly_costs[0]['time'] < now - timedelta(hours=1):
                old_cost = self.hourly_costs.popleft()
                self.cost_accumulator -= old_cost['cost']
            
            # Check cost limit
            if self.cost_accumulator >= self.max_cost_per_hour:
                logger.warning(f"Cost limit reached: ${self.cost_accumulator:.2f} in the last hour")
                return False
            
            return True
    
    def record_request(self, cost: float = 0.0):
        """Record a request"""
        with self.lock:
            now = datetime.now()
            self.request_times.append(now)
            
            if cost > 0:
                self.hourly_costs.append({'time': now, 'cost': cost})
                self.cost_accumulator += cost
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current API usage statistics"""
        with self.lock:
            now = datetime.now()
            
            # Count requests in last minute
            recent_requests = sum(
                1 for t in self.request_times
                if t > now - timedelta(minutes=1)
            )
            
            return {
                'requests_last_minute': recent_requests,
                'cost_last_hour': round(self.cost_accumulator, 4),
                'remaining_requests': self.max_requests_per_minute - recent_requests,
                'remaining_budget': round(self.max_cost_per_hour - self.cost_accumulator, 4)
            }
    
    def reset_stats(self):
        """Reset all statistics"""
        with self.lock:
            self.request_times.clear()
            self.hourly_costs.clear()
            self.cost_accumulator = 0.0
