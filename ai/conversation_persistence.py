#!/usr/bin/env python3
"""Conversation context persistence."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ConversationStore:
    """Stores conversation context across sessions."""
    
    def __init__(self, storage_dir: str = "conversations"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
    
    def save_context(self, account_id: str, context: List[Dict]):
        """Save conversation context."""
        try:
            file_path = self.storage_dir / f"{account_id}.json"
            with open(file_path, 'w') as f:
                json.dump({
                    'account_id': account_id,
                    'messages': context,
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
            
            logger.debug(f"Saved conversation context for {account_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save context: {e}")
            return False
    
    def load_context(self, account_id: str) -> Optional[List[Dict]]:
        """Load conversation context."""
        try:
            file_path = self.storage_dir / f"{account_id}.json"
            
            if not file_path.exists():
                return []
            
            with open(file_path, 'r') as f:
                data = json.load(f)
                return data.get('messages', [])
                
        except Exception as e:
            logger.error(f"Failed to load context: {e}")
            return []
    
    def append_message(self, account_id: str, role: str, content: str):
        """Append message to conversation."""
        context = self.load_context(account_id)
        context.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        
        # Limit context size (keep last 50 messages)
        if len(context) > 50:
            context = context[-50:]
        
        self.save_context(account_id, context)


_conv_store = None

def get_conversation_store():
    global _conv_store
    if _conv_store is None:
        _conv_store = ConversationStore()
    return _conv_store


