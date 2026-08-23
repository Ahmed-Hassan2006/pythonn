impor
import re
from bs4 import BeautifulSoup
import pyperclip
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel, QListWidget, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from curl_cffi import requests as curl_requests

# ==========================================
# 0. نظام الاتصال الحصري والمقاوم للحظر
# ==========================================

class RobustSession:
    def __init__(self):  # تم التصحيح إلى __init__
        self.session = curl_requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

    def get(self, url, timeout=15):
        return self.session.get(url, impersonate="chrome120", timeout=timeout)

def get_soup(html_text):
    try:
        return BeautifulSoup(html_text, 'lxml')
    except Exception:
        return BeautifulSoup(html_text, 'html.parser')

def extract_numbers_from_anchors(soup, base_url, country_code_prefix=None):
    """مستخرج عام يجمع الأرقام ويفلتر الصفحات الرقمية (Pagination) تلقائياً"""
    numbers = []
    number_urls = {}
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.text.strip()

        clean_text = re.sub(r'[\s\-()]', '', text)
        
        if clean_text.startswith("+") and clean_text[1:].isdigit() and len(clean_text) >= 8:
            phone = clean_text
        elif clean_text.isdigit() and len(clean_text) >= 10:
            phone = "+" + clean_text
        else:
            match = re.search(r'\+?(\d{10,15})', href)
            if match:
                phone = "+" + match.group(1)
            else:
                continue
                
        # استبعاد أرقام الترقيم البريدي أو أرقام الصفحات القصيرة جداً
        if len(phone.replace("+", "")) < 8:
            continue
                
        if country_code_prefix:
            if not phone.startswith(country_code_prefix):
                continue
                
        if phone not in numbers:
            numbers.append(phone)
            if href.startswith('http'):
                full_url = href
            else:
                full_url = f"{base_url.rstrip('/')}/{href.lstrip('/')}"
            number_urls[phone] = full_url
            
    return numbers, number_urls

def parse_messages_generic(soup):
    messages = []
    table = soup.find('table')
    if table:
        rows = table.find_all('tr')
        for row in rows:
            cols = [td.text.strip() for td in row.find_all(['td', 'th'])]
            if len(cols) >= 2:
                if any(x in cols[0].lower() for x in ["sender", "from", "المرسل"]):
                    continue
                sender = cols[0]
                time_ago = cols[1] if len(cols) > 2 else "مؤخراً"
                text = cols[2] if len(cols) >= 3 else cols[1]
                messages.append({"sender": sender, "time": time_ago, "text": text})

    if not messages:
        for block in soup.find_all('div', class_=re.compile(r'message|msg|shadow-sm|card|comment|row', re.I)):
            text_nodes = [s.strip() for s in block.stripped_strings]
            if len(text_nodes) >= 2:
                sender = text_nodes[0]
                text = " ".join(text_nodes[1:])
                if len(sender) < 30 and len(text) > 5:
                    messages.append({"sender": sender, "time": "مؤخراً", "text": text})
    return messages

# ==========================================
# 1. محركات جلب الأرقام والرسائل (Scraping Engines)
# ==========================================

class ReceiveSmssEngine:
    def __init__(self):  # تم التصحيح إلى __init__
        self.base_url = "https://receive-smss.com"
        self.session = RobustSession()
        self.number_urls = {}

    def get_numbers(self, country):
        try:
            res = self.session.get(self.base_url, timeout=15)
            soup = get_soup(res.text)
            
            match = re.search(r'\((.*?)\)', country)
            prefix = match.group(1) if match else None
            
            numbers, urls = extract_numbers_from_anchors(soup, self.base_url, prefix)
            self.number_urls.update(urls)
            return numbers
        except Exception as e:
            raise Exception(f"فشل جلب الأرقام: {e}")

    def fetch_messages(self, number):
        try:
            url = self.number_urls.get(number) or f"{self.base_url}/sms/{number.replace('+', '')}/"
            res = self.session.get(url, timeout=15)
            soup = get_soup(res.text)
            return parse_messages_generic(soup)
        except Exception as e:
            raise Exception(f"فشل جلب الرسائل: {e}")

