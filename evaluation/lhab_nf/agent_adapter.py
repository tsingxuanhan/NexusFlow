"""
NexusFlow Agent Adapter
========================
Connects LHAB-NF runner to the actual NexusFlow agent system.
Supports both direct API calls and in-process execution.
"""

import os
import sys
import json
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lhab_nf.task_schema import Step

logger = logging.getLogger("lhab_nf.agent_adapter")


class NexusFlowRealAdapter:
    """
    Real execution adapter connecting to NexusFlow server (port 8900).
    
    Execution flow:
    1. POST /api/tasks to create task
    2. POST /api/tasks/{task_id}/execute with step config
    3. GET /api/tasks/{task_id}/result to collect output
    4. Map agent_role to AGENT_ID_MAP for routing
    """
    
    def __init__(self, server_url: str = "http://localhost:8900", config: Dict = None):
        self.server_url = server_url
        self.config = config or {}
        self.session = None
        self.execution_log = []
        
        # Agent role mapping (from v3.3 naming)
        self.agent_id_map = {
            "coordinator": "coordinator",
            "planner": "planner",
            "executor": "executor",
            "reviewer": "reviewer",
            "researcher": "researcher",
            "coder": "coder",
            "analyst": "analyst",
            "synthesizer": "synthesizer",
            "caster": "caster",
            "miner": "miner",
            "assayer": "assayer",
            "artisan": "artisan",
        }
    
    def _get_session(self):
        """Lazy init HTTP session."""
        if self.session is None:
            try:
                import requests
                self.session = requests.Session()
                self.session.headers.update({
                    "Content-Type": "application/json",
                })
                self.session.timeout = 300  # 5 min for complex tasks
            except ImportError:
                # Fallback to urllib
                import urllib.request
                self.session = urllib.request
            
        return self.session
    
    def execute_step(self, step: Step, context: Dict) -> Dict:
        """
        Execute step through NexusFlow server.
        
        Args:
            step: Step to execute
            context: Execution context
        
        Returns:
            StepResult dict
        """
        start_time = time.time()
        
        try:
            # Map role to agent ID
            agent_id = self.agent_id_map.get(step.agent_role, step.agent_role)
            
            # Prepare task payload
            payload = {
                "description": step.description,
                "agent_role": agent_id,
                "device_preference": step.device_preference,
                "privacy_level": step.privacy_level,
                "context": {
                    "step_id": step.id,
                    "input_deps": step.input_deps,
                    "task_context": context.get("step_outputs", {}),
                },
                "config": {
                    "max_retries": 2,
                    "timeout_seconds": 120,
                }
            }
            
            # Execute via server API
            result = self._call_server("/api/tasks/execute", payload)
            
            elapsed = time.time() - start_time
            
            return {
                "step_id": step.id,
                "success": result.get("success", False),
                "output": result.get("output", {}),
                "error": result.get("error"),
                "elapsed_seconds": elapsed,
                "tokens_used": result.get("tokens_used", 0),
                "cost_cny": result.get("cost_cny", 0.0),
                "agent_role": agent_id,
                "device_used": result.get("device_used", step.device_preference),
                "privacy_violation": result.get("privacy_violation", False),
            }
        
        except Exception as e:
            logger.error(f"Step execution failed: {e}")
            return {
                "step_id": step.id,
                "success": False,
                "output": None,
                "error": str(e),
                "elapsed_seconds": time.time() - start_time,
                "tokens_used": 0,
                "cost_cny": 0.0,
                "agent_role": step.agent_role,
                "device_used": step.device_preference,
                "privacy_violation": False,
            }
    
    def _call_server(self, endpoint: str, payload: Dict) -> Dict:
        """Call NexusFlow server API."""
        url = f"{self.server_url}{endpoint}"
        
        session = self._get_session()
        
        if hasattr(session, 'post'):
            # requests library
            resp = session.post(url, json=payload)
            if resp.status_code == 200:
                return resp.json()
            else:
                raise Exception(f"Server error {resp.status_code}: {resp.text}")
        else:
            # urllib fallback
            import urllib.request
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={
                "Content-Type": "application/json"
            })
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode('utf-8'))
    
    def health_check(self) -> bool:
        """Check if server is reachable."""
        try:
            session = self._get_session()
            if hasattr(session, 'get'):
                resp = session.get(f"{self.server_url}/api/health")
                return resp.status_code == 200
            else:
                import urllib.request
                req = urllib.request.Request(f"{self.server_url}/api/health")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.warning(f"Server health check failed: {e}")
            return False


class NexusFlowInProcessAdapter:
    """
    In-process execution adapter (no server required).
    
    Directly imports and calls NexusFlow modules.
    Faster but requires all dependencies installed.
    """
    
    def __init__(self, nexusflow_root: str = None):
        self.nexusflow_root = nexusflow_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.execution_log = []
    
    def execute_step(self, step: Step, context: Dict) -> Dict:
        """Execute step in-process."""
        # TODO: Implement in-process execution
        # This would:
        # 1. Import nexusflow.engine modules
        # 2. Create agent instance
        # 3. Call agent.run() with step config
        # 4. Collect result
        
        raise NotImplementedError(
            "In-process adapter not yet implemented. "
            "Use server adapter (--server) for now."
        )
