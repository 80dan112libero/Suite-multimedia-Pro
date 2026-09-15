import os
# Silenzia l'avviso DPI di Qt6 su Windows prima di caricare altre librerie.
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false"
import json
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                                 QHBoxLayout, QPushButton, QSlider, QLabel, 
                                 QFileDialog, QInputDialog, QStyle, QToolBar)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QUrl, QTime, QPropertyAnimation

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mediaplayer_settings.json")

class ModernMediaPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Media Player Pro - Suite Multimediale di Daniele Barile")
        self.setMinimumSize(900, 600)

        # Componenti Core
        self.media_player = QMediaPlayer()
        self.video_widget = QVideoWidget()
        self.audio_output = QAudioOutput()
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.setAudioOutput(self.audio_output)

        self.settings = self.load_settings()
        self.setup_ui()
        self.apply_modern_style()
        self.start_animation()
        
        if self.settings.get("last_file"):
            self.media_player.setSource(QUrl.fromLocalFile(self.settings["last_file"]))

        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        self.media_player.playbackStateChanged.connect(self.update_buttons)

    def apply_modern_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #121212; color: #ffffff; font-family: 'Segoe UI'; }
            QToolBar { background-color: #1e1e1e; border: none; border-bottom: 1px solid #333333; padding: 5px; }
            QPushButton { background-color: #D4AF37; color: #000000; border-radius: 6px; padding: 8px; font-weight: bold; min-width: 40px; }
            QPushButton:hover { background-color: #e5c05b; }
            QSlider::groove:horizontal { border: 1px solid #d1d1d1; height: 4px; background: #e5e5e5; border-radius: 2px; }
            QSlider::handle:horizontal { background: #D4AF37; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
            QLabel { color: #D4AF37; font-weight: bold; }
        """)

    def start_animation(self):
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(1000)
        self.anim.setStartValue(0)
        self.anim.setEndValue(1)
        self.anim.start()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Area Video
        layout.addWidget(self.video_widget, 1)

        # Slider del tempo
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.set_position)
        layout.addWidget(self.position_slider)

        # Controlli
        controls = QHBoxLayout()
        
        self.play_btn = QPushButton()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_btn.clicked.connect(self.play_pause)
        controls.addWidget(self.play_btn)

        self.stop_btn = QPushButton()
        self.stop_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_btn.clicked.connect(self.stop_video)
        controls.addWidget(self.stop_btn)

        self.time_lbl = QLabel("00:00 / 00:00")
        controls.addWidget(self.time_lbl)

        controls.addStretch()

        # Volume
        controls.addWidget(QLabel("Vol:"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.settings.get("volume", 70))
        self.audio_output.setVolume(0.7)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(lambda v: self.audio_output.setVolume(v / 100))
        controls.addWidget(self.volume_slider)

        layout.addLayout(controls)

        # Toolbar per File e Streaming
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        open_act = toolbar.addAction("Apri File")
        open_act.triggered.connect(self.open_file)
        
        stream_act = toolbar.addAction("Apri Stream URL")
        stream_act.triggered.connect(self.open_stream)

        # Footer Brand
        self.footer_label = QLabel("Powered by Daniele Barile")
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer_label.setStyleSheet("color: #d4af37; font-family: 'Helvetica'; font-size: 18px; font-weight: bold; margin-top: 2px; margin-bottom: 2px;")
        layout.addWidget(self.footer_label)

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    return json.load(f)
            except: pass
        return {"volume": 70, "last_file": "", "history": []}

    def save_settings(self):
        self.settings["volume"] = self.volume_slider.value()
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self.settings, f, indent=4)
        except: pass

    def closeEvent(self, event):
        self.save_settings()
        event.accept()

    def open_file(self):
        file_dialog = QFileDialog(self)
        path, _ = file_dialog.getOpenFileName(self, "Seleziona Media", "", 
            "Video (*.mp4 *.avi *.mkv *.mov *.wmv);;Audio (*.mp3 *.wav *.m4a);;Tutti i file (*.*)")
        if path:
            self.settings["last_file"] = path
            self.media_player.setSource(QUrl.fromLocalFile(path))
            self.media_player.play()

    def open_stream(self):
        url, ok = QInputDialog.getText(self, "Streaming", "Inserisci URL dello stream (http/rtsp):")
        if ok and url:
            self.media_player.setSource(QUrl(url))
            self.media_player.play()

    def play_pause(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def stop_video(self):
        self.media_player.stop()

    def update_buttons(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def position_changed(self, position):
        self.position_slider.setValue(position)
        self.update_duration_label(position, self.media_player.duration())

    def duration_changed(self, duration):
        self.position_slider.setRange(0, duration)

    def set_position(self, position):
        self.media_player.setPosition(position)

    def update_duration_label(self, current, total):
        curr_time = QTime(0, 0).addMSecs(current).toString("mm:ss")
        total_time = QTime(0, 0).addMSecs(total).toString("mm:ss")
        self.time_lbl.setText(f"{curr_time} / {total_time}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = ModernMediaPlayer()
    player.showMaximized()
    sys.exit(app.exec())