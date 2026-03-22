# 📊 Analyzer Pro – Smart Business Analysis Platform

Analyzer Pro is a Flask-based web application that helps businesses manage inventory, track expenses, and generate AI-powered forecasts for better decision-making.

---

## 🚀 Features

* 📦 Inventory Management
* 💰 Expense Tracking
* 📈 Sales & Profit Visualization
* 🤖 AI-Based Forecasting (Prophet Model)
* 📊 Interactive Dashboards (Plotly)
* 🔐 User Authentication (Login/Register)
* 📄 Export Reports (PDF & Excel)

---

## 🛠️ Tech Stack

* **Backend:** Flask (Python)
* **Frontend:** HTML, CSS
* **Database:** MySQL
* **Libraries:**

  * Pandas
  * NumPy
  * Scikit-learn
  * Prophet
  * Plotly
  * Matplotlib
* **Other Tools:**

  * Docker
  * Git & GitHub

---

## 📂 Project Structure

```
AnalyzerPro/
│── static/              # CSS & Images
│── templates/           # HTML files
│── app.py               # Main Flask app
│── db.py                # Database connection
│── requirements.txt     # Dependencies
│── Dockerfile           # Docker setup
```

---

## ⚙️ Setup Instructions

### 🔹 1. Clone Repository

```
git clone https://github.com/ayushie18/Analyzer_Pro.git
cd Analyzer_Pro
```

---

### 🔹 2. Install Dependencies

```
pip install -r requirements.txt
```

---

### 🔹 3. Setup MySQL Database

* Create a database named: `project`
* Update credentials in `db.py`

---

### 🔹 4. Run Application

```
python app.py
```

Open in browser:

```
http://127.0.0.1:5000
```

---

## 🐳 Run with Docker

### Build Image

```
docker build -t flask-app .
```

### Run Container

```
docker run -p 5000:5000 flask-app
```

---

## 📸 Screenshots

(Add screenshots here for better presentation)

---

## 🌟 Future Enhancements

* 📊 Advanced Analytics Dashboard
* 🔔 Alerts & Notifications
* ☁️ Cloud Deployment
* 📱 Mobile Responsive UI

---

## 👩‍💻 Author

**Ayushi Kumari**
GitHub: https://github.com/ayushie18

---

## ⭐ If you like this project

Give it a ⭐ on GitHub!
