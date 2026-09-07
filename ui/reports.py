"""
Reports Page for SCADA System
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QComboBox, QDateEdit, QGroupBox, QGridLayout,
                             QFileDialog, QMessageBox, QProgressBar)
from PyQt6.QtCore import Qt, QDate, QThread, pyqtSignal
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import pandas as pd
import numpy as np
from datetime import datetime
import os

class ReportWorker(QThread):
    """Worker thread for report generation"""
    
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, report_type, start_date, end_date, db, output_path):
        super().__init__()
        self.report_type  = report_type
        self.start_date   = start_date
        self.end_date     = end_date
        self.db           = db
        self.output_path  = output_path   # user-chosen save path
        
    def run(self):
        try:
            self.progress.emit(10)
            if self.report_type == "Daily":
                self.generate_daily_report()
            elif self.report_type == "Loss":
                self.generate_loss_report()
            elif self.report_type == "Forecast":
                self.generate_forecast_report()
            elif self.report_type == "Schedule":
                self.generate_schedule_report()
            self.progress.emit(100)
            self.finished.emit(True, "Report generated successfully")
        except Exception as e:
            self.finished.emit(False, str(e))
    
    # ── shared style helper ───────────────────────────────────────────────────
    @staticmethod
    def _header_style():
        return TableStyle([
            ('BACKGROUND',   (0, 0), (-1,  0), colors.HexColor("#1e3a5f")),
            ('TEXTCOLOR',    (0, 0), (-1,  0), colors.whitesmoke),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',     (0, 0), (-1,  0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0), (-1,  0), 12),
            ('BOTTOMPADDING',(0, 0), (-1,  0), 10),
            ('BACKGROUND',   (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, colors.HexColor("#f1f5f9")]),
            ('GRID',         (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ])

    def _make_doc(self, pagesize=None):
        from reportlab.lib.pagesizes import letter
        return SimpleDocTemplate(
            self.output_path,
            pagesize=pagesize or letter,
            leftMargin=0.75*inch, rightMargin=0.75*inch,
            topMargin=0.75*inch,  bottomMargin=0.75*inch,
        )

    def _title_block(self, styles, title, subtitle=""):
        story = []
        title_style = ParagraphStyle(
            'ReportTitle', parent=styles['Heading1'],
            fontSize=20, spaceAfter=6, textColor=colors.HexColor("#0f172a"),
        )
        story.append(Paragraph(title, title_style))
        if subtitle:
            story.append(Paragraph(subtitle, styles['Normal']))
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  "
            f"Period: {self.start_date} to {self.end_date}",
            styles['Normal'],
        ))
        story.append(Spacer(1, 16))
        return story

    # ── Daily report ──────────────────────────────────────────────────────────
    def generate_daily_report(self):
        self.progress.emit(20)
        doc    = self._make_doc()
        styles = getSampleStyleSheet()
        story  = self._title_block(styles, "Daily SCADA Load Report",
                                   "Sukkur Power Distribution — Feeder Summary")

        df = self.db.get_feeder_data(self.start_date, self.end_date)
        self.progress.emit(50)

        if df.empty:
            story.append(Paragraph("No load data found for the selected date range.", styles['Normal']))
        else:
            # Overall summary table
            total_load = df['load'].sum()
            total_loss = df['loss'].sum() if 'loss' in df.columns else 0
            loss_pct   = (total_loss / total_load * 100) if total_load > 0 else 0
            peak_row   = df.loc[df['load'].idxmax()]

            summary_data = [
                ['Metric', 'Value'],
                ['Total Demand (MW)',   f"{total_load:,.2f}"],
                ['Average Demand (MW)', f"{df['load'].mean():.2f}"],
                ['Peak Demand (MW)',    f"{df['load'].max():.2f}"],
                ['Peak Time',           str(peak_row['timestamp'])[:16]],
                ['Peak Feeder',         str(peak_row.get('feeder', '—'))],
                ['Total System Loss (MW)', f"{total_loss:,.2f}"],
                ['Loss Percentage',     f"{loss_pct:.2f} %"],
            ]
            t = Table(summary_data, colWidths=[3.0*inch, 3.0*inch])
            t.setStyle(self._header_style())
            story.append(Paragraph("System Summary", styles['Heading2']))
            story.append(t)
            story.append(Spacer(1, 14))

            # Per-feeder breakdown
            self.progress.emit(70)
            grp = df.groupby('feeder').agg(
                avg_load=('load','mean'), peak_load=('load','max'),
                total_load=('load','sum'),
                total_loss=('loss','sum') if 'loss' in df.columns else ('load', 'count'),
            ).round(2).reset_index()

            feeder_data = [['Feeder', 'Avg Load (MW)', 'Peak (MW)', 'Total (MW)', 'Total Loss (MW)']]
            for _, row in grp.iterrows():
                feeder_data.append([
                    str(row['feeder']),
                    f"{row['avg_load']:.2f}",
                    f"{row['peak_load']:.2f}",
                    f"{row['total_load']:.2f}",
                    f"{row.get('total_loss', 0):.2f}",
                ])
            t2 = Table(feeder_data, colWidths=[2.2*inch, 1.3*inch, 1.2*inch, 1.2*inch, 1.3*inch])
            t2.setStyle(self._header_style())
            story.append(Paragraph("Feeder-Level Breakdown", styles['Heading2']))
            story.append(t2)

        self.progress.emit(90)
        doc.build(story)

    # ── Loss report ───────────────────────────────────────────────────────────
    def generate_loss_report(self):
        self.progress.emit(20)
        from reportlab.lib.pagesizes import landscape, letter as ltr
        doc    = self._make_doc(pagesize=landscape(ltr))
        styles = getSampleStyleSheet()
        story  = self._title_block(styles, "Technical Loss Analysis Report",
                                   "Non-Technical Loss Detection — Sukkur Distribution Network")

        df = self.db.get_feeder_data(self.start_date, self.end_date)
        self.progress.emit(50)

        if df.empty:
            story.append(Paragraph("No data found for the selected date range.", styles['Normal']))
        else:
            if 'loss' not in df.columns:
                df['loss'] = 0.0

            total_load = df['load'].sum()
            total_loss = df['loss'].sum()
            loss_pct   = (total_loss / total_load * 100) if total_load > 0 else 0

            story.append(Paragraph(
                f"Overall System Loss: <b>{loss_pct:.2f}%</b>  "
                f"(Total: {total_loss:,.1f} MW  /  Injected: {total_load:,.1f} MW)",
                styles['Normal'],
            ))
            story.append(Spacer(1, 12))

            # Loss by feeder
            self.progress.emit(65)
            lb = df.groupby('feeder')['loss'].agg(['mean','sum','std']).round(3).reset_index()
            loss_data = [['Feeder', 'Avg Loss (MW)', 'Total Loss (MW)', 'Std Dev (MW)', 'Loss %']]
            for _, row in lb.iterrows():
                feeder_load = df[df['feeder'] == row['feeder']]['load'].sum()
                fp = (row['sum'] / feeder_load * 100) if feeder_load > 0 else 0
                loss_data.append([
                    str(row['feeder']),
                    f"{row['mean']:.3f}",
                    f"{row['sum']:.2f}",
                    f"{row['std']:.3f}",
                    f"{fp:.2f}%",
                ])
            t = Table(loss_data, colWidths=[2.5*inch, 1.4*inch, 1.4*inch, 1.4*inch, 1.0*inch])
            t.setStyle(self._header_style())
            story.append(Paragraph("Loss by Feeder", styles['Heading2']))
            story.append(t)
            story.append(Spacer(1, 14))

            story.append(Paragraph("Recommendations", styles['Heading2']))
            recs = [
                "1. Conduct thermal imaging surveys on feeders with highest recorded losses.",
                "2. Upgrade aging distribution transformers on feeders with > 15% loss.",
                "3. Deploy capacitor banks for reactive power compensation.",
                "4. Audit smart-meter data against feeder injection records to identify energy theft.",
                "5. Balance phase loads across feeders to reduce neutral-conductor losses.",
            ]
            for r in recs:
                story.append(Paragraph(r, styles['Normal']))

        self.progress.emit(90)
        doc.build(story)

    # ── Forecast report ───────────────────────────────────────────────────────
    def generate_forecast_report(self):
        self.progress.emit(20)
        doc    = self._make_doc()
        styles = getSampleStyleSheet()
        story  = self._title_block(styles, "Short-Term Load Forecast Report",
                                   "AI Model Performance — Sukkur Distribution Network")
        self.progress.emit(40)

        # Pull stored metrics from model_registry.json
        try:
            import json, os
            from config import MODELS_DIR
            reg_path = os.path.join(MODELS_DIR, "model_registry.json")
            with open(reg_path) as f:
                registry = json.load(f)
        except Exception:
            registry = {}

        if not registry:
            story.append(Paragraph(
                "No trained model registry found. Run train_models_offline.py first.",
                styles['Normal'],
            ))
        else:
            self.progress.emit(60)
            rows = [['Feeder', 'Model', 'MAPE (%)', 'RMSE (MW)', 'R²', 'Epochs', 'Trained At']]
            for feeder, entry in registry.items():
                for model_type, info in entry.get('models', {}).items():
                    m = info.get('metrics', {})
                    rows.append([
                        feeder,
                        model_type,
                        f"{m.get('mape', '—'):.2f}" if isinstance(m.get('mape'), float) else '—',
                        f"{m.get('rmse', '—'):.3f}" if isinstance(m.get('rmse'), float) else '—',
                        f"{m.get('r2',   '—'):.4f}" if isinstance(m.get('r2'),   float) else '—',
                        str(info.get('epochs_trained', '—')),
                        str(entry.get('trained_at', '—'))[:10],
                    ])

            col_w = [1.8*inch, 0.8*inch, 0.9*inch, 0.9*inch, 0.8*inch, 0.7*inch, 1.0*inch]
            t = Table(rows, colWidths=col_w)
            t.setStyle(self._header_style())
            story.append(Paragraph("Model Registry — Performance Metrics", styles['Heading2']))
            story.append(t)
            story.append(Spacer(1, 12))
            story.append(Paragraph(
                "Target thresholds: MAPE < 5.0%  |  RMSE < 100 MW  |  R² > 0.95",
                styles['Normal'],
            ))

        # Also include any DB forecast rows if available
        self.progress.emit(80)
        try:
            df = self.db.get_forecast_data()
            if not df.empty and 'predicted_load' in df.columns:
                story.append(Spacer(1, 14))
                story.append(Paragraph("Recent Forecast Runs (from database)", styles['Heading2']))
                latest = df.sort_values('timestamp').groupby('feeder').tail(3)
                cols   = ['feeder', 'timestamp', 'predicted_load', 'model_used'] if 'model_used' in df.columns else ['feeder', 'timestamp', 'predicted_load']
                subset = latest[cols].copy()
                subset['timestamp'] = subset['timestamp'].astype(str).str[:16]
                tdata = [list(subset.columns)] + subset.values.tolist()
                t2 = Table([[str(c) for c in row] for row in tdata])
                t2.setStyle(self._header_style())
                story.append(t2)
        except Exception:
            pass

        doc.build(story)

    # ── Schedule report ───────────────────────────────────────────────────────
    def generate_schedule_report(self):
        self.progress.emit(20)
        from reportlab.lib.pagesizes import landscape, letter as ltr
        doc    = self._make_doc(pagesize=landscape(ltr))
        styles = getSampleStyleSheet()
        story  = self._title_block(styles, "Load Shedding Schedule Report",
                                   "Optimised Power Distribution — Sukkur Grid")
        self.progress.emit(40)

        # Try date-specific query first, then fall back to all records
        schedule = self.db.fetch_all(
            "SELECT * FROM schedules WHERE DATE(created_at) BETWEEN ? AND ? ORDER BY created_at DESC LIMIT 500",
            (self.start_date, self.end_date),
        )
        if not schedule:
            schedule = self.db.fetch_all(
                "SELECT * FROM schedules ORDER BY created_at DESC LIMIT 200"
            )
        self.progress.emit(65)

        if not schedule:
            story.append(Paragraph(
                "No schedule data found. Run the Optimization page to generate a schedule first.",
                styles['Normal'],
            ))
        else:
            PRIORITY_LABELS = {
                'critical': 'CRITICAL (Hospital)',
                'high':     'HIGH (Industrial)',
                'medium':   'MEDIUM (Commercial)',
                'low':      'LOW (Residential)',
            }
            sched_data = [['Hour', 'Feeder', 'Priority', 'Allocated (MW)', 'Demand (MW)', 'Status']]
            for item in schedule:
                alloc  = float(item.get('allocated_power') or 0)
                demand = float(item.get('demand_per_hour') or item.get('demand') or 0)
                status = "ON ✓" if alloc > 0 else "OFF ✗"
                sched_data.append([
                    str(item.get('hour', '—')),
                    str(item.get('feeder', '—')),
                    PRIORITY_LABELS.get(str(item.get('priority', '')), str(item.get('priority', '—'))),
                    f"{alloc:.2f}",
                    f"{demand:.2f}" if demand else "—",
                    status,
                ])

            col_w = [0.6*inch, 2.0*inch, 1.8*inch, 1.1*inch, 1.1*inch, 0.8*inch]
            t = Table(sched_data, colWidths=col_w, repeatRows=1)
            ts_style = self._header_style()
            # Colour ON rows green, OFF rows red
            for ri, row in enumerate(sched_data[1:], start=1):
                if row[-1].startswith("ON"):
                    ts_style.add('BACKGROUND', (5, ri), (5, ri), colors.HexColor("#dcfce7"))
                else:
                    ts_style.add('BACKGROUND', (5, ri), (5, ri), colors.HexColor("#fee2e2"))
            t.setStyle(ts_style)
            story.append(Paragraph(f"Schedule Details  ({len(sched_data)-1} entries)", styles['Heading2']))
            story.append(t)

        self.progress.emit(90)
        doc.build(story)

class ReportsPage(QWidget):
    """Reports generation page"""
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QLabel("Reports")
        header.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(header)
        
        # Report type
        type_group = QGroupBox("Report Type")
        type_layout = QVBoxLayout()
        self.report_combo = QComboBox()
        self.report_combo.addItems(["Daily", "Loss", "Forecast", "Schedule"])
        type_layout.addWidget(self.report_combo)
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)
        
        # Date range
        date_group = QGroupBox("Date Range")
        date_layout = QHBoxLayout()
        
        date_layout.addWidget(QLabel("From:"))
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addDays(-7))
        self.start_date.setCalendarPopup(True)
        date_layout.addWidget(self.start_date)
        
        date_layout.addWidget(QLabel("To:"))
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        date_layout.addWidget(self.end_date)
        
        date_group.setLayout(date_layout)
        layout.addWidget(date_group)
        
        # Generate button
        self.generate_btn = QPushButton("Generate Report")
        self.generate_btn.setMinimumHeight(50)
        self.generate_btn.clicked.connect(self.generate_report)
        layout.addWidget(self.generate_btn)
        
        # Export CSV button
        self.export_btn = QPushButton("Export to CSV")
        self.export_btn.clicked.connect(self.export_csv)
        layout.addWidget(self.export_btn)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # ── Live summary panel (units always visible) ──────────────────────
        summary_group = QGroupBox("Live system summary (last loaded data)")
        grid = QGridLayout()
        grid.setSpacing(8)

        def _stat_row(label, attr_name, row):
            lbl = QLabel(label)
            lbl.setStyleSheet("color:#64748b;font-size:12px;")
            val = QLabel("—")
            val.setStyleSheet("font-size:13px;font-weight:bold;")
            grid.addWidget(lbl, row, 0)
            grid.addWidget(val, row, 1)
            setattr(self, attr_name, val)

        _stat_row("Total metered load (sum of all feeders):",    "_sum_lbl",  0)
        _stat_row("Average hourly load per feeder:",             "_avg_lbl",  1)
        _stat_row("Peak load recorded:",                         "_peak_lbl", 2)
        _stat_row("Total system loss:",                          "_loss_lbl", 3)
        _stat_row("Overall loss percentage:",                    "_lpct_lbl", 4)
        _stat_row("Number of active alerts:",                    "_alrt_lbl", 5)

        summary_group.setLayout(grid)
        layout.addWidget(summary_group)
        self._refresh_summary()

        layout.addStretch()
        self.setLayout(layout)
    
    def _refresh_summary(self):
        """Populate the live summary panel with units."""
        try:
            df = self.db.get_feeder_data()
            if df.empty:
                for attr in ("_sum_lbl","_avg_lbl","_peak_lbl","_loss_lbl","_lpct_lbl"):
                    getattr(self, attr).setText("No data loaded")
                self._alrt_lbl.setText("—")
                return
            total_load = df['load'].sum()
            avg_load   = df.groupby('feeder')['load'].mean().mean()
            peak_load  = df['load'].max()
            peak_row   = df.loc[df['load'].idxmax()]
            total_loss = df['loss'].sum() if 'loss' in df.columns else 0
            loss_pct   = (total_loss / total_load * 100) if total_load > 0 else 0
            alerts     = len(self.db.get_active_alerts())

            self._sum_lbl.setText(f"{total_load:,.1f} MW  (across all feeders, all time periods)")
            self._avg_lbl.setText(f"{avg_load:.1f} MW  per feeder average")
            self._peak_lbl.setText(f"{peak_load:.1f} MW  — {peak_row['feeder']}  at  {str(peak_row['timestamp'])[:16]}")
            self._loss_lbl.setText(f"{total_loss:,.1f} MW  (sum of recorded line losses)")
            self._lpct_lbl.setText(f"{loss_pct:.1f} %  of total metered input")
            self._alrt_lbl.setText(f"{alerts}  unresolved alerts")
        except Exception as e:
            print(f"Summary refresh error: {e}")

    def generate_report(self):
        """Generate selected report — saves to user-chosen location."""
        report_type = self.report_combo.currentText()
        start_date  = self.start_date.date().toString("yyyy-MM-dd")
        end_date    = self.end_date.date().toString("yyyy-MM-dd")
        
        # Ask for save location BEFORE starting worker
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Report",
            f"{report_type.lower()}_report_{datetime.now().strftime('%Y%m%d')}.pdf",
            "PDF Files (*.pdf)",
        )
        
        if not filename:
            return   # user cancelled

        if not filename.endswith(".pdf"):
            filename += ".pdf"

        self.generate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Pass the chosen path directly to the worker
        self.worker = ReportWorker(report_type, start_date, end_date, self.db, filename)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(lambda s, m: self.report_finished(s, m, filename))
        self.worker.start()
    
    def report_finished(self, success, message, filename):
        """Handle report generation completion"""
        self.progress_bar.setVisible(False)
        self.generate_btn.setEnabled(True)
        
        if success:
            QMessageBox.information(
                self, "Report Generated",
                f"Report saved to:\n{filename}"
            )
            self.db.log_action("system", "report_generation", f"Generated {self.report_combo.currentText()} report")
        else:
            QMessageBox.critical(self, "Report Error", f"Error generating report: {message}")
    
    def export_csv(self):
        """Export data to CSV"""
        report_type = self.report_combo.currentText()
        start_date = self.start_date.date().toString("yyyy-MM-dd")
        end_date = self.end_date.date().toString("yyyy-MM-dd")
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", f"{report_type.lower()}_data.csv", "CSV Files (*.csv)"
        )
        
        if filename:
            try:
                if report_type == "Daily":
                    df = self.db.get_feeder_data(start_date, end_date)
                elif report_type == "Loss":
                    df = self.db.get_feeder_data(start_date, end_date)
                elif report_type == "Forecast":
                    df = self.db.get_forecast_data()
                elif report_type == "Schedule":
                    schedule = self.db.fetch_all(
                        "SELECT * FROM schedules WHERE schedule_date BETWEEN ? AND ?",
                        (start_date, end_date)
                    )
                    df = pd.DataFrame(schedule)
                
                if not df.empty:
                    df.to_csv(filename, index=False)
                    QMessageBox.information(self, "Export Successful", f"Data exported to {filename}")
                    self.db.log_action("system", "csv_export", f"Exported {report_type} data")
                else:
                    QMessageBox.warning(self, "No Data", "No data available for export")
            
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Error exporting data: {str(e)}")