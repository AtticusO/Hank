import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel

app = QApplication(sys.argv)

# Create the main window
window = QWidget()
window.setGeometry(100, 100, 300, 200) # x, y, width, height
window.setWindowTitle('PyQt5 Hello World')

# Add a label to the window
label = QLabel('Welcome to PyQt5!', parent=window)
label.move(100, 80) # x, y positioning

window.show()
sys.exit(app.exec_())


