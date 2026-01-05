"""
Auto-Save System - Handles automatic saving of game state and session data
"""

import json
import os
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone


class AutoSaveSystem:
    """Handles automatic saving of game sessions"""
    FILES_TO_SAVE = [
        'state.json',
        'transcript.md',
        'changelog.md',
        'turn.md',
        'npc_memory.json',
        'npc_relationships.json',
        'mood_state.json',
        'discovery_log.json',
    ]
    
    def __init__(self, session_slug: str, save_interval: int = 300, base_root: Optional[Path] = None):
        """Initialize the auto-save system
        
        Args:
            session_slug: The session identifier
            save_interval: Auto-save interval in seconds (default: 300 = 5 minutes)
        """
        self.session_slug = session_slug
        self.save_interval = save_interval
        self.last_save_time = 0
        self.save_count = 0
        self.running = False
        self.save_thread = None
        
        root = base_root or Path(__file__).resolve().parent.parent
        self.session_root = root / "sessions" / session_slug
        self.save_data_file = self.session_root / "auto_save.json"
        
        # Load existing save data
        self._load_save_data()
    
    def _load_save_data(self):
        """Load auto-save metadata"""
        if self.save_data_file.exists():
            with self.save_data_file.open() as f:
                data = json.load(f)
                self.last_save_time = data.get('last_save_time', 0)
                self.save_count = data.get('save_count', 0)
        else:
            self.last_save_time = 0
            self.save_count = 0
    
    def _save_metadata(self):
        """Save auto-save metadata"""
        data = {
            'last_save_time': self.last_save_time,
            'save_count': self.save_count,
            'session_slug': self.session_slug
        }
        
        with self.save_data_file.open('w') as f:
            json.dump(data, f, indent=2)
    
    def start_auto_save(self):
        """Start the auto-save thread"""
        if self.running:
            return
        
        self.running = True
        self.save_thread = threading.Thread(target=self._auto_save_loop, daemon=True)
        self.save_thread.start()
    
    def stop_auto_save(self):
        """Stop the auto-save thread"""
        self.running = False
        if self.save_thread:
            self.save_thread.join()
    
    def _auto_save_loop(self):
        """Main auto-save loop"""
        while self.running:
            try:
                # Check if it's time to save
                current_time = time.time()
                if current_time - self.last_save_time >= self.save_interval:
                    self.perform_auto_save()
                
                # Sleep for a short interval
                time.sleep(10)
            except Exception as e:
                print(f"Auto-save error: {e}")
                time.sleep(60)  # Wait longer if there's an error
    
    def perform_auto_save(self):
        """Perform an auto-save of the current session"""
        try:
            print(f"Performing auto-save for session: {self.session_slug}")
            
            # Get current timestamp
            timestamp = datetime.now(timezone.utc).isoformat()
            save_id = self._format_save_id("auto", timestamp)
            
            # Create save directory
            session_dir = self.session_root
            saves_dir = session_dir / "saves"
            saves_dir.mkdir(exist_ok=True)
            
            # Create save file
            save_file = saves_dir / f"{save_id}.json"
            
            # Collect data to save
            save_data = self._capture_session(save_id, timestamp, save_type='auto')
            with save_file.open('w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2)
            
            # Update save metadata
            self.last_save_time = time.time()
            self.save_count += 1
            self._save_metadata()
            
            print(f"Auto-save completed: {save_id}")
            return True
            
        except Exception as e:
            print(f"Auto-save failed: {e}")
            return False
    
    def get_save_history(self, limit: int = 10) -> List[Dict]:
        """Get auto-save history"""
        session_dir = self.session_root
        saves_dir = session_dir / "saves"
        
        if not saves_dir.exists():
            return []
        
        # Get all auto-save files
        save_files = list(saves_dir.glob("auto-*.json"))
        
        # Sort by timestamp (newest first)
        save_files.sort(reverse=True)
        
        # Load save data
        saves = []
        for save_file in save_files[:limit]:
            try:
                with save_file.open() as f:
                    save_data = json.load(f)
                    saves.append(save_data)
            except Exception:
                continue
        
        return saves
    
    def get_auto_save_status(self) -> Dict:
        """Get current auto-save status"""
        return {
            'running': self.running,
            'save_interval': self.save_interval,
            'last_save_time': self.last_save_time,
            'save_count': self.save_count,
            'next_save_in': max(0, self.save_interval - (time.time() - self.last_save_time))
        }

    def _capture_session(self, save_id: str, timestamp: str, save_type: str, save_name: Optional[str] = None) -> Dict:
        """Capture the current session files into a structured payload."""
        session_dir = self.session_root
        files_payload: Dict[str, Dict[str, object]] = {}

        for filename in self.FILES_TO_SAVE:
            file_path = session_dir / filename
            if not file_path.exists():
                continue
            try:
                content = file_path.read_text(encoding='utf-8')
            except Exception:
                # Fallback to binary-safe read if text decode fails
                content = file_path.read_bytes().decode('utf-8', errors='replace')
            files_payload[filename] = {
                'content': content,
                'mtime': file_path.stat().st_mtime,
            }

        return {
            'save_id': save_id,
            'session_slug': self.session_slug,
            'timestamp': timestamp,
            'save_type': save_type,
            'save_name': save_name,
            'data': {
                'files': files_payload,
            },
        }
    
    def manual_save(self, save_name: str = "manual") -> Dict:
        """Perform a manual save"""
        try:
            # Get current timestamp
            timestamp = datetime.now(timezone.utc).isoformat()
            save_id = self._format_save_id(save_name, timestamp)
            
            # Create save directory
            session_dir = self.session_root
            saves_dir = session_dir / "saves"
            saves_dir.mkdir(exist_ok=True)
            
            # Create save file
            save_file = saves_dir / f"{save_id}.json"
            
            save_data = self._capture_session(save_id, timestamp, save_type='manual', save_name=save_name)
            with save_file.open('w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2)
            
            return {
                'success': True,
                'save_id': save_id,
                'timestamp': timestamp,
                'saved_files': list(save_data['data']['files'].keys()),
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _format_save_id(self, prefix: str, timestamp: str) -> str:
        """Sanitize timestamp for filesystem-safe save identifiers."""
        safe_timestamp = timestamp.replace(":", "-")
        return f"{prefix}-{safe_timestamp}"

    def restore_save(self, save_id: str) -> Dict:
        """Restore a save by writing captured files back to the session directory."""
        try:
            session_dir = self.session_root
            saves_dir = session_dir / "saves"
            save_file = saves_dir / f"{save_id}.json"
            
            if not save_file.exists():
                return {'success': False, 'error': 'Save not found'}
            
            with save_file.open(encoding='utf-8') as f:
                save_data = json.load(f)
            
            files_payload = save_data.get('data', {}).get('files', {})
            for filename, payload in files_payload.items():
                dest = session_dir / filename
                dest.parent.mkdir(parents=True, exist_ok=True)
                content = payload.get('content', '')
                dest.write_text(content, encoding='utf-8')
                mtime = payload.get('mtime')
                if mtime:
                    try:
                        dest.touch()
                        os.utime(dest, (mtime, mtime))
                    except Exception:
                        pass

            return {
                'success': True,
                'save_data': save_data,
                'message': 'Session files restored from save point'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_save_info(self, save_id: str) -> Optional[Dict]:
        """Get information about a specific save"""
        try:
            session_dir = self.session_root
            saves_dir = session_dir / "saves"
            save_file = saves_dir / f"{save_id}.json"
            
            if not save_file.exists():
                return None
            
            with save_file.open() as f:
                return json.load(f)
            
        except Exception:
            return None


def get_auto_save_system(session_slug: str, save_interval: int = 300, base_root: Optional[Path] = None) -> AutoSaveSystem:
    """Get the auto-save system for a session"""
    return AutoSaveSystem(session_slug, save_interval, base_root=base_root)

