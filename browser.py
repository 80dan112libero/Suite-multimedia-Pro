import os
# Silenzia l'avviso DPI di Qt6 su Windows prima di caricare altre librerie
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false"
import sys
import json # Import json for bookmarks
import time
try:
    from PyQt6.QtCore import QUrl, Qt, QSize, QPropertyAnimation
    from PyQt6.QtWidgets import (QApplication, QMainWindow, QLineEdit, QToolBar, QFileDialog, QLabel,
                                 QMessageBox, QStyle, QTabWidget, QWidget, QVBoxLayout, 
                                 QPushButton, QInputDialog, QMenu, QToolButton,
                                 QSizePolicy)
    from PyQt6.QtGui import QAction, QIcon, QKeySequence
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEngineProfile, QWebEnginePage
except ImportError:
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Errore Libreria", "Librerie Browser mancanti.\nEsegui: pip install PyQt6 PyQt6-WebEngine")
    sys.exit()

# Define a default bookmarks file path
BOOKMARKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bookmarks.json')
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'history.json')
PASSWORDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'passwords.json')
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')

class ModernBrowser(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Web Browser - Suite Multimediale di Daniele Barile")
        self.setMinimumSize(1200, 800)

        # Container principale con layout verticale
        self.main_container = QWidget()
        self.main_layout = QVBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.setCentralWidget(self.main_container)

        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True) # Make tabs look more modern
        self.tab_widget.setTabsClosable(True) # Allow closing tabs
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.current_tab_changed) # Connect signal for tab changes
        self.main_layout.addWidget(self.tab_widget)

        self.setup_persistent_profile()

        self.bookmarks = [] 
        self.history = []
        self.passwords = []
        self.settings = {"homepage": "https://www.google.it", "last_tabs": []}

        self.load_bookmarks()
        self.load_history()
        self.load_passwords()
        self.load_settings()

        self.setup_ui()
        self.apply_modern_style()
        self.start_animation()

        # Ripristina l'ultima sessione o apri la homepage
        last_tabs = self.settings.get("last_tabs", [])
        if last_tabs:
            for url_str in last_tabs:
                self.add_new_tab(QUrl(url_str))
        else:
            self.add_new_tab(QUrl(self.settings.get("homepage", "https://www.google.it")), "Nuova Scheda")

    def setup_persistent_profile(self):
        """Configura il profilo per memorizzare sessioni, cookie e dati dei siti (es. YouTube History)."""
        self.profile = QWebEngineProfile.defaultProfile()
        storage_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_data")
        if not os.path.exists(storage_path):
            os.makedirs(storage_path)
        
        self.profile.setPersistentStoragePath(storage_path)
        self.profile.setCachePath(os.path.join(storage_path, "cache"))
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        
        # Imposta un User Agent moderno (fondamentale per la persistenza dell'account Google)
        self.profile.setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        
        # Connetti il segnale per i download
        self.profile.downloadRequested.connect(self.handle_download)

    def apply_modern_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #121212; color: #ffffff; font-family: 'Segoe UI Variable', 'Segoe UI'; }
            QPushButton { border-radius: 8px; padding: 6px 12px; } /* Arrotonda i QPushButton */
            QToolButton { border-radius: 8px; padding: 4px; } /* Arrotonda i QToolButton */
            QToolBar { background-color: #1e1e1e; border: none; border-bottom: 1px solid #333333; spacing: 8px; padding: 6px; }
            QLineEdit { background-color: #1e1e1e; color: #ffffff; border: 1px solid #D4AF37; border-radius: 6px; padding: 6px 12px; font-size: 13px; }
            QLineEdit:focus { border: 1px solid #ffffff; background-color: #1e1e1e; }
            QTabWidget::pane { border: none; background: #1e1e1e; }
            QTabBar::tab { background: #e5e5e5; color: #5d5d5d; padding: 8px 16px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; }
            QTabBar::tab:selected { background: #f3f3f3; color: #D4AF37; border-bottom: 2px solid #D4AF37; font-weight: bold; }
            QMenu { background-color: #ffffff; color: #1a1a1a; border: 1px solid #d1d1d1; border-radius: 8px; padding: 5px; }
            QMenu::item:selected { background-color: #D4AF37; color: #ffffff; }
            QToolButton { color: #1a1a1a; }
        """)

    def start_animation(self):
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(1000)
        self.anim.setStartValue(0)
        self.anim.setEndValue(1)
        self.anim.start()

    @property
    def current_browser(self):
        """Returns the QWebEngineView of the currently active tab."""
        return self.tab_widget.currentWidget()

    def setup_ui(self):
        # Main Toolbar
        self.main_toolbar = QToolBar("Navigazione Principale")
        self.main_toolbar.setIconSize(QSize(24, 24))
        self.main_toolbar.setMovable(False)
        self.addToolBar(self.main_toolbar)

        # --- Pulsanti di Navigazione ---
        self.back_act = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack), "Indietro", self)
        self.back_act.triggered.connect(lambda: self.current_browser.back() if self.current_browser else None)
        self.main_toolbar.addAction(self.back_act)

        self.forward_act = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward), "Avanti", self)
        self.forward_act.triggered.connect(lambda: self.current_browser.forward() if self.current_browser else None)
        self.main_toolbar.addAction(self.forward_act)

        self.reload_act = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload), "Ricarica", self)
        self.reload_act.triggered.connect(lambda: self.current_browser.reload() if self.current_browser else None)
        self.main_toolbar.addAction(self.reload_act)

        self.home_act = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon), "Home", self)
        self.home_act.triggered.connect(lambda: self.current_browser.setUrl(QUrl(self.settings.get("homepage", "https://www.google.it"))) if self.current_browser else None)
        self.main_toolbar.addAction(self.home_act)

        # --- Barra degli Indirizzi ---
        self.address_bar = QLineEdit()
        self.address_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.address_bar.setMinimumWidth(800)
        self.address_bar.setPlaceholderText("Cerca su Google o digita un indirizzo")
        self.address_bar.returnPressed.connect(self.navigate_to_url)
        self.main_toolbar.addWidget(self.address_bar)

        # --- Controlli Zoom ---
        zoom_in = QAction("Zoom +", self)
        zoom_in.setShortcut(QKeySequence("Ctrl++"))
        zoom_in.triggered.connect(lambda: self.current_browser.setZoomFactor(self.current_browser.zoomFactor() + 0.1) if self.current_browser else None)
        self.addAction(zoom_in)

        zoom_out = QAction("Zoom -", self)
        zoom_out.setShortcut(QKeySequence("Ctrl+-"))
        zoom_out.triggered.connect(lambda: self.current_browser.setZoomFactor(max(0.2, self.current_browser.zoomFactor() - 0.1)) if self.current_browser else None)
        self.addAction(zoom_out)

        # --- Pulsante Preferiti (Stella) ---
        self.star_act = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton), "Aggiungi ai preferiti", self)
        self.star_act.triggered.connect(self.add_current_page_as_bookmark)
        self.main_toolbar.addAction(self.star_act)

        # --- Estensioni e Profilo (Simulati) ---
        self.main_toolbar.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarContextHelpButton), "Estensioni")
        self.main_toolbar.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation), "Profilo")

        # --- Pulsante Menu Principale (Chrome Menu) ---
        self.menu_button = QToolButton()
        self.menu_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMenuButton))
        self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.main_menu = QMenu(self)
        self.main_menu.aboutToShow.connect(self.refresh_chrome_menu)
        self.menu_button.setMenu(self.main_menu)
        self.main_toolbar.addWidget(self.menu_button)

        # Bookmarks Toolbar
        self.bookmarks_toolbar = QToolBar("Preferiti")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.bookmarks_toolbar) # Add below main toolbar
        self.refresh_bookmarks_bar() # Populate bookmarks bar

        # Footer Brand
        self.footer_label = QLabel("Powered by Daniele Barile")
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer_label.setStyleSheet("color: #d4af37; font-family: 'Helvetica'; font-size: 18px; font-weight: bold; margin-top: 2px; margin-bottom: 2px;")
        self.main_layout.addWidget(self.footer_label)

    def refresh_chrome_menu(self):
        self.main_menu.clear()

        # Gruppo Schede
        new_tab_act = QAction("Nuova scheda", self)
        new_tab_act.setShortcut(QKeySequence("Ctrl+T"))
        new_tab_act.triggered.connect(lambda: self.add_new_tab(QUrl(self.settings.get("homepage"))))
        self.main_menu.addAction(new_tab_act)

        new_win_act = QAction("Nuova finestra", self)
        new_win_act.setShortcut(QKeySequence("Ctrl+N"))
        new_win_act.triggered.connect(lambda: os.startfile(__file__))
        self.main_menu.addAction(new_win_act)

        self.main_menu.addSeparator()

        # Utility
        hist_menu = self.main_menu.addMenu("Cronologia")
        hist_menu.addAction("Cancella cronologia").triggered.connect(self.clear_history)
        hist_menu.addSeparator()
        if not self.history:
            hist_menu.addAction("Vuota").setEnabled(False)
        for h in self.history[:15]:
            ha = QAction(f"{h['title'][:40]}...", self)
            ha.triggered.connect(lambda checked, url=h['url']: self.add_new_tab(QUrl(url), h['title']))
            hist_menu.addAction(ha)
        
        down_act = QAction("Download", self)
        down_act.setShortcut(QKeySequence("Ctrl+J"))
        down_act.triggered.connect(lambda: os.startfile(os.path.expanduser("~/Downloads")))
        self.main_menu.addAction(down_act)

        # Sottomenu Preferiti
        book_menu = self.main_menu.addMenu("Preferiti")
        book_menu.addAction("Gestisci preferiti").triggered.connect(lambda: QMessageBox.information(self, "Preferiti", "Gestore in arrivo..."))
        book_menu.addSeparator()
        for bm in self.bookmarks:
            ba = QAction(bm['title'], self)
            ba.triggered.connect(lambda checked, url=bm['url']: self.add_new_tab(QUrl(url), bm['title']))
            book_menu.addAction(ba)

        self.main_menu.addSeparator()

        # Gestione Password
        pwd_menu = self.main_menu.addMenu("Password")
        pwd_menu.addAction("Salva login corrente").triggered.connect(self.save_current_password)
        pwd_menu.addAction("Mostra password salvate").triggered.connect(self.manage_passwords)

        # Azioni Pagina
        print_act = QAction("Stampa...", self)
        print_act.setShortcut(QKeySequence("Ctrl+P"))
        print_act.triggered.connect(lambda: QMessageBox.information(self, "Stampa", "Invio alla stampante di sistema..."))
        self.main_menu.addAction(print_act)

        find_act = QAction("Trova...", self)
        find_act.setShortcut(QKeySequence("Ctrl+F"))
        find_act.triggered.connect(self.find_in_page)
        self.main_menu.addAction(find_act)

        self.main_menu.addSeparator()
        self.main_menu.addAction("Impostazioni").triggered.connect(self.open_settings)
        self.main_menu.addAction("Esci").triggered.connect(self.close)

    def add_new_tab(self, qurl=None, title="Nuova Scheda"):
        browser = QWebEngineView()
        # Crea una nuova pagina associata al profilo persistente
        page = QWebEnginePage(self.profile, browser)
        browser.setPage(page)
        
        settings = browser.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)

        if qurl:
            browser.setUrl(qurl)
        else:
            browser.setUrl(QUrl(self.settings.get("homepage", "https://www.google.it")))

        index = self.tab_widget.addTab(browser, title)
        self.tab_widget.setCurrentIndex(index)

        # Connect signals for the new browser
        browser.urlChanged.connect(self.update_address_bar)
        browser.loadFinished.connect(lambda ok: self.add_to_history(browser.url(), browser.title()) if ok else None)
        browser.titleChanged.connect(self.update_tab_title)
        browser.loadFinished.connect(lambda ok: self.update_tab_icon(browser, ok))

        self.update_address_bar(browser.url()) # Update address bar for the new tab

    def handle_download(self, download):
        """Gestisce le richieste di download in stile Chrome."""
        suggested_path = os.path.join(os.path.expanduser("~/Downloads"), download.suggestedFileName())
        path, _ = QFileDialog.getSaveFileName(self, "Salva file come...", suggested_path)
        
        if path:
            download.setDownloadDirectory(os.path.dirname(path))
            download.setDownloadFileName(os.path.basename(path))
            download.accept()
            
            download.finished.connect(lambda: QMessageBox.information(self, "Download", f"Download completato:\n{os.path.basename(path)}"))
        else:
            download.cancel()

    def close_tab(self, index):
        if self.tab_widget.count() < 2:
            self.close() # Close application if only one tab is left
            return
        self.tab_widget.removeTab(index)

    def current_tab_changed(self, index):
        if self.current_browser:
            self.update_address_bar(self.current_browser.url())
            self.setWindowTitle(f"{self.current_browser.title()} - Suite Ufficio")
        else:
            self.address_bar.clear()
            self.setWindowTitle("Web Browser - Suite Ufficio")

    def open_local_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Apri Documento", "", 
            "Tutti i file supportati (*.pdf *.html *.htm *.txt *.docx *.doc *.odt *.csv);;"
            "Documenti Office (*.docx *.doc *.odt);;"
            "Web Pages (*.html *.htm);;PDF (*.pdf);;Tutti i file (*.*)"
        )
        if file_path:
            ext = file_path.lower().split('.')[-1]
            # Gestione formati non renderizzabili direttamente nel browser
            office_exts = ['doc', 'docx', 'odt', 'csv']
            if ext in office_exts:
                reply = QMessageBox.question(self, "Apri Documento", 
                    f"Il formato .{ext} non può essere visualizzato direttamente nel browser.\nVuoi aprirlo con l'applicazione di sistema?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    os.startfile(file_path)
            else:
                self.add_new_tab(QUrl.fromLocalFile(file_path), os.path.basename(file_path))

    def find_in_page(self):
        text, ok = QInputDialog.getText(self, "Trova", "Cerca testo nella pagina:")
        if ok and text and self.current_browser:
            # Cerca il testo. findText evidenzia automaticamente le occorrenze
            self.current_browser.findText(text)

    def navigate_to_url(self):
        text = self.address_bar.text().strip()
        if not text: return
        
        if self.current_browser:
            if os.path.exists(text):
                self.current_browser.setUrl(QUrl.fromLocalFile(os.path.abspath(text)))
            elif "." in text and " " not in text:
                if not text.startswith(("http://", "https://", "file://")):
                    text = "https://" + text
                self.current_browser.setUrl(QUrl(text))
            else:
                self.current_browser.setUrl(QUrl(f"https://www.google.com/search?q={text}"))

    def update_address_bar(self, qurl):
        if self.current_browser == self.sender(): # Only update if it's the current tab's URL
            self.address_bar.setText(qurl.toString())
            self.address_bar.setCursorPosition(0)

    def update_tab_title(self, title):
        if self.current_browser == self.sender(): # Only update if it's the current tab
            index = self.tab_widget.indexOf(self.sender())
            self.tab_widget.setTabText(index, title)
            self.setWindowTitle(f"{title} - Suite Multimediale di Daniele Barile")

    def update_tab_icon(self, browser, ok):
        if ok:
            index = self.tab_widget.indexOf(browser)
            # QWebEngineView doesn't directly expose favicon, so we'll use a generic icon for now
            self.tab_widget.setTabIcon(index, self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))

    # --- Bookmarks functionality ---
    def load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
            except: self.history = []
        else: self.history = []

    def save_history(self):
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=4)
        except: pass

    def add_to_history(self, qurl, title):
        url = qurl.toString()
        if not url or url == "about:blank" or "google.com/search" in url: return
        if self.history and self.history[0]['url'] == url: return
        entry = {"title": title if title else url, "url": url, "time": time.strftime("%Y-%m-%d %H:%M")}
        self.history.insert(0, entry)
        self.history = self.history[:200]
        self.save_history()

    def clear_history(self):
        if QMessageBox.question(self, "Cronologia", "Vuoi cancellare tutta la cronologia?") == QMessageBox.StandardButton.Yes:
            self.history = []
            self.save_history()

    def load_passwords(self):
        if os.path.exists(PASSWORDS_FILE):
            try:
                with open(PASSWORDS_FILE, 'r', encoding='utf-8') as f:
                    self.passwords = json.load(f)
            except: self.passwords = []
        else: self.passwords = []

    def save_passwords(self):
        try:
            with open(PASSWORDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.passwords, f, indent=4)
        except: pass

    def save_current_password(self):
        if not self.current_browser: return
        url = self.current_browser.url().host()
        user, ok1 = QInputDialog.getText(self, "Salva Password", f"Username per {url}:")
        if ok1 and user:
            pwd, ok2 = QInputDialog.getText(self, "Salva Password", "Password:", QLineEdit.EchoMode.Password)
            if ok2 and pwd:
                self.passwords.append({"site": url, "user": user, "password": pwd})
                self.save_passwords()

    def manage_passwords(self):
        if not self.passwords:
            QMessageBox.information(self, "Password", "Nessuna password salvata.")
            return
        msg = "Credenziali salvate:\n\n" + "\n".join([f"{p['site']}: {p['user']} / {p['password']}" for p in self.passwords])
        QMessageBox.information(self, "Gestore Password", msg)

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
            except: self.settings = {"homepage": "https://www.google.it"}
        else: self.settings = {"homepage": "https://www.google.it"}

    def save_settings(self):
        # Memorizza le schede correnti per la prossima sessione
        tabs = []
        for i in range(self.tab_widget.count()):
            w = self.tab_widget.widget(i)
            if isinstance(w, QWebEngineView):
                tabs.append(w.url().toString())
        self.settings['last_tabs'] = tabs

        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4)
        except: pass

    def open_settings(self):
        new_hp, ok = QInputDialog.getText(self, "Impostazioni", "Pagina iniziale:", QLineEdit.EchoMode.Normal, self.settings.get('homepage'))
        if ok and new_hp:
            self.settings['homepage'] = new_hp
            self.save_settings()

    def load_bookmarks(self):
        if os.path.exists(BOOKMARKS_FILE):
            try:
                with open(BOOKMARKS_FILE, 'r', encoding='utf-8') as f:
                    self.bookmarks = json.load(f)
            except json.JSONDecodeError:
                self.bookmarks = []
                QMessageBox.warning(self, "Errore Preferiti", "Il file dei preferiti è corrotto. Creazione di un nuovo file.")
        else:
            self.bookmarks = []

    def save_bookmarks(self):
        try:
            with open(BOOKMARKS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.bookmarks, f, indent=4)
        except Exception as e:
            QMessageBox.critical(self, "Errore Salvataggio Preferiti", f"Impossibile salvare i preferiti: {e}")

    def refresh_bookmarks_bar(self):
        # Clear existing bookmark buttons
        self.bookmarks_toolbar.clear()

        # Add buttons for each bookmark
        for bookmark in self.bookmarks:
            action = QAction(bookmark['title'], self)
            action.triggered.connect(lambda checked, url=bookmark['url']: self.add_new_tab(QUrl(url), bookmark['title']))
            self.bookmarks_toolbar.addAction(action)

    def add_current_page_as_bookmark(self):
        if not self.current_browser:
            QMessageBox.warning(self, "Aggiungi Preferito", "Nessuna pagina aperta da aggiungere ai preferiti.")
            return

        current_url = self.current_browser.url().toString()
        current_title = self.current_browser.title()

        # Check if already bookmarked
        for bm in self.bookmarks:
            if bm['url'] == current_url:
                QMessageBox.information(self, "Aggiungi Preferito", "Questa pagina è già tra i preferiti.")
                return

        # Prompt user for title
        title, ok = QInputDialog.getText(self, "Aggiungi Preferito", "Titolo del preferito:", QLineEdit.EchoMode.Normal, current_title)
        if ok and title:
            self.bookmarks.append({"title": title, "url": current_url})
            self.save_bookmarks()
            self.refresh_bookmarks_bar()

    def closeEvent(self, event):
        self.save_bookmarks() 
        self.save_history()
        self.save_passwords()
        self.save_settings()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModernBrowser()
    window.showMaximized()
    sys.exit(app.exec())


#ciao a tutti!