class Sms24Engine:
    def __init__(self):  # تم التصحيح إلى __init__
        self.base_url = "https://sms24.me"
        self.session = RobustSession()
        self.number_urls = {}

    def get_numbers(self, country_code):
        try:
            code = country_code.split()[0].lower()
            res = self.session.get(f"{self.base_url}/en/countries/{code}", timeout=15)
            soup = get_soup(res.text)
            
            numbers, urls = extract_numbers_from_anchors(soup, self.base_url)
            self.number_urls.update(urls)
            return numbers
        except Exception as e:
            raise Exception(f"تعذر الاتصال بالسيرفر: {e}")

    def fetch_messages(self, number):
        try:
            url = self.number_urls.get(number) or f"{self.base_url}/en/numbers/{number.replace('+', '')}"
            res = self.session.get(url, timeout=15)
            soup = get_soup(res.text)
            return parse_messages_generic(soup)
        except Exception as e:
            raise Exception(f"فشل جلب الرسائل: {e}")

class SmsOnlineCoEngine:
    def __init__(self):  # تم التصحيح إلى __init__
        self.base_url = "https://sms-online.co"
        self.session = RobustSession()
        self.number_urls = {}

    def get_numbers(self, country_code):
        try:
            match = re.search(r'\((.*?)\)', country_code)
            code = match.group(1).upper() if match else country_code.split()[0].upper()
            
            res = self.session.get(f"{self.base_url}/receive-free-sms", timeout=15)
            soup = get_soup(res.text)
            
            prefix_map = {"US": "+1", "UK": "+44", "SE": "+46", "MY": "+60", "PR": "+1"}
            prefix = prefix_map.get(code)
            
            numbers, urls = extract_numbers_from_anchors(soup, self.base_url, prefix)
            self.number_urls.update(urls)
            return numbers
        except Exception as e:
            raise Exception(f"فشل الاتصال بالسيرفر: {e}")

    def fetch_messages(self, number):
        try:
            url = self.number_urls.get(number) or f"{self.base_url}/receive-free-sms/{number.replace('+', '')}"
            res = self.session.get(url, timeout=15)
            soup = get_soup(res.text)
            return parse_messages_generic(soup)
        except Exception as e:
            raise Exception(f"فشل جلب الرسائل: {e}")

class AnonymSmsEngine:
    def __init__(self):  # تم التصحيح إلى __init__
        self.base_url = "https://anonymsms.com"
        self.session = RobustSession()
        self.number_urls = {}

    def get_numbers(self, country_code):
        try:
            match = re.search(r'\((.*?)\)', country_code)
            code = match.group(1).lower() if match else country_code.split()[0].lower()
            
            mapping = {
                "us": "united-states",
                "uk": "united-kingdom",
                "ca": "canada",
                "es": "spain",
                "ge": "georgia"
            }
            mapped_country = mapping.get(code, "united-states")
            
            res = self.session.get(f"{self.base_url}/{mapped_country}/", timeout=15)
            soup = get_soup(res.text)
            
            prefix_map = {
                "us": "+1",
                "uk": "+44",
                "ca": "+1",
                "es": "+34",
                "ge": "+995"
            }
            prefix = prefix_map.get(code)
            
            numbers, urls = extract_numbers_from_anchors(soup, self.base_url, prefix)
            self.number_urls.update(urls)
            return numbers
        except Exception as e:
            raise Exception(f"خطأ في الاتصال بالسيرفر: {e}")

    def fetch_messages(self, number):
        try:
            url = self.number_urls.get(number) or f"{self.base_url}/{number}/"
            res = self.session.get(url, timeout=15)
            soup = get_soup(res.text)
            return parse_messages_generic(soup)
        except Exception as e:
            raise Exception(f"فشل جلب الرسائل: {e}")

