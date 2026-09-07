

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QGroupBox, QCheckBox, QDoubleSpinBox,
                             QSpinBox, QTabWidget, QMessageBox, QFileDialog)
from PyQt6.QtCore import Qt, QTimer
from datetime import datetime

class SettingsPage(QWidget):
    """System settings page"""
    
    def __init__(self, db, theme_manager):
        super().__init__()
        self.db = db
        self.theme_manager = theme_manager
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QLabel("System Settings")
        header.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(header)
        
        # Tab widget
        tabs = QTabWidget()
        
        # General settings
        general_tab = self.create_general_tab()
        tabs.addTab(general_tab, "General")
        
        # Thresholds
        thresholds_tab = self.create_thresholds_tab()
        tabs.addTab(thresholds_tab, "Thresholds")
        
        # Database settings
        db_tab = self.create_database_tab()
        tabs.addTab(db_tab, "Database")
        
        layout.addWidget(tabs)
        
        # Save button
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setMinimumHeight(40)
        self.save_btn.clicked.connect(self.save_settings)
        layout.addWidget(self.save_btn)
        
        self.setLayout(layout)
    
    def create_general_tab(self):
        """Create general settings tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Theme
        theme_group = QGroupBox("Theme")
        theme_layout = QVBoxLayout()
        self.theme_check = QCheckBox("Use Dark Theme")
        self.theme_check.setChecked(self.theme_manager.current_theme == "dark")
        self.theme_check.toggled.connect(self.theme_manager.toggle_theme)
        theme_layout.addWidget(self.theme_check)
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)
        
        # Monitoring
        monitor_group = QGroupBox("Monitoring")
        monitor_layout = QVBoxLayout()
        self.auto_refresh = QCheckBox("Enable Auto-Refresh")
        self.real_time = QCheckBox("Enable Real-Time Monitoring")
        self.auto_optimize = QCheckBox("Auto-Optimize Schedule")
        monitor_layout.addWidget(self.auto_refresh)
        monitor_layout.addWidget(self.real_time)
        monitor_layout.addWidget(self.auto_optimize)
        monitor_group.setLayout(monitor_layout)
        layout.addWidget(monitor_group)
        
        layout.addStretch()
        tab.setLayout(layout)
        return tab
    
    def create_thresholds_tab(self):
        """Create thresholds settings tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        thresholds = [
            ("Loss Threshold (%)", "loss_threshold", 0, 50, 5.0),
            ("Overload Threshold (%)", "overload_threshold", 0, 100, 80.0),
            ("Spike Threshold (%)", "spike_threshold", 0, 100, 20.0),
            ("MAPE Threshold (%)", "mape_threshold", 0, 50, 10.0),
        ]
        
        self.threshold_inputs = {}
        
        for label, key, min_val, max_val, default in thresholds:
            group = QGroupBox(label)
            layout_group = QHBoxLayout()
            
            spin = QDoubleSpinBox()
            spin.setRange(min_val, max_val)
            spin.setValue(float(self.db.get_setting(key) or default))
            spin.setSuffix(" %")
            layout_group.addWidget(spin)
            
            group.setLayout(layout_group)
            layout.addWidget(group)
            
            self.threshold_inputs[key] = spin
        
        # Retention
        retention_group = QGroupBox("Data Retention")
        retention_layout = QHBoxLayout()
        self.retention_spin = QSpinBox()
        self.retention_spin.setRange(1, 365)
        self.retention_spin.setValue(int(self.db.get_setting('retention_days') or 30))
        self.retention_spin.setSuffix(" days")
        retention_layout.addWidget(self.retention_spin)
        retention_group.setLayout(retention_layout)
        layout.addWidget(retention_group)
        
        layout.addStretch()
        tab.setLayout(layout)
        return tab
    
    def create_database_tab(self):
        """Create database settings tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Database info
        info_group = QGroupBox("Database Information")
        info_layout = QVBoxLayout()
        
        # Get database size
        import os
        if os.path.exists("database.db"):
            size = os.path.getsize("database.db") / (1024 * 1024)
            info_layout.addWidget(QLabel(f"Database Size: {size:.2f} MB"))
        
        # Get record counts
        tables = ['users', 'datasets', 'feeder_data', 'forecasts', 'schedules', 'alerts', 'logs']
        for table in tables:
            count = self.db.fetch_all(f"SELECT COUNT(*) as count FROM {table}")[0]['count']
            info_layout.addWidget(QLabel(f"{table}: {count} records"))
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Backup
        backup_group = QGroupBox("Backup")
        backup_layout = QVBoxLayout()
        
        backup_btn = QPushButton("Backup Database")
        backup_btn.clicked.connect(self.backup_database)
        backup_layout.addWidget(backup_btn)
        
        restore_btn = QPushButton("Restore Database")
        restore_btn.clicked.connect(self.restore_database)
        backup_layout.addWidget(restore_btn)
        
        backup_group.setLayout(backup_layout)
        layout.addWidget(backup_group)
        
        # Cleanup
        cleanup_group = QGroupBox("Data Cleanup")
        cleanup_layout = QVBoxLayout()
        
        cleanup_btn = QPushButton("Clean Old Data")
        cleanup_btn.clicked.connect(self.cleanup_data)
        cleanup_layout.addWidget(cleanup_btn)
        
        cleanup_group.setLayout(cleanup_layout)
        layout.addWidget(cleanup_group)
        
        layout.addStretch()
        tab.setLayout(layout)
        return tab
    
    def load_settings(self):
        """Load settings from database"""
        # Load general settings
        self.auto_refresh.setChecked(self.db.get_setting('auto_refresh') == 'true')
        self.real_time.setChecked(self.db.get_setting('real_time_monitoring') == 'true')
        self.auto_optimize.setChecked(self.db.get_setting('auto_optimize') == 'true')
        
        # Load thresholds
        for key, spin in self.threshold_inputs.items():
            value = self.db.get_setting(key)
            if value:
                spin.setValue(float(value))
    
    def save_settings(self):
        """Save settings to database"""
        try:
            # Save general settings
            self.db.update_setting('auto_refresh', str(self.auto_refresh.isChecked()).lower())
            self.db.update_setting('real_time_monitoring', str(self.real_time.isChecked()).lower())
            self.db.update_setting('auto_optimize', str(self.auto_optimize.isChecked()).lower())
            
            # Save thresholds
            for key, spin in self.threshold_inputs.items():
                self.db.update_setting(key, str(spin.value()))
            
            # Save retention
            self.db.update_setting('retention_days', str(self.retention_spin.value()))
            
            QMessageBox.information(self, "Settings Saved", "Settings saved successfully")
            self.db.log_action("system", "settings_update", "Updated system settings")
            
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Error saving settings: {str(e)}")
    
    def backup_database(self):
        """Backup database"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Backup Database", f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
            "SQLite Database (*.db)"
        )
        
        if filename:
            import shutil
            try:
                shutil.copy2("database.db", filename)
                QMessageBox.information(self, "Backup Complete", f"Database backed up to:\n{filename}")
                self.db.log_action("system", "backup", "Database backup created")
            except Exception as e:
                QMessageBox.critical(self, "Backup Error", f"Error backing up database: {str(e)}")
    
    def restore_database(self):
        """Restore database from backup"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Restore Database", "", "SQLite Database (*.db)"
        )
        
        if filename:
            reply = QMessageBox.question(
                self, "Confirm Restore",
                "Restoring will overwrite current database. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                import shutil
                try:
                    shutil.copy2(filename, "database.db")
                    QMessageBox.information(self, "Restore Complete", "Database restored successfully")
                    self.db.log_action("system", "restore", "Database restored from backup")
                except Exception as e:
                    QMessageBox.critical(self, "Restore Error", f"Error restoring database: {str(e)}")
    
    def cleanup_data(self):
        """Clean old data based on retention"""
        retention_days = self.retention_spin.value()
        
        reply = QMessageBox.question(
            self, "Confirm Cleanup",
            f"Delete data older than {retention_days} days?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Delete old data
                cutoff_date = f"datetime('now', '-{retention_days} days')"
                
                tables = ['feeder_data', 'forecasts', 'schedules', 'alerts', 'logs']
                for table in tables:
                    self.db.execute_query(f"DELETE FROM {table} WHERE timestamp < {cutoff_date}")
                
                QMessageBox.information(self, "Cleanup Complete", f"Data older than {retention_days} days deleted")
                self.db.log_action("system", "cleanup", f"Cleaned data older than {retention_days} days")
                
            except Exception as e:
                QMessageBox.critical(self, "Cleanup Error", f"Error cleaning data: {str(e)}")