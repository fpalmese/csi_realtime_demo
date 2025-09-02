import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt6.QtGui import QPainter, QPen, QFont
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtCore import QTimer
import random
from PyQt6.QtGui import QConicalGradient, QColor

class QTGauge(QWidget):
    def __init__(self, title="Gauge", unit="KB", min_value=0, max_value=100):
        super().__init__()
        self.title = title
        self.unit = unit
        self.min_value = min_value
        self.max_value = max_value
        self.value = min_value
        self.setMinimumSize(200, 200)
        self.text_value = ""
    
    def set_unit(self,unit):
        self.unit = unit
        
    # value is in KB
    def set_value(self, value):
        #self.value = max(self.min_value, min(self.max_value, value))
        self.text_value = f"{round(value,1)}"
        self.value = round(max(self.min_value, min(self.max_value, value)), 1)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRect(10, 10, self.width()-20, self.height()-20)

        # Draw background circle
        pen_bg = QPen(Qt.GlobalColor.lightGray, 20)
        painter.setPen(pen_bg)
        painter.drawArc(rect, 0, 16*360)

        # Draw value arc with gradient
        angle_span = int(360 * (self.value - self.min_value) / (self.max_value - self.min_value))

        # Create a conical gradient centered in the widget
        center_x = rect.center().x() - 6  # Adjust for pen width
        center_y = rect.center().y()
        gradient = QConicalGradient(center_x, center_y, 90)  # 90 degrees is the start angle

        # Define gradient colors (customize as needed)
        gradient.setColorAt(0.0, QColor(255, 0, 0))   # Red
        gradient.setColorAt(0.5, QColor(255, 255, 0)) # Yellow
        gradient.setColorAt(1.0, QColor(0, 255, 0))   # Green

        pen_value = QPen()
        pen_value.setWidth(20)
        pen_value.setBrush(gradient)
        painter.setPen(pen_value)
        # paint (adjust for pen width)
        painter.drawArc(rect, 87*16, -angle_span*16)

        # Draw title
        #painter.setPen(Qt.GlobalColor.white)
        # set pen color to global text color
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self.title} ({self.unit})\n{self.text_value}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = QWidget()
    #win.setStyleSheet("background-color: white;")  # fallback for window background
    layout = QVBoxLayout(win)

    gauge = QTGauge(title="PCAP Size", min_value=0, max_value=100)
    layout.addWidget(gauge)


    def update_gauge():
        gauge.set_value(random.randint(0, 100))

    timer = QTimer()
    timer.timeout.connect(update_gauge)
    timer.start(1000)

    win.show()
    sys.exit(app.exec())