class ReceiveSmsFreeCcEngine:
    def __init__(self):  # تم التصحيح إلى __init__
        self.base_url = "https://receive-sms-free.cc"
        self.session = RobustSession()
        self.number_urls = {}

    def get_numbers(self, country_code):
        try:
            match = re.search(r'\((.*?)\)', country_code)
            code = match.group(1) if match else country_code.split()[0]
            
            res = self.session.get(f"{self.base_url}/Free-{code}-Phone-Number/", timeout=15)
            soup = get_soup(res.text)
            
            prefix_map = {
                "USA": "+1",
                "UK": "+44",
                "Canada": "+1",
                "Germany": "+49",
                "France": "+33",
                "Morocco": "+212",  # إضافة المغرب
                "India": "+91"      # إضافة الهند
            }
            prefix = prefix_map.get(code)
            
            numbers, urls = extract_numbers_from_anchors(soup, self.base_url, prefix)
            self.number_urls.update(urls)
            return numbers
        except Exception as e:
            raise Exception(f"خطأ في الاتصال بالسيرفر: {e}")
            
    def fetch_messages(self, number):
        try:
            url = self.number_urls.get(number)
            if not url:
                country = "USA"
                if number.startswith("+44"): country = "UK"
                elif number.startswith("+33"): country = "France"
                elif number.startswith("+49"): country = "Germany"
                elif number.startswith("+212"): country = "Morocco"  # فك تشفير المغرب
                elif number.startswith("+91"): country = "India"      # فك تشفير الهند
                elif number.startswith("+1") and len(number) > 11: country = "Canada"
                url = f"{self.base_url}/Free-{country}-Phone-Number/{number.replace('+', '')}.html"
                
            res = self.session.get(url, timeout=15)
            soup = get_soup(res.text)
            return parse_messages_generic(soup)
        except Exception as e:
            raise Exception(f"فشل جلب الرسائل: {e}")

# ==========================================
# 2. الهيكل الموحد لربط الدول بالسيرفرات المخصصة
# ==========================================

COUNTRY_DATA = { 
    "الولايات المتحدة الأمريكية": { 
        "engines": { 
            1: "الولايات المتحدة (+1)", 
            2: "us (أمريكا)", 
            3: "الولايات المتحدة (US)", 
            4: "الولايات المتحدة (US)", 
            5: "أمريكا (USA)" 
        } 
    }, 
    "المملكة المتحدة (بريطانيا)": { 
        "engines": { 
            1: "بريطانيا (+44)", 
            2: "gb (بريطانيا)", 
            3: "بريطانيا (UK)", 
            4: "بريطانيا (UK)", 
            5: "بريطانيا (UK)" 
        } 
    }, 
    "كندا": { 
        "engines": { 
            1: "كندا (+1)", 
            2: "ca (كندا)", 
            4: "كندا (CA)", 
            5: "كندا (Canada)" 
        } 
    }, 
    "فرنسا": { 
        "engines": { 
            1: "فرنسا (+33)", 
            2: "fr (فرنسا)", 
            5: "فرنسا (France)" 
        } 
    }, 
    "ألمانيا": { 
        "engines": { 
            2: "de (ألمانيا)", 
            5: "ألمانيا (Germany)" 
        } 
    }, 
    "إسبانيا": { 
        "engines": { 
            2: "es (إسبانيا)", 
            4: "إسبانيا (ES)" 
        } 
    }, 
    "السويد": { 
        "engines": { 
            2: "se (السويد)", 
            3: "السويد (SE)" 
        } 
    }, 
    "ماليزيا (شرق آسيا)": { 
        "engines": { 
            3: "ماليزيا (MY)" 
        } 
    }, 
    "بورتوريكو": { 
        "engines": { 
            3: "بورتوريكو (PR)" 
        } 
    }, 
    "جورجيا": { 
        "engines": { 
            4: "جورجيا (GE)" 
        } 
    },
    # --- إضافة الدول العربية والشرقية الجديدة بالكامل ---
    "مصر (عربي)": {
        "engines": {
            2: "egypt (مصر)"
        }
    },
    "المغرب (عربي)": {
        "engines": {
            1: "المغرب (+212)",
            2: "morocco (المغرب)",
            5: "Morocco"
        }
    },
    "الأردن (عربي)": {
        "engines": {
            2: "jordan (الأردن)"
        }
    },
    "الهند (شرقي)": {
        "engines": {
            1: "الهند (+91)",
            2: "india (الهند)",
            5: "India"
        }
    },
    "الصين (شرقي)": {
        "engines": {
            2: "china (الصين)"
        }
    },
    "أوزبكستان (شرقي)": {
        "engines": {
            2: "uzbekistan (أوزبكستان)"
        }
    }
}

