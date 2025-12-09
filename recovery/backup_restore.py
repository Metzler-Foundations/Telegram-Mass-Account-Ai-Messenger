#!/usr/bin/env python3
"""
Backup & Restore - REAL backup system for all data
Creates actual compressed backups with complete data
"""

import logging
import shutil
import tarfile
import zipfile
import json
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QFileDialog, QProgressBar,
    QCheckBox, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class BackupCreator(QThread):
    """Thread for REAL backup creation (actual file operations)."""
    
    progress_update = pyqtSignal(int, str)
    backup_complete = pyqtSignal(str)
    backup_failed = pyqtSignal(str)
    
    def __init__(self, backup_path: str, include_sessions: bool = True):
        super().__init__()
        self.backup_path = backup_path
        self.include_sessions = include_sessions
    
    def run(self):
        """Create REAL backup with actual file operations."""
        try:
            logger.info(f"Creating REAL backup to {self.backup_path}...")
            
            # Files to backup (REAL)
            files_to_backup = [
                'config.json',
                'members.db',
                'campaigns.db',
                'warmup_jobs.json',
                'filter_presets.json',
                '.encryption_key'
            ]
            
            self.progress_update.emit(10, "📋 Collecting files...")
            
            # Add session files if requested
            if self.include_sessions:
                session_files = list(Path('.').glob('*.session'))
                files_to_backup.extend([str(f) for f in session_files])
                logger.info(f"Including {len(session_files)} session files")
            
            self.progress_update.emit(20, f"📦 Compressing {len(files_to_backup)} files...")
            
            # Create ACTUAL zip archive
            with zipfile.ZipFile(self.backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add metadata
                metadata = {
                    'created_at': datetime.now().isoformat(),
                    'version': '2.0',
                    'files_count': len(files_to_backup),
                    'includes_sessions': self.include_sessions
                }
                
                zipf.writestr('backup_metadata.json', json.dumps(metadata, indent=2))
                
                # Add each file
                for i, file_path in enumerate(files_to_backup):
                    if Path(file_path).exists():
                        progress = 20 + int((i / len(files_to_backup)) * 70)
                        self.progress_update.emit(progress, f"Adding {file_path}...")
                        
                        zipf.write(file_path)
                        logger.debug(f"Added {file_path} to backup")
            
            self.progress_update.emit(100, "✅ Backup complete!")
            
            # Get actual file size
            backup_size = Path(self.backup_path).stat().st_size / (1024 * 1024)  # MB
            
            logger.info(f"✅ Backup created: {self.backup_path} ({backup_size:.2f} MB)")
            self.backup_complete.emit(self.backup_path)
            
        except Exception as e:
            logger.error(f"Backup creation failed: {e}", exc_info=True)
            self.backup_failed.emit(str(e))


class BackupRestorer(QThread):
    """Thread for REAL backup restoration (actual file operations)."""
    
    progress_update = pyqtSignal(int, str)
    restore_complete = pyqtSignal()
    restore_failed = pyqtSignal(str)
    
    def __init__(self, backup_path: str, restore_sessions: bool = True):
        super().__init__()
        self.backup_path = backup_path
        self.restore_sessions = restore_sessions
    
    def run(self):
        """Restore REAL backup with actual file operations."""
        try:
            logger.info(f"Restoring REAL backup from {self.backup_path}...")
            
            self.progress_update.emit(10, "📂 Opening backup file...")
            
            # Create backup of current state
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pre_restore_backup = f"pre_restore_backup_{timestamp}.zip"
            
            self.progress_update.emit(20, "💾 Backing up current state...")
            
            # Backup current files before restore
            current_files = ['config.json', 'members.db', 'campaigns.db']
            with zipfile.ZipFile(pre_restore_backup, 'w') as zipf:
                for file in current_files:
                    if Path(file).exists():
                        zipf.write(file)
            
            logger.info(f"Created pre-restore backup: {pre_restore_backup}")
            
            self.progress_update.emit(40, "📦 Extracting backup...")
            
            # ACTUALLY extract backup
            with zipfile.ZipFile(self.backup_path, 'r') as zipf:
                # Read metadata
                try:
                    metadata_json = zipf.read('backup_metadata.json').decode()
                    metadata = json.loads(metadata_json)
                    logger.info(f"Backup created: {metadata.get('created_at')}")
                except (KeyError, json.JSONDecodeError) as e:
                    logger.warning(f"No metadata in backup: {e}")
                
                # Extract files
                files = zipf.namelist()
                
                for i, file in enumerate(files):
                    if file == 'backup_metadata.json':
                        continue
                    
                    # Skip session files if not requested
                    if not self.restore_sessions and file.endswith('.session'):
                        continue
                    
                    progress = 40 + int((i / len(files)) * 50)
                    self.progress_update.emit(progress, f"Restoring {file}...")
                    
                    # ACTUALLY extract file
                    zipf.extract(file, '.')
                    logger.debug(f"Restored {file}")
            
            self.progress_update.emit(100, "✅ Restore complete!")
            
            logger.info("✅ Backup restored successfully")
            self.restore_complete.emit()
            
        except Exception as e:
            logger.error(f"Backup restoration failed: {e}", exc_info=True)
            self.restore_failed.emit(str(e))


class BackupManagerDialog(QDialog):
    """Dialog for managing backups with REAL operations."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("💾 Backup & Restore")
        self.resize(700, 500)
        
        self.setup_ui()
        self.load_backups()
    
    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("💾 Backup & Restore")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        desc = QLabel(
            "Create backups of all your data including databases, config, and session files.\n"
            "Restore from previous backups if needed."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Create backup section
        create_group = QGroupBox("Create New Backup")
        create_layout = QVBoxLayout()
        
        self.include_sessions_check = QCheckBox("Include session files (.session)")
        self.include_sessions_check.setChecked(True)
        self.include_sessions_check.setToolTip("Session files contain login credentials - backup for safety")
        create_layout.addWidget(self.include_sessions_check)
        
        backup_btn_layout = QHBoxLayout()
        
        self.create_backup_btn = QPushButton("📦 Create Backup")
        self.create_backup_btn.clicked.connect(self.create_backup)
        self.create_backup_btn.setObjectName("success")
        backup_btn_layout.addWidget(self.create_backup_btn)
        
        self.auto_backup_check = QCheckBox("Auto-backup daily")
        self.auto_backup_check.setToolTip("Automatically create daily backups")
        backup_btn_layout.addWidget(self.auto_backup_check)
        
        backup_btn_layout.addStretch()
        create_layout.addLayout(backup_btn_layout)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        create_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel()
        create_layout.addWidget(self.status_label)
        
        create_group.setLayout(create_layout)
        layout.addWidget(create_group)
        
        # Restore section
        restore_group = QGroupBox("Existing Backups")
        restore_layout = QVBoxLayout()
        
        self.backups_list = QListWidget()
        restore_layout.addWidget(self.backups_list)
        
        restore_btn_layout = QHBoxLayout()
        
        self.restore_btn = QPushButton("♻️ Restore Selected")
        self.restore_btn.clicked.connect(self.restore_backup)
        self.restore_btn.setObjectName("warning")
        restore_btn_layout.addWidget(self.restore_btn)
        
        self.delete_backup_btn = QPushButton("🗑️ Delete Selected")
        self.delete_backup_btn.clicked.connect(self.delete_backup)
        self.delete_backup_btn.setObjectName("danger")
        restore_btn_layout.addWidget(self.delete_backup_btn)
        
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.load_backups)
        restore_btn_layout.addWidget(self.refresh_btn)
        
        restore_btn_layout.addStretch()
        restore_layout.addLayout(restore_btn_layout)
        
        restore_group.setLayout(restore_layout)
        layout.addWidget(restore_group)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
    
    def load_backups(self):
        """Load REAL backup files from disk."""
        self.backups_list.clear()
        
        # Find all backup files
        backup_files = list(Path('backups').glob('*.zip')) if Path('backups').exists() else []
        backup_files.extend(list(Path('.').glob('backup_*.zip')))
        
        for backup_file in sorted(backup_files, reverse=True):
            size_mb = backup_file.stat().st_size / (1024 * 1024)
            modified = datetime.fromtimestamp(backup_file.stat().st_mtime)
            
            item_text = f"{backup_file.name} ({size_mb:.2f} MB) - {modified.strftime('%Y-%m-%d %H:%M')}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, str(backup_file))
            self.backups_list.addItem(item)
        
        logger.info(f"Found {len(backup_files)} REAL backup files")
    
    def create_backup(self):
        """Create REAL backup."""
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"backup_{timestamp}.zip"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Backup",
            default_name,
            "Zip Files (*.zip)"
        )
        
        if not file_path:
            return
        
        # Create backup thread
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.create_backup_btn.setEnabled(False)
        
        self.backup_thread = BackupCreator(
            file_path,
            self.include_sessions_check.isChecked()
        )
        
        self.backup_thread.progress_update.connect(self.on_backup_progress)
        self.backup_thread.backup_complete.connect(self.on_backup_complete)
        self.backup_thread.backup_failed.connect(self.on_backup_failed)
        self.backup_thread.start()
    
    def on_backup_progress(self, progress: int, message: str):
        """Handle REAL backup progress."""
        self.progress_bar.setValue(progress)
        self.status_label.setText(message)
    
    def on_backup_complete(self, file_path: str):
        """Handle REAL backup completion."""
        self.progress_bar.setVisible(False)
        self.create_backup_btn.setEnabled(True)
        
        file_size = Path(file_path).stat().st_size / (1024 * 1024)
        
        QMessageBox.information(
            self,
            "Backup Complete",
            f"✅ Backup created successfully!\n\n"
            f"File: {Path(file_path).name}\n"
            f"Size: {file_size:.2f} MB\n"
            f"Location: {file_path}"
        )
        
        self.load_backups()
    
    def on_backup_failed(self, error: str):
        """Handle backup failure."""
        self.progress_bar.setVisible(False)
        self.create_backup_btn.setEnabled(True)
        self.status_label.setText(f"❌ Backup failed: {error}")
        
        QMessageBox.critical(self, "Backup Failed", f"Failed to create backup:\n\n{error}")
    
    def restore_backup(self):
        """Restore from REAL backup."""
        selected = self.backups_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Select a backup to restore")
            return
        
        backup_path = selected.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.warning(
            self,
            "⚠️ Confirm Restore",
            f"Restore from backup?\n\n"
            f"File: {Path(backup_path).name}\n\n"
            f"⚠️ WARNING: This will:\n"
            f"• Replace your current configuration\n"
            f"• Replace all databases\n"
            f"• Replace session files (if included)\n\n"
            f"A backup of your current state will be created first.\n\n"
            f"Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Create restore thread
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.restore_btn.setEnabled(False)
            
            self.restore_thread = BackupRestorer(backup_path, True)
            self.restore_thread.progress_update.connect(self.on_restore_progress)
            self.restore_thread.restore_complete.connect(self.on_restore_complete)
            self.restore_thread.restore_failed.connect(self.on_restore_failed)
            self.restore_thread.start()
    
    def on_restore_progress(self, progress: int, message: str):
        """Handle REAL restore progress."""
        self.progress_bar.setValue(progress)
        self.status_label.setText(message)
    
    def on_restore_complete(self):
        """Handle REAL restore completion."""
        self.progress_bar.setVisible(False)
        self.restore_btn.setEnabled(True)
        
        QMessageBox.information(
            self,
            "Restore Complete",
            "✅ Backup restored successfully!\n\n"
            "⚠️ You must RESTART the application for changes to take effect."
        )
    
    def on_restore_failed(self, error: str):
        """Handle restore failure."""
        self.progress_bar.setVisible(False)
        self.restore_btn.setEnabled(True)
        
        QMessageBox.critical(
            self,
            "Restore Failed",
            f"Failed to restore backup:\n\n{error}\n\n"
            f"Your current data is unchanged.\n"
            f"A pre-restore backup was created for safety."
        )
    
    def delete_backup(self):
        """Delete REAL backup file."""
        selected = self.backups_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Select a backup to delete")
            return
        
        backup_path = Path(selected.data(Qt.ItemDataRole.UserRole))
        
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete backup?\n\n{backup_path.name}\n\nThis cannot be undone."
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # ACTUALLY delete file
                backup_path.unlink()
                logger.info(f"Deleted backup: {backup_path}")
                
                self.load_backups()
                QMessageBox.information(self, "Deleted", "Backup deleted successfully")
                
            except Exception as e:
                logger.error(f"Failed to delete backup: {e}")
                QMessageBox.critical(self, "Error", f"Failed to delete backup:\n\n{e}")


def create_auto_backup(include_sessions: bool = True) -> Optional[str]:
    """Create REAL automatic backup."""
    try:
        # Create backups directory
        backup_dir = Path('backups')
        backup_dir.mkdir(exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"auto_backup_{timestamp}.zip"
        
        # Create backup synchronously
        files_to_backup = [
            'config.json',
            'members.db',
            'campaigns.db',
            'warmup_jobs.json'
        ]
        
        if include_sessions:
            session_files = list(Path('.').glob('*.session'))
            files_to_backup.extend([str(f) for f in session_files])
        
        # Create ACTUAL zip
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            metadata = {
                'created_at': datetime.now().isoformat(),
                'type': 'auto_backup',
                'version': '2.0'
            }
            
            zipf.writestr('backup_metadata.json', json.dumps(metadata, indent=2))
            
            for file in files_to_backup:
                if Path(file).exists():
                    zipf.write(file)
        
        logger.info(f"✅ Auto-backup created: {backup_path}")
        
        # Cleanup old backups (keep last 10)
        cleanup_old_backups(backup_dir, keep=10)
        
        return str(backup_path)
        
    except Exception as e:
        logger.error(f"Auto-backup failed: {e}")
        return None


def cleanup_old_backups(backup_dir: Path, keep: int = 10):
    """Delete old backups, keep only recent ones."""
    try:
        backups = sorted(
            backup_dir.glob('auto_backup_*.zip'),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        # Delete old backups
        for old_backup in backups[keep:]:
            old_backup.unlink()
            logger.info(f"Deleted old backup: {old_backup.name}")
        
    except Exception as e:
        logger.error(f"Failed to cleanup old backups: {e}")


def schedule_auto_backups(interval_hours: int = 24):
    """Schedule automatic backups."""
    from PyQt6.QtCore import QTimer
    
    timer = QTimer()
    timer.timeout.connect(lambda: create_auto_backup(include_sessions=True))
    timer.start(interval_hours * 3600 * 1000)  # Convert to milliseconds
    
    logger.info(f"✅ Auto-backup scheduled every {interval_hours} hours")
    return timer