# ==========================================
# 3. واجهات المستخدم الرسومية (PySide6)
# ==========================================

class InboxWindow(QWidget):
    def __init__(self, engine, number):  # تم التصحيح إلى __init__
        super().__init__()
        self.engine = engine
        self.number = number
        self.setWindowTitle(f"الوارد - {self.number}")
        self.resize(700, 500)
        self.setLayoutDirection(Qt.RightToLeft)

        layout = QVBoxLayout()
        warn_lbl = QLabel("⚠️ تنبيه: هذه الأرقام عامة ومكشوفة للجميع. لا تستخدمها لحساباتك الحساسة.")
        warn_lbl.setStyleSheet("color: #ffb74d; font-weight: bold;")
        
        hbox = QHBoxLayout()
        btn_refresh = QPushButton("🔄 تحديث الرسائل")
        btn_refresh.clicked.connect(self.load_messages)
        btn_copy = QPushButton("📋 نسخ الرقم")
        btn_copy.clicked.connect(lambda: pyperclip.copy(self.number))
        
        hbox.addWidget(btn_refresh)
        hbox.addWidget(btn_copy)
        
        self.list_widget = QListWidget()
        self.list_widget.setWordWrap(True)
        
        layout.addWidget(warn_lbl)
        layout.addLayout(hbox)
        layout.addWidget(self.list_widget)
        self.setLayout(layout)
        
        self.load_messages()

    def load_messages(self):
        self.list_widget.clear()
        self.list_widget.addItem("⏳ جاري سحب الرسائل من السيرفر... يرجى الانتظار")
        QApplication.processEvents()
        
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            messages = self.engine.fetch_messages(self.number)
            QApplication.setOverrideCursor(Qt.ArrowCursor)
            
            self.list_widget.clear()
            if not messages:
                self.list_widget.addItem("📭 لم تصل أي رسالة مؤخراً لهذا الرقم، أو أن السيرفر محمي حالياً.")
            else:
                for msg in messages:
                    display_text = f"👤 من: {msg['sender']}  ⏱️ {msg['time']}\n✉️ الرسالة: {msg['text']}\n" + ("_"*60)
                    self.list_widget.addItem(display_text)
        except Exception as e:
            QApplication.setOverrideCursor(Qt.ArrowCursor)
            self.list_widget.clear()
            QMessageBox.critical(self, "خطأ بالاتصال", str(e))

class MainWindow(QMainWindow):
    def __init__(self):  # تم التصحيح إلى __init__
        super().__init__()
        self.setWindowTitle("مُجمّع أرقام SMS")
        self.resize(600, 500)
        self.setLayoutDirection(Qt.RightToLeft)
        self.apply_dark_theme()

        self.engines_cache = {}
        self.inbox_windows = []

        central = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("برنامج جلب الأرقام والرسائل:")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        
        self.combo_countries = QComboBox()
        self.combo_countries.addItems(sorted(COUNTRY_DATA.keys()))
        self.combo_countries.currentIndexChanged.connect(self.on_country_changed)
        
        self.combo_engines = QComboBox()
        
        btn_get_numbers = QPushButton("🔍 استخراج الأرقام المتاحة")
        btn_get_numbers.clicked.connect(self.load_numbers)
        
        self.list_numbers = QListWidget()
        
        btn_confirm = QPushButton("تأكيد")
        btn_confirm.setStyleSheet("background-color: #2e7d32; color: white;")
        btn_confirm.clicked.connect(self.open_inbox)
        
        layout.addWidget(title)
        layout.addWidget(QLabel("1. اختر الدولة المطلوب تفعيلها:"))
        layout.addWidget(self.combo_countries)
        layout.addWidget(QLabel("2. السيرفر المتاح لتلك الدولة:"))
        layout.addWidget(self.combo_engines)
        layout.addWidget(btn_get_numbers)
        layout.addWidget(QLabel("3. الأرقام المستخرجة (اختر رقمًا ثم اضغط تأكيد):"))
        layout.addWidget(self.list_numbers)
        layout.addWidget(btn_confirm)
        
        central.setLayout(layout)
        self.setCentralWidget(central)
        
        self.on_country_changed()

    def get_engine_by_id(self, idx):
        if idx not in self.engines_cache:
            if idx == 1:
                self.engines_cache[idx] = ReceiveSmssEngine()
            elif idx == 2:
                self.engines_cache[idx] = Sms24Engine()
            elif idx == 3:
                self.engines_cache[idx] = SmsOnlineCoEngine()
            elif idx == 4:
                self.engines_cache[idx] = AnonymSmsEngine()
            else:
                self.engines_cache[idx] = ReceiveSmsFreeCcEngine()
        return self.engines_cache[idx]

    def on_country_changed(self):
        self.list_numbers.clear()
        self.combo_engines.clear()
        
        selected_country = self.combo_countries.currentText()
        if selected_country in COUNTRY_DATA:
            engines_dict = COUNTRY_DATA[selected_country]["engines"]
            for engine_id in sorted(engines_dict.keys()):
                display_name = f"سيرفر {engine_id}"
                self.combo_engines.addItem(display_name, engine_id)

    def load_numbers(self):
        self.list_numbers.clear()
        
        selected_country = self.combo_countries.currentText()
        engine_idx = self.combo_engines.currentData()
        
        if not selected_country or not engine_idx:
            return
            
        self.list_numbers.addItem("⏳ جاري جلب الأرقام... يرجى الانتظار")
        QApplication.processEvents()
        
        try:
            engine = self.get_engine_by_id(engine_idx)
            country_param = COUNTRY_DATA[selected_country]["engines"][engine_idx]
            
            QApplication.setOverrideCursor(Qt.WaitCursor)
            numbers = engine.get_numbers(country_param)
            QApplication.setOverrideCursor(Qt.ArrowCursor)
            
            self.list_numbers.clear()
            if not numbers or len(numbers) == 0 or (len(numbers) == 1 and ("لا توجد" in numbers[0] or "عفوا" in numbers[0])):
                self.list_numbers.addItem("⚠️ لا توجد أرقام متاحة حالياً على هذا السيرفر لهذه الدولة.")
            else:
                self.list_numbers.addItems(numbers)
                
        except Exception as e:
            QApplication.setOverrideCursor(Qt.ArrowCursor)
            self.list_numbers.clear()
            QMessageBox.critical(self, "خطأ بالاتصال", "فشل جلب الأرقام من السيرفر المحدد. يرجى المحاولة لاحقاً.")

    def open_inbox(self):
        selected = self.list_numbers.currentItem()
        if not selected:
            QMessageBox.warning(self, "تنبيه", "الرجاء تحديد رقم من القائمة أولاً!")
            return
            
        number = selected.text().strip()
        if "لا توجد" in number or "⚠️" in number or "⏳" in number:
            return
            
        engine_idx = self.combo_engines.currentData()
        engine = self.get_engine_by_id(engine_idx)
        
        win = InboxWindow(engine, number)
        win.show()
        self.inbox_windows.append(win)

    def apply_dark_theme(self):
        dark_stylesheet = """
        QWidget { background-color: #121212; color: #e0e0e0; font-family: Tahoma, Arial; font-size: 14px; }
        QPushButton { background-color: #1976d2; color: white; border: none; padding: 10px; border-radius: 5px; font-weight: bold; }
        QPushButton:hover { background-color: #1565c0; }
        QPushButton:pressed { background-color: #0d47a1; }
        QComboBox, QListWidget { background-color: #1e1e1e; border: 1px solid #333333; padding: 8px; border-radius: 4px; }
        QListWidget::item:selected { background-color: #d84315; color: white; }
        """
        self.setStyleSheet(dark_stylesheet)

# تم تعديل السطر ليكون بالصيغة القياسية لتشغيل بايثون
